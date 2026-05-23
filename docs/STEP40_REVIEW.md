# Step 40 Review — V1: Platform Depth (Grid Table Walls)

**Status:** APPROVED 2026-05-20
**Date:** 2026-05-20

---

## What changed

### `constants.py`

| Addition | Detail |
|----------|--------|
| `TABLE_DEPTH: float = 8.0` | World units the walls hang below y=0. |
| `TABLE_SIDE_COLOR: ColorRGB = (40, 40, 55)` | Base colour for all wall faces — darker cool-blue than tile tops (90, 90, 110). |

### `cube_data.py`

New module-level constants:
- `_WALL_MULT_FRONT = 0.75`, `_WALL_MULT_LEFT = 0.65`, `_WALL_MULT_RIGHT = 0.50` — directional shading matching `FACE_MULTS` convention.
- `_shade(color, mult)` — trivial helper that applies a multiplier to a `ColorRGB`.

New function `get_table_edge_faces(grid_width, grid_depth, front_edge_z, table_depth=TABLE_DEPTH)`:

| Wall | Quads | Position | Winding | Colour |
|------|-------|----------|---------|--------|
| Front | `grid_width` | `z = front_edge_z − 0.5` | Matches cube back (-Z) face | `TABLE_SIDE_COLOR × 0.75` = (30, 30, 41) |
| Left | `grid_depth − front_edge_z` | `x = −0.5` | Matches cube +X face | `TABLE_SIDE_COLOR × 0.65` = (26, 26, 35) |
| Right | `grid_depth − front_edge_z` | `x = grid_width − 0.5` | Matches cube -X face | `TABLE_SIDE_COLOR × 0.50` = (20, 20, 27) |

Each quad spans `y ∈ [0, −TABLE_DEPTH]`. No edge outlines (`edge_color=None`).

Face count invariant: `len(faces) == grid_width + 2 × (grid_depth − front_edge_z)`, asserted at return.

### `renderer.py`

`FaceDescriptor` edge_color type widened from `ColorRGB` to `ColorRGB | None` — backward compatible (all existing faces always pass a `ColorRGB`; `None` now supported for wall faces which suppress `pygame.draw.aalines`).

### `main.py`

- Added `get_table_edge_faces` to `cube_data` imports.
- Added `ColorRGB` to `constants` imports (needed to annotate `eff_edge: ColorRGB | None` in `_build_cube_faces`).
- Added `_build_table_edge_faces(renderer, grid)` (~20 lines): projects raw wall quads via `renderer.project_face`, returns `list[ProjectedFace]`. Post-loop assert: `len(faces) <= max_wall_faces`.
- Inserted `face_list.extend(_build_table_edge_faces(renderer, grid))` as the first face-list call (before `_build_grid_faces`), so walls sort correctly with tiles and cubes.

---

## Dynamic behaviour

The **front wall** z-position is read from `grid.front_edge_z` every frame.  As penalty rows are deleted, `front_edge_z` advances toward higher z, and the front wall visually recedes — the platform erodes in sync with gameplay state.  The left and right walls also shrink (fewer row segments) as `front_edge_z` increases.

---

## Performance

| Stage | Initial wall faces | Worst-case wall faces |
|-------|-------------------|-----------------------|
| Stage 1 (7-wide) | 7 + 16 = 23 | 7 + 120 = 127 |
| Stage 10 (11-wide) | 11 + 56 = 67 | 11 + 120 = 131 |

~10–20% increase to face list count. Painter's-algorithm sort: ~5% additional overhead in worst case. Allocation profile: O(wall_faces) tuples per frame, no hidden cost.

---

## Panel findings

| Reviewer | Verdict | Finding |
|----------|---------|---------|
| Vision Lead | APPROVED | TABLE_DEPTH=8.0 is well-calibrated for the scale; dark void reinforces "suspended abyss" aesthetic from I.Q. source material; front wall recession on row deletion is a correct design touch. |
| Code Quality | APPROVED | All 10 Power-of-Ten rules satisfied; face count formula correct for all edge cases (`front_edge_z=0`, `front_edge_z=grid_depth-1`); `FaceDescriptor` type change is backward compatible. |
| UX Tester | APPROVED | Wall brightness (20–30) creates 3:1 contrast vs platform tiles (97); walls are visible at 21.8° camera elevation without dominating the frame; no distraction risk during gameplay. |
| Platform Engineer | APPROVED | No WASM-incompatible patterns; `pygame.draw.polygon` clips below-viewport vertices gracefully; sort overhead negligible; `_shade` called 3× per frame (not per-quad). |

No blockers. No advisory-only items.

---

## Post-panel fix (2026-05-20)

User testing confirmed the walls were completely invisible. Root-cause analysis:

**Back-face culling** — all three wall windings produced a negative 2D cross product
for the follow camera (eye at z≈27, looking at z≈46, right = (−1, 0, 0)).  The
analytical fix is to reverse every winding so the cross product is positive.

**Near-plane geometry** — the front wall at `fz = front_edge_z − 0.5 = −0.5` (game
start) is behind the camera; `project_vertex` correctly returns `None` for all its
vertices, so the face is safely suppressed until penalty rows push `front_edge_z`
into the frustum (≥ ~25 deleted rows).  This is expected behaviour.

**Viewport clipping** — left/right wall segments at gz < ~25 are behind the camera;
segments gz = 25–40 have their bottom vertices (y = −8) below the viewport but are
still partially visible because `pygame.draw.polygon` clips to screen bounds; segments
gz ≥ 40 are fully visible.  With the player at z ≈ 46 the camera always looks at
gz ≥ 40 territory, so the walls are visible throughout normal gameplay.

Changed in `cube_data.py` (windings reversed for all three faces):
- Front wall: `(x1, 0, fz), (x0, 0, fz), (x0, −d, fz), (x1, −d, fz)`
- Left wall: `(lx, 0, z1), (lx, 0, z0), (lx, −d, z0), (lx, −d, z1)`
- Right wall: `(rx, 0, z0), (rx, 0, z1), (rx, −d, z1), (rx, −d, z0)`

ruff and mypy --strict both pass with zero warnings.

---

## How to test

### Basic wall visibility

1. `python main.py` — start a game.
2. The grid platform should appear to have dark vertical walls below its three visible edges: front (facing camera), left, and right.
3. The walls should be visibly darker than the tile tops.

### Front wall recedes on row deletion

1. Miss cubes until the PENALTY_THRESHOLD is reached (3 misses) — a row is deleted.
2. The front wall's z-position should visibly shift backward one tile, matching the new front edge of the grid.
3. Repeat to confirm the wall tracks `front_edge_z` correctly.

### Stage transition (grid width change)

1. Complete stages to reach Stage 5 (9-wide) or Stage 9 (11-wide).
2. The side walls should correctly widen to match the new `grid.width`.

### No artifacts during STAGE_INTRO animation

1. At stage start, the rolling-wave animation rises cubes. Wall faces should remain stationary (they are not y-biased by `_intro_y_bias`).

### Overview camera (TITLE, GAME_OVER, VICTORY)

1. Let the game reach TITLE or GAME_OVER. The overview camera is used — walls may appear different (more foreshortened) or partially off-screen. No crash expected.

---

## Files changed

- `constants.py` (`TABLE_DEPTH`, `TABLE_SIDE_COLOR`)
- `cube_data.py` (`_WALL_MULT_*`, `_shade`, `get_table_edge_faces`)
- `renderer.py` (`FaceDescriptor` edge_color type widened)
- `main.py` (`_build_table_edge_faces`, `ColorRGB` import, face_list call, `eff_edge` annotation)
