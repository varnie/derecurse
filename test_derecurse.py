"""
Tests for derecurse.
Run with: python -m pytest test_derecurse.py -v
"""

import sys
import warnings
from pathlib import Path
import pytest

try:
    from derecurse import derecurse, RecursionPattern, __version__
    from derecurse.analyzer import analyze
    from derecurse.cps import cps_rewrite
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from derecurse import derecurse, RecursionPattern, __version__
    from derecurse.analyzer import analyze
    from derecurse.cps import cps_rewrite

# Depth used to verify CPS/trampoline beyond the default recursion limit.
DEEP = 5000


def _wrap_non_tail(func, *args):
    """Apply @derecurse and run once at depth that triggers CPS; fail on rewrite warnings."""
    wrapped = derecurse(func)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", category=UserWarning)
        result = wrapped(*args)
    failures = [
        w for w in caught
        if "CPS rewrite failed" in str(w.message)
    ]
    assert not failures, "; ".join(str(w.message) for w in failures)
    return wrapped, result


def _wrap_tail(func):
    """Apply @derecurse to a tail-recursive function; fail on AST/trampoline rewrite warnings."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", category=UserWarning)
        wrapped = derecurse(func)
    failures = [
        w for w in caught
        if "rewrite failed" in str(w.message) or "Could not optimize" in str(w.message)
    ]
    assert not failures, "; ".join(str(w.message) for w in failures)
    return wrapped


# ─── Raw functions (undecorated — @derecurse applied inside tests) ──────────

def _factorial(n, acc=1):
    if n == 0: return acc
    return _factorial(n - 1, n * acc)

def _countdown(n):
    if n <= 0: return 0
    return _countdown(n - 1)

def _gcd(a, b):
    if b == 0: return a
    return _gcd(b, a % b)

def _power(base, exp, acc=1):
    if exp == 0: return acc
    return _power(base, exp - 1, acc * base)

def _mysum(n, acc=0):
    if n == 0: return acc
    return _mysum(n - 1, acc + n)

def _fib_tail(n, a=0, b=1):
    if n == 0: return a
    return _fib_tail(n - 1, b, a + b)

def _deep(n, acc=0):
    if n == 0: return acc
    return _deep(n - 1, acc + 1)

def _collatz_steps(n, steps=0):
    if n == 1: return steps
    if n % 2 == 0:
        return _collatz_steps(n // 2, steps + 1)
    return _collatz_steps(3 * n + 1, steps + 1)

def _countdown_kw(n, result=0):
    if n == 0: return result
    return _countdown_kw(n=n - 1, result=result)

def add(a, b):
    return a + b

def fib_nontail(n):
    if n <= 1: return n
    return fib_nontail(n - 1) + fib_nontail(n - 2)

def _sum_nontail(n):
    if n <= 0: return 0
    return n + _sum_nontail(n - 1)

def _sum_left(n):
    if n <= 0: return 0
    return _sum_left(n - 1) + 1

def _sum_right(n):
    if n <= 0: return 0
    return 1 + _sum_right(n - 1)

def _sum_ifexp(n):
    if n <= 0: return 0
    return _sum_ifexp(n - 1) + 0 if n % 2 == 0 else _sum_ifexp(n - 1) + 1

_arr = list(range(2000))

def _sub_slice_test(n):
    if n <= 0: return 0
    return _arr[_sub_slice_test(n - 1)] + 1

def _sub_val_test(n):
    if n <= 0: return [0]
    return [_sub_val_test(n - 1)[0] + 1]

def _list_elts(n):
    if n <= 0: return []
    return [_list_elts(n - 1), 0]

def _tuple_elts(n):
    if n <= 0: return ()
    return (_tuple_elts(n - 1), 0)

def _set_elts(n):
    if n <= 0: return frozenset()
    return frozenset({_set_elts(n - 1), 0})

def _dict_nontail(n):
    if n <= 0: return {0: 0}
    return {0: _dict_nontail(n - 1)}

def _compare_nontail(n):
    if n <= 0: return 0
    return (_compare_nontail(n - 1) > 0) + 0

def _boolop3_or(n):
    if n <= 0: return 0
    return (_boolop3_or(n - 1) or True or False) + 0

def _boolop3_and(n):
    if n <= 0: return 1
    return _boolop3_and(n - 1) and n

def _assign_nontail(n, acc=0):
    if n <= 0: return acc
    acc = _assign_nontail(n - 1, acc + 1)
    return acc

def _unary_nontail(n):
    if n <= 0: return 0
    return -_unary_nontail(n - 1)

def _attr_nontail(n):
    if n <= 0: return 0
    return _attr_nontail(n - 1).real + 1

def _seq3_max(n):
    if n <= 0: return 0
    return max(_seq3_max(n - 1) + 1, _seq3_max(n - 2) + 2, _seq3_max(n - 3) + 3, 0)

def _dict_kwargs(n):
    if n <= 0: return {}
    return {**_dict_kwargs(n - 1), n: n}

def _multi_branch_nontail(n):
    if n <= 0: return 0
    if n % 2 == 0:
        return _multi_branch_nontail(n - 1) + 1
    return _multi_branch_nontail(n - 2) + 2

def _while_nontail(n):
    if n <= 0: return 0
    total = 0
    i = 0
    while i < n % 5:
        total += 1
        i += 1
    return _while_nontail(n - 1) + total

def _for_nontail(n):
    if n <= 0: return 0
    total = 0
    for _ in range(n % 3):
        total += 1
    return _for_nontail(n - 1) + total

def _try_nontail(n):
    if n <= 0: return 0
    try:
        return _try_nontail(n - 1) + 1
    except ValueError:
        return 0


# ─── Analyzer tests ───────────────────────────────────────────────────────────

class TestAnalyzer:

    def test_no_recursion(self):
        def f(a, b): return a + b
        assert analyze(f).pattern == RecursionPattern.NO_RECURSION

    def test_tail_call_simple(self):
        def f(n, acc=1):
            if n == 0: return acc
            return f(n - 1, n * acc)
        result = analyze(f)
        assert result.pattern == RecursionPattern.TAIL_CALL
        assert result.tail_call_count == 1
        assert result.non_tail_count == 0

    def test_non_tail_fib(self):
        def fib(n):
            if n <= 1: return n
            return fib(n - 1) + fib(n - 2)
        result = analyze(fib)
        assert result.pattern == RecursionPattern.NON_TAIL
        assert result.non_tail_count == 2

    def test_tail_call_countdown(self):
        def f(n):
            if n <= 0: return 0
            return f(n - 1)
        assert analyze(f).pattern == RecursionPattern.TAIL_CALL

    def test_tail_call_two_params(self):
        def f(base, exp, acc=1):
            if exp == 0: return acc
            return f(base, exp - 1, acc * base)
        assert analyze(f).pattern == RecursionPattern.TAIL_CALL

    def test_params_extracted(self):
        def f(n, acc=1):
            if n == 0: return acc
            return f(n - 1, n * acc)
        result = analyze(f)
        assert result.params == ["n", "acc"]
        assert result.defaults == {"acc": 1}

    def test_non_tail_sum(self):
        def f(lst):
            if not lst: return 0
            return lst[0] + f(lst[1:])
        assert analyze(f).pattern == RecursionPattern.NON_TAIL

    def test_tail_with_multiple_branches(self):
        def f(a, b):
            if b == 0: return a
            return f(b, a % b)
        assert analyze(f).pattern == RecursionPattern.TAIL_CALL

    def test_assignment_non_tail(self):
        assert analyze(_assign_nontail).pattern == RecursionPattern.NON_TAIL

    def test_is_optimizable(self):
        tail = analyze(_factorial)
        nontail = analyze(fib_nontail)
        plain = analyze(add)
        assert tail.is_optimizable()
        assert not nontail.is_optimizable()
        assert not plain.is_optimizable()

    def test_notes_on_non_tail(self):
        result = analyze(fib_nontail)
        assert result.notes
        assert "non-tail" in result.notes[0].lower()

    def test_recursive_call_counts(self):
        result = analyze(fib_nontail)
        assert result.recursive_calls == 2
        assert result.non_tail_count == 2
        assert result.tail_call_count == 0


# ─── CPS / AST regression ───────────────────────────────────────────────────

class TestCPS:

    def test_cps_rewrite_compiles(self):
        """Generated CPS AST must compile on all supported Python versions."""
        analysis = analyze(_sum_left)
        rewritten = cps_rewrite(_sum_left, analysis)
        assert rewritten.__derecurse_strategy__ == "cps_trampoline"

    def test_cps_no_warning_on_deep_binop_left(self):
        _, result = _wrap_non_tail(_sum_left, DEEP)
        assert result == DEEP

    def test_cps_no_warning_on_deep_binop_right(self):
        _, result = _wrap_non_tail(_sum_right, DEEP)
        assert result == DEEP

    def test_cps_no_warning_on_deep_fib(self):
        _, result = _wrap_non_tail(fib_nontail, 25)
        assert result == 75025

    def test_lazy_cps_strategy_before_activation(self):
        f = derecurse(_sum_left)
        assert f.__derecurse_strategy__ == "lazy_cps"

    def test_cached_cps_on_second_deep_call(self):
        f = derecurse(_sum_left)
        assert f(DEEP) == DEEP
        assert f(DEEP) == DEEP


# ─── Decorator tests ──────────────────────────────────────────────────────────

class TestDerecurse:

    def test_package_version(self):
        assert isinstance(__version__, str) and __version__

    def test_factorial_correct(self):
        f = _wrap_tail(_factorial)
        assert f(0) == 1
        assert f(1) == 1
        assert f(5) == 120
        assert f(10) == 3628800

    def test_factorial_large(self):
        f = derecurse(_factorial)
        result = f(5000)
        assert result > 0

    def test_factorial_strategy_tag(self):
        f = derecurse(_factorial)
        assert hasattr(f, "__derecurse_strategy__")
        assert f.__derecurse_strategy__ in ("tail_call_to_loop", "trampoline")

    def test_countdown(self):
        f = derecurse(_countdown)
        assert f(0) == 0
        assert f(1) == 0
        assert f(100) == 0

    def test_countdown_large(self):
        f = derecurse(_countdown)
        assert f(100_000) == 0

    def test_gcd(self):
        f = derecurse(_gcd)
        assert f(12, 8) == 4
        assert f(100, 75) == 25
        assert f(17, 13) == 1
        assert f(0, 5) == 5

    def test_power(self):
        f = derecurse(_power)
        assert f(2, 0) == 1
        assert f(2, 10) == 1024
        assert f(3, 4) == 81

    def test_sum_tail(self):
        f = derecurse(_mysum)
        assert f(10) == 55
        assert f(100) == 5050

    def test_non_recursive_unchanged(self):
        wrapped = derecurse(add)
        assert wrapped(2, 3) == 5
        assert not hasattr(wrapped, "__derecurse_strategy__")

    def test_non_tail_strategy(self):
        f = derecurse(fib_nontail)
        assert f.__derecurse_strategy__ == "lazy_cps"

    def test_non_tail_still_works(self):
        f = derecurse(fib_nontail)
        assert f(10) == 55

    def test_tail_has_analysis_metadata(self):
        f = _wrap_tail(_factorial)
        assert hasattr(f, "__derecurse_analysis__")
        assert f.__derecurse_analysis__.pattern == RecursionPattern.TAIL_CALL

    def test_non_tail_deep(self):
        _, result = _wrap_non_tail(_sum_nontail, DEEP)
        assert result == DEEP * (DEEP + 1) // 2

    def test_non_tail_binop_left(self):
        f, _ = _wrap_non_tail(_sum_left, DEEP)
        assert f(10) == 10

    def test_non_tail_binop_right(self):
        f, _ = _wrap_non_tail(_sum_right, DEEP)
        assert f(10) == 10

    def test_non_tail_both_binop_sides(self):
        _, result = _wrap_non_tail(fib_nontail, 20)
        assert result == 6765

    def test_non_tail_ifexp(self):
        _, result = _wrap_non_tail(_sum_ifexp, DEEP)
        assert result == DEEP // 2

    def test_non_tail_subscript_slice(self):
        _, result = _wrap_non_tail(_sub_slice_test, 500)
        assert result == 500

    def test_non_tail_subscript_value(self):
        f, r = _wrap_non_tail(_sub_val_test, 500)
        assert isinstance(r, list) and r[0] == 500
        r = f(10)
        assert isinstance(r, list) and r[0] == 10

    def test_non_tail_list(self):
        f = derecurse(_list_elts)
        r = f(10)
        assert isinstance(r, list) and len(r) == 2

    def test_non_tail_tuple(self):
        f = derecurse(_tuple_elts)
        r = f(10)
        assert isinstance(r, tuple) and len(r) == 2

    def test_non_tail_set(self):
        f, r = _wrap_non_tail(_set_elts, 200)
        assert isinstance(r, frozenset)
        assert f(10) is not None

    def test_non_tail_dict(self):
        f = derecurse(_dict_nontail)
        r = f(3)
        assert isinstance(r, dict)

    def test_non_tail_compare(self):
        _, result = _wrap_non_tail(_compare_nontail, DEEP)
        assert result == 0

    def test_non_tail_boolop_or(self):
        f = derecurse(_boolop3_or)
        assert f(10) == 1

    def test_non_tail_boolop_or_deep(self):
        _, result = _wrap_non_tail(_boolop3_or, DEEP)
        assert result == 1

    def test_non_tail_boolop_and(self):
        _, result = _wrap_non_tail(_boolop3_and, DEEP)
        assert result == DEEP

    def test_wrapped_preserved(self):
        f = derecurse(_factorial)
        assert hasattr(f, "__wrapped__")

    def test_name_preserved(self):
        f = derecurse(_factorial)
        assert f.__name__ == "_factorial"

    def test_two_base_cases(self):
        f = derecurse(_collatz_steps)
        assert f(1) == 0
        assert f(6) == 8

    def test_keyword_args_in_call(self):
        f = derecurse(_countdown_kw)
        assert f(5) == 0
        assert f(100) == 0

    def test_non_tail_unary(self):
        _, result = _wrap_non_tail(_unary_nontail, DEEP)
        assert result == 0

    def test_non_tail_attr(self):
        _, result = _wrap_non_tail(_attr_nontail, DEEP)
        assert result == DEEP

    def test_non_tail_seq3(self):
        f = derecurse(_seq3_max)
        assert f(0) == 0
        assert f(1) == 3
        assert f(2) == 4
        assert f(3) == 5
        assert f(5) == 7
        assert f(10) == 12

    def test_non_tail_dict_kwargs(self):
        f, r = _wrap_non_tail(_dict_kwargs, 500)
        assert isinstance(r, dict) and len(r) == 500
        assert f(10) is not None

    def test_non_tail_multi_branch(self):
        _, result = _wrap_non_tail(_multi_branch_nontail, DEEP)
        assert result == DEEP + 1

    def test_non_tail_while(self):
        _, result = _wrap_non_tail(_while_nontail, DEEP)
        assert result == DEEP * 2

    def test_non_tail_for(self):
        _, result = _wrap_non_tail(_for_nontail, DEEP)
        assert result == DEEP + 1

    def test_non_tail_try(self):
        _, result = _wrap_non_tail(_try_nontail, DEEP)
        assert result == DEEP

    def test_assignment_form_shallow_only(self):
        """Recursive call in assignment, not in return — CPS cannot rewrite the body."""
        f = derecurse(_assign_nontail)
        assert f(10) == 10


# ─── Stress tests ─────────────────────────────────────────────────────────────

class TestStress:

    def test_no_stack_overflow(self):
        f = derecurse(_deep)
        default_limit = sys.getrecursionlimit()
        assert f(default_limit * 10) == default_limit * 10

    def test_fibonacci_large_tail(self):
        f = derecurse(_fib_tail)
        assert f(0) == 0
        assert f(1) == 1
        assert f(10) == 55
        assert f(50) == 12586269025
        result = f(10_000)
        assert result > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
