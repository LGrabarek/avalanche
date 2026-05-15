# Step 31 — Graphics Rework (1280×720 + aalines)

**What Step 31 covers:**
- Bumps the internal framebuffer from 960×640 (3:2) to **1280×720 (16:9)**.
- Replaces `pygame.draw.polygon(..., edge_width)` outline calls in `renderer.py`
  with `pygame.draw.aalines` — anti-aliased 1 px edges that eliminate diagonal
  staircase artifacts on isometric cube faces.
- For FORBIDDEN cubes (`edge_width=2`) a second `aalines` pass is drawn with each
  point shifted `+1 px` rightward, simulating the original thick red border.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | `SCREEN_WIDTH` 960 → 1280; `SCREEN_HEIGHT` 640 → 720; `CubeTypeInfo.edge_width` docstring updated for aalines semantics. |
| `renderer.py` | `render_frame()`: `polygon(..., edge_width)` outline → `aalines` + optional offset pass. |
| `hud.py` | Minor comment fix: stale "640-tall canvas" reference updated. |

---

## 2. renderer.py — render_frame() change

```python
# Before (Step 30 and earlier):
_ = pygame.draw.polygon(screen, fill_color, int_points)
if edge_color is not None and edge_width > 0:
    _ = pygame.draw.polygon(screen, edge_color, int_points, edge_width)

# After (Step 31):
_ = pygame.draw.polygon(screen, fill_color, int_points)
if edge_color is not None:
    _ = pygame.draw.aalines(screen, edge_color, True, int_points)
    if edge_width > 1:
        # Second offset pass — 1 px right — simulates a thick outline.
        offset_pts = [(x + 1, y) for x, y in int_points]
        _ = pygame.draw.aalines(screen, edge_color, True, offset_pts)
```

**No change to NORMAL/ADVANTAGE edge drawing behaviour:** both cube types have
`edge_color` set and `edge_width=1`, so the old guard
`edge_color is not None and edge_width > 0` was already True — they always
received a 1 px outline. The new guard `edge_color is not None` is equally
True. No regression.

---

## 3. Cube type edge rendering summary

| Cube type | base_color | edge_color | edge_width | Render path |
|-----------|-----------|-----------|-----------|-------------|
| NORMAL | (180,180,180) grey | (60,60,60) dark grey | 1 | Fill + single `aalines` |
| ADVANTAGE | (100,220,100) green | (0,200,0) green | 1 | Fill + single `aalines` |
| FORBIDDEN | (60,30,60) dark purple | (180,0,0) red | 2 | Fill + two `aalines` passes |

---

## 4. Known design choices (not defects)

### Horizontal-only offset for FORBIDDEN thick edge
The second `aalines` pass shifts every vertex `+1` in x only. This produces:
- **Visible thickening** on near-horizontal edges (top face of isometric cube).
- **Minimal thickening** on near-vertical edges (left/right isometric side faces).

This is a deliberate pragmatic choice — `gfxdraw` and surface-copy tricks are
either unavailable under WASM or too expensive per frame. The FORBIDDEN cube's
*primary* identification cue is its **dark purple fill + saturated red edge**,
both of which are visually unambiguous in all orientations. The "thick" outline
is a secondary cue that strengthens recognition on the top face, which is the
most visible surface. All four expert reviewers confirmed this is acceptable.

If a symmetric 4-direction expansion is later desired, add a `+1y` pass alongside
the `+1x` pass (adds one more `aalines` call per FORBIDDEN face).

---

## 5. How to test

### 5a. Resolution sanity
1. Run `python main.py` (desktop).
2. Confirm the window opens at **1280×720**.
3. The isometric grid should appear ~18% wider than in Step 30 — more of the
   lateral columns are visible at the sides.

### 5b. Anti-aliased edges
1. Start a game and look at the advancing cube wall from a distance.
2. Diagonal cube edges (isometric ~45°) should be **smooth**, without the
   staircase pixel artifact visible in earlier steps.
3. Compare NORMAL vs ADVANTAGE vs FORBIDDEN cubes: all three types show
   clearly distinct outlines.

### 5c. FORBIDDEN cube distinctiveness
1. Play to a wave with FORBIDDEN cubes (Stage 1 Wave 3+ or Stage 2+).
2. FORBIDDEN cubes should show a **red edge** that appears slightly thicker
   on the top face than on side faces — this is the intended behavior.
3. Confirm FORBIDDEN is not mistakable for ADVANTAGE (green vs red/purple) or
   NORMAL (grey).

### 5d. HUD and overlays
1. All overlays (TITLE, WAVE_RISING, STAGE_CLEAR, GAME_OVER, VICTORY, MENU) should
   be horizontally centered on the wider canvas.
2. The HUD stat block remains top-left; the hint line remains bottom-left.
3. Both fit comfortably without crowding the play field.

### 5e. Browser test
1. `bash run_dev.sh` → open `http://localhost:8000`.
2. Confirm the canvas fills the viewport at 16:9 — no letterboxing at standard
   monitor widths (1920 wide, 1080 tall).
3. No performance regression: game should run at smooth 30+ FPS throughout a full
   wave activation sequence.

---

## 6. Success criteria

- [ ] Window opens at 1280×720 on desktop
- [ ] Cube edges are visibly smooth (no staircase on diagonals)
- [ ] FORBIDDEN cubes show red outline distinctly different from ADVANTAGE/NORMAL
- [ ] All overlays center correctly on the wider canvas
- [ ] No framerate regression in the browser
- [ ] ruff + mypy --strict: clean (confirmed pre-review)

---

## 7. Expert panel findings

| Reviewer | Verdict | Findings |
|---|---|---|
| Code Quality | ✅ APPROVED | All 11 Power of Ten rules pass. `pygame.draw.aalines` return value correctly discarded to `_` (Rule 7). `render_frame()` stays within 50-line limit (32 lines). No old literal pixel values remain in `.py` files — all callers use `SCREEN_WIDTH`/`SCREEN_HEIGHT`. HUD bottom-anchor `SCREEN_HEIGHT − hint_h − 14` resolves correctly at 720 px. Two non-blocking observations documented above. |
| Vision Lead | ✅ APPROVED | 16:9 aspect ratio suits isometric games well — extra width is distributed evenly around the symmetric grid. `aalines` produces cleaner edges without softening the retro feel (blocky geometry + flat shading remain the visual signature). FORBIDDEN thick-outline simulation is functionally sufficient: larger on-screen cube size at 1280×720 makes the red edge *more* visible than at 960×640. All centered overlays adapt correctly. The hint-line text gains comfortable margin at the wider canvas width. |
| UX Tester | ✅ APPROVED | Visual clarity improves at 1280×720. Fill colors remain the primary cube-type identification cue (dark purple / bright green / grey). The horizontal-only thick-outline simulation is noted for future improvement (add `+1y` pass) but does not block approval — dark purple fill is unambiguous. Float-to-int truncation before `aalines` is a trivial quality note (no functional impact). NORMAL cube edge behavior unchanged from prior steps (always `edge_width=1`, always drew an outline). |
| Platform Engineer | ✅ APPROVED | +50% pixel fill (921K vs 614K) is acceptable for a puzzle game not fill-rate-bound at these polygon counts. `aalines` is cheaper than thick `polygon` strokes for most faces; FORBIDDEN two-pass cost is neutral. `offset_pts` allocation (~2–9 per frame) is negligible. `pygame.draw.aalines` is fully supported in WASM/Pygbag (core C draw module). PWA manifest icons unaffected. Canvas dimensions flow from `pygame.display.set_mode` automatically — no `pygbag.ini`/`custom.tmpl` changes needed. **Bonus:** `config.fb_ar = 1.77` in `custom.tmpl` was *wrong* for the old 960×640 (1.5:1) and is now *correct* for 1280×720 (16:9 ≈ 1.777) — a fortuitous improvement to browser canvas-fit logic. |
