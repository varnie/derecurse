# derecurse (Proof of Concept)

Automatic recursion optimizer for Python. The `@derecurse` decorator rewrites
tail-recursive functions as iterative loops, eliminating `RecursionError` and
allowing millions of recursive calls without stack growth.

> ⚠️ **Disclaimer:** This project is an academic **Proof of Concept (PoC)** designed to explore AST manipulation and compiler theory in Python. It is **not recommended for production use** due to performance trade-offs, debugging complexity, and strict dependency on Python's internal AST structures.

## Quick start

```python
from derecurse import derecurse

@derecurse
def factorial(n, acc=1):
    if n == 0:
        return acc
    return factorial(n - 1, n * acc)

factorial(100_000)  # no RecursionError
```

## How it works

1. **Analyze** — the decorator inspects the function's AST to classify its
   recursion pattern (tail call, non-tail, or none).
2. **Tail-call rewrite** — the AST is rewritten in-place to a `while True`
   loop with parameter reassignment. The original source is never modified.
3. **Non-tail CPS rewrite** — for non-tail-recursive functions (e.g. naive
   Fibonacci), a CPS (Continuation-Passing Style) conversion + thunk trampoline
   is used. The function runs at native speed for shallow calls, and only
   converts on the first `RecursionError`.
4. **Fall back** — if source inspection fails (e.g. in a REPL or lambda),
   a trampoline-based approach is used instead, which works without source
   access.

## ⚠️ Performance & Architecture Trade-offs

* **Tail-Call Optimization:** High performance. Rewriting to a `while` loop runs at native loop speed and uses $O(1)$ memory.
* **Non-Tail CPS Optimization:** Extremely heavy. Every recursive step in CPS mode wraps computations into a new `lambda` function object. While the *lazy* wrapper ensures **zero overhead for shallow calls**, deep calls that trigger the CPS trampoline will run **2–10x slower** than native Python code and generate massive amounts of short-lived objects for the Garbage Collector.

## Installation

```bash
pip install git+https://github.com/varnie/derecurse.git
```

Or from a local clone:

```bash
git clone https://github.com/varnie/derecurse.git
cd derecurse
pip install .
```

## Features

* **Zero runtime dependencies** — Pure Python standard library (`ast`, `inspect`, `threading`).
* **Three optimization strategies** — AST loop rewrite (tail calls), lazy CPS trampoline (non-tail), and functional trampoline (fallback).
* **Non-tail recursion support** — Naive Fibonacci, deep tree traversals, and complex expressions work to arbitrary depth via lazy CPS conversion.
* **Zero overhead for shallow calls** — Non-tail functions run at full native speed until the stack actually overflows; CPS transformation kicks in transparently on `RecursionError`.
* **Introspection** — Optimized functions carry `__derecurse_strategy__`, `__derecurse_analysis__`, and `__wrapped__` attributes for analysis.
* **Thread-safe** — The trampoline uses per-function locks to ensure safety during concurrent execution.


## Limitations & Edge Cases

* **Expression Support:** Non-tail CPS conversion currently handles `BinOp`, `IfExp`, `BoolOp`, and `UnaryOp` patterns containing self-calls. Other complex expression shapes will fall through to native recursion (offering no stack protection).
* **Mutual Recursion:** Functions that call each other (A → B → A) are not supported.
* **Debugging & Tracebacks:** Once a function is transformed via CPS, its traceback inside logs becomes a dense sequence of repetitive `lambda` thunk evaluations inside `<derecurse:func_name>`, making traditional debugging and post-mortem analysis difficult.
* **Python Upgrades:** Because this library directly manipulates Python's Internal AST nodes, minor changes to the Python language grammar (such as required node attributes introduced in Python 3.8/3.11+) can cause the compiler to break. Requires Python 3.10+.


## Development

```bash
git clone https://github.com/varnie/derecurse.git
cd derecurse
pip install -e ".[dev]"
pytest tests/ -v
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --extra dev
uv run pytest tests/ -v
```

## API

```python
@derecurse
def foo(n, acc=0):
    ...
```

`RecursionPattern` — enum with `NO_RECURSION`, `TAIL_CALL`, `NON_TAIL`,
`MUTUAL`.

`analyze(func)` — returns an `AnalysisResult` with the function's pattern,
parameter names, call counts, and notes.

## License

MIT
