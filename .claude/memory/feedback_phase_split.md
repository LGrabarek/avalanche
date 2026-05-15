---
name: Steps 3+ split into Phase A (Dev) and Phase B (Test)
description: Each implementation step from Step 3 onward is explicitly broken into a development phase and a testing phase so work can be paused between them
type: feedback
---

Steps 3 through 11 in `docs/PLAN.md` are split into two phases. A step is only complete once both phases pass.

- **Phase A — Development.** All work that doesn't need the user: implement the code, run `ruff check .` + `mypy --strict`, run desktop self-tests, invoke the 4-agent expert panel, resolve CONCERNS, write `docs/STEP<N>_REVIEW.md`, update `PROGRESS.md`. Ends with "awaiting user verification."
- **Phase B — Testing.** User runs the browser per STEP<N>_REVIEW.md and reports. I apply fixes (re-running ruff/mypy/self-test/panel as needed) and flip the tracker to `APPROVED <date>` once the user says "approved."

**Why:** user needs clean pause points when waiting for Claude usage limits to refresh. A single-block step that bundles dev + panel + user review was awkward to resume mid-stream. Phase A → Phase B gives two natural, resumable checkpoints per step, both easily restartable from `PROGRESS.md` + the current `STEP<N>_REVIEW.md`.

**How to apply:** when starting a step, announce which phase you're entering. Within Phase A, proceed through all the non-user work sequentially and stop at "awaiting user verification." Do not ask the user for anything mid-Phase-A unless genuinely blocked. Within Phase B, wait for user report; do not pre-emptively start the next step's Phase A until the user approves. The `PROGRESS.md` step-tracker columns `Phase A (Dev)` and `Phase B (Test)` reflect progress explicitly — update them as phases transition.
