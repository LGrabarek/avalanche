# Step 24 — User Review (Camera rework, A7)

**What Step 24 covers:**
- Raises camera elevation from ~25° to ~28° by lifting `CAMERA_POS` Y from 13.0 to 15.0
  in `constants.py`. No code changes — purely constant tuning.
- Improves depth perception: rows are slightly more distinguishable, the advancing wave
  reads more clearly, and the checkerboard tile pattern opens up at the new angle.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | `CAMERA_POS` Y: 13.0 → 15.0; camera comment block rewritten with new geometry |

No other constants changed. `CAMERA_TARGET`, `CAMERA_FOV`, `NEAR_PLANE`, `FAR_PLANE`,
and the Z offset (−28 from grid centre) are all unchanged.

---

## 2. Design details

### Camera geometry

| | Before (Step 16B) | After (Step 24) |
|---|---|---|
| Camera position | (3.0, 13.0, −16.0) | (3.0, 15.0, −16.0) |
| Elevation angle | ~25° | ~28° |
| Direction vector | (0, −13, 28) | (0, −15, 28) |

### Why it helps

The wave advances along the Z axis (toward the player). At a steeper viewing angle:
- Each row of the grid occupies slightly more vertical screen space.
- The checkerboard pattern (TILE_CHECKER_DELTA = 8) is more legible because the tiles
  are slightly less foreshortened.
- Cubes near the back of the grid are more distinct from each other.
- The DANGER_TOP_COLOR (yellow) on front-edge cubes is slightly more prominent.

### Clip-bound verification (computed numerically)

All critical vertices project safely within NDC [−1, 1]:

| Vertex | y_ndc | Safe? |
|---|---|---|
| Front-row floor (z=−0.5) | −0.61 | ✓ above −1.0 |
| Back-row floor (z=24.5) | +0.30 | ✓ below +1.0 |
| Front-row cube top (y=1) | −0.53 | ✓ |
| Front-left corner (x=−0.5) | x_ndc = +0.24 | ✓ |
| Back-right corner (x=6.5) | x_ndc = −0.12 | ✓ |

The full grid remains visible with comfortable margin on all sides.

---

## 3. How to test

### 3a. Visual impression check

1. Run `bash run_dev.sh` → open `http://localhost:8000`.
2. Start a game and compare the view to before.
3. The grid should feel **slightly more overhead** — row boundaries clearer, the
   checkerboard pattern a touch more open, the wave advancing more visually distinct.
4. The full grid (all 25 rows) should still be visible — no rows clipped at top or bottom.

### 3b. Confirm no clipping

- The **front row** (closest to camera, at bottom of screen) should be fully visible
  and not cut off at the bottom edge.
- The **back row** (furthest, at top of screen) should be fully visible and not cut off
  at the top edge.
- All seven columns of the grid should fit within the left/right viewport.

### 3c. Gameplay unchanged

- The wave advances, player moves, captures, and scoring all behave identically.
- Cube colors, face shading, player shadow, checkerboard, and DANGER telegraph (yellow
  top face on front-edge cubes) should all look correct.
- No regressions from any previously-approved feature.

---

## 4. Success criteria

- [ ] Grid rows are slightly more distinct in depth compared to the previous angle.
- [ ] All 25 rows visible; no geometry clipped at any viewport edge.
- [ ] Gameplay feel unchanged (only the viewpoint shifted, not the game).
- [ ] No visual artefacts or obvious rendering errors.

---

## 5. Expert panel findings (Step 24)

| Reviewer | Verdict | Finding |
|---|---|---|
| Vision Lead | APPROVED | 28° preserves three-face cube read; moves elevation toward original I.Q. range (25–30°); checkerboard and DANGER_TOP improved |
| Code Quality | APPROVED | Comment geometry accurate; TODO removal appropriate; no other constants reference old Y value; camera block needs no assertions |
| UX Tester | APPROVED | Front-row spacing ~22 px/row (up from ~21); mid-grid +4–9% separability; player shadow unaffected; no regression |
| Platform Engineer | APPROVED | VP matrix computed at init from module constants — no stale-cache risk; WASM-inert; near-plane distance 22 world units ≫ 0.1 |

No changes required by the panel.

---

## 6. What to tell me after you review

- **"Step 24 approved, proceed"** — move on to Step 25 (Audio system, A1).
- **"Grid feels more top-down than I'd like"** — describe the feel and I can try a smaller
  Y value (e.g. 14.0 for 26.5°).
- **"Rows are harder to read than before"** — unlikely given the math, but describe what
  you see and I'll investigate.
- **"Changes needed: [X]"** — address and re-run panel.
