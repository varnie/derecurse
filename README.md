# derecurse

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
2. **Rewrite** — for tail-recursive functions, the AST is rewritten in-place
   to a `while True` loop with parameter reassignment. This is transparent —
   the original source is never modified.
3. **Fall back** — if source inspection fails (e.g. in a REPL or lambda),
   a trampoline-based approach is used instead, which works without source
   access.
4. **Warn** — non-tail-recursive functions (e.g. naive Fibonacci) are returned
   unchanged with a warning and a hint about adding an accumulator.

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
- **Two optimization strategies** — AST rewrite (clean) and trampoline (universal)
- **Graceful degradation** — non-tail functions pass through with a warning
- **Introspection** — rewritten functions carry `__derecurse_strategy__`,
  `__derecurse_analysis__`, and `__wrapped__` attributes
- **Thread-safe** — trampoline uses per-function locks for concurrent access

## Limitations

- Only **tail-recursive** functions are optimized. Non-tail recursion
  (e.g. `return f(n-1) + f(n-2)`) cannot be safely converted and is left
  unchanged.
- Requires Python 3.10+.

## Development

```bash
git clone https://github.com/varnie/derecurse.git
cd derecurse
pip install -e .
pip install pytest
pytest -v
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
