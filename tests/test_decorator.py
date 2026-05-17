"""@derecurse decorator integration tests."""

from derecurse import RecursionPattern, __version__, derecurse

from tests.helpers import (
    DEEP,
    add,
    assign_nontail,
    attr_nontail,
    boolop3_and,
    boolop3_or,
    collatz_steps,
    compare_nontail,
    countdown,
    countdown_kw,
    dict_kwargs,
    dict_nontail,
    factorial,
    fib_nontail,
    gcd,
    list_elts,
    multi_branch_nontail,
    mysum,
    power,
    seq3_max,
    set_elts,
    sub_slice_test,
    sub_val_test,
    sum_ifexp,
    sum_left,
    sum_nontail,
    sum_right,
    tuple_elts,
    unary_nontail,
    try_nontail,
    for_nontail,
    while_nontail,
    wrap_non_tail,
    wrap_tail,
)


class TestDerecurse:
    def test_package_version(self):
        assert isinstance(__version__, str) and __version__

    def test_factorial_correct(self):
        f = wrap_tail(factorial)
        assert f(0) == 1
        assert f(1) == 1
        assert f(5) == 120
        assert f(10) == 3628800

    def test_factorial_large(self):
        f = derecurse(factorial)
        result = f(5000)
        assert result > 0

    def test_factorial_strategy_tag(self):
        f = derecurse(factorial)
        assert hasattr(f, "__derecurse_strategy__")
        assert f.__derecurse_strategy__ in ("tail_call_to_loop", "trampoline")

    def test_countdown(self):
        f = derecurse(countdown)
        assert f(0) == 0
        assert f(1) == 0
        assert f(100) == 0

    def test_countdown_large(self):
        f = derecurse(countdown)
        assert f(100_000) == 0

    def test_gcd(self):
        f = derecurse(gcd)
        assert f(12, 8) == 4
        assert f(100, 75) == 25
        assert f(17, 13) == 1
        assert f(0, 5) == 5

    def test_power(self):
        f = derecurse(power)
        assert f(2, 0) == 1
        assert f(2, 10) == 1024
        assert f(3, 4) == 81

    def test_sum_tail(self):
        f = derecurse(mysum)
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
        f = wrap_tail(factorial)
        assert hasattr(f, "__derecurse_analysis__")
        assert f.__derecurse_analysis__.pattern == RecursionPattern.TAIL_CALL

    def test_non_tail_deep(self):
        _, result = wrap_non_tail(sum_nontail, DEEP)
        assert result == DEEP * (DEEP + 1) // 2

    def test_non_tail_binop_left(self):
        f, _ = wrap_non_tail(sum_left, DEEP)
        assert f(10) == 10

    def test_non_tail_binop_right(self):
        f, _ = wrap_non_tail(sum_right, DEEP)
        assert f(10) == 10

    def test_non_tail_both_binop_sides(self):
        _, result = wrap_non_tail(fib_nontail, 20)
        assert result == 6765

    def test_non_tail_ifexp(self):
        _, result = wrap_non_tail(sum_ifexp, DEEP)
        assert result == DEEP // 2

    def test_non_tail_subscript_slice(self):
        _, result = wrap_non_tail(sub_slice_test, 500)
        assert result == 500

    def test_non_tail_subscript_value(self):
        f, r = wrap_non_tail(sub_val_test, 500)
        assert isinstance(r, list) and r[0] == 500
        r = f(10)
        assert isinstance(r, list) and r[0] == 10

    def test_non_tail_list(self):
        f = derecurse(list_elts)
        r = f(10)
        assert isinstance(r, list) and len(r) == 2

    def test_non_tail_tuple(self):
        f = derecurse(tuple_elts)
        r = f(10)
        assert isinstance(r, tuple) and len(r) == 2

    def test_non_tail_set(self):
        f, r = wrap_non_tail(set_elts, 200)
        assert isinstance(r, frozenset)
        assert f(10) is not None

    def test_non_tail_dict(self):
        f = derecurse(dict_nontail)
        r = f(3)
        assert isinstance(r, dict)

    def test_non_tail_compare(self):
        _, result = wrap_non_tail(compare_nontail, DEEP)
        assert result == 0

    def test_non_tail_boolop_or(self):
        f = derecurse(boolop3_or)
        assert f(10) == 1

    def test_non_tail_boolop_or_deep(self):
        _, result = wrap_non_tail(boolop3_or, DEEP)
        assert result == 1

    def test_non_tail_boolop_and(self):
        _, result = wrap_non_tail(boolop3_and, DEEP)
        assert result == DEEP

    def test_wrapped_preserved(self):
        f = derecurse(factorial)
        assert hasattr(f, "__wrapped__")

    def test_name_preserved(self):
        f = derecurse(factorial)
        assert f.__name__ == "factorial"

    def test_two_base_cases(self):
        f = derecurse(collatz_steps)
        assert f(1) == 0
        assert f(6) == 8

    def test_keyword_args_in_call(self):
        f = derecurse(countdown_kw)
        assert f(5) == 0
        assert f(100) == 0

    def test_non_tail_unary(self):
        _, result = wrap_non_tail(unary_nontail, DEEP)
        assert result == 0

    def test_non_tail_attr(self):
        _, result = wrap_non_tail(attr_nontail, DEEP)
        assert result == DEEP

    def test_non_tail_seq3(self):
        f = derecurse(seq3_max)
        assert f(0) == 0
        assert f(1) == 3
        assert f(2) == 4
        assert f(3) == 5
        assert f(5) == 7
        assert f(10) == 12

    def test_non_tail_dict_kwargs(self):
        f, r = wrap_non_tail(dict_kwargs, 500)
        assert isinstance(r, dict) and len(r) == 500
        assert f(10) is not None

    def test_non_tail_multi_branch(self):
        _, result = wrap_non_tail(multi_branch_nontail, DEEP)
        assert result == DEEP + 1

    def test_non_tail_while(self):
        _, result = wrap_non_tail(while_nontail, DEEP)
        assert result == DEEP * 2

    def test_non_tail_for(self):
        _, result = wrap_non_tail(for_nontail, DEEP)
        assert result == DEEP + 1

    def test_non_tail_try(self):
        _, result = wrap_non_tail(try_nontail, DEEP)
        assert result == DEEP

    def test_assignment_form_shallow_only(self):
        """Recursive call in assignment, not in return — CPS cannot rewrite the body."""
        f = derecurse(assign_nontail)
        assert f(10) == 10
