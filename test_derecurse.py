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


# ─── Module-level optimized functions ────────────────────────────────────────
# derecurse works best on module-level functions (getsource + trampoline both work)

@derecurse
def factorial(n, acc=1):
    if n == 0: return acc
    return factorial(n - 1, n * acc)

@derecurse
def countdown(n):
    if n <= 0: return 0
    return countdown(n - 1)

@derecurse
def gcd(a, b):
    if b == 0: return a
    return gcd(b, a % b)

@derecurse
def power(base, exp, acc=1):
    if exp == 0: return acc
    return power(base, exp - 1, acc * base)

@derecurse
def mysum(n, acc=0):
    if n == 0: return acc
    return mysum(n - 1, acc + n)

@derecurse
def fib_tail(n, a=0, b=1):
    if n == 0: return a
    return fib_tail(n - 1, b, a + b)

@derecurse
def deep(n, acc=0):
    if n == 0: return acc
    return deep(n - 1, acc + 1)

@derecurse
def collatz_steps(n, steps=0):
    if n == 1: return steps
    if n % 2 == 0:
        return collatz_steps(n // 2, steps + 1)
    return collatz_steps(3 * n + 1, steps + 1)

@derecurse
def countdown_kw(n, result=0):
    if n == 0: return result
    return countdown_kw(n=n - 1, result=result)

def add(a, b):
    return a + b
add_wrapped = derecurse(add)

def fib_nontail(n):
    if n <= 1: return n
    return fib_nontail(n - 1) + fib_nontail(n - 2)


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
        assert factorial(0) == 1
        assert factorial(1) == 1
        assert factorial(5) == 120
        assert factorial(10) == 3628800

    def test_factorial_large(self):
        result = factorial(5000)
        assert result > 0

    def test_factorial_strategy_tag(self):
        assert hasattr(factorial, "__derecurse_strategy__")
        assert factorial.__derecurse_strategy__ in ("tail_call_to_loop", "trampoline")

    def test_countdown(self):
        assert countdown(0) == 0
        assert countdown(1) == 0
        assert countdown(100) == 0

    def test_countdown_large(self):
        assert countdown(100_000) == 0

    def test_gcd(self):
        assert gcd(12, 8) == 4
        assert gcd(100, 75) == 25
        assert gcd(17, 13) == 1
        assert gcd(0, 5) == 5

    def test_power(self):
        assert power(2, 0) == 1
        assert power(2, 10) == 1024
        assert power(3, 4) == 81

    def test_sum_tail(self):
        assert mysum(10) == 55
        assert mysum(100) == 5050

    def test_non_recursive_unchanged(self):
        assert add_wrapped(2, 3) == 5
        assert not hasattr(add_wrapped, "__derecurse_strategy__")

    def test_non_tail_warns(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            derecurse(fib_nontail)
            assert len(w) == 1
            assert "non-tail" in str(w[0].message).lower()

    def test_non_tail_still_works(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            f = derecurse(fib_nontail)
        assert f(10) == 55

    def test_wrapped_preserved(self):
        assert hasattr(factorial, "__wrapped__")

    def test_name_preserved(self):
        assert factorial.__name__ == "factorial"

    def test_two_base_cases(self):
        assert collatz_steps(1) == 0
        assert collatz_steps(6) == 8

    def test_keyword_args_in_call(self):
        assert countdown_kw(5) == 0
        assert countdown_kw(100) == 0


# ─── Stress tests ─────────────────────────────────────────────────────────────

class TestStress:

    def test_no_stack_overflow(self):
        default_limit = sys.getrecursionlimit()
        assert deep(default_limit * 10) == default_limit * 10

    def test_fibonacci_large_tail(self):
        assert fib_tail(0) == 0
        assert fib_tail(1) == 1
        assert fib_tail(10) == 55
        assert fib_tail(50) == 12586269025
        result = fib_tail(10_000)
        assert result > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
