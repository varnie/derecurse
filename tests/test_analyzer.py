"""AST analyzer tests."""

from derecurse import RecursionPattern
from derecurse.analyzer import analyze

from tests.helpers import add, assign_nontail, factorial, fib_nontail


class TestAnalyzer:
    def test_no_recursion(self):
        def f(a, b):
            return a + b

        assert analyze(f).pattern == RecursionPattern.NO_RECURSION

    def test_tail_call_simple(self):
        def f(n, acc=1):
            if n == 0:
                return acc
            return f(n - 1, n * acc)

        result = analyze(f)
        assert result.pattern == RecursionPattern.TAIL_CALL
        assert result.tail_call_count == 1
        assert result.non_tail_count == 0

    def test_non_tail_fib(self):
        def fib(n):
            if n <= 1:
                return n
            return fib(n - 1) + fib(n - 2)

        result = analyze(fib)
        assert result.pattern == RecursionPattern.NON_TAIL
        assert result.non_tail_count == 2

    def test_tail_call_countdown(self):
        def f(n):
            if n <= 0:
                return 0
            return f(n - 1)

        assert analyze(f).pattern == RecursionPattern.TAIL_CALL

    def test_tail_call_two_params(self):
        def f(base, exp, acc=1):
            if exp == 0:
                return acc
            return f(base, exp - 1, acc * base)

        assert analyze(f).pattern == RecursionPattern.TAIL_CALL

    def test_params_extracted(self):
        def f(n, acc=1):
            if n == 0:
                return acc
            return f(n - 1, n * acc)

        result = analyze(f)
        assert result.params == ["n", "acc"]
        assert result.defaults == {"acc": 1}

    def test_non_tail_sum(self):
        def f(lst):
            if not lst:
                return 0
            return lst[0] + f(lst[1:])

        assert analyze(f).pattern == RecursionPattern.NON_TAIL

    def test_tail_with_multiple_branches(self):
        def f(a, b):
            if b == 0:
                return a
            return f(b, a % b)

        assert analyze(f).pattern == RecursionPattern.TAIL_CALL

    def test_assignment_non_tail(self):
        assert analyze(assign_nontail).pattern == RecursionPattern.NON_TAIL

    def test_is_optimizable(self):
        tail = analyze(factorial)
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
