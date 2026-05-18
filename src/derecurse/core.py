"""
Core @derecurse decorator.

Strategy selection:
1. Try AST analysis (requires getsource) → rewrite to loop
2. Fall back to trampoline (works universally, no source needed)
"""

from __future__ import annotations

import functools
import threading
import warnings
from collections.abc import Callable
from typing import TypeVar

from .analyzer import analyze, RecursionPattern
from .trampoline import trampoline_wrap

F = TypeVar("F", bound=Callable)


def derecurse(func: F) -> Callable:
    """
    Decorator that automatically optimizes recursive functions.

    For tail-recursive functions:
      - Tries AST rewrite to a clean iterative loop first
      - Falls back to trampoline if source is unavailable
    Non-tail recursive functions are returned unchanged with a warning.

    Example:
        @derecurse
        def factorial(n, acc=1):
            if n == 0: return acc
            return factorial(n - 1, n * acc)

        factorial(100_000)  # works fine, no RecursionError
    """
    analysis = analyze(func)

    if analysis.pattern == RecursionPattern.NO_RECURSION:
        return func

    if analysis.pattern == RecursionPattern.TAIL_CALL:
        # Try AST rewrite first (cleanest output)
        try:
            from .rewriter import rewrite_tail_call
            optimized = rewrite_tail_call(func, analysis)
            optimized.__derecurse_analysis__ = analysis
            return optimized
        except Exception as exc:
            warnings.warn(
                f"[derecurse] AST rewrite failed for '{func.__name__}': {exc}",
                stacklevel=2,
            )

        # Fall back to trampoline — works without source code
        try:
            optimized = trampoline_wrap(func)
            optimized.__derecurse_analysis__ = analysis
            return optimized
        except Exception as e:
            warnings.warn(
                f"[derecurse] Could not optimize '{func.__name__}': {e}",
                stacklevel=2,
            )
            return func

    if analysis.pattern == RecursionPattern.NON_TAIL:
        return _lazy_cps_wrapper(func, analysis)

    return func


def _lazy_cps_wrapper(func, analysis):
    """
    Lazy CPS wrapper for non-tail-recursive functions.
    Runs the original function directly (zero overhead) and only
    CPS-converts on the first RecursionError.
    """
    cps_func = None
    _lock = threading.Lock()

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        nonlocal cps_func
        try:
            return func(*args, **kwargs)
        except RecursionError:
            with _lock:
                if cps_func is None:
                    cps_func = _build_cps(func, analysis)
                    if cps_func is None:
                        raise
            return cps_func(*args, **kwargs)

    wrapper.__derecurse_strategy__ = "lazy_cps"
    wrapper.__wrapped__ = func
    return wrapper


def _build_cps(func, analysis):
    """Attempt CPS rewrite; return None on failure."""
    try:
        from .cps import cps_rewrite
        cps_func = cps_rewrite(func, analysis)
        cps_func.__derecurse_analysis__ = analysis
        return cps_func
    except Exception as exc:
        warnings.warn(
            f"[derecurse] CPS rewrite failed for '{func.__name__}': {exc}",
            stacklevel=2,
        )
        return None
