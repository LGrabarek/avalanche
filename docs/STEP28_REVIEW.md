# Step 28 — User Review (All waves visible + activation system)

**What Step 28 covers:**
- All stage waves are spawned at stage start as **static grey pending cubes** — visible
  during TITLE, WAVE_RISING, and gameplay screens.
- Pending cubes do NOT advance on tick, cannot be captured or crushed, and render
  uniformly in `PENDING_CUBE_COLOR = (90, 90, 90)`.
- **Activation**: when the WAVE_RISING timer expires, `_begin_wave()` flips the
  current wave's cubes from `pending=True` to `pending=False` — they begin advancing
  on the very next tick.
- `active_cube_count` (non-pending cubes) is used for wave-clear detection instead
  of `cube_count` (total).
- `GRID_DEPTH` was expanded from 25 → 40 to accommodate all wave rows.
  `PLAYER_SPAWN_Z` is now hardcoded to 21 (unchanged from before, just no longer
  derived from GRID_DEPTH).

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | `GRID_DEPTH` 25→40; `PLAYER_SPAWN_Z` hardcoded to 21; `WAVE_GAP_ROWS=2`; `PENDING_CUBE_COLOR=(90,90,90)` |
| `wave_data.py` | `spawn_positions(mirror, z_start=None)` — `z_start` overrides default back-wall placement |
| `wave_manager.py` | `Cube.pending: bool=False`; `spawn_cube(pending=False)`; `_advance_tick` skips pending; `iter_cubes` yields 5-tuple `(gx,gz,progress,cube_type,pending)`; `active_cube_count` property; `activate_pending(z_min, z_max)`; `cube_at`/`capturable_at`/`danger_cubes` skip pending |
| `game_manager.py` | New: `_wave_z_starts`, `_compute_wave_z_starts`, `_spawn_all_waves_pending`, `_activate_wave`, `_begin_wave`; `start_first_wave` calls `_spawn_all_waves_pending`; `update()` calls `_begin_wave`; `on_tick` uses `active_cube_count`; `_on_stage_complete` spawns pending for new stage |
| `main.py` | `_build_cube_faces` unpacks 5-tuple; pending cubes rendered in `PENDING_CUBE_COLOR` |

---

## 2. Wave layout geometry

All rows fully filled (7 cubes per row, no empty columns). No gap rows between waves.
Waves are packed at the **far end** of the grid (highest z values) and advance toward
the player. Stage depth = stage number: Stage 1 has 1 row per wave; Stage 2 has 2 rows.

### Stage 1 (1-row waves)

```
z=21  PLAYER_SPAWN_Z (player starts here)
z=22–35  empty (approach space)
z=36  Wave 0  ─  7 cubes — active when wave starts
z=37  Wave 1  ─  7 cubes — pending
z=38  Wave 2  ─  7 cubes — pending
z=39  Wave 3  ─  7 cubes — pending
```

### Stage 2 (2-row waves)

```
z=21  PLAYER_SPAWN_Z
z=22–31  empty
z=32  Wave 0 front row  ─┐  14 cubes — active when wave starts
z=33  Wave 0 back row   ─┘
z=34  Wave 1 front row  ─┐  14 cubes — pending
z=35  Wave 1 back row   ─┘
z=36  Wave 2 front row  ─┐  14 cubes — pending
z=37  Wave 2 back row   ─┘
z=38  Wave 3 front row  ─┐  14 cubes — pending
z=39  Wave 3 back row   ─┘
```

All positions fit within GRID_DEPTH=40 (valid range z=0..39).

---

## 3. How to test

### 3a. Pending cubes visible on title screen
1. Launch the game. Before pressing any key, look at the grid from the overview camera.
2. You should see **grey static cubes** in 4 bands across the far rows of the grid
   (roughly where z=22–35).
3. The grey cubes should be **perfectly still** — no tumble animation.

### 3b. Wave 0 activates on game start
1. Press any key to start (WAVE_RISING 2-second pause).
2. After the pause, wave 0's cubes (the front-most grey band) should **come to life**
   — they start tumbling toward the player in the normal cube colour (grey NORMAL,
   green ADVANTAGE, purple FORBIDDEN). The cubes behind them stay grey and static.

### 3c. Wave 1 activates after wave 0 clears
1. Clear wave 0 (capture or let all cubes fall off).
2. WAVE_RISING pause shows (2 seconds). The second band of grey cubes should be
   visible in the background.
3. After the pause, wave 1's cubes come to life and advance.

### 3d. Pending cubes block player movement
1. During WAVE_ACTIVE, try to move the player toward the back of the grid.
2. The player should be blocked at z=22 (wave 0 front row) — cannot walk into the
   pending/active cube rows.

### 3e. Restart resets pending cubes
1. Die (GAME OVER) and restart.
2. On the TITLE screen again, you should see all 4 grey wave bands, same as 3a.

### 3f. Stage 2 layout
1. Clear all Stage 1 waves → STAGE CLEAR screen → press key → Stage 2.
2. On WAVE_RISING for Stage 2's first wave, the title/overview should show Stage 2's
   pending cubes (similar layout, Wave 3 has 3 rows instead of 2).

---

## 4. Success criteria

- [ ] Grey pending cubes visible on TITLE screen — static, no animation
- [ ] Wave 0 activates (colour + motion) when WAVE_RISING expires
- [ ] Subsequent waves activate in order, with 2-second pause between each
- [ ] Pending cubes block player movement into the back rows
- [ ] Cleared wave's cubes disappear; pending cubes from remaining waves stay put
- [ ] Restart restores all pending cubes on the TITLE screen
- [ ] No visual glitches (pending cubes don't flicker or animate)

---

## 5. Expert panel findings

| Reviewer | Verdict | Findings |
|---|---|---|
| Code Quality | APPROVED | All 11 Power of Ten rules pass. `assert activated >= 0` in `activate_pending` is technically a no-op (counter only increments), but defense-in-depth is preserved by `_begin_wave`'s `active_cube_count > 0` postcondition assert. |
| Vision Lead | APPROVED | All frustum bounds verified numerically. Back-right corner of z=39 row subtends only 4° horizontally vs 35° half-angle — 30° margin, no clipping. NEAR_PLANE and FAR_PLANE both satisfied. Wave z-layout correct; Stage 2 max z=36 < 40. Stale `z=24`/`z=23` row comments updated to `row 0 (back)` / `row 1 (front)` and camera comment updated. |
| UX Tester | APPROVED | Static grey pending cubes readable vs blue-tinted platform tiles. 1-row gap (player z=21, wave front z=22) creates correct tension without instant death. 2-second WAVE_RISING gives sufficient time to register colour change on activation. Pending cube **edges** were initially leaking type info (red for FORBIDDEN); fixed by overriding edge to `(50,50,50)` for pending cubes in `_build_cube_faces`. |
| Platform Engineer | APPROVED | `active_cube_count` is a linear scan (37 cubes max in practice), called once per tick — negligible. `blocked_tiles` frozenset grows from ~7 to 37 elements, still O(1) per lookup. 5-tuple `iter_cubes` unpacked correctly. Pending-cube rendering adds ~180 extra face projections/frame (2× old count) — acceptable for 60fps WASM. Grid grows from 175→280 tiles; tile cache is a future optimisation if frame drops occur. |

---

## 6. What to tell me after you review

- **"Step 28 approved"** — pending cubes look and feel correct; proceed to Step 29.
- **"Grey cubes are hard to see"** — I'll adjust `PENDING_CUBE_COLOR` brightness.
- **"Grey cubes animate when they shouldn't"** — describe what you see; `progress=0.0`
  should prevent tumbling.
- **"Player can walk through pending cubes"** — report the z position; `blocked_tiles`
  includes pending cubes.
- **"Wrong cubes activate"** — describe which wave is wrong; I'll trace `_wave_z_starts`.
