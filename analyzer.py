"""
AST Analyzer for derecurse.

Inspects a function's AST to classify its recursion pattern:
  - TAIL_CALL     : recursive call is the last operation (can become a loop)
  - NON_TAIL      : recursive call is embedded in a larger expression
  - NO_RECURSION  : function does not call itself
  - MUTUAL        : calls another function that calls back (future)
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from enum import Enum, auto
from dataclasses import dataclass, field


class RecursionPattern(Enum):
    NO_RECURSION = auto()
    TAIL_CALL    = auto()   # return f(...)  with nothing after
    NON_TAIL     = auto()   # return f(...) + something
    MUTUAL       = auto()   # future


@dataclass
class AnalysisResult:
    pattern: RecursionPattern
    func_name: str
    params: list[str]               # positional param names in order
    defaults: dict[str, object]     # param_name → default value
    recursive_calls: int = 0
    tail_call_count: int = 0
    non_tail_count: int = 0
    notes: list[str] = field(default_factory=list)

    def is_optimizable(self) -> bool:
        return self.pattern == RecursionPattern.TAIL_CALL


def analyze(func) -> AnalysisResult:
    """
    Parse and analyze a function's AST to detect recursion pattern.
    Returns an AnalysisResult with full classification.
    """
    src = _get_source(func)
    tree = ast.parse(src)

    # Get the function def node
    func_def = _find_func_def(tree, func.__name__)
    if func_def is None:
        return AnalysisResult(
            pattern=RecursionPattern.NO_RECURSION,
            func_name=func.__name__,
            params=[],
            defaults={},
            notes=["Could not parse function AST"],
        )

    params, defaults = _extract_params(func_def, func)
    analyzer = _RecursionVisitor(func.__name__)
    analyzer.visit(func_def)

    if analyzer.recursive_calls == 0:
        pattern = RecursionPattern.NO_RECURSION
    elif analyzer.non_tail_count > 0:
        pattern = RecursionPattern.NON_TAIL
    elif analyzer.tail_call_count > 0:
        pattern = RecursionPattern.TAIL_CALL
    else:
        pattern = RecursionPattern.NO_RECURSION

    notes = []
    if pattern == RecursionPattern.NON_TAIL:
        notes.append(
            f"Found {analyzer.non_tail_count} non-tail recursive call(s) — "
            "cannot safely convert to loop without memoization"
        )
    if pattern == RecursionPattern.TAIL_CALL:
        notes.append(
            f"Found {analyzer.tail_call_count} tail call(s) — "
            "will rewrite as iterative loop"
        )

    return AnalysisResult(
        pattern=pattern,
        func_name=func.__name__,
        params=params,
        defaults=defaults,
        recursive_calls=analyzer.recursive_calls,
        tail_call_count=analyzer.tail_call_count,
        non_tail_count=analyzer.non_tail_count,
        notes=notes,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_source(func) -> str:
    src = inspect.getsource(func)
    return textwrap.dedent(src)


def _find_func_def(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _extract_params(func_def: ast.FunctionDef, func) -> tuple[list[str], dict]:
    """
    Extract ordered param names and their default values from the live function
    (using inspect, which is more reliable than re-evaluating AST defaults).
    """
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    defaults = {
        name: param.default
        for name, param in sig.parameters.items()
        if param.default is not inspect.Parameter.empty
    }
    return params, defaults


# ─── AST Visitor ──────────────────────────────────────────────────────────────

class _RecursionVisitor(ast.NodeVisitor):
    """
    Walks the function body and classifies each recursive call as
    tail-call or non-tail.

    Tail-call = the recursive call is the direct value of a `return`
    statement, with no surrounding expression.

    Non-tail = the recursive call appears inside a larger expression,
    e.g.  return f(n-1) + f(n-2)  or  x = f(n-1) + 1; return x
    """

    def __init__(self, func_name: str):
        self.func_name = func_name
        self.recursive_calls = 0
        self.tail_call_count = 0
        self.non_tail_count = 0
        self._in_tail_position = False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Only analyze the top-level function body, not nested funcs
        if node.name == self.func_name:
            self._visit_body(node.body)

    def _visit_body(self, stmts: list[ast.stmt]):
        for stmt in stmts:
            self._visit_stmt(stmt)

    def _visit_stmt(self, stmt: ast.stmt):
        if isinstance(stmt, ast.Return):
            if stmt.value is not None:
                self._check_expr_for_tail(stmt.value)
        elif isinstance(stmt, ast.If):
            self._visit_body(stmt.body)
            self._visit_body(stmt.orelse)
        elif isinstance(stmt, (ast.For, ast.While, ast.AsyncFor)):
            self._visit_body(stmt.body)
            self._visit_body(stmt.orelse)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            self._visit_body(stmt.body)
        elif isinstance(stmt, ast.Try):
            self._visit_body(stmt.body)
            for handler in stmt.handlers:
                self._visit_body(handler.body)
            self._visit_body(stmt.orelse)
            self._visit_body(stmt.finalbody if hasattr(stmt, 'finalbody') else [])
        elif hasattr(ast, 'Match') and isinstance(stmt, ast.Match):
            for case in stmt.cases:
                self._visit_body(case.body)
        else:
            # For assignments, expressions, etc — any recursive call here is non-tail
            self._scan_non_tail(stmt)

    def _check_expr_for_tail(self, expr: ast.expr):
        """
        Check if `expr` (the value of a return statement) is a tail call.
        A direct call to self.func_name → tail call.
        Anything else that *contains* a call → non-tail.
        """
        if self._is_direct_self_call(expr):
            self.recursive_calls += 1
            self.tail_call_count += 1
        else:
            # Scan for any embedded recursive calls → non-tail
            self._scan_for_embedded_calls(expr)

    def _is_direct_self_call(self, node: ast.expr) -> bool:
        """True if node is exactly `func_name(...)` — no surrounding ops."""
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == self.func_name
        )

    def _scan_for_embedded_calls(self, node: ast.AST):
        """Recursively scan for self-calls that are NOT in tail position."""
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == self.func_name
            ):
                self.recursive_calls += 1
                self.non_tail_count += 1

    def _scan_non_tail(self, node: ast.AST):
        """Scan any statement that is not a return — all calls here are non-tail."""
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == self.func_name
            ):
                self.recursive_calls += 1
                self.non_tail_count += 1
