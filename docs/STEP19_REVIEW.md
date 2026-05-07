# Step 19 — User Review (Grid Texture + Player Shadow + Danger Telegraph)

**What Step 19 covers (B3c + B3d + B3e):**
- **B3c** — PLATFORM tiles now alternate between two shades (checkerboard). Every tile where
  `(grid_x + grid_z) % 2 == 1` is lightened by `TILE_CHECKER_DELTA = 8` per channel.
  MARKED and ADVANTAGE_TRAP tiles are unaffected.
- **B3d** — A dark floor ellipse `(30, 30, 40)` is drawn beneath the player each frame,
  sized from the projected bounding box of the player's four footprint corners at `y = 0`.
  It renders above the grid tiles and below the player cube.
- **B3e** — Cubes one tick from the platform's front edge (`grid_z == front_edge_z + 1`)
  have their top face rendered in `DANGER_TOP_COLOR = (255, 220, 0)` (saturated yellow)
  as a visual countdown telegraph.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | Added `TILE_CHECKER_DELTA: int = 8`; `DANGER_TOP_COLOR: ColorRGB = (255, 220, 0)` |
| `cube_data.py` | `get_tile_face()` branches on parity to compute lightened `fill` for PLATFORM tiles |
| `wave_manager.py` | New `danger_cubes(front_edge_z)` method returning `frozenset[tuple[int,int]]` |
| `main.py` | Added `SHADOW_COLOR`; added `_draw_player_shadow()`; extended `_build_cube_faces()` with `danger` parameter; split render into 3 passes (grid+cubes+markers → shadow → player); updated HUD face count |

No wave data, scoring, input handling, or physics was changed.

---

## 2. Design details

### B3c — Checkerboard

```
PLATFORM base tile:     (90, 90, 110)
PLATFORM alt tile:      (98, 98, 118)     ← (grid_x + grid_z) % 2 == 1
MARKED:                 (200, 220, 255)   unchanged
ADVANTAGE_TRAP:         (80, 200, 80)     unchanged
```

The delta is deliberately conservative. If the pattern looks imperceptible in the browser,
`TILE_CHECKER_DELTA` can be raised to 12–14 without clashing with any other tile state.

### B3d — Player shadow

The shadow ellipse is sized from the projected bounding box of the 4 floor-level corners
of the player footprint (`±PLAYER_HALF_EXTENT = ±0.4` in each axis at `y = 0`). If any
corner is behind the camera near-plane, the shadow is silently skipped. The `(30, 30, 40)`
colour is ~40% darker than the tile base (~90 brightness), reading as ambient occlusion.

Render order (drawn on `scene_surf` each frame):
```
1. renderer.render_frame(scene_surf, face_list)      ← grid + cubes + markers
2. _draw_player_shadow(scene_surf, renderer, player) ← shadow on tiles
3. renderer.render_frame(scene_surf, player_faces)   ← player atop shadow
4. effects.draw(scene_surf, renderer)                ← flash particles on top
```

### B3e — Danger telegraph

`WaveManager.danger_cubes(front_edge_z)` returns a `frozenset[tuple[int, int]]` of
`(grid_x, grid_z)` pairs for cubes where `grid_z == front_edge_z + 1`. At the normal
`front_edge_z = 0`, this flags cubes in row 1 — one tick from the drop edge. The
`DANGER_TOP_COLOR = (255, 220, 0)` top-face override is applied to face index 0
(the `+Y` top face) in `_build_cube_faces`.

Color rationale: saturated yellow is orthogonal to all three cube base colours (grey,
green, dark purple) and to the player blue `(130, 200, 255)`, while matching the
`(255, 220, 50)` PERFECT! warning vocabulary in existing overlays.

---

## 3. How to test

### 3a. Checkerboard (B3c)
1. Run `bash run_dev.sh` → open `http://localhost:8000`.
2. Start a wave. Before any cubes advance, look at the grid.
3. You should see a subtle alternating light/dark tile pattern across the platform — a
   diagonal checkerboard (every other tile slightly brighter).
4. MARKED tiles (light blue) and ADVANTAGE_TRAP tiles (green) should show no checker effect.
5. If the checkerboard is invisible: bump `TILE_CHECKER_DELTA` from 8 → 12 in
   `constants.py` and re-test. If it looks too loud, 8 is correct.

### 3b. Player shadow (B3d)
1. Move the player around the grid.
2. A small dark ellipse should follow the player, sitting on the tile beneath the player cube.
3. The ellipse should be visible on both the dark and light checker tiles.
4. The player cube should appear **above** the shadow (shadow under the cube, not on top).
5. During AVALANCHE/crush (player cube squashes), the shadow should still appear at floor
   level — the crush visual only changes the player cube shape, not the shadow.

### 3c. Danger telegraph (B3e)
1. Let a wave advance until some cubes reach row 2 (the second row from the front edge).
2. The very next tick, those cubes will be in row 1. At that point their **top face should
   turn yellow** while all other faces remain normal.
3. On the tick after that, those cubes either drop off the edge (missed) or the player
   captures them. The yellow only lasts for one tick.
4. The yellow top face should appear on all cube types (Normal grey, Advantage green,
   Forbidden purple). Yellow contrasts clearly with all three.
5. At normal `TICK_INTERVAL = 1.2 s`, the yellow warning is visible for ~1.2 s —
   enough reaction time. In turbo mode (0.25 s), it is a "last call" indicator.

### 3d. No regressions
- Title screen, wave progression, pause menu, scoring all work as before.
- MARKED tile cone markers still show correctly.
- Face count in the HUD (debug display) should now show all faces including the player.

---

## 4. Success criteria

- [ ] Checkerboard pattern visible on the platform tiles (subtle alternating light/dark).
- [ ] MARKED and ADVANTAGE_TRAP tiles show **no** checker effect.
- [ ] Player shadow ellipse visible beneath the player cube, on top of the tile surface.
- [ ] Player cube draws on top of its own shadow.
- [ ] Cubes in row 1 (or `front_edge_z + 1`) have a yellow top face.
- [ ] Yellow top face disappears when the cube advances or is captured.
- [ ] Yellow top face visible on Normal, Advantage, and Forbidden cube types.
- [ ] No gameplay regression.

---

## 5. Expert panel findings (Step 19)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED (conditional) | `DANGER_TOP_COLOR = (255,255,255)` (white) sits too close in luminance to the player's blue top `(130,200,255)`, risking visual merge when a danger cube is directly in front of the player. Recommended saturated yellow `(255,220,0)` — orthogonal to all cube palettes and matches existing PERFECT! warning vocabulary. | Changed `DANGER_TOP_COLOR` from `(255,255,255)` → `(255,220,0)`. |
| UX Tester | APPROVED (conditional) | `TILE_CHECKER_DELTA = 8` sits at threshold of perceptibility during fast AVALANCHE ticks; recommend verifying visually before closing the step. One-tick warning horizon is correct as specified; two-tick worth revisiting in playtesting. | No code change; flagged for visual verification in review. |
| Code Quality | APPROVED | All Power of Ten rules satisfied; mypy --strict + ruff clean; assert/Rule-7/Rule-9 all correct. | No change needed. |
| Platform Engineer | APPROVED | Two render passes safe under WASM budget. `project_vertex` safe for `z = -0.4` (player at front edge). All-void grid (`front_edge_z = 25`) correctly returns empty frozenset. `len(face_list)` after in-place sort is correct. | No change needed. |

---

## 6. What to tell me after you review

- **"Step 19 approved, proceed"** — move on to Step 20 (Stage 2 waves, B5).
- **"Approved, plus this fix: [specific change]"** — apply and re-verify.
- **"Checker is invisible — bump the delta"** — I will raise `TILE_CHECKER_DELTA` to 12
  and re-run the panel.
- **"Changes needed: [X, Y, Z]"** — address and re-run panel.
