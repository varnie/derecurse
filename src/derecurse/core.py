"""
Core @derecurse decorator.

Strategy selection:
1. Try AST analysis (requires getsource) → rewrite to loop
2. Fall back to trampoline (works universally, no source needed)
"""

from __future__ import annotations

import warnings
from typing import TypeVar, Callable

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
        warnings.warn(
            f"[derecurse] '{func.__name__}' has non-tail recursion "
            f"({analysis.non_tail_count} call(s) embedded in expressions). "
            "Cannot safely convert to loop. "
            "Hint: add an accumulator parameter to make it tail-recursive.",
            stacklevel=2,
        )
        return func

    return func
