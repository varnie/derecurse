"""
CPS (Continuation-Passing Style) Rewriter.

Transforms non-tail-recursive functions into CPS form with a thunk
trampoline, eliminating stack growth for functions like naive fib.

The transformation:
   Input:   def fib(n):
                if n <= 1: return n
                return fib(n - 1) + fib(n - 2)

   CPS:     def _fib_cps(n, k):
                if n <= 1: return lambda: k(n)
                return lambda: _fib_cps(n-1, lambda v1: lambda:
                                   lambda _fib_cps(n-2, lambda v2: lambda:
                                   lambda: k(v1+v2)))

   Wrapper: def fib(n):
                __k = lambda v: lambda: v
                __r = _fib_cps(n, __k)
                while callable(__r):
                    __r = __r()
                return __r
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from .analyzer import AnalysisResult

_fresh_counter = 0


def _fresh(prefix="v"):
    global _fresh_counter
    _fresh_counter += 1
    return f"{prefix}{_fresh_counter}"


def _to_k(thing: str | ast.expr) -> ast.expr:
    """Convert a continuation reference to an AST expression.

    `thing` is either a string (parameter name, e.g. "__k__") or an
    AST expression (e.g. a Lambda continuation from a parent expression).
    """
    if isinstance(thing, str):
        return ast.Name(id=thing, ctx=ast.Load())
    return thing


def _arguments(
    *params: str | ast.arg,
    defaults: list[ast.expr] | None = None,
    kwarg: ast.arg | None = None,
) -> ast.arguments:
    """Build ast.arguments with all fields required since Python 3.8."""
    args = [p if isinstance(p, ast.arg) else ast.arg(arg=p) for p in params]
    return ast.arguments(
        posonlyargs=[],
        args=args,
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=kwarg,
        defaults=defaults or [],
    )


def _call(
    func: ast.expr,
    args: list[ast.expr] | None = None,
    keywords: list[ast.keyword] | None = None,
) -> ast.Call:
    """Build ast.Call with keywords field required since Python 3.9."""
    return ast.Call(func=func, args=args or [], keywords=keywords or [])


def cps_rewrite(func, analysis: AnalysisResult):
    global _fresh_counter
    _fresh_counter = 0

    src = inspect.getsource(func)
    src = textwrap.dedent(src)
    tree = ast.parse(src)

    cps_name = f"_{analysis.func_name}_cps"
    orig_name = analysis.func_name
    params = analysis.params

    transformer = _CPSTransformer(orig_name, cps_name, params)
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)

    wrapper_func = _build_wrapper(orig_name, cps_name, params, analysis.defaults)
    wrapper_tree = ast.Module(body=[wrapper_func], type_ignores=[])
    ast.fix_missing_locations(wrapper_tree)

    namespace = func.__globals__.copy()
    code = compile(new_tree, filename=f"<derecurse:{func.__name__}>", mode="exec")
    exec(code, namespace)
    wrapper_code = compile(
        wrapper_tree, filename=f"<derecurse:{func.__name__}>", mode="exec"
    )
    exec(wrapper_code, namespace)
    new_func = namespace[orig_name]

    new_func.__name__ = func.__name__
    new_func.__qualname__ = func.__qualname__
    new_func.__doc__ = func.__doc__
    new_func.__wrapped__ = func
    new_func.__derecurse_strategy__ = "cps_trampoline"

    return new_func


# ─── AST Transformer ────────────────────────────────────────────────────────


class _CPSTransformer(ast.NodeTransformer):
    def __init__(self, func_name: str, cps_name: str, params: list[str]):
        self.func_name = func_name
        self.cps_name = cps_name
        self.params = params

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name != self.func_name:
            return node

        k_arg = ast.arg(arg="__k__")
        node.args.args.append(k_arg)
        node.name = self.cps_name

        new_body = self._transform_body(node.body)
        node.body = new_body
        return node

    def _transform_body(self, stmts: list[ast.stmt]) -> list[ast.stmt]:
        result = []
        for stmt in stmts:
            result.extend(self._transform_stmt(stmt))
        return result

    def _transform_stmt(self, stmt: ast.stmt) -> list[ast.stmt]:
        if isinstance(stmt, ast.Return) and stmt.value is not None:
            cps_val = _cps_expr(stmt.value, self.func_name, "__k__")
            return [ast.Return(value=cps_val)]

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
            return [type(stmt)(items=stmt.items, body=new_body)]

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
                body=new_body, handlers=new_handlers,
                orelse=new_orelse, finalbody=new_finalbody,
            )]

        elif hasattr(ast, "Match") and isinstance(stmt, ast.Match):
            new_cases = [
                ast.match_case(
                    pattern=case.pattern, guard=case.guard,
                    body=self._transform_body(case.body),
                )
                for case in stmt.cases
            ]
            return [ast.Match(subject=stmt.subject, cases=new_cases)]

        return [stmt]


# ─── CPS Expression Transform ────────────────────────────────────────────────


def _has_self_call(node: ast.AST, func_name: str) -> bool:
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == func_name
        ):
            return True
    return False


def _cps_expr(expr: ast.expr, func_name: str, k_name: str | ast.expr) -> ast.expr:
    """
    CPS-transform an expression. Returns a thunk (lambda: ...) that,
    when called, either calls k(value) for pure exprs or performs
    one step of CPS computation and returns the next thunk.
    """

    # ── Pure expression (no self-calls) ──────────────────────────────────
    if not _has_self_call(expr, func_name):
        return ast.Lambda(
            args=_arguments(),
            body=ast.Call(
                func=_to_k(k_name),
                args=[expr],
                keywords=[],
            ),
        )

    # ── Direct self-call: func(args) ─────────────────────────────────────
    if _is_direct_self_call(expr, func_name):
        cps_func = f"_{func_name}_cps"
        return ast.Lambda(
            args=_arguments(),
            body=ast.Call(
                func=ast.Name(id=cps_func, ctx=ast.Load()),
                args=list(expr.args)
                + [_to_k(k_name)],
                keywords=expr.keywords,
            ),
        )

    # ── BoolOp: convert to IfExp then CPS ────────────────────────────────
    if isinstance(expr, ast.BoolOp):
        vals = expr.values
        if isinstance(expr.op, ast.Or):
            # a or b or c  →  a if a else (b if b else c)
            ifexp = vals[-1]
            for v in reversed(vals[:-1]):
                ifexp = ast.IfExp(test=v, body=v, orelse=ifexp)
        else:
            # a and b and c  →  b if a else (c if b else False) -- wrong!
            # and: (a and b and c) → c if (a and b) else False, but in Python
            # 'and' short-circuits: returns first falsy or last value.
            # Desugaring: a and b and c → c if a and b else a -- nope
            # Correct: a and b and c → (b if a else a) and c -- hmm, wrong again
            # Actual: a and b and c → b if a else a, then if result and c
            # → c if result else result
            # Simpler: fold left-to-right: (a and b) -> IfExp(test=a, body=b, orelse=a)
            ifexp = vals[0]
            for v in vals[1:]:
                ifexp = ast.IfExp(test=ifexp, body=v, orelse=ifexp)
        return _cps_expr(ifexp, func_name, k_name)

    # ── IfExp: CPS both branches ─────────────────────────────────────────
    if isinstance(expr, ast.IfExp):
        test_has = _has_self_call(expr.test, func_name)
        if test_has:
            # Evaluate the test via CPS first; branch on a pure Name (never the
            # original function — that would bypass CPS and blow the stack).
            v = _fresh("c")
            orelse_cps = _cps_expr(expr.orelse, func_name, k_name)
            if expr.body is expr.test:
                if_body: ast.expr = ast.Lambda(
                    args=_arguments(),
                    body=_call(_to_k(k_name), [ast.Name(id=v, ctx=ast.Load())]),
                )
            else:
                if_body = _cps_expr(expr.body, func_name, k_name)
            inner_k = ast.Lambda(
                args=_arguments(v),
                body=ast.Lambda(
                    args=_arguments(),
                    body=_call(
                        ast.IfExp(
                            test=ast.Name(id=v, ctx=ast.Load()),
                            body=if_body,
                            orelse=orelse_cps,
                        ),
                    ),
                ),
            )
            return _cps_expr(expr.test, func_name, inner_k)

        body_cps = _cps_expr(expr.body, func_name, k_name)
        orelse_cps = _cps_expr(expr.orelse, func_name, k_name)
        return ast.Lambda(
            args=_arguments(),
            body=_call(
                ast.IfExp(
                    test=_cps_purify(expr.test, func_name),
                    body=body_cps,
                    orelse=orelse_cps,
                ),
            ),
        )

    # ── BinOp ────────────────────────────────────────────────────────────
    if isinstance(expr, ast.BinOp):
        left_has = _has_self_call(expr.left, func_name)
        right_has = _has_self_call(expr.right, func_name)

        if not left_has and not right_has:
            return ast.Lambda(
                args=_arguments(),
                body=ast.Call(
                    func=_to_k(k_name),
                    args=[expr],
                    keywords=[],
                ),
            )

        if left_has and not right_has:
            v = _fresh("b")
            inner_k = _make_binop_k(
                v, expr.right, expr.op, k_name, right_on_left=True
            )
            if _is_direct_self_call(expr.left, func_name):
                return ast.Lambda(
                    args=_arguments(),
                    body=ast.Call(
                        func=ast.Name(id=f"_{func_name}_cps", ctx=ast.Load()),
                        args=list(expr.left.args) + [inner_k],
                        keywords=expr.left.keywords,
                    ),
                )
            return _cps_expr(expr.left, func_name, inner_k)

        if not left_has and right_has:
            v = _fresh("b")
            inner_k = _make_binop_k(
                v, expr.left, expr.op, k_name, right_on_left=False
            )
            if _is_direct_self_call(expr.right, func_name):
                return ast.Lambda(
                    args=_arguments(),
                    body=ast.Call(
                        func=ast.Name(id=f"_{func_name}_cps", ctx=ast.Load()),
                        args=list(expr.right.args) + [inner_k],
                        keywords=expr.right.keywords,
                    ),
                )
            return _cps_expr(expr.right, func_name, inner_k)

        # Both sides have self-calls
        v1 = _fresh("b")
        v2 = _fresh("b")
        inner2_k = ast.Lambda(
            args=_arguments(v2),
            body=ast.Lambda(
                args=_arguments(),
                body=ast.Call(
                    func=_to_k(k_name),
                    args=[
                        ast.BinOp(
                            left=ast.Name(id=v1, ctx=ast.Load()),
                            op=expr.op,
                            right=ast.Name(id=v2, ctx=ast.Load()),
                        )
                    ],
                    keywords=[],
                ),
            ),
        )
        if _is_direct_self_call(expr.right, func_name):
            inner1_k_body: ast.expr = ast.Call(
                func=ast.Name(id=f"_{func_name}_cps", ctx=ast.Load()),
                args=list(expr.right.args) + [inner2_k],
                keywords=expr.right.keywords,
            )
        else:
            inner1_k_body = _cps_expr(expr.right, func_name, inner2_k)
        inner1_k = ast.Lambda(
            args=_arguments(v1),
            body=ast.Lambda(
                args=_arguments(), body=inner1_k_body,
            ),
        )
        if _is_direct_self_call(expr.left, func_name):
            return ast.Lambda(
                args=_arguments(),
                body=ast.Call(
                    func=ast.Name(id=f"_{func_name}_cps", ctx=ast.Load()),
                    args=list(expr.left.args) + [inner1_k],
                    keywords=expr.left.keywords,
                ),
            )
        return _cps_expr(expr.left, func_name, inner1_k)

    # ── Call (non-self) ──────────────────────────────────────────────────
    if isinstance(expr, ast.Call):
        # Check if any arg/keyword value contains a self-call.
        all_parts: list[ast.expr] = list(expr.args) + [kw.value for kw in expr.keywords]
        if any(_has_self_call(p, func_name) for p in all_parts):
            n_args = len(expr.args)

            def rebuild(parts: list[ast.expr]) -> ast.Call:
                return ast.Call(
                    func=expr.func,
                    args=parts[:n_args],
                    keywords=[
                        ast.keyword(arg=kw.arg, value=parts[n_args + i])
                        for i, kw in enumerate(expr.keywords)
                    ],
                )

            result = _cps_seq(all_parts, func_name, k_name, rebuild)
            if result is not None:
                return result
        return ast.Lambda(
            args=_arguments(),
            body=ast.Call(
                func=_to_k(k_name),
                args=[expr],
                keywords=[],
            ),
        )

    # ── UnaryOp ───────────────────────────────────────────────────────────
    if isinstance(expr, ast.UnaryOp):
        op_has = _has_self_call(expr.operand, func_name)
        if op_has:
            v = _fresh("u")
            inner_k = ast.Lambda(
                args=_arguments(v),
                body=ast.Lambda(
                    args=_arguments(),
                    body=ast.Call(
                        func=_to_k(k_name),
                        args=[
                            ast.UnaryOp(op=expr.op, operand=ast.Name(id=v, ctx=ast.Load()))
                        ],
                        keywords=[],
                    ),
                ),
            )
            return _cps_expr(expr.operand, func_name, inner_k)

    # ── Attribute ─────────────────────────────────────────────────────────
    if isinstance(expr, ast.Attribute):
        if _has_self_call(expr.value, func_name):
            v = _fresh("a")
            inner_k = ast.Lambda(
                args=_arguments(v),
                body=ast.Lambda(
                    args=_arguments(),
                    body=ast.Call(
                        func=_to_k(k_name),
                        args=[
                            ast.Attribute(
                                value=ast.Name(id=v, ctx=ast.Load()),
                                attr=expr.attr, ctx=ast.Load(),
                            )
                        ],
                        keywords=[],
                    ),
                ),
            )
            return _cps_expr(expr.value, func_name, inner_k)

    # ── Subscript ────────────────────────────────────────────────────────────
    if isinstance(expr, ast.Subscript):
        val_has = _has_self_call(expr.value, func_name)
        slc_has = _has_self_call(expr.slice, func_name)
        if val_has and not slc_has:
            v = _fresh("s")
            inner_k = ast.Lambda(
                args=_arguments(v),
                body=ast.Lambda(
                    args=_arguments(),
                    body=ast.Call(
                        func=_to_k(k_name),
                        args=[
                            ast.Subscript(
                                value=ast.Name(id=v, ctx=ast.Load()),
                                slice=expr.slice,
                                ctx=ast.Load(),
                            )
                        ],
                        keywords=[],
                    ),
                ),
            )
            return _cps_expr(expr.value, func_name, inner_k)
        if not val_has and slc_has:
            v = _fresh("s")
            inner_k = ast.Lambda(
                args=_arguments(v),
                body=ast.Lambda(
                    args=_arguments(),
                    body=ast.Call(
                        func=_to_k(k_name),
                        args=[
                            ast.Subscript(
                                value=expr.value,
                                slice=ast.Name(id=v, ctx=ast.Load()),
                                ctx=ast.Load(),
                            )
                        ],
                        keywords=[],
                    ),
                ),
            )
            return _cps_expr(expr.slice, func_name, inner_k)
        if val_has and slc_has:
            return _cps_seq([expr.value, expr.slice], func_name, k_name,
                            lambda parts: ast.Subscript(
                                value=parts[0], slice=parts[1], ctx=ast.Load(),
                            ))

    # ── Compare ──────────────────────────────────────────────────────────────
    if isinstance(expr, ast.Compare):
        # left op comparator1 op comparator2 ...
        all_parts = [expr.left] + list(expr.comparators)
        result = _cps_seq(all_parts, func_name, k_name,
                          lambda parts: ast.Compare(
                              left=parts[0],
                              ops=expr.ops,
                              comparators=parts[1:],
                          ))
        if result is not None:
            return result

    # ── List / Tuple / Set ──────────────────────────────────────────────────
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        elts = expr.elts
        if isinstance(expr, ast.Set):
            def rebuild(parts):
                return ast.Set(elts=parts)
        else:
            def rebuild(parts):
                return type(expr)(elts=parts, ctx=ast.Load())
        result = _cps_seq(list(elts), func_name, k_name, rebuild)
        if result is not None:
            return result

    # ── Dict ─────────────────────────────────────────────────────────────────
    if isinstance(expr, ast.Dict):
        result = _cps_dict(expr, func_name, k_name)
        if result is not None:
            return result

    # ── Fallback: thunk(k(expr)) — won't help deep recursion ─────────────
    return ast.Lambda(
        args=_arguments(),
        body=_call(_to_k(k_name), [expr]),
    )


def _cps_dict(node: ast.Dict, func_name: str, k_name: str | ast.expr) -> ast.expr | None:
    """CPS-transform a Dict literal, handling None keys for ** unpacking."""
    parts: list[ast.expr] = []
    slot_map: list[tuple[int, bool]] = []  # (key_or_value_index, is_key)
    for i, (k, v) in enumerate(zip(node.keys or [], node.values)):
        if k is not None:
            parts.append(k)
            slot_map.append((i, True))
        parts.append(v)
        slot_map.append((i, False))
    if not any(_has_self_call(p, func_name) for p in parts):
        return None

    n_items = len(node.keys or [])
    def rebuild(ps: list[ast.expr]) -> ast.expr:
        keys: list[ast.expr | None] = [None] * n_items
        values: list[ast.expr] = [None] * n_items  # type: ignore[list-item]
        pi = 0
        for i, (k, v) in enumerate(zip(node.keys or [], node.values)):
            if k is not None:
                keys[i] = ps[pi]
                pi += 1
            else:
                keys[i] = None
            values[i] = ps[pi]
            pi += 1
        return ast.Dict(keys=keys, values=values)
    return _cps_seq(parts, func_name, k_name, rebuild)


def _cps_seq(
    exprs: list[ast.expr],
    func_name: str,
    k_name: str | ast.expr,
    rebuild: object,
) -> ast.expr | None:
    """
    Evaluate a list of sub-expressions left-to-right, CPS-converting
    any that contain self-calls. Returns a thunk (lambda: ...) or None
    if no CPS is needed.

    rebuild receives a list of ast.expr — the original expressions with
    CPS-containing ones replaced by temp var Names.
    """
    cps_indices = [i for i, e in enumerate(exprs) if _has_self_call(e, func_name)]
    if not cps_indices:
        return None

    temps = [_fresh("t") for _ in cps_indices]
    cps_name = f"_{func_name}_cps"

    def full_list():
        result = list(exprs)
        for idx, pos in enumerate(cps_indices):
            result[pos] = ast.Name(id=temps[idx], ctx=ast.Load())
        return result

    if isinstance(k_name, str):
        curr_k: ast.expr = _to_k(k_name)
        final_k: ast.expr = _to_k(k_name)
    else:
        curr_k = k_name
        final_k = k_name

    for idx in range(len(cps_indices) - 1, -1, -1):
        t_var = temps[idx]

        if idx == len(cps_indices) - 1:
            body: ast.expr = _call(final_k, [rebuild(full_list())])
        else:
            next_pos = cps_indices[idx + 1]
            next_expr = exprs[next_pos]
            if _is_direct_self_call(next_expr, func_name):
                body = ast.Call(
                    func=ast.Name(id=cps_name, ctx=ast.Load()),
                    args=list(next_expr.args) + [curr_k],
                    keywords=next_expr.keywords,
                )
            else:
                body = _cps_expr(next_expr, func_name, curr_k)

        curr_k = ast.Lambda(
            args=_arguments(t_var),
            body=ast.Lambda(args=_arguments(), body=body),
        )

    first = exprs[cps_indices[0]]
    return _cps_expr(first, func_name, curr_k)


def _is_direct_self_call(expr: ast.expr, func_name: str) -> bool:
    """True if expr is a direct self-call like f(args), not a compound."""
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == func_name
    )


def _cps_purify(expr: ast.expr, func_name: str) -> ast.expr:
    """
    Strip self-calls from a condition expression by wrapping in a temp var.
    If the test contains a self-call, capture it before the if.
    For v1, if the test contains self-calls, we fall back to a simple
    call — this may cause RecursionError for deeply nested conditions
    but preserves correctness for shallow ones.
    """
    if _has_self_call(expr, func_name):
        # Return the test as-is; the self-call will be executed in the
        # test context. This is fine for simple cases like:
        #   return f(n) if f(n-1) > 0 else 0
        # The test's self-call will be evaluated eagerly, which may
        # cause RecursionError. For v1 this is acceptable.
        pass
    return expr


def _make_binop_k(
    v_name: str,
    other_side: ast.expr,
    op: ast.operator,
    k_name: str,
    right_on_left: bool,
) -> ast.Lambda:
    """Build a continuation lambda that applies a BinOp with the captured value."""
    if right_on_left:
        # v_name op other_side
        body_expr: ast.expr = ast.BinOp(
            left=ast.Name(id=v_name, ctx=ast.Load()),
            op=op,
            right=other_side,
        )
    else:
        # other_side op v_name
        body_expr = ast.BinOp(
            left=other_side,
            op=op,
            right=ast.Name(id=v_name, ctx=ast.Load()),
        )
    return ast.Lambda(
        args=_arguments(v_name),
        body=ast.Lambda(
            args=_arguments(),
            body=_call(_to_k(k_name), [body_expr]),
        ),
    )


# ─── Wrapper Builder ─────────────────────────────────────────────────────────


def _build_wrapper(
    orig_name: str, cps_name: str, params: list[str],
    defaults_dict: dict[str, object] | None = None,
) -> ast.FunctionDef:
    """
    Build the trampoline wrapper AST:

      def orig_name(p1, p2=p2_default, ...):
          __k__ = lambda v: v
          __r__ = cps_name(p1, p2, ..., __k__)
          while callable(__r__):
              __r__ = __r__()
          return __r__
    """
    # Build defaults list right-aligned with trailing params
    defaults_list: list[ast.expr] = []
    if defaults_dict:
        for p in reversed(params):
            if p in defaults_dict:
                val = defaults_dict[p]
                defaults_list.insert(
                    0, val if isinstance(val, ast.expr) else ast.Constant(value=val),
                )
            else:
                break

    body: list[ast.stmt] = [
        # __k__ = lambda v: v  — identity continuation (no extra thunk)
        ast.Assign(
            targets=[ast.Name(id="__k__", ctx=ast.Store())],
            value=ast.Lambda(
                args=_arguments("__v__"),
                body=ast.Name(id="__v__", ctx=ast.Load()),
            ),
        ),
        # __r__ = cps_name(p1, p2, ..., __k__)
        ast.Assign(
            targets=[ast.Name(id="__r__", ctx=ast.Store())],
            value=_call(
                ast.Name(id=cps_name, ctx=ast.Load()),
                [ast.Name(id=p, ctx=ast.Load()) for p in params]
                + [ast.Name(id="__k__", ctx=ast.Load())],
            ),
        ),
        # while callable(__r__): __r__ = __r__()
        ast.While(
            test=_call(
                ast.Name(id="callable", ctx=ast.Load()),
                [ast.Name(id="__r__", ctx=ast.Load())],
            ),
            body=[
                ast.Assign(
                    targets=[ast.Name(id="__r__", ctx=ast.Store())],
                    value=_call(ast.Name(id="__r__", ctx=ast.Load())),
                ),
            ],
            orelse=[],
        ),
        # return __r__
        ast.Return(value=ast.Name(id="__r__", ctx=ast.Load())),
    ]

    return ast.FunctionDef(
        name=orig_name,
        args=_arguments(*params, defaults=defaults_list or None),
        body=body,
        decorator_list=[],
    )
