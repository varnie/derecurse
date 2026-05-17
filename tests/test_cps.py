"""CPS rewrite and lazy activation tests."""

from derecurse import derecurse
from derecurse.analyzer import analyze
from derecurse.cps import cps_rewrite

from tests.helpers import DEEP, fib_nontail, sum_left, sum_right, wrap_non_tail


class TestCPS:
    def test_cps_rewrite_compiles(self):
        """Generated CPS AST must compile on all supported Python versions."""
        analysis = analyze(sum_left)
        rewritten = cps_rewrite(sum_left, analysis)
        assert rewritten.__derecurse_strategy__ == "cps_trampoline"

    def test_cps_no_warning_on_deep_binop_left(self):
        _, result = wrap_non_tail(sum_left, DEEP)
        assert result == DEEP

    def test_cps_no_warning_on_deep_binop_right(self):
        _, result = wrap_non_tail(sum_right, DEEP)
        assert result == DEEP

    def test_cps_no_warning_on_deep_fib(self):
        _, result = wrap_non_tail(fib_nontail, 25)
        assert result == 75025

    def test_lazy_cps_strategy_before_activation(self):
        f = derecurse(sum_left)
        assert f.__derecurse_strategy__ == "lazy_cps"

    def test_cached_cps_on_second_deep_call(self):
        f = derecurse(sum_left)
        assert f(DEEP) == DEEP
        assert f(DEEP) == DEEP
