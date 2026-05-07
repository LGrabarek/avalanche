# Step 27 — User Review (Player-following camera + zoom)

**What Step 27 covers:**
- The camera now follows the player cube during all gameplay phases, at the
  same isometric elevation angle (~29°) as before but significantly closer.
- TITLE, GAME_OVER, and VICTORY screens keep the fixed overview camera so the
  full grid is visible on non-gameplay screens.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | Added `CAMERA_FOLLOW_OFFSET = (0, 10, -18)` and `CAMERA_FOLLOW_FOV = 42.0` |
| `renderer.py` | Added `rebuild_vp(eye, target, fov)` method; `__init__` now stores `_aspect` and calls `rebuild_vp` instead of building the matrix inline |
| `player.py` | Added `world_pos` property returning `(grid_x+0.5, 0.0, grid_z+0.5)` |
| `main.py` | Added `_FOLLOW_CAMERA_PHASES` frozenset; per-frame camera update before face list construction |

---

## 2. How the camera works

**Geometry:**
- Camera offset from player tile centre: (0, +10, −18) world units
- Elevation angle: atan2(10, 18) ≈ 29° (matches the overview camera's 28°)
- Camera-to-player distance: ~20.6 units (was ~33 for the overview)
- FOV: 42° vertical (was 50°) — narrower at close range reduces distortion

**What you see:**
- Cubes spawn at z = 24–22 (back of grid), approaching toward z = 0
- With player at spawn (z = 21), camera sits at z = 3 looking toward z = 21
- Cubes at z = 24 are 21 units from the camera — clearly visible in the upper frame
- The approaching wave fills more of the screen than in v1.0

**Camera tracking:**
- Player moves left → world shifts right
- Player moves toward back (higher z) → world shifts toward camera
- Tracking is instantaneous (no smoothing) — each tile hop shifts the view

---

## 3. How to test

### 3a. Basic follow behaviour
1. Start a game. Notice the camera is closer and more intimate than v1.0.
2. Move the player left (A key) — the grid should visibly shift right.
3. Move right (D key) — grid shifts left.
4. Move backward (S key, toward front edge) — world shifts toward you.
5. The player cube should always appear near the screen centre.

### 3b. Front-edge visibility
1. With player at spawn (z = 21): the front-row tiles at z = 0–2 will NOT be visible — they are behind the camera. This is by design.
2. Retreat the player to z = 10 (S key seven times): z = 0 becomes visible — the camera is now at z = −8, looking toward z = 10.

### 3c. Approaching wave visibility
1. Let a wave start. The cubes at z = 24 should be visible in the upper portion of the screen.
2. As they tumble toward z = 0, they grow larger as they approach the camera.

### 3d. Overview camera on end screens
1. Trigger GAME OVER (let a cube crush you). The camera should snap to the full-grid overview (same as v1.0 TITLE camera).
2. Press any key to restart — camera should snap back to the follow camera when the first wave starts.

### 3e. Phase transitions
1. Pause (Esc) mid-wave — camera should hold still at the player's current position.
2. Clear a wave — camera should stay at the player's position during the WAVE_RISING banner.
3. Clear a stage — STAGE CLEAR overlay should appear with the follow camera (partial grid view).

---

## 4. Success criteria

- [ ] Player cube is always near the screen centre during gameplay
- [ ] World pans in the opposite direction to player movement
- [ ] Cubes approaching from z = 24 are clearly visible in the upper frame
- [ ] TITLE screen shows the full overview (no player-following)
- [ ] GAME OVER / VICTORY screens show the full overview
- [ ] Pause menu holds camera at player's position (no snap to overview)
- [ ] Camera is noticeably closer and more intimate than v1.0

---

## 5. Expert panel findings (Step 27)

| Reviewer | Verdict | Finding |
|---|---|---|
| Vision Lead | APPROVED | Geometry verified; 29° elevation correct; FOV 42° well-chosen; y=0.0 camera target is preferable to y=0.5 (preserves screen space for approaching cubes); phase set complete and correct |
| Code Quality | APPROVED | All Power of Ten rules pass; `rebuild_vp` Rule 5 check valid; `world_pos` Rule 5 exemption correct; `frozenset[GamePhase]` annotation correct for Python 3.9+; no ruff/mypy issues |
| UX Tester | CHANGES NEEDED (resolved) | (1) `ROW_COLLAPSING` removed from phase set (dead phase); (2) y=0.0 kept but docstring updated with rationale (Vision Lead approved); (3) z=−18 kept — geometry analysis showed −14 would worsen occlusion; (4+5) STAGE_CLEAR and MENU intent documented with inline comments |
| Platform Engineer | APPROVED | ~150 float ops/frame acceptable (<21% of existing poly-projection cost); `math.tan`/`math.sqrt` per frame not a concern; 16-element list allocation per frame within normal GC budget; no WASM compatibility issues |

---

## 6. What to tell me after you review

- **"Step 27 approved"** — camera feel is right; proceed to Step 28 (all waves visible).
- **"Camera feels too close"** — I'll increase `|CAMERA_FOLLOW_OFFSET.z|` from 18 toward 22–25.
- **"Camera feels too far"** — I'll reduce from 18 toward 14–16.
- **"FOV feels wrong"** — describe whether it feels too narrow/claustrophobic or too wide/fishy and I'll adjust `CAMERA_FOLLOW_FOV`.
- **"Player is off-centre"** — describe which direction and I'll tune the x/z offset.
