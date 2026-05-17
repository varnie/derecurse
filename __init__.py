"""
derecurse — automatic recursion optimizer.

Detects recursion patterns via AST analysis and rewrites
functions to use efficient iterative strategies.

Usage:
    from derecurse import derecurse

    @derecurse
    def factorial(n, acc=1):
        if n == 0: return acc
        return factorial(n - 1, n * acc)
"""

from .core import derecurse
from .analyzer import RecursionPattern

__all__ = ["derecurse", "RecursionPattern"]
__version__ = "0.1.0"
