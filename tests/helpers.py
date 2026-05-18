"""Shared helpers and sample recursive functions for derecurse tests."""

from __future__ import annotations

import warnings

from derecurse import derecurse

# Depth used to verify CPS/trampoline beyond the default recursion limit.
DEEP = 5000


def wrap_non_tail(func, *args):
    """Apply @derecurse and run at depth that triggers CPS; fail on rewrite warnings."""
    wrapped = derecurse(func)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", category=UserWarning)
        result = wrapped(*args)
    failures = [cw for cw in caught if "CPS rewrite failed" in str(cw.message)]
    assert not failures, "; ".join(str(f.message) for f in failures)
    return wrapped, result


def wrap_tail(func):
    """Apply @derecurse to a tail-recursive function; fail on rewrite warnings."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", category=UserWarning)
        wrapped = derecurse(func)
    failures = [
        w for w in caught
        if "rewrite failed" in str(w.message) or "Could not optimize" in str(w.message)
    ]
    assert not failures, "; ".join(str(w.message) for w in failures)
    return wrapped


# ─── Sample functions (undecorated — @derecurse applied inside tests) ───────


def factorial(n, acc=1):
    if n == 0:
        return acc
    return factorial(n - 1, n * acc)


def countdown(n):
    if n <= 0:
        return 0
    return countdown(n - 1)


def gcd(a, b):
    if b == 0:
        return a
    return gcd(b, a % b)


def power(base, exp, acc=1):
    if exp == 0:
        return acc
    return power(base, exp - 1, acc * base)


def mysum(n, acc=0):
    if n == 0:
        return acc
    return mysum(n - 1, acc + n)


def fib_tail(n, a=0, b=1):
    if n == 0:
        return a
    return fib_tail(n - 1, b, a + b)


def deep(n, acc=0):
    if n == 0:
        return acc
    return deep(n - 1, acc + 1)


def collatz_steps(n, steps=0):
    if n == 1:
        return steps
    if n % 2 == 0:
        return collatz_steps(n // 2, steps + 1)
    return collatz_steps(3 * n + 1, steps + 1)


def countdown_kw(n, result=0):
    if n == 0:
        return result
    return countdown_kw(n=n - 1, result=result)


def add(a, b):
    return a + b


def fib_nontail(n):
    if n <= 1:
        return n
    return fib_nontail(n - 1) + fib_nontail(n - 2)


def sum_nontail(n):
    if n <= 0:
        return 0
    return n + sum_nontail(n - 1)


def sum_left(n):
    if n <= 0:
        return 0
    return sum_left(n - 1) + 1


def sum_right(n):
    if n <= 0:
        return 0
    return 1 + sum_right(n - 1)


def sum_ifexp(n):
    if n <= 0:
        return 0
    return sum_ifexp(n - 1) + 0 if n % 2 == 0 else sum_ifexp(n - 1) + 1


_arr = list(range(2000))


def sub_slice_test(n):
    if n <= 0:
        return 0
    return _arr[sub_slice_test(n - 1)] + 1


def sub_val_test(n):
    if n <= 0:
        return [0]
    return [sub_val_test(n - 1)[0] + 1]


def list_elts(n):
    if n <= 0:
        return []
    return [list_elts(n - 1), 0]


def tuple_elts(n):
    if n <= 0:
        return ()
    return (tuple_elts(n - 1), 0)


def set_elts(n):
    if n <= 0:
        return frozenset()
    return frozenset({set_elts(n - 1), 0})


def dict_nontail(n):
    if n <= 0:
        return {0: 0}
    return {0: dict_nontail(n - 1)}


def compare_nontail(n):
    if n <= 0:
        return 0
    return (compare_nontail(n - 1) > 0) + 0


def boolop3_or(n):
    if n <= 0:
        return 0
    return (boolop3_or(n - 1) or True or False) + 0


def boolop3_and(n):
    if n <= 0:
        return 1
    return boolop3_and(n - 1) and n


def assign_nontail(n, acc=0):
    if n <= 0:
        return acc
    acc = assign_nontail(n - 1, acc + 1)
    return acc


def unary_nontail(n):
    if n <= 0:
        return 0
    return -unary_nontail(n - 1)


def attr_nontail(n):
    if n <= 0:
        return 0
    return attr_nontail(n - 1).real + 1


def seq3_max(n):
    if n <= 0:
        return 0
    return max(seq3_max(n - 1) + 1, seq3_max(n - 2) + 2, seq3_max(n - 3) + 3, 0)


def dict_kwargs(n):
    if n <= 0:
        return {}
    return {**dict_kwargs(n - 1), n: n}


def multi_branch_nontail(n):
    if n <= 0:
        return 0
    if n % 2 == 0:
        return multi_branch_nontail(n - 1) + 1
    return multi_branch_nontail(n - 2) + 2


def while_nontail(n):
    if n <= 0:
        return 0
    total = 0
    i = 0
    while i < n % 5:
        total += 1
        i += 1
    return while_nontail(n - 1) + total


def for_nontail(n):
    if n <= 0:
        return 0
    total = 0
    for _ in range(n % 3):
        total += 1
    return for_nontail(n - 1) + total


def try_nontail(n):
    if n <= 0:
        return 0
    try:
        return try_nontail(n - 1) + 1
    except ValueError:
        return 0
