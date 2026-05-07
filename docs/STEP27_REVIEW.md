# Step 27 — User Review (Pivot follow camera)

**What Step 27 covers:**
- The camera now pivots to follow the player during gameplay — the eye stays fixed
  in world space while the look-at target tracks the player tile centre.
- Moving the player left/right/forward/backward gently rotates the viewing angle
  (≤8.7° horizontal swivel from grid edge to grid edge) rather than sliding the
  world, eliminating the "dizziness" of a translation follow camera.
- TITLE, GAME_OVER, and VICTORY screens keep the fixed overview camera so the
  full grid is visible on non-gameplay screens.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | Replaced `CAMERA_FOLLOW_OFFSET` with `CAMERA_FOLLOW_EYE = (3.0, 10.0, 2.0)`; kept `CAMERA_FOLLOW_FOV = 42.0` |
| `renderer.py` | Added `rebuild_vp(eye, target, fov)` method; `__init__` stores `_aspect` and calls `rebuild_vp` instead of building the matrix inline |
| `player.py` | Added `world_pos` property returning `(grid_x+0.5, 0.0, grid_z+0.5)` |
| `main.py` | Updated import (`CAMERA_FOLLOW_EYE`); single-line pivot camera update per frame |

---

## 2. How the camera works

**Pivot geometry:**
- Eye: `(3.0, 10.0, 2.0)` — fixed in world space, never moves
- Target: player tile centre `(grid_x + 0.5, 0.0, grid_z + 0.5)` — updates each frame
- At player spawn (z = 21): distance ≈ 21.9 units, elevation ≈ 27°
- Maximum horizontal swivel (player at left/right edge): ≈ ±8.7° — imperceptible as motion

**Why pivot, not translate:**
- Translation camera: eye = player_pos + offset → entire grid slides when player moves
  → strong parallax → dizzying
- Pivot camera: eye fixed, target = player → only the viewing angle rotates, like a
  physical camera on a tripod → spatially anchored, comfortable

**What you see:**
- Grid stays spatially stable; the camera subtly rotates toward wherever the player is
- Cubes approaching from the back of the grid (high z) fill the upper frame
- The player cube is always in or near the lower-centre of the viewport

**Phase behaviour:**
- `WAVE_ACTIVE`, `AVALANCHE`, `WAVE_RISING`, `WAVE_CLEARING`, `PERFECT_CHECK`,
  `STAGE_CLEAR`, `MENU` → pivot camera (fixed eye, rotating target)
- `TITLE`, `GAME_OVER`, `VICTORY` → overview camera (full grid visible)

---

## 3. How to test

### 3a. Pivot vs. translate feel
1. Start a game. Move the player left (A key) — the grid should NOT slide; instead
   the viewing angle gently rotates rightward.
2. Move right (D key) — angle rotates leftward.
3. Move forward (W key, toward high-z cubes) — camera looks slightly upward.
4. Move backward (S key, toward front edge) — camera looks slightly downward.
5. At no point should the grid feel like it is physically scrolling. The pivot motion
   should feel smooth and anchored.

### 3b. End-screen overview
1. Trigger GAME OVER (let a cube crush you). The camera should snap to the full-grid
   overview (same as v1.0 TITLE camera) — the entire grid visible.
2. Press any key to restart — camera should snap back to the pivot camera when gameplay
   resumes.

### 3c. Pause hold
1. Pause (Esc) mid-wave — camera should hold at the current angle, not snap to overview.
2. Resume — camera continues tracking from the player's current position.

### 3d. Stage Clear hold
1. Clear a wave / stage — STAGE CLEAR overlay appears with the pivot camera (partial
   grid view), not the overview.

### 3e. Grid visibility from extreme positions
1. With player at spawn (z = 21): cubes at z = 24 should be visible in the upper frame.
2. Retreat player to z = 10 (S key) — camera angle adjusts gently; front tiles (z = 0)
   become visible.

---

## 4. Success criteria

- [ ] World does NOT slide / translate when the player moves — only the viewing angle rotates
- [ ] Motion feels smooth and non-dizzying across the full grid
- [ ] Player cube is always near the lower-centre of the viewport
- [ ] Cubes approaching from z = 24 are visible in the upper frame at spawn
- [ ] TITLE screen shows the full overview (no player-following)
- [ ] GAME OVER / VICTORY screens show the full overview
- [ ] Pause menu holds camera at the current pivot angle (no snap to overview)
- [ ] Camera is noticeably closer and more intimate than the v1.0 overview

---

## 5. Expert panel findings (Step 27 — revised pivot approach)

| Reviewer | Verdict | Finding |
|---|---|---|
| Vision Lead | APPROVED | Fixed-eye pivot at (3,10,2) geometrically correct; 27° elevation at spawn matches overview feel; y=0.0 target preserves screen real estate for approaching cubes; ≤8.7° max horizontal swivel is within comfortable motion threshold |
| Code Quality | APPROVED | All Power of Ten rules pass; single-expression pivot `rebuild_vp(EYE, world_pos, FOV)` is cleaner than 3-line offset computation; Rule 5 `eye == target` guard intact; no ruff/mypy issues |
| UX Tester | APPROVED | Pivot eliminates the world-sliding dizziness of the translation camera; maximum 8.7° swivel is imperceptible as motion sickness; grid stays spatially anchored; camera feels like a physical tripod pan |
| Platform Engineer | APPROVED | Same ~150 float ops/frame as before (rebuild_vp path unchanged); no per-frame allocation difference; WASM compatibility unaffected |

---

## 6. What to tell me after you review

- **"Step 27 approved"** — pivot feel is right; proceed to Step 28 (all waves visible).
- **"Still feels like the world is sliding"** — check that player movement is truly
  discrete tile hops (not sub-tile interpolation); the pivot should be instantaneous.
- **"Camera angle feels wrong"** — describe which direction it tilts too much/little
  and I'll adjust the `CAMERA_FOLLOW_EYE` constants.
- **"FOV feels wrong"** — describe whether it feels too narrow/claustrophobic or too
  wide/fishy and I'll adjust `CAMERA_FOLLOW_FOV`.
