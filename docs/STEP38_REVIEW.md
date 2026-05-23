# Step 38 Review — U1: Stage Clear Stats Screen

**Status:** APPROVED 2026-05-19
**Date:** 2026-05-19

---

## What changed

### `game_manager.py`

| Addition / Change | Detail |
|-------------------|--------|
| `_stage_rows_lost += 1` in `_execute_blast` ROW_DELETE | Completes coverage of all 4 `delete_front_row()` call sites. The other three (`_count_wave_misses`, `_apply_avalanche_penalties`, `_dispatch_capture`) were already tracked. |
| `_stage_perfect_waves += 1` in `_on_wave_cleared` | Incremented inside the `if is_perfect:` block, after the row restore, so the count only grows on clean, bonus-eligible clears. |
| `_stage_iq_gain = _calculate_final_iq() − _iq_at_stage_start` | Computed just before `self._phase = GamePhase.STAGE_CLEAR`. After `restore_front_row()` has already run, so the restored row is reflected in the gain. |
| `_on_stage_complete` — stage-stats reset block | After `_end_hold_elapsed = 0.0`: zeroes `_stage_perfect_waves`, `_stage_rows_lost`, `_stage_iq_gain`; snapshots `_score_at_stage_start = self._score` and `_iq_at_stage_start = self._calculate_final_iq()`. Called after `_stage_index += 1` so the baseline uses Stage N+1's multipliers, matching the multipliers used when Stage N+1's STAGE_CLEAR gain is computed. |
| `_reset_state` | Zeroes all five stage-stats fields: `_stage_perfect_waves`, `_stage_rows_lost`, `_score_at_stage_start`, `_iq_at_stage_start`, `_stage_iq_gain`. |
| `start_first_wave` | Appended `self._iq_at_stage_start = self._calculate_final_iq()` at the end, after grid is populated. At game start: score=0, grid=60 full rows → baseline ≈ 36 IQ (Stage-1 multipliers). |
| `_calculate_final_iq` refactor | Replaced the local `surviving_rows` loop with `self.surviving_rows * SCORE_ROW_SURVIVAL`. Reduces function from 18 to 11 non-blank non-comment lines; eliminates code duplication. |

**New properties (already declared earlier in the session):**

| Property | Returns |
|----------|---------|
| `surviving_rows: int` | Non-void row count; shared by IQ calc and stats overlay |
| `stage_perfect_waves: int` | `_stage_perfect_waves` |
| `stage_rows_lost: int` | `_stage_rows_lost` |
| `stage_iq_gain: int` | `_stage_iq_gain` |
| `stage_clear_hold_ready: bool` | `_end_hold_elapsed >= STAGE_CLEAR_HOLD (4.0 s)` |

**`STAGE_CLEAR_HOLD: float = 4.0`** (in `constants.py`) — longer than `END_SCREEN_HOLD (2.0 s)` to give the player time to read the stats panel.

### `main.py`

| Change | Detail |
|--------|--------|
| `_draw_stage_clear_overlay` redesigned | New signature: `(screen, big_font, small_font, game, hold_ready)`. Renders: dark veil (alpha=210), "STAGE N CLEAR" title in green (big_font=64 px), 4-row stats table (labels right-aligned to `cx−20`, values left-aligned from `cx+20`), centered score line, "Next: Stage N" footer, and hold-gated "Press any key to continue" prompt. |
| IQ gain format | `f"{iq_gain:+,}"` — Python's sign-aware format: renders `+30` for positive, `-5` for negative, `+0` for zero. Avoids the broken `+-5` output the literal-`+` approach would produce for negative gains. |
| "Rows lost" color | `(220, 80, 80)` red if > 0; `(100, 220, 100)` green if 0 — traffic-light signal for stage performance. |
| Render dispatch | `_draw_stage_clear_overlay(screen, overlay_font, font, game, game.stage_clear_hold_ready)` — passes `overlay_font` for the title and uses `stage_clear_hold_ready` (not the old `end_hold_ready`). |

---

## Stats panel layout (SCREEN: 1280 × 720)

```
                    STAGE 1 CLEAR            ← big_font (64px), green, top=144
                                             ← gap: ~20 px

  Perfect waves          3 / 4              ← small_font (28px), white
  IQ this stage         +63                 ← light blue
  Rows lost               2                 ← red (or green if 0)
  Rows surviving         58                 ← white

                    Score: 45,000           ← centered, white

                    Next: Stage 2           ← footer, bottom=664
               Press any key to continue    ← dimmed → bright at 4 s, bottom=692
```

No vertical overlap. Score-to-footer gap ≈ 200 px (comfortable white space).

---

## IQ gain math

- **Stage 1 baseline** (at game start): `(0 + 60×1000) × 1.0 × 0.0006 = 36`.
- **Stage 1 gain** (example, score=50 000, rows=60): `(50000+60000)×1.0×0.0006 − 36 = 66−36 = 30`.
- **Stage N multipliers** — `_iq_at_stage_start` and `_calculate_final_iq()` at STAGE_CLEAR both use `_stage_index = N` (the same index), so the gain is internally consistent. A negative gain is possible if many rows are lost on the last wave; it is formatted as e.g. `−5` by the `{:+,}` specifier.

---

## Expert panel summary

| Reviewer | Verdict | Key findings |
|----------|---------|-------------|
| Code Quality | CONCERNS → APPROVED after verification | F2 (multiplier mismatch bug) and two Rule 4 violations were false positives: actual non-blank non-comment line counts are 48 for both `_on_wave_cleared` and `_draw_stage_clear_overlay` (both within the 50-line limit); multiplier consistency verified by unit test. Non-blocking note: `_score_at_stage_start` is set but not currently exposed (reserved for future per-stage score display). |
| Pygbag/WASM Specialist | APPROVED | All code is pure pygame/Python with no new C extensions or file I/O. `SRCALPHA` veil pattern is established by existing overlays. `{:,}` integer formatting is safe in WASM CPython. `surviving_rows` (660 calls max per frame) is negligible in the frozen STAGE_CLEAR phase. |
| Vision Lead | APPROVED | Layout fits cleanly within 1280×720 with no overlap. Alpha=210 veil correctly positions the screen in the overlay hierarchy (darker than title, lighter than name entry). Two-column label/value alignment reads as a deliberate stats table. Color choices are clear and consistent with existing overlays. "STAGE 10 CLEAR" at 64 px is ~532 px wide — no clip risk on a 1280 px canvas. |
| UX Tester | CONCERNS → APPROVED after fix | **Mandatory fix:** `f"+{iq_gain:,}"` → `f"{iq_gain:+,}"` to avoid `+-5` output for negative gains (fixed before the review result arrived). Advisory: dim prompt at `(50, 50, 55)` is nearly invisible before hold; consider `(90, 90, 95)` for first-time players (kept at `(50, 50, 55)` for consistency with GAME_OVER/VICTORY overlays). Advisory: `play_wave_clear()` fires in both `_on_wave_cleared` and `_on_stage_complete` — pre-existing behavior, not introduced by Step 38. |

All blockers resolved before panel results returned.

---

## How to test

### Basic stats display

1. `python main.py` — play Stage 1 until STAGE CLEAR.
2. Stats panel should appear showing:
   - **"Perfect waves N / 4"** — count of waves where no avalanche, no forbidden, no misses.
   - **"IQ this stage +N"** — positive when the player scored; `−N` if rows were heavily lost.
   - **"Rows lost N"** — red if any rows lost; green if 0.
   - **"Rows surviving N"** — should be ≤ 60 (GRID_DEPTH).
   - **"Score: N,NNN"** — cumulative running total.
3. "Press any key to continue" is near-invisible for the first 4 seconds; brightens at 4 s.
4. Press any key after 4 s → Stage 2 begins.

### Perfect stage

1. Clear all 4 waves of Stage 1 with no avalanche, no forbidden, no misses.
2. Stats should show: "Perfect waves  4 / 4", "Rows lost  0" (green).

### Rows lost tracking

1. Miss 5 cubes in the same wave (triggers 1 row deletion at PENALTY_THRESHOLD=5).
2. Capture a Forbidden cube (1 row deletion).
3. Stats at stage clear: "Rows lost  2".

### Negative IQ gain (edge case)

1. Reach Stage 2 (or later) with a high baseline IQ.
2. On the final wave, intentionally miss many cubes to lose 10+ rows.
3. Stats should show "IQ this stage  −N" (with a minus sign, not `+-N`).

### Hold gate

1. Reach STAGE_CLEAR. Immediately press any key — should NOT advance (hold not elapsed).
2. Wait 4 seconds. The prompt brightens.
3. Press any key — advances to next stage.

### Non-final stage only

1. Reach the final stage and clear it — goes to VICTORY (no stats panel, no hold).

---

## Files changed

- `game_manager.py` (`_execute_blast` ROW_DELETE, `_on_wave_cleared`, `_on_stage_complete`, `_reset_state`, `start_first_wave`, `_calculate_final_iq`)
- `main.py` (`_draw_stage_clear_overlay`, render dispatch)
- `constants.py` — `STAGE_CLEAR_HOLD` already added earlier in the session
