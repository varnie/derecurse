"""Stress tests for deep recursion."""

import sys

from derecurse import derecurse

from tests.helpers import deep, fib_tail


class TestStress:
    def test_no_stack_overflow(self):
        f = derecurse(deep)
        default_limit = sys.getrecursionlimit()
        assert f(default_limit * 10) == default_limit * 10

    def test_fibonacci_large_tail(self):
        f = derecurse(fib_tail)
        assert f(0) == 0
        assert f(1) == 1
        assert f(10) == 55
        assert f(50) == 12586269025
        result = f(10_000)
        assert result > 0
