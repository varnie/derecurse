"""
Tests for derecurse.
Run with: python -m pytest tests/ -v
"""

import sys
import warnings
from pathlib import Path
import pytest

try:
    from derecurse import derecurse, RecursionPattern
    from derecurse.analyzer import analyze
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from derecurse import derecurse, RecursionPattern
    from derecurse.analyzer import analyze


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


# ─── Decorator tests ──────────────────────────────────────────────────────────

class TestDerecurse:

    def test_factorial_correct(self):
        f = derecurse(_factorial)
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

    def test_non_tail_deep(self):
        f = derecurse(_sum_nontail)
        assert f(5000) == 5000 * 5001 // 2

    def test_non_tail_binop_left(self):
        f = derecurse(_sum_left)
        assert f(10) == 10
        assert f(5000) == 5000

    def test_non_tail_binop_right(self):
        f = derecurse(_sum_right)
        assert f(10) == 10
        assert f(5000) == 5000

    def test_non_tail_ifexp(self):
        f = derecurse(_sum_ifexp)
        assert f(10) == 5
        assert f(5000) == 2500

    def test_non_tail_subscript_slice(self):
        f = derecurse(_sub_slice_test)
        assert f(10) == 10
        assert f(500) == 500

    def test_non_tail_subscript_value(self):
        f = derecurse(_sub_val_test)
        r = f(10)
        assert isinstance(r, list) and r[0] == 10
        r = f(500)
        assert isinstance(r, list) and r[0] == 500

    def test_non_tail_list(self):
        f = derecurse(_list_elts)
        r = f(10)
        assert isinstance(r, list) and len(r) == 2

    def test_non_tail_tuple(self):
        f = derecurse(_tuple_elts)
        r = f(10)
        assert isinstance(r, tuple) and len(r) == 2

    def test_non_tail_set(self):
        import sys as _sys
        old = _sys.getrecursionlimit()
        _sys.setrecursionlimit(300)
        try:
            f = derecurse(_set_elts)
            r = f(10)
            assert isinstance(r, frozenset)
            r = f(500)
            assert isinstance(r, frozenset)
        finally:
            _sys.setrecursionlimit(old)

    def test_non_tail_dict(self):
        f = derecurse(_dict_nontail)
        r = f(3)
        assert isinstance(r, dict)

    def test_non_tail_compare(self):
        import sys as _sys
        old = _sys.getrecursionlimit()
        _sys.setrecursionlimit(300)
        try:
            f = derecurse(_compare_nontail)
            assert f(10) == 0
            assert f(5000) == 0
        finally:
            _sys.setrecursionlimit(old)

    def test_non_tail_boolop3(self):
        f = derecurse(_boolop3_or)
        assert f(10) == 1

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
        import sys as _sys
        f = derecurse(_unary_nontail)
        assert f(10) == 0
        old = _sys.getrecursionlimit()
        _sys.setrecursionlimit(300)
        try:
            assert f(5000) == 0
        finally:
            _sys.setrecursionlimit(old)

    def test_non_tail_attr(self):
        import sys as _sys
        f = derecurse(_attr_nontail)
        assert f(10) == 10
        old = _sys.getrecursionlimit()
        _sys.setrecursionlimit(300)
        try:
            assert f(5000) == 5000
        finally:
            _sys.setrecursionlimit(old)

    def test_non_tail_seq3(self):
        f = derecurse(_seq3_max)
        assert f(0) == 0
        assert f(1) == 3
        assert f(2) == 4
        assert f(3) == 5
        assert f(5) == 7
        assert f(10) == 12

    def test_non_tail_dict_kwargs(self):
        import sys as _sys
        f = derecurse(_dict_kwargs)
        r = f(10)
        assert isinstance(r, dict) and len(r) == 10
        old = _sys.getrecursionlimit()
        _sys.setrecursionlimit(300)
        try:
            r = f(500)
            assert isinstance(r, dict) and len(r) == 500
        finally:
            _sys.setrecursionlimit(old)

    def test_non_tail_multi_branch(self):
        import sys as _sys
        f = derecurse(_multi_branch_nontail)
        assert f(10) == 11
        old = _sys.getrecursionlimit()
        _sys.setrecursionlimit(300)
        try:
            assert f(5000) == 5001
        finally:
            _sys.setrecursionlimit(old)

    def test_non_tail_while(self):
        import sys as _sys
        f = derecurse(_while_nontail)
        assert f(10) == 20
        old = _sys.getrecursionlimit()
        _sys.setrecursionlimit(300)
        try:
            assert f(5000) == 10000
        finally:
            _sys.setrecursionlimit(old)

    def test_non_tail_for(self):
        import sys as _sys
        f = derecurse(_for_nontail)
        assert f(10) == 10
        old = _sys.getrecursionlimit()
        _sys.setrecursionlimit(300)
        try:
            assert f(5000) == 5001
        finally:
            _sys.setrecursionlimit(old)

    def test_non_tail_try(self):
        import sys as _sys
        f = derecurse(_try_nontail)
        assert f(10) == 10
        old = _sys.getrecursionlimit()
        _sys.setrecursionlimit(300)
        try:
            assert f(5000) == 5000
        finally:
            _sys.setrecursionlimit(old)


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
