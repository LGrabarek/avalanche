# Step 45 Review — Row Animations, Camera Zoom, Wave-Tracking Camera

**Status:** AWAITING USER
**Date:** 2026-05-22

---

## What changed

### `constants.py`

| Constant | Value | Purpose |
|----------|-------|---------|
| `CAM_ZOOM_OUT` | 1.80 | Camera pulls back 80% along viewing ray during row events (front edge fully visible) |
| `CAM_ZOOM_SPEED_OUT` | 7.0 s⁻¹ | Snappy departure (half-life ~99 ms) |
| `CAM_ZOOM_SPEED_IN` | 2.2 s⁻¹ | Gradual return (~1.4 s to 95%) |
| `CRUMBLE_PRE_ZOOM_DELAY` | 0.50 s | Camera settle time — tiles are invisible while the camera zooms out |
| `ROW_CRUMBLE_DURATION` | 0.55 s | Per-tile fade duration |
| `ROW_CRUMBLE_STAGGER` | 1.00 s | Delay between successive rows in a multi-row crumble (dramatic one-at-a-time) |
| `MAX_CRUMBLE_TILES` | 176 | Rule-3 cap (16 rows × max width 11) |
| `ROW_ARRIVAL_DURATION` | 0.90 s | Arrival highlight fade duration |
| `MAX_ARRIVAL_TILES` | 11 | Rule-3 cap (one row at a time, max width 11) |

### `player.py` — restored to Step 43 single-tile movement

- Internal state uses `_grid_x` / `_grid_z` (integer tile indices). No sub-grid.
- `_prev_grid_x` / `_prev_grid_z` saved on every move, reset, and position-clamp call.
- `grid_x` / `grid_z` return `_grid_x` / `_grid_z` directly.
- `world_pos` — `(self._grid_x + 0.5, 0.0, self._grid_z + 0.5)`.
- `vis_world_pos` — smooth-step interpolation from `_prev_grid_*` to `_grid_*` over `MOVE_COOLDOWN`.
- `try_move` — full-tile steps (±1 on the tile grid); blocking checked directly.
- No `at_tile_centre` property.
- All rendering call sites use `vis_world_pos`; all game-logic call sites use `grid_x/z`.

### `effects.py`

- `_CrumbleTile` and `_ArrivalTile` dataclasses (grid_x, grid_z, elapsed, duration).
- `spawn_row_crumbles(z_rows, grid_width)` — takes rows sorted back-to-front; tiles start with
  `elapsed = -(CRUMBLE_PRE_ZOOM_DELAY + row_idx * ROW_CRUMBLE_STAGGER)`.
- `spawn_row_arrival(gz, grid_width)` — tiles start with `elapsed = -CRUMBLE_PRE_ZOOM_DELAY`.
- `iter_crumble_tiles()`, `iter_arrival_tiles()` — yield `(x, z, progress)` only for tiles
  with `elapsed >= 0` (both guards in place).
- `has_active_row_anim` — True while either list is non-empty (including tiles in pre-zoom delay,
  so the camera zooms out before the first tile becomes visible).
- `_update_row_anims(dt)` — advances timers; evicts tiles with `elapsed >= duration`.
- `reset()` — clears both lists.

### `game_manager.py`

- All `delete_front_row()` call sites notify effects: `spawn_row_crumbles([crumble_z], grid.width)`.
- `restore_front_row()` call site notifies effects: `spawn_row_arrival(arrival_z, grid.width)`.

### `main.py`

- `_build_crumble_faces(renderer, effects)` — fades PLATFORM → black per tile over crumble
  duration; cap assertion uses `_MAX_CRUMBLE_TILES`.
- `_build_arrival_faces(renderer, effects)` — warm-gold → platform colour; cap assertion uses
  `_MAX_ARRIVAL_TILES`.
- Both inserted into `face_list` after `_build_grid_faces`, before `_build_cube_faces`.
- Camera follow target:
  ```
  wave_target_z = float(game.wave_front_z) + 0.5 - wave.tick_progress
  ```
  Between ticks `wave.tick_progress` interpolates 0→1 so the camera tracks the
  visually-tumbling front row continuously, not just at integer tick boundaries.
  After a tick fires, `wave_front_z` decreases by 1 and `tick_progress` resets to 0 —
  giving continuity: `(front − 1) + 0.5 = front − 0.5`. ✓
- Camera zoom: per-frame exponential lerp toward `CAM_ZOOM_OUT` while `effects.has_active_row_anim`,
  otherwise toward 1.0.
- Marking uses `player.grid_x` / `player.grid_z` directly — no `at_tile_centre` gate.

---

## Self-tests

18 tests, 104 checks — all pass:
```
RESULT: all 104 checks passed (OK)
```

Covers: crumble spawn/iter/stagger/expiry/cap (pre-zoom delay timing), arrival
spawn/iter/expiry/cap (pre-zoom delay timing), `has_active_row_anim` lifecycle,
player `vis_world_pos` at rest and mid-move (single-tile grid attribute names),
`_smooth_step` range, camera zoom constants and convergence, reset behaviour.

---

## How to test (browser)

### Player movement — tile-snapped
1. Start a game; move the player (arrow keys / WASD).
2. Each key press moves one full tile; hold SPACE (mark) at any position — blue mark
   should appear on the tile underfoot.
3. The character should visually glide smoothly between tile centres.

### Row crumble animation — 1-second stagger
1. Deliberately let multiple normal cubes fall off the front edge across the same wave.
2. When the wave clears, the camera should visibly zoom out (80% pull-back), pause for
   ~0.5 s, then the deleted row(s) should fade grey → black.
3. If more than one row was deleted, the rows should crumble one at a time with a clear
   ~1-second gap between each fade — not a quick ripple.

### Camera follows wave front
1. Start a game and watch the camera during WAVE_ACTIVE.
2. The camera should follow the frontmost row of cubes as they tumble forward in real time
   — not jump discretely at each tick boundary.
3. When standing still, the camera should track the wave, not the player.
4. After a wave clears and crumbles, the camera should hold its position through the
   crumble animation, then slowly drift back once animations finish.

### Camera zoom timing
1. Trigger any row deletion.
2. The camera zoom-out should complete snappily (within ~1 frame).
3. The 0.5 s pre-zoom delay should be noticeable — there is a pause before the fade begins.
4. After all animations complete, the camera should slowly drift back over ~1.5 s.

### Row arrival animation (Perfect clear)
1. Achieve a Perfect clear: capture all Normal and Advantage cubes, let all Forbidden pass.
2. During the WAVE_RISING pause, the new back row should glow warm-gold and fade to normal
   over ~0.90 s, preceded by the same ~0.5 s camera-settle delay.

---

## Files changed

- `constants.py` (9 constants updated/added)
- `player.py` (restored Step 43 single-tile grid; `_grid_x/z`, `vis_world_pos`, `try_move`)
- `effects.py` (pre-zoom delay applied to both spawn functions; arrival iter guard added)
- `game_manager.py` (all `delete_front_row`/`restore_front_row` call sites notify effects)
- `main.py` (wave-tracking camera with `tick_progress`; crumble/arrival face builders wired)
- `_test_step45.py` (18 tests, 104 checks — updated for single-tile player attributes)
