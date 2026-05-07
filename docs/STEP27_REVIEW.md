# Step 27 — User Review (Smooth pivot follow camera)

**What Step 27 covers:**
- The camera pivots to follow the player during gameplay from a **fixed** world-space
  eye position — no translation, no world-sliding.
- The look-at target **smoothly lerps** toward the player's floor tile via exponential
  decay, turning discrete 1-tile hops into a continuous camera glide.
- The eye is positioned **behind** the front edge of the grid (z = −2) so the camera
  always looks in the +z direction regardless of player position, keeping A/D correctly
  mapped to screen-left/right at all player z values.
- TITLE, GAME_OVER, and VICTORY screens keep the fixed overview camera.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | `CAMERA_FOLLOW_EYE = (3.0, 12.0, −2.0)`; `CAMERA_FOLLOW_FOV = 42.0`; added `CAMERA_FOLLOW_SMOOTH = 5.0` |
| `renderer.py` | `rebuild_vp(eye, target, fov)` method; `__init__` stores `_aspect` |
| `player.py` | `world_pos` property → `(grid_x+0.5, 0.0, grid_z+0.5)` |
| `main.py` | `_update_smooth_camera()` helper; `cam_xz` smooth state; 3-line camera block |

---

## 2. How the camera works

**Geometry:**
- Eye: `(3.0, 12.0, −2.0)` — fixed forever in world space
- eye.z = −2 is behind the entire grid (z = 0 is the front edge).
  Every valid player tile has target.z ≥ 0.5, so the camera **always** looks
  toward +z. D key (world +x) is always screen-right; A key always screen-left.
- At player spawn (z = 21): elevation ≈ 27°, distance ≈ 26 u — intimate but not
  claustrophobic
- Horizontal swivel range: 6° left (x=0) to 8.5° right (x=6) — 15° total arc,
  below the perceptual threshold for camera motion

**Smooth follow:**
- Each frame: `alpha = 1 − exp(−5 × dt)`
- At MOVE_COOLDOWN (0.12 s): camera closes ~45% of the gap per hop
- Catches up to ~92% in 0.5 s — visible lag that feels like a weighted tripod
- On phase transition (TITLE → gameplay, GAME_OVER → restart): target **snaps**
  to spawn position immediately — no slow pan across the board

---

## 3. How to test

### 3a. Smooth follow feel
1. Start a game. Move the player left (A key). The camera should gently drift
   leftward — not snap instantly, not slide the world.
2. Hold A continuously. The camera should chase you in a smooth weighted glide,
   never quite catching up until you stop.
3. Stop moving. Camera should ease to rest at your position within ~0.5 s.

### 3b. A/D orientation — floor frame, not player frame
1. Play until the player retreats toward z = 5 or lower (near the front edge).
2. Press D. Player should move to screen-right regardless of how close they are
   to the front edge. This should be consistent from z=21 all the way to z=0.
3. Press A. Player should move to screen-left. The direction should never swap.

### 3c. Restart snap
1. Let a cube crush you (GAME OVER). Press any key to restart.
2. The camera should **immediately** be at spawn position — no pan from the
   death position.

### 3d. Overview screens
1. On TITLE, GAME OVER, VICTORY — full overview camera (whole grid visible).
2. Press a key to start/restart — camera snaps to spawn pivot, then smoothly
   follows from there.

### 3e. Pause hold
1. Pause (Esc) mid-wave. Camera holds at current follow position.
2. Resume — follow resumes from current player position.

---

## 4. Success criteria

- [ ] Camera movement is smooth — no per-hop snapping visible
- [ ] D key always moves right on screen; A key always moves left (at any z)
- [ ] Camera restarts at spawn on game restart (no slow pan)
- [ ] World appears stable — no sliding/translation when player moves
- [ ] TITLE / GAME OVER / VICTORY show full overview
- [ ] Pause holds camera position

---

## 5. Expert panel findings (Step 27 — smooth pivot + eye.z fix)

| Reviewer | Verdict | Findings |
|---|---|---|
| Vision Lead | APPROVED | eye=(3,12,−2) geometry verified; elevation 27° at spawn; always looks +z (target.z ≥ 0.5 > −2); swivel 6–8.5° ≤ perceptual threshold |
| Code Quality | APPROVED | All 11 Power of Ten rules pass; `assert len(cam_xz)==2` is meaningful (mypy cannot prove list length); snap-on-transition logic is correct for start, restart, and phase re-entry |
| UX Tester | APPROVED | k=5 lerp is well-tuned (~45%/hop, ~92% in 0.5 s); A/D inversion definitively fixed by eye.z=−2; snap-on-restart prevents pan; "base tiles" feel achieved via fixed-eye pivot |
| Platform Engineer | APPROVED | `cam_xz` allocated once before loop, mutated in-place — no per-frame heap allocation; `math.exp` available in WASM; dt-clamp interaction correct (alpha=0.39 at max clamp, no camera lurch) |

---

## 6. What to tell me after you review

- **"Step 27 approved"** — camera feel is right; proceed to Step 28 (all waves visible).
- **"Camera still snaps / not smooth enough"** — I'll lower `CAMERA_FOLLOW_SMOOTH`
  from 5.0 toward 2–3 for more lag.
- **"Camera is too slow / laggy"** — I'll raise from 5.0 toward 8–10.
- **"A/D still seems wrong"** — describe the player z at which it happens and I'll
  investigate; the geometry guarantees it shouldn't occur with eye.z=−2.
- **"Angle feels wrong"** — describe too close/far or too steep/shallow and I'll
  adjust `CAMERA_FOLLOW_EYE`.
