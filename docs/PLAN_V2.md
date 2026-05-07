# Avalanche — v2 Plan

## Status: Step 26 (turbo freeze bug fix) — IN PROGRESS

v2 work lives on the `v2` branch. All changes are localhost-tested and panel-reviewed
before merging to `master` / deploying to GitHub Pages.

---

## Resumption notes

When starting a new v2 session:
1. Read `docs/PROGRESS.md` for the v1 history and the full step tracker (Steps 1–25).
2. Read **this file** for the v2 roadmap and the current step.
3. Check the v2 step tracker below, then read the corresponding spec section.
4. The review pipeline from `CLAUDE.md` hard rule 4 is mandatory for every step:
   self-test → expert panel → `docs/STEP<N>_REVIEW.md` → await user approval.
5. v2 branch policy: all work on `v2`; merge to `master` (and push to GitHub Pages)
   only when the user explicitly approves.

---

## v2 Step tracker

Step numbering continues from v1 (Steps 1–25).

| Step | ID  | Description                       | Phase A (Dev) | Phase B (Test) | Status      |
|------|-----|-----------------------------------|---------------|----------------|-------------|
| 26   | BF1 | Turbo freeze exploit fix          | IN PROGRESS   | NOT STARTED    | IN PROGRESS |

**Phase A values:** `NOT STARTED` → `IN PROGRESS` → `AWAITING USER`
**Phase B values:** `NOT STARTED` → `IN PROGRESS` → `APPROVED <date>`

---

## Outstanding deferred items (carry-forward from v1)

These were out-of-scope during v1 and are documented here for sequencing.

### OD1 — Stage 3+ wave data

**Status:** `STAGES` tuple in `game_manager.py` is bounded to 2 stages. After Stage 2
the game goes to VICTORY. Stage 3+ patterns need to be designed and tested against
the per-stage tick interval table.

**Files:** `wave_data.py`, `constants.py` (`STAGES`, `STAGE_TICK_INTERVALS`,
`IQ_DIFFICULTY_MULTIPLIERS`), `game_manager.py` (`_on_stage_complete`).

### OD2 — Lighthouse 100 PWA score

**Status:** A `screenshots` manifest entry is needed for a perfect Lighthouse score.
Requires a real screenshot taken after the game is deployed.

**Files:** `static/manifest.json`.

### OD3 — Custom domain

**Status:** Add a `CNAME` file to `static/` and configure GitHub Pages when desired.

### OD4 — Mobile / touchscreen controls

**Status:** Game is `orientation: landscape`, keyboard-only by design. On-screen
controls are not planned. Bluetooth keyboard on phone is supported.

---

## v2 Bug fixes

### BF1 — Turbo freeze exploit *(Step 26 — current)*

**Symptom:** Tapping F rapidly to advance cubes resets the tumble animation to its
starting frame on each tap. If done quickly enough, the wave can be frozen entirely:
the cubes never reach the front edge while the player is free to move without penalty.

**Root cause:** `wave_manager.py` `tick_interval.setter` (old lines 86-90):

```python
if self._tick_elapsed >= value:
    self._tick_elapsed = 0.0   # ← exploit: resets timer to zero on every tap
```

The reset was designed to prevent an overshoot assertion when the game transitions
from normal speed (1.2 s) to avalanche speed (0.12 s) mid-tumble — `_tick_elapsed`
could be ~0.33 s, which would exceed the new 0.12 s interval and trip the assert on
the very next frame.

**Exploit path:**
1. Player holds F → `tick_interval` drops to `TURBO_TICK_INTERVAL` (0.25 s).
2. If `_tick_elapsed > 0.25 s`, the setter resets it to 0.0 — the animation
   restarts from frame 0.
3. Player releases F → `tick_interval` rises back to `TICK_INTERVAL` (stage-
   dependent, e.g. 1.2 s). Because elapsed is 0.0, the new 1.2 s count restarts.
4. Player immediately taps F again when elapsed reaches 0.25 s → timer resets to 0
   again, animation restarts.
5. Repeat: the wave never advances because the timer never reaches any interval.

**Fix (applied in `wave_manager.py`):**

```python
# Old:
if self._tick_elapsed >= value:
    self._tick_elapsed = 0.0

# New:
if self._tick_elapsed >= value:
    self._tick_elapsed = max(0.0, value - 1e-6)
```

Instead of resetting to zero, clamp to `(value - 1e-6)`. On the very next
`update(dt)` call, `dt` (≥ a single frame ≈ 0.016 s) pushes elapsed past `value`,
a tick fires immediately. The wave can never be frozen — each turbo toggle fires a
tick rather than restarting the countdown.

**Overshoot safety:** Worst case overshoot = `DT_CLAMP - 1e-6 ≈ 0.1 s`, which is
less than `AVALANCHE_TICK_INTERVAL = 0.12 s`. The `update()` overshoot assert
(`elapsed - interval < DT_CLAMP`) remains satisfied for all reachable states.

**Animation note:** The user-visible effect changes: pressing F no longer restarts
the tumble animation from frame 0 — it fires a tick immediately (cubes snap to the
next position). This is correct UX: turbo should advance the wave, not reset it.

**Files changed:** `wave_manager.py` (setter comment + one-line fix).

---

## Session log

### Session 2026-05-06 — v2 branch created + Step 26 implemented

- v2 branch created from `v1.0` tag (post-audio, dev-overlay-removed).
- Codebase audit: no TODO/FIXME comments; `STAGES` bounded to 2; deferred items
  catalogued above.
- Turbo freeze bug analysed in full. Fix designed and applied to
  `wave_manager.py` `tick_interval.setter`.
- ruff + mypy --strict: clean.
- Expert panel review pending.
