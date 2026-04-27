# Avalanche — Claude Instructions

This file is auto-loaded at the start of every session. Read it first, then consult `.claude/memory/MEMORY.md` for the full index of project knowledge.

---

## Project at a glance

**What:** A faithful reproduction of **I.Q.: Intelligent Qube** (1997 PlayStation puzzle game), built entirely in Python and shipped as a browser **PWA**.

**Stack:** Pygame CE + Pygbag (CPython → WebAssembly) + PWA (manifest + service worker).

**Canonical reference:** `Research/Intelligent Qube Technical Reproduction Research.md` — authoritative source for game mechanics, scoring, and architecture.

**Entry point:** `main.py` — async loop, `await asyncio.sleep(0)` each frame.

---

## Hard rules (do not violate)

1. **Pygbag compatibility is non-negotiable.** Every code change must keep the game runnable in the browser:
   - Async main loop with `await asyncio.sleep(0)` every frame.
   - No C extensions beyond `pygame-ce`.
   - No filesystem writes at runtime.
   - No `pygame.SysFont` (not available under WASM); use `pygame.font.Font(None, …)` or a bundled `.ttf` in `assets/`.
2. **Modularity over cleverness.** Game logic and rendering stay decoupled. Tunables live in `constants.py`. Cube types are data-driven via the `CUBE_TYPES` registry with `CubeBehavior` enum hooks — adding a new cube type means adding an entry, not rewriting logic.
3. **Retain the retro feel** — especially difficulty. The original I.Q. is punishing by design. Do not soften the timing, scoring, or crush rules to make the game "fairer."
4. **Never skip the review pipeline.** After every implementation step:
   - **Self-test rigorously** (invariants, desktop smoke tests where possible).
   - **Expert panel review** (4 parallel agents — see `.claude/memory/project_expert_panel.md`).
   - **User review** with detailed testing instructions (see `docs/STEP1_REVIEW.md` for the template).
   - Wait for explicit user approval before starting the next step.
5. **Progress is resumable.** Every session must be able to pick up where the last one left off by reading `docs/PROGRESS.md` and `docs/PLAN.md` first.

---

## Repository layout

```
F:/Python/Avalanche/
├── CLAUDE.md                     ← you are here
├── README.md
├── main.py, constants.py, renderer.py, cube_data.py, …   (game source)
├── run_dev.sh                    ← `bash run_dev.sh` launches the dev server
├── pygbag.ini, pyproject.toml, uv.lock
├── docs/
│   ├── PLAN.md                   ← full 11-step implementation plan
│   ├── PROGRESS.md               ← step tracker + session log (READ FIRST)
│   └── STEP<N>_REVIEW.md         ← per-step user-review instructions
├── Research/
│   └── Intelligent Qube Technical Reproduction Research.md
├── .claude/
│   ├── memory/
│   │   ├── MEMORY.md             ← index of supporting memory files
│   │   ├── project_avalanche.md
│   │   ├── project_expert_panel.md
│   │   ├── feedback_review_process.md
│   │   ├── feedback_extensibility.md
│   │   └── reference_pygbag_config.md
│   ├── launch.json
│   └── settings.local.json
└── build/                        ← pygbag output (not tracked)
```

---

## Session startup checklist

When resuming a session, do these in order **before touching code**:

1. Read `docs/PROGRESS.md` to see which step is current and what's approved.
2. Read `docs/PLAN.md` for the step's goals and test criteria.
3. Skim `.claude/memory/MEMORY.md` if you need a refresher on the review panel, extensibility rules, or pygbag quirks.
4. Confirm with the user before starting if the next step isn't yet approved.

---

## Running the game locally

```bash
cd F:/Python/Avalanche
bash run_dev.sh            # Git Bash on Windows or WSL; both work
# → open http://localhost:8000 (first load ~30s while pygbag fetches CPython)
```

See `.claude/memory/reference_pygbag_config.md` for flag details and known quirks (WSL networking, the `--bind 0.0.0.0` trap, hidden-tab rAF pause).

---

## User-invoked shortcuts

- **"Let the panel of experts review"** — launch 4 parallel agents with the personas in `.claude/memory/project_expert_panel.md` and report back.
- **"Resume"** — start from the session startup checklist above.






# Coding Standards — Power of Ten (Python)

Derived from Gerard J. Holzmann's *The Power of Ten: Rules for Developing Safety Critical Code* (NASA/JPL), adapted for Python. These rules apply to all Python code written in this project.

**Guiding principle:** Every rule is stated so that compliance can be verified by reading the code or running a tool. Rules never contradict each other. When two rules both apply, the more specific rule governs.

---

## Rule 1 — No Recursion
Do not write recursive functions. Every call chain must terminate at a known depth without a function calling itself, directly or indirectly. Use an explicit stack (a `list`) or iterative loop instead.

**Why it matters in Python:** Python's default recursion limit is 1000 frames; exceeding it raises `RecursionError`. Iterative solutions are always possible and easier to trace.

## Rule 2 — Every `while` Loop Has an Explicit Bound
`for` loops over finite iterables are fine. Every `while` loop must include a counter and an explicit ceiling check. The form of the check depends on *why* exceeding the bound can happen:

- **Bug (internal state):** use `assert`. The loop is iterating over internal data structures and exceeding the bound means the program is broken.
- **Runtime condition (external state):** use `raise` with a specific exception. The loop is waiting on a queue, retrying a flaky call, or draining external input — exceeding the bound is a legitimate failure mode that callers may want to catch.

```python
# Internal bound — programming error if exceeded
MAX_STEPS = 1000
steps = 0
while not solver.converged():
    assert steps < MAX_STEPS, "solver failed to converge"
    steps += 1
    solver.step()

# External bound — runtime condition
MAX_RETRIES = 5
attempts = 0
while not response_ok:
    if attempts >= MAX_RETRIES:
        raise TimeoutError(f"no successful response after {MAX_RETRIES} attempts")
    attempts += 1
    response_ok = try_request()
```

Exception: one top-level application event loop (e.g., `while True: handle_event()`) is permitted without a bound, clearly labeled with a comment.

## Rule 3 — No Unbounded Collection Growth
Any collection that grows inside an unbounded or externally-driven loop must have a documented maximum size, enforced before each addition:

```python
assert len(results) < MAX_RESULTS, "results exceeded maximum capacity"
results.append(item)
```

**Exempt:** comprehensions and single-pass transformations over an already-bounded input (e.g., `[x * 2 for x in inputs]`) inherit their bound from the input and need no additional check.

**Required:** any `append`, `add`, or `__setitem__` call whose execution count depends on runtime conditions (network responses, user input, file contents of unknown size).

## Rule 4 — Functions Stay Under 50 Lines
No function body may exceed 50 lines, excluding blank lines and comments. When splitting, divide along a **logical boundary** — a coherent sub-task that can be named and tested independently. Do not split arbitrarily; each resulting function must have a single clear purpose.

## Rule 5 — At Least One Meaningful Check Per Function
Every function must contain at least one runtime check. Add a second check if the function has a second distinct invariant to verify. Do not add checks that duplicate what the type system already proves, and do not pad with trivially-true assertions.

A check is **meaningful** only if it tests a property that the type annotations (enforced by Rule 10) cannot prove. Examples of meaningful checks:
- Value ranges (`if b == 0: raise ValueError(...)`)
- Relationships between inputs (`assert len(keys) == len(values)`)
- Invariants preserved by the function (`assert len(result) == len(source)`)
- Domain constraints (`if not email.endswith(...): raise ...`)

Use `raise` for invalid inputs from callers (preconditions on untrusted data). Use `assert` for internal invariants (conditions that indicate a bug if violated).

```python
def scale(values: list[float], factor: float) -> list[float]:
    if factor < 0:
        raise ValueError("factor must be non-negative")        # precondition on input
    result = [v * factor for v in values]
    assert len(result) == len(values), "scaling changed length"  # invariant mypy cannot prove
    return result
```

**Exempt:** functions of 5 lines or fewer whose parameters are fully typed, have no branching, and perform a single pure operation. A trivial getter or single-line wrapper need not carry defensive checks.

## Rule 6 — Narrow Scope for All Variables
Define variables as close to their first use as possible. Do not declare at the top of a function what is only needed halfway through. Do not use module-level mutable state as a substitute for passing arguments. Do not use `global`. Use `nonlocal` only when no cleaner alternative exists.

When Rule 9 requires assigning an intermediate value to a named variable, that variable still follows Rule 6: it lives only in the immediate block where it is used.

## Rule 7 — Handle Every Return Value
Do not silently discard the return value of a function that returns a meaningful result. If a return value is intentionally ignored, assign it to `_` and include an inline comment naming the specific reason:

```python
_ = cache.pop(key, None)  # key may be absent; absence is not an error
```

Every function must also validate its own inputs (see Rule 5). The caller's check of a return value and the callee's check of its own output are complementary, not redundant — they defend different boundaries.

## Rule 8 — No Metaprogramming
Do not use `eval`, `exec`, `__getattr__`-based dispatch, `setattr` for runtime attribute creation, monkey patching, or decorators that silently alter a function's inputs, outputs, or control flow.

Acceptable uses: decorators that only add logging, timing, caching with a documented cache policy, or register the function in a visible registry. The rule of thumb: after the decorator runs, a reader of the call site must still be able to predict what executes.

## Rule 9 — Shallow Access, Named Callables
Do not chain more than two attribute or index accesses in a single expression. `a.b.c` is the limit; `a.b.c.d` must be broken up. Assign the intermediate object to a named local variable, which lives only in the block where it is used (Rule 6).

```python
# Not allowed
value = config.database.connection.pool.timeout

# Allowed
pool = config.database.connection.pool
value = pool.timeout
```

Pass named functions as callbacks, not `lambda` expressions. Lambdas are permitted only as `key=` arguments to `sorted`, `min`, `max`, and similar built-ins, and only when the expression is a single operation.

## Rule 10 — Zero Linter and Type Warnings
All code must pass the following with zero errors or warnings:
- **`ruff check .`** — style and lint
- **`mypy --strict`** — type checking with full annotations required

Every function parameter and return value must have a type annotation. Because `mypy --strict` proves type correctness, Rule 5's meaningful-check requirement explicitly excludes type checks — the type system already enforces them.

If a tool reports a false positive, rewrite the code to remove the ambiguity. Suppression comments (`# type: ignore`, `# noqa`) are permitted only when the specific rule code and reason are named on the same line:

```python
result = legacy_api()  # type: ignore[no-untyped-call]  -- third-party lib lacks stubs
```

## Rule 11 — Explicit Timeouts on All I/O and API Calls
Every call that blocks on something outside the Python process must pass an explicit `timeout` argument. This includes, without exception:

- **HTTP / REST / GraphQL API calls** (`requests`, `httpx`, `urllib`, SDK clients for any external service)
- **Database queries** (connection timeouts and per-query/statement timeouts)
- **Subprocess execution** (`subprocess.run`, `subprocess.Popen.communicate`)
- **Socket operations** (raw `socket`, message queues, gRPC, websockets)
- **File I/O on non-local paths** (network drives, mounted cloud storage, named pipes)
- **Inter-process communication** (multiprocessing queues, pipes, shared-memory waits)
- **Any SDK or library method that ultimately performs one of the above**, including wrappers layered over HTTP/DB clients

If the library does not accept a `timeout` argument, wrap the call using `concurrent.futures` with `timeout=`, `asyncio.wait_for`, or an equivalent mechanism that enforces a ceiling.

Timeouts must be **short enough to be meaningful for the use case** — typically seconds to a minute for interactive paths, minutes for batch. `timeout=None`, `timeout=0`, and values over one hour require an inline comment justifying the specific reason.

```python
response = httpx.get(url, timeout=10.0)                     # OK
result = subprocess.run(cmd, timeout=30, check=True)         # OK
rows = cursor.execute(query, timeout=5)                      # OK

# Wrapping a library that lacks timeout support
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
    future = ex.submit(legacy_client.fetch, url)
    data = future.result(timeout=15)
```

This rule extends Rule 2's bounded-execution guarantee across process boundaries. A program that obeys Rules 1, 2, 3, and 11 is guaranteed to make forward progress or fail loudly in bounded time.

---

## Consistency Summary

| Pair | Relationship |
|------|--------------|
| 1 + 2 | Together guarantee bounded stack and bounded iteration |
| 2 + 11 | Together guarantee bounded execution across process boundaries |
| 3 + 5 | Rule 3 is the specific form of Rule 5's precondition for collection growth |
| 4 + 5 | Rule 5's 5-line exemption prevents ceremony in trivial helpers |
| 5 + 10 | Rule 10's type system removes type checks from Rule 5's scope |
| 6 + 9 | Rule 9's intermediate variables live in the narrow scope Rule 6 requires |
| 7 + 5 | Caller-side and callee-side checks defend different boundaries |
| 8 + 10 | Metaprogramming defeats static analysis; banning it makes Rule 10 meaningful |

---

*Source: G.J. Holzmann, "The Power of Ten — Rules for Developing Safety Critical Code," NASA/JPL Laboratory for Reliable Software.*
