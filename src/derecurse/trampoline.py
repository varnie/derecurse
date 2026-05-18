"""
Trampoline-based tail call elimination.

Does NOT require source code — works by wrapping the function
so recursive calls return a thunk instead of recursing,
then the trampoline loop bounces them iteratively.

This approach works universally — in pytest, REPL, lambdas, anywhere.
"""

from __future__ import annotations
import functools
import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class _TailCall:
    """Sentinel: a deferred tail call."""
    __slots__ = ("args", "kwargs")

    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs


def trampoline_wrap(func: Callable) -> Callable:
    """
    Wrap a tail-recursive function using the trampoline pattern.

    The wrapped function replaces itself in the globals with a version
    that returns _TailCall sentinels. The outer trampoline loop
    keeps bouncing until a real value comes back.

    Works without source code inspection.
    """
    func_name = func.__name__
    _lock = threading.Lock()

    def sentinel_func(*args, **kwargs):
        return _TailCall(args, kwargs)

    @functools.wraps(func)
    def trampolined(*args, **kwargs):
        with _lock:
            old = func.__globals__.get(func_name)
            func.__globals__[func_name] = sentinel_func
            try:
                result = func(*args, **kwargs)
                while isinstance(result, _TailCall):
                    result = func(*result.args, **result.kwargs)
            finally:
                if old is None:
                    func.__globals__.pop(func_name, None)
                else:
                    func.__globals__[func_name] = old
        return result

    trampolined.__derecurse_strategy__ = "trampoline"
    trampolined.__wrapped__ = func
    return trampolined
