# Step 26 — User Review (Turbo freeze exploit fix)

**What Step 26 covers:**
- One-line fix to `wave_manager.py` `tick_interval.setter` that closes the turbo wave-freeze exploit.
- No new features, no new files, no API changes.

---

## 1. What changed

| File | Change |
|---|---|
| `wave_manager.py` | `tick_interval.setter`: clamp `_tick_elapsed` to `max(0.0, value - 1e-6)` instead of `0.0` when elapsed ≥ new interval |
| `docs/PLAN_V2.md` | New file: v2 roadmap, step tracker, deferred items inventory |

---

## 2. The bug

**Symptom:** Tapping F rapidly froze the wave. Cubes never advanced to the front edge while the player could move freely — no penalty was incurred regardless of how long the player took.

**Root cause:** When `tick_interval` changed (turbo on/off), the setter reset `_tick_elapsed = 0.0` whenever elapsed exceeded the new interval. Rapid F tapping triggered this reset on every tap, keeping the timer permanently near zero. The wave never fired a tick.

The reset was originally needed to prevent an overshoot assertion when the game transitions from normal speed (1.2 s) to avalanche speed (0.12 s) mid-tumble — `_tick_elapsed` could be ~0.33 s, which would exceed the new 0.12 s interval and trip the assert on the very next frame.

---

## 3. The fix

```python
# Old:
if self._tick_elapsed >= value:
    self._tick_elapsed = 0.0

# New:
if self._tick_elapsed >= value:
    self._tick_elapsed = max(0.0, value - 1e-6)
```

Instead of resetting to zero, clamp to `value - 1e-6`. On the very next `update(dt)` call (any `dt > 1e-6`, always true at 30+ FPS), the timer crosses the threshold and a tick fires immediately. Each turbo toggle fires a tick rather than restarting the countdown — the wave cannot be frozen.

**Overshoot safety:** Worst-case overshoot = `DT_CLAMP - 1e-6 ≈ 0.1 s`. Minimum tick interval = `AVALANCHE_TICK_INTERVAL = 0.12 s`. Assertion `overshoot < tick_interval` → `0.1 < 0.12` ✓. The assert in `update()` remains satisfied.

---

## 4. How to test

### 4a. Basic turbo still works
1. Start a game. Hold F — cubes should tick noticeably faster.
2. Release F — speed returns to normal.
3. Holding F during avalanche should have no effect (wave already at max speed).

### 4b. Freeze exploit is closed
1. Start a wave. Wait ~0.3 s (so `_tick_elapsed` is above 0.25 s).
2. Tap F rapidly (4–5 taps per second).
3. **Expected (fixed):** Cubes continue to advance. The wave cannot be frozen.
4. **Old behavior (should no longer occur):** Cubes restart their tumble animation from frame 0 on each tap; wave freezes indefinitely.

### 4c. Turbo at wave start
1. Press F immediately when a new wave spawns (elapsed ≈ 0).
2. Cubes should tick at turbo speed. No snap or animation glitch.

### 4d. No regression — normal gameplay
1. Play through a full wave without pressing F. Behaviour should be identical to v1.0.
2. Let avalanche trigger. The avalanche speed-up should work exactly as before.

---

## 5. Success criteria

- [ ] Holding F visibly accelerates the wave
- [ ] Releasing F returns the wave to normal speed
- [ ] Rapid F tapping no longer freezes the wave — cubes always advance
- [ ] No animation restart glitch on turbo toggle
- [ ] Normal gameplay (no F key) is unchanged from v1.0
- [ ] Avalanche speed-up is unchanged

---

## 6. Expert panel findings (Step 26)

| Reviewer | Verdict | Finding |
|---|---|---|
| Vision Lead | APPROVED | Fix is mechanically correct and exploit-closing; turbo now accelerates the wave as intended; consistent with I.Q. philosophy |
| Code Quality | APPROVED | `max(0.0, ...)` is defensive but correct; overshoot math verified; all Power of Ten rules pass; comment accurately documents both original intent and new behavior |
| UX Tester | APPROVED | Animation snap-forward is acceptable; hold-F feel preserved; exploit fully closed; no legitimate use case removed |
| Platform Engineer | APPROVED | IEEE 754 float precision identical on desktop and WASM; tick fires on next frame at any real framerate; no WASM compatibility issues; overshoot assertion math verified against actual constants |

---

## 7. What to tell me after you review

- **"Step 26 approved"** — fix is confirmed; we can merge v2 to master and push to GitHub Pages, or continue with more v2 features.
- **"F key still freezes"** — describe the exact tap cadence so I can investigate further.
- **"Turbo feels different"** — describe specifically what changed vs. v1.0.
