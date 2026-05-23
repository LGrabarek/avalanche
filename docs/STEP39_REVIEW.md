# Step 39 Review — U2: Row Gained/Lost HUD Counter

**Status:** APPROVED 2026-05-19
**Date:** 2026-05-19

---

## What changed

### `effects.py`

| Addition | Detail |
|----------|--------|
| `ROW_DELTA_LIFETIME: float = 1.5` | Seconds before a label disappears. |
| `ROW_DELTA_FLOAT_SPEED: float = 40.0` | Pixels per second of vertical drift. |
| `ROW_DELTA_ANCHOR_Y: int = 120` | Initial screen-Y for freshly spawned labels (clears the HUD stat block which ends ~y=140). |
| `MAX_ROW_DELTA_EVENTS: int = 16` | Rule-3 cap on simultaneous labels. |
| `RowDeltaEvent` dataclass | `delta: int`, `elapsed: float`, `screen_y: float` fields; `alpha: float` computed property (`max(0.0, 1.0 − elapsed / lifetime)`). |
| `FlashEffects._row_deltas` | `list[RowDeltaEvent]` — live label set, bounded by `MAX_ROW_DELTA_EVENTS`. |
| `FlashEffects.row_deltas` property | Returns `tuple[RowDeltaEvent, ...]` — immutable snapshot for the renderer. |
| `FlashEffects.spawn_row_delta(delta)` | Asserts `delta in (1, -1)`; drops silently at cap; appends with post-condition assert. |
| `FlashEffects._update_row_deltas(dt)` | Advances `elapsed`; drifts `screen_y` (`−= delta × speed × dt`); evicts expired labels; post-condition asserts cap. |
| `FlashEffects.update(dt)` | Calls `_update_row_deltas(dt)` unconditionally — labels advance even when flash list is empty. |
| `FlashEffects.reset()` | `_row_deltas.clear()` + assert. |

**Float direction formula:**  
`ev.screen_y -= float(ev.delta) * ROW_DELTA_FLOAT_SPEED * dt`
- `delta = +1` (row gain): `screen_y` decreases → label floats **upward** ✓  
- `delta = -1` (row loss): `screen_y` increases → label floats **downward** ✓

---

### `game_manager.py`

Five call sites wired — all `delete_front_row()` and the one `restore_front_row()`:

| Call site | Event |
|-----------|-------|
| `_count_wave_misses` | Penalty-threshold row deletion |
| `_apply_avalanche_penalties` | Avalanche-penalty row deletion |
| `_execute_blast` ROW_DELETE | Forbidden blast → row deletion |
| `_dispatch_capture` ROW_DELETE | Forbidden capture → row deletion |
| `_on_wave_cleared` Perfect path | Row restoration → `spawn_row_delta(+1)` |

No `delete_front_row()` or `restore_front_row()` call site was missed.

---

### `main.py`

| Change | Detail |
|--------|--------|
| `from effects import MAX_ROW_DELTA_EVENTS as _MAX_ROW_DELTA_EVENTS` | Imported for the Rule-3 cap assert in `_draw_row_deltas`. |
| `_draw_row_deltas(screen, font, effects)` | New render function — see layout details below. |
| Render-loop call | `_draw_row_deltas(screen, font, effects)` placed at line 940, after `hud.draw()` and before any overlay — labels are covered by all overlay blits (WAVE_RISING, STAGE_CLEAR, GAME_OVER, etc.). |

**`_draw_row_deltas` design:**

- Labels: `"+1"` (green) for gains, `"-1"` (red) for losses — pure ASCII, no Unicode glyphs that may be absent in some FreeType builds.
- Fade: `surf.set_alpha(int(ev.alpha * 255))` — surface-level alpha fade keeps colour at full saturation while becoming transparent; avoids the opaque-black-ghost artefact of RGB-multiply approaches.
- Position: `surf.get_rect(right=SCREEN_WIDTH − 20, top=int(ev.screen_y))` — right-aligned 20 px from the screen edge, vertically tracked by `ev.screen_y`.

---

## Panel findings and fixes applied before approval

| Reviewer | Verdict | Finding | Resolution |
|----------|---------|---------|------------|
| Code Quality | APPROVED | No Rule violations; all 5 call sites covered; float direction and alpha math correct; Rule-3 caps complete. | No changes needed. |
| Pygbag/WASM | CONCERNS → fixed | **BLOCKER:** `▲`/`▼` (U+25B2/U+25BC, Geometric Shapes block) not reliably present in FreeSansBold FreeType builds; renders as tofu or blank under WASM. | Replaced `"+1 ▲"` / `"-1 ▼"` with `"+1"` / `"-1"` (ASCII). Fixed before approval. |
| Vision Lead | APPROVED | Placement at right edge (x=1260) is uncontested; green-up / red-down is intuitive; 60 px travel over 1.5 s is readable; initial stacking on simultaneous events is acceptable cosmetically. | No changes needed. |
| UX Tester | CONCERNS → fixed | **BLOCKER:** RGB-multiply fade (colour → black) produces an opaque black glyph as alpha approaches 0; visible against lighter overlays. | Switched to `surf.set_alpha(int(ev.alpha * 255))`. Fixed before approval. |

**Advisory notes (non-blocking, no action taken):**

- Simultaneous multi-row penalties (e.g., avalanche with 3 deletions) produce labels stacked at y=120 that drift downward together. They look like one label rather than three. The original I.Q. did not annotate multi-row avalanche penalties either; accepted.
- `ROW_DELTA_ANCHOR_Y = 120` is a constant tuned to clear the HUD stat block (bottom ≈ y=140). If a sixth HUD stat line is ever added, this constant will need a nudge.
- All overlays draw after `_draw_row_deltas` in the render loop; labels are naturally covered by any overlay veil.

---

## Visual layout

```
Screen: 1280 × 720

                                  +1     ← green, right-aligned at x=1260, y≈120→60 (floats up)
                                  -1     ← red,   right-aligned at x=1260, y≈120→180 (floats down)

HUD stat block (left-anchored):
  Score:    …
  Wave:     …
  Rows:     …
  IQ:       …
  Code:     …
```

No overlap between right-aligned delta labels and left-anchored HUD stats.

---

## How to test

### Row loss feedback

1. `python main.py` — start a wave.
2. Miss 5 cubes in a row (reaches PENALTY_THRESHOLD).
3. A red **-1** should appear at the top-right corner and drift downward, fading over ~1.5 s.

### Row gain feedback

1. Clear a wave without misses, forbidden captures, or avalanche penalties (Perfect wave).
2. A green **+1** should appear at the top-right corner and drift upward, fading over ~1.5 s.

### Multiple penalties

1. Miss 10 cubes in a single wave (triggers 2 penalty-threshold deletions).
2. Two red **-1** labels should appear (stacked at the same y position initially, drifting apart as they move).

### No labels during TITLE / HIGH_SCORE

1. Let the game reach TITLE or HIGH_SCORE screen — no labels should be visible (effects are reset on restart; no delta events fire outside gameplay phases).

### Labels covered by overlays

1. Trigger a Perfect wave clear — a green **+1** spawns.
2. The WAVE_RISING overlay immediately appears and covers the label area.
3. After the WAVE_RISING overlay clears, the label may still be visible if < 1.5 s have elapsed.

### Avalanche penalty during avalanche

1. Let the avalanche reach the front edge — AVALANCHE phase starts.
2. Miss cubes during avalanche to trigger `_apply_avalanche_penalties`.
3. Red **-1** labels should appear.

---

## Post-panel changes (approved in same session)

Four additional changes were approved alongside the panel fixes:

### 1. Permanent HUD row counter (`hud.py`)

A static `Rows: N` label is now drawn top-right, right-aligned 20 px from the screen edge at `y=10` — the same vertical position as the top-left stat block and the same horizontal anchor as the floating `+1`/`−1` delta labels. This gives the player a persistent readout so the animated deltas have an obvious reference value to move toward/away from.

- `HUD_ROW_COUNTER_RIGHT_MARGIN = 20` (mirrors `_draw_row_deltas` right margin)
- `MAX_HUD_CACHE_ENTRIES` bumped from 6 → 7 to accommodate the new "rows" cache slot
- `_draw_row_counter(screen, font)` uses the same `_render` cache helper as other stat lines
- `Hud.draw` calls `_draw_row_counter` after `_draw_stat_block` and `_draw_hint_line`

### 2. Wave-passes-through-wave crash-retry bug fix (`game_manager.py`)

**Root cause:** `_repack_pending_waves()` called `reset_for_new_wave()` (clears all cubes) then rebuilt pending cubes by iterating `self._waves` — which still contained already-cleared wave slots (`0..wave_index-1`). Those slots were rematerialised as pending cubes that occupied low-z positions; the newly activated wave sat at higher z and visually passed through them on the next advance.

**Fix:** Trim `_waves` and `_wave_mirrors` to `[wave_index:]` and reset `_wave_index = 0` before the repack loop:

```python
if self._wave_index > 0:
    self._waves = self._waves[self._wave_index:]
    self._wave_mirrors = self._wave_mirrors[self._wave_index:]
    self._wave_index = 0
```

Two post-trim asserts verify the slice is non-empty and that `waves`/`mirrors` remain in sync.

### 3. 1-second temporal stagger for simultaneous row delta events (`effects.py`)

When multiple row-loss or row-gain events fire in the same frame (e.g. an avalanche penalty deleting 2 rows), previously they all appeared at `y=120` simultaneously and looked like one label. Now each successive same-frame spawn is delayed by `ROW_DELTA_STAGGER = 1.0` seconds so they appear one at a time.

Mechanism: `_next_delta_delay` accumulates +1 s per spawn (capped at 4 s), decays by `dt` each frame. `spawn_row_delta` assigns `-_next_delta_delay` as the initial `elapsed`, so labels with `elapsed < 0` are invisible (`alpha = 0.0`) and do not drift. The `_update_row_deltas` drift branch is gated on `elapsed >= 0.0`.

### 4. "Rows gained" in STAGE_CLEAR stats overlay (`game_manager.py`, `main.py`)

`GameManager._stage_rows_gained` tracks how many rows were restored via Perfect clears in the current stage. It increments in the Perfect path of `_on_wave_cleared` and resets in `_on_stage_complete` and `_reset_state`. A `stage_rows_gained` property exposes it read-only.

The STAGE_CLEAR overlay (`_draw_stage_clear_overlay` in `main.py`) now shows a fifth stat row:

| Stat | Source |
|------|--------|
| Perfect waves | `_stage_perfect_waves` |
| IQ this stage | `_stage_iq_gain` |
| **Rows gained** | `_stage_rows_gained` (new) |
| Rows lost | `_stage_rows_lost` |
| Rows surviving | `surviving_rows` |

---

## Files changed

- `effects.py` (constants, `RowDeltaEvent`, `FlashEffects` additions + stagger mechanism)
- `game_manager.py` (5 `spawn_row_delta` call sites + crush-retry bug fix + `_stage_rows_gained` tracking)
- `hud.py` (`_draw_row_counter`, `MAX_HUD_CACHE_ENTRIES` bump)
- `main.py` (`_MAX_ROW_DELTA_EVENTS` import, `_draw_row_deltas`, render-loop call, "Rows gained" stat in stage-clear overlay)
