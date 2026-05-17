# derecurse Proof of Concept

Automatic recursion optimizer for Python. The `@derecurse` decorator rewrites
tail-recursive functions as iterative loops, eliminating `RecursionError` and
allowing millions of recursive calls without stack growth.

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

- **Zero runtime dependencies** — pure Python stdlib (`ast`, `inspect`, ...)
- **Three optimization strategies** — AST rewrite (tail calls), CPS trampoline
  (non-tail), and thunk trampoline (fallback)
- **Non-tail recursion support** — naive Fibonacci, tree traversal, and other
  non-tail patterns work to arbitrary depth via lazy CPS conversion
- **Zero overhead for shallow calls** — non-tail functions run at native speed
  until the first `RecursionError`, then CPS kicks in transparently
- **Introspection** — rewritten functions carry `__derecurse_strategy__`,
  `__derecurse_analysis__`, and `__wrapped__` attributes
- **Thread-safe** — trampoline uses per-function locks for concurrent access

## Limitations

- Non-tail CPS conversion handles `BinOp`, `IfExp`, `BoolOp`, and `UnaryOp`
  patterns with self-calls. Other expression shapes fall through to native
  recursion (no stack overflow protection).
- Mutual recursion is not yet handled.
- CPS-converted functions are 2–10× slower than native for deep calls
  (closure overhead), but shallow calls run at full speed.
- Requires Python 3.10+.

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
