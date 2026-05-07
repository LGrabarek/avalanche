# Step 21 — User Review (Per-stage tick interval table, A2)

**What Step 21 covers:**
- `STAGE_TICK_INTERVALS` and `STAGE_AVALANCHE_TICK_INTERVALS` tables in `constants.py`.
- `GameManager` reads from these tables using `_stage_index` via two new private properties.
- Stage 1: normal 1.2 s, avalanche 0.15 s (unchanged).
- Stage 2: normal **0.9 s** (25% faster), avalanche **0.12 s** (20% faster).
- `WaveManager.reset_for_new_wave()` no longer resets the tick interval — decoupled from stage knowledge. Callers set it.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | Replaced `TICK_INTERVAL = 1.2` and `AVALANCHE_TICK_INTERVAL = 0.15` with `STAGE_TICK_INTERVALS = [1.2, 0.9]`, `STAGE_AVALANCHE_TICK_INTERVALS = [0.15, 0.12]`, and `TICK_SPEED_DECAY = 0.9`; kept aliases at index 0 for backward compat; updated turbo comment to reference tables |
| `wave_manager.py` | `reset_for_new_wave()` removed `self._tick_interval = TICK_INTERVAL`; updated docstring to state that caller sets the interval |
| `game_manager.py` | Removed `TICK_INTERVAL` + `AVALANCHE_TICK_INTERVAL` imports; added `STAGE_TICK_INTERVALS`, `STAGE_AVALANCHE_TICK_INTERVALS`, and `TICK_SPEED_DECAY` imports; added `_cur_tick_interval` (formula-based) + `_cur_avalanche_tick_interval` (table-based) private properties; updated 5 call sites: `_spawn_wave`, `_on_stage_complete`, `_trigger_avalanche`, `set_turbo`, `on_menu_open` |

No changes to `hud.py`, `main.py`, `wave_data.py`, `renderer.py`, or any other file.

---

## 2. Design details

### Tick tables and speed schedule

```python
STAGE_TICK_INTERVALS: list[float] = [1.2, 0.9]          # Stage 1 + Stage 2 hand-tuned
TICK_SPEED_DECAY: float = 0.9                            # 10 % faster on odd stages
STAGE_AVALANCHE_TICK_INTERVALS: list[float] = [0.15, 0.12]  # panic-mode cadence
```

Avalanche values must exceed `DT_CLAMP = 0.1 s` (see `WaveManager.update()` overshoot
assertion). Stage 2 avalanche (0.12 s) has a 20 ms margin — tighter than Stage 1 (50 ms)
but safe. Avalanche speed stays at 0.12 s for all stages beyond Stage 2.

### Speed schedule (normal tick)

| Stage | Index | Interval | vs. previous |
|---|---|---|---|
| 1 | 0 | 1.200 s | — |
| 2 | 1 | 0.900 s | −25% (hand-tuned) |
| 3 | 2 | 0.810 s | −10% ← speed step |
| 4 | 3 | 0.810 s | same |
| 5 | 4 | 0.729 s | −10% ← speed step |
| 6 | 5 | 0.729 s | same |
| 7 | 6 | 0.656 s | −10% ← speed step |
| … | … | … | pattern repeats |

### Formula (GameManager._cur_tick_interval)

```python
if i == 0:
    return STAGE_TICK_INTERVALS[0]          # Stage 1: 1.2 s
result = STAGE_TICK_INTERVALS[1] * (TICK_SPEED_DECAY ** (i // 2))  # Stage 2+
```

- `i // 2` equals 0 for Stage 2, 1 for Stages 3–4, 2 for Stages 5–6, etc.
- Odd stages get a new multiplier; even stages reuse the same exponent, holding speed steady.
- The assert `result > 0` acts as Rule-5 invariant (the formula can only reach zero via
  float underflow at astronomically large stage indices).

### Call site inventory

| Call site | Before | After |
|---|---|---|
| `_spawn_wave()` | `reset_for_new_wave()` set interval internally | Now sets `wave.tick_interval = _cur_tick_interval` after `reset_for_new_wave()` |
| `_on_stage_complete()` | `reset_for_new_wave()` set interval internally | Now sets `wave.tick_interval = _cur_tick_interval` after `reset_for_new_wave()` |
| `_trigger_avalanche()` | `AVALANCHE_TICK_INTERVAL` (Stage-1 only) | `_cur_avalanche_tick_interval` |
| `set_turbo(False)` | Restored to `TICK_INTERVAL` (Stage-1 only!) | Restores to `_cur_tick_interval` |
| `on_menu_open()` | Cleared turbo to `TICK_INTERVAL` (Stage-1 only!) | Clears turbo to `_cur_tick_interval` |

Note: `set_turbo(False)` and `on_menu_open()` were silently broken for Stage 2 before this step — they would have snapped back to 1.2 s instead of 0.9 s. Step 21 fixes that latent bug.

---

## 3. How to test

### 3a. Stage 1 unchanged

1. Run `bash run_dev.sh` → open `http://localhost:8000`.
2. Play Stage 1. The tick cadence should feel identical to before.
3. Hold **F** (turbo): cubes should visually speed up. Release: back to normal.
4. Press Esc while in turbo → Resume: normal speed resumes (not stuck at turbo).

### 3b. Stage 2 is noticeably faster

1. Clear all four Stage 1 waves to reach Stage 2.
2. On the Stage 2 Wave 1 spawn, the cubes should visibly advance faster (0.9 s vs 1.2 s — ~25% faster).
3. The difference should be felt as "meaningfully harder" rather than brutal or subtle.

### 3c. Turbo restores to Stage 2 speed

1. In Stage 2, hold **F** — cubes speed up.
2. Release **F** — cubes return to 0.9 s cadence (not 1.2 s Stage-1 speed).
3. (If you mistakenly see a slow-down to 1.2 s on turbo release, this would indicate the pre-Step-21 bug was not fixed.)

### 3d. Avalanche is faster in Stage 2

1. In Stage 2, let a cube reach your position to trigger an avalanche.
2. The avalanche (auto-advance) should feel slightly faster than in Stage 1 (0.12 s vs 0.15 s).

### 3e. Restart always returns to Stage 1 speed

1. Reach Stage 2, then:
   - Esc → Restart, OR
   - Let a cube crush you → game over → any key
2. Stage 1 Wave 1 cubes should advance at 1.2 s again.

### 3f. No regressions

- All Stage 1 mechanics (timing, scoring, captures, PERFECT! bonus, STAGE CLEAR overlay)
  behave identically to before.
- HUD, overlays, sound (none yet), menus — all unchanged.

---

## 4. Success criteria

- [ ] Stage 1 tick speed feels unchanged at 1.2 s.
- [ ] Stage 2 tick speed is noticeably faster (0.9 s).
- [ ] Turbo in Stage 2 releases back to 0.9 s (not 1.2 s).
- [ ] Stage 2 avalanche is faster than Stage 1 (0.12 s vs 0.15 s).
- [ ] Restart from any end-screen returns to Stage 1 speed.
- [ ] No crashes, assertion failures, or regressions in Stage 1 gameplay.

---

## 5. Expert panel findings (Step 21)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED | Turbo comment referenced stale fixed values (1.2 s, 0.15 s) instead of tables | Updated comment to reference `STAGE_TICK_INTERVALS[0]` and `STAGE_AVALANCHE_TICK_INTERVALS[0]` |
| Code Quality | CONCERNS → APPROVED | `_on_stage_complete` didn't immediately set `tick_interval` after `reset_for_new_wave()`, violating the docstring contract (safe but inconsistent) | Added `self._wave.tick_interval = self._cur_tick_interval` in `_on_stage_complete` |
| Code Quality | APPROVED | Stale Step 5A docstring referenced `AVALANCHE_TICK_INTERVAL` (removed constant) | Updated Step 5A bullet in module docstring |
| UX Tester | APPROVED | Turbo carryover at stage transition: safe because `_spawn_wave` always overwrites, but `_on_stage_complete` didn't explicitly clear it (same as Code Quality finding) | Fixed by same change above |
| UX Tester | APPROVED (advisory) | No HUD indicator of speed change — player discovers it empirically. Intentional: faithful to original I.Q. design. | No change; noted for future consideration |
| Platform Engineer | APPROVED | All 7 boundary checks clean: WASM assert safety, frozen-phase window, setter redundancy, empty-table guard, DT_CLAMP margin, restart path, turbo fix confirmation | No change needed |
| Platform Engineer | APPROVED | Note: `set_turbo(False)` would have returned to Stage-1 speed (bug) — Step 21 correctly fixed this latent issue | Confirmed as fix, not regression |

---

## 6. What to tell me after you review

- **"Step 21 approved, proceed"** — move on to Step 22 (bundled `.ttf` font, A3).
- **"Approved, plus this fix: [specific change]"** — apply and re-verify.
- **"Stage 2 too slow / too fast"** — adjust `STAGE_TICK_INTERVALS[1]` accordingly.
- **"Changes needed: [X, Y, Z]"** — address and re-run panel.
