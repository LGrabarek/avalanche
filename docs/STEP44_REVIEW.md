# Step 44 Review — Wave Arrangement Variants + Grid-Depth Growth Fixes

**Status:** AWAITING USER APPROVAL
**Date:** 2026-05-21

---

## What changed

### Part A — Wave arrangement variants (original Step 44)

#### `wave_data.py`

| Change | Detail |
|--------|--------|
| `select_all_waves` docstring | Clarified that slot 0 is the "fixed anchor wave" not the "gentlest" wave (W0 contains FORBIDDEN from Stage 3 onward) |
| `select_all_waves` shuffle logic | Slot 0 (opener) always placed first; slots 1-3 shuffled with `rng.shuffle` before A/B variant selection. Deterministic: same RNG seed → same ordering. |

Before (pseudo-code):
```
for each stage: W0→W1→W2→W3 in fixed order, pick A or B per slot
```

After:
```
for each stage: W0 first (fixed), then shuffle [W1, W2, W3], pick A or B per slot
```

Variety: 3! = 6 orderings × 2^4 = 16 A/B combos = **96 possible sequences per stage**.

#### `game_manager.py` (Part A)

| Change | Detail |
|--------|--------|
| `_reload_remaining_waves` | Now derives pool keys from `_all_stage_waves[stage_index]` (the run's shuffled selection) instead of `STAGE_POOL_SLOTS` (fixed order). Pool key extracted as `wave_ref.code[:-1]` (e.g. `"S3W2A"` → `"S3W2"`). |

---

### Part B — Grid-depth growth bug fixes (post-Step-44 bug reports)

Three bugs were reported by the user after Step 44:
1. **Stage 5 width asymmetric**: void rows from penalties were receiving PLATFORM tiles in new columns when the grid widened.
2. **Perfect-wave row not appearing**: the new row at z=60+ was dead space — wave stack still packed from z=59.
3. **Waves not starting at back wall**: hardcoded `GRID_DEPTH-1=59` was used regardless of actual grid depth.

#### `grid_manager.py`

| Change | Detail |
|--------|--------|
| `set_active_width` void propagation | After copying existing columns, if the entire copied row is void (`all(... == TileState.VOID for x in range(copy_cols))`), the new columns beyond `old_width` are also set to VOID. Previously they defaulted to PLATFORM, creating asymmetric grid after stage widening. |

#### `game_manager.py` (Part B)

| Change | Detail |
|--------|--------|
| `_compute_wave_z_starts` back wall | Changed `z_back = GRID_DEPTH - 1` → `z_back = self._grid.depth - 1`. Waves now pack from the actual back wall, which may be 60, 61, 62… after Perfect-wave grid growth. |
| `_spawn_all_waves_pending` depth sync | Added `self._wave.grid_depth = self._grid.depth` before `_compute_wave_z_starts()` so WaveManager's range caps are correct at every stage/reload start. |
| `_repack_pending_waves` depth sync | Same sync added before the repack's `_compute_wave_z_starts()` call. |
| `_on_wave_cleared` defensive sync | Added `self._wave.grid_depth = self._grid.depth` immediately after `restore_front_row()` returns (Perfect branch) so the cap is updated the moment the grid grows — before any subsequent activate/remove call in the same phase. |

#### `wave_data.py`

| Change | Detail |
|--------|--------|
| `spawn_positions` z_start validation | Removed upper-bound cap `z_start < GRID_DEPTH`. Now only checks `z_start >= 0`. The live ceiling is enforced by `WaveManager.spawn_cube` via `self._grid_depth`. |

#### `wave_manager.py`

| Change | Detail |
|--------|--------|
| `_grid_depth: int` field | Added to `__init__`, defaults to `GRID_DEPTH`. Tracks authoritative grid depth. |
| `grid_depth` property + setter | Setter validates `value > 0`. Called by `GameManager` before any wave spawn/activate after grid depth changes. |
| `spawn_cube` range check | `GRID_DEPTH` → `self._grid_depth`. Cap assertion: `GRID_WIDTH * self._grid_depth`. |
| `spawn_debug_row` back row | `GRID_DEPTH - 1` → `self._grid_depth - 1`. |
| `_advance_tick` bound check | `GRID_DEPTH` → `self._grid_depth`. Cap assertion: `GRID_WIDTH * self._grid_depth`. |
| `activate_pending` range check | `GRID_DEPTH` → `self._grid_depth`. |
| `remove_pending_in_range` range check | `GRID_DEPTH` → `self._grid_depth`. |
| `MAX_ACTIVE_CUBES` comment | Updated to note this is used by `main.py` for the face-list cap (a conservative static ceiling), NOT the per-instance assertion cap (which is `GRID_WIDTH * self._grid_depth`). |

---

## Expert panel findings

### Part A (Wave arrangement variants)

| Reviewer | Verdict | Finding |
|----------|---------|---------|
| Vision Lead | APPROVED WITH CONCERNS (fixed) | "gentlest introduction" was inaccurate for Stages 3-10. Fixed to "fixed anchor wave." |
| Code Quality | APPROVED | All 10 rules satisfied. |
| UX Tester | APPROVED WITH CONCERNS (non-blocking) | Wave codes lose ordering signal; W-number soft difficulty expectation broken for experienced players. Neither blocks the feature. |
| Platform Engineer | APPROVED | `rng.shuffle` WASM-safe. All 80 wave codes validated. |

### Part B (Grid-depth growth fixes)

| Reviewer | Verdict | Finding |
|----------|---------|---------|
| Vision Lead | APPROVED WITH CONCERNS (fixed) | Void propagation correct; waves now pack from actual back wall. Defensive sync added to `_on_wave_cleared` per recommendation. |
| Code Quality | APPROVED WITH CONCERNS (fixed) | `spawn_debug_row` updated to use `self._grid_depth - 1`. `MAX_ACTIVE_CUBES` comment clarified. All Power-of-Ten rules satisfied; ruff + mypy --strict: zero errors. |
| UX Tester | APPROVED WITH CONCERNS (non-blocking) | Perfect reward is subtle visually but mechanically real. Void rows staying void on stage widening is correct I.Q. design intent. |
| Platform Engineer | APPROVED WITH CONCERNS (fixed) | All WASM-safe. `MAX_ACTIVE_CUBES` comment updated per recommendation. Sync timing analysis confirmed correct. |

---

## How to test

### Wave order varies between runs (Part A)
1. Start a new game and note the first three waves of Stage 1 (check the HUD wave code label, e.g. "S1W2A").
2. Reach game over or victory, then restart.
3. The wave order in Stage 1 should be different in at least some runs (not always W1→W2→W3 after the opener).
   - The opener (W0) should always appear first.
   - W1, W2, W3 may appear in any order after it.

### Opener always first (Part A)
1. Across multiple restarts, Stage 1's first active wave (after the stage intro) should always be an S1W0 variant (code "S1W0A" or "S1W0B").
2. Same for Stage 2 (S2W0A/B), Stage 3 (S3W0A/B), etc.

### Stage 5 width increase symmetric (Part B — Bug 1 fix)
1. Lose enough waves in Stages 1-4 to delete at least one front row (deliberately let 3 normal cubes fall off).
2. Progress to Stage 5 (grid should widen from 7→9 columns).
3. **Before the fix:** new columns 7-8 had PLATFORM tiles even in void rows — right half of grid appeared where left half was empty.
4. **After the fix:** void rows stay void across their full 9-column width. The widened grid is symmetric: if z=0 is void on columns 0-6, it is also void on columns 7-8.

### Perfect wave adds usable row at back (Part B — Bug 2/3 fix)
1. Achieve a Perfect wave on a full grid (no void rows, capture all Normal+Advantage, let all Forbidden pass, zero misses).
2. The "+1" floating row-delta label should appear.
3. On the next stage wave spawn, the wave stack should be pushed one row further from the player — the back of the pending grey cube stack should sit at z=60, not z=59.
4. Repeat for a second Perfect: wave stack back should now be at z=61.
5. The additional rows should be walkable (player can move onto them when no cubes are present).

### Waves start at actual back wall (Part B — Bug 3 fix)
1. Achieve at least one Perfect wave on a full grid to grow depth to 61.
2. At the next stage, the wave stack's rearmost grey column should be at the very back edge of the visible platform — no empty row gap between the wave and the back wall.
3. **Before the fix:** there was always an empty row at z=60 behind the wave stack after grid growth.
4. **After the fix:** no gap — the wave packs from z=60.

### Crush-retry respects the shuffled order (Part A)
1. Get crushed on any wave (deliberately walk into a cube).
2. The "AGAIN!" banner appears and the wave replays.
3. After clearing it, the *next* wave should be from the same shuffled sequence that was active before the crush.

---

## Files changed

- `wave_data.py` (`select_all_waves` — shuffle logic + docstring; `spawn_positions` — z_start cap removed)
- `game_manager.py` (`_reload_remaining_waves` — pool key derivation; `_compute_wave_z_starts` — live depth; `_spawn_all_waves_pending`, `_repack_pending_waves`, `_on_wave_cleared` — depth sync)
- `grid_manager.py` (`set_active_width` — void propagation)
- `wave_manager.py` (`_grid_depth` field, `grid_depth` property/setter, `spawn_cube`, `spawn_debug_row`, `_advance_tick`, `activate_pending`, `remove_pending_in_range` — GRID_DEPTH → self._grid_depth)
