"""
Tail Call Rewriter.

Takes a tail-recursive function and rewrites it as an iterative loop.

Input:
    def factorial(n, acc=1):
        if n == 0: return acc
        return factorial(n - 1, n * acc)

Output (conceptually):
    def factorial(n, acc=1):
        while True:
            if n == 0: return acc
            (n, acc) = (n - 1, n * acc)

The rewrite happens at the AST level, then the new function is compiled
and returned. The original source is never modified.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from .analyzer import AnalysisResult


def rewrite_tail_call(func, analysis: AnalysisResult):
    """
    Rewrite a tail-recursive function as an iterative loop.
    Returns a new function object with identical signature.
    """
    src = inspect.getsource(func)
    src = textwrap.dedent(src)
    tree = ast.parse(src)

    # Find and transform the function definition
    transformer = TailCallTransformer(analysis.func_name, analysis.params)
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)

    # Compile the new AST
    code = compile(new_tree, filename=f"<derecurse:{func.__name__}>", mode="exec")

    # Execute in a copy of the function's globals so we get the new function
    namespace = func.__globals__.copy()
    # Inject control-flow signal for loop restart
    namespace["__derecurse_restart__"] = type("_DerecurseRestart", (Exception,), {})
    exec(code, namespace)
    new_func = namespace[func.__name__]

    # Preserve metadata
    new_func.__name__ = func.__name__
    new_func.__qualname__ = func.__qualname__
    new_func.__doc__ = func.__doc__
    new_func.__wrapped__ = func
    new_func.__derecurse_strategy__ = "tail_call_to_loop"

    return new_func


class TailCallTransformer(ast.NodeTransformer):
    """
    AST transformer that rewrites tail calls into loop updates.

    Strategy:
    1. Wrap the entire function body in `while True:`
    2. Replace each `return func_name(args...)` with
       a simultaneous reassignment of all params, then `continue`
    3. Leave all other `return expr` statements untouched
    """

    def __init__(self, func_name: str, params: list[str]):
        self.func_name = func_name
        self.params = params

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name != self.func_name:
            return node

        # Transform the body — replace tail calls in return statements
        new_body = self._transform_body(node.body)

        # Wrap in try/except to catch restart signal.
        # This avoids `continue` scoping bugs when user code has its own loops.
        handler = ast.ExceptHandler(
            type=ast.Name(id="__derecurse_restart__", ctx=ast.Load()),
            name=None,
            body=[ast.Continue()],
        )
        try_body = ast.Try(
            body=new_body,
            handlers=[handler],
            orelse=[],
            finalbody=[],
        )

        # Wrap the whole body in `while True:`
        while_loop = ast.While(
            test=ast.Constant(value=True),
            body=[try_body, ast.Break()],
            orelse=[],
        )

        node.body = [while_loop]
        return node

    def _transform_body(self, stmts: list[ast.stmt]) -> list[ast.stmt]:
        result = []
        for stmt in stmts:
            result.extend(self._transform_stmt(stmt))
        return result

    def _transform_stmt(self, stmt: ast.stmt) -> list[ast.stmt]:
        if isinstance(stmt, ast.Return) and stmt.value is not None:
            transformed = self._try_transform_tail_return(stmt)
            if transformed is not None:
                return transformed
            return [stmt]

        elif isinstance(stmt, ast.If):
            new_body = self._transform_body(stmt.body)
            new_orelse = self._transform_body(stmt.orelse)
            return [ast.If(test=stmt.test, body=new_body, orelse=new_orelse)]

        elif isinstance(stmt, (ast.For, ast.While, ast.AsyncFor)):
            new_body = self._transform_body(stmt.body)
            kw = dict(body=new_body, orelse=stmt.orelse)
            if isinstance(stmt, ast.While):
                kw["test"] = stmt.test
            else:
                kw["target"] = stmt.target
                kw["iter"] = stmt.iter
            return [type(stmt)(**kw)]

        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            new_body = self._transform_body(stmt.body)
            cls = type(stmt)
            return [cls(
                items=stmt.items,
                body=new_body,
            )]

        elif isinstance(stmt, ast.Try):
            new_body = self._transform_body(stmt.body)
            new_handlers = [
                ast.ExceptHandler(
                    type=h.type, name=h.name,
                    body=self._transform_body(h.body),
                )
                for h in stmt.handlers
            ]
            new_orelse = self._transform_body(stmt.orelse)
            new_finalbody = self._transform_body(stmt.finalbody)
            return [ast.Try(
                body=new_body,
                handlers=new_handlers,
                orelse=new_orelse,
                finalbody=new_finalbody,
            )]

        elif hasattr(ast, 'Match') and isinstance(stmt, ast.Match):
            new_cases = [
                ast.match_case(
                    pattern=case.pattern, guard=case.guard,
                    body=self._transform_body(case.body),
                )
                for case in stmt.cases
            ]
            return [ast.Match(subject=stmt.subject, cases=new_cases)]

        return [stmt]

    def _try_transform_tail_return(self, stmt: ast.Return) -> list[ast.stmt] | None:
        """
        If `return func_name(a, b, c)` → replace with simultaneous
        param update + continue.

        Returns None if this is not a tail call to our function.
        """
        expr = stmt.value
        if not (
            isinstance(expr, ast.Call)
            and isinstance(expr.func, ast.Name)
            and expr.func.id == self.func_name
        ):
            return None

        call: ast.Call = expr

        # Build the new argument values
        new_values: dict[str, ast.expr] = {}

        for i, arg_val in enumerate(call.args):
            if i < len(self.params):
                new_values[self.params[i]] = arg_val

        for kw in call.keywords:
            if kw.arg is not None:
                new_values[kw.arg] = kw.value

        params_to_update = [p for p in self.params if p in new_values]

        if not params_to_update:
            return None

        raise_stmt = ast.Raise(
            exc=ast.Name(id="__derecurse_restart__", ctx=ast.Load()),
            cause=None,
        )

        if len(params_to_update) == 1:
            p = params_to_update[0]
            assign = ast.Assign(
                targets=[ast.Name(id=p, ctx=ast.Store())],
                value=new_values[p],
            )
            return [assign, raise_stmt]

        targets = ast.Tuple(
            elts=[ast.Name(id=p, ctx=ast.Store()) for p in params_to_update],
            ctx=ast.Store(),
        )
        values = ast.Tuple(
            elts=[new_values[p] for p in params_to_update],
            ctx=ast.Load(),
        )
        assign = ast.Assign(targets=[targets], value=values)
        return [assign, raise_stmt]
