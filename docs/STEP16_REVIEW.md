# Step 16 — User Review (Face Shading + Camera Tuning)

**What Step 16 covers:**
- **B3a — Face shading pass:** Each cube type now derives its six face colours from a single
  `base_color` multiplied by per-face brightness constants (`FACE_MULTS`). The two lateral
  faces are now distinct — the screen-left (+X) face is lit (×0.75), the screen-right (-X)
  face is shadow (×0.55) — matching a light source from the upper-left screen corner.
- **B3b — Camera tuning:** Camera Y raised from 12.0 → 13.0, increasing elevation from
  23.2° to 24.9° for slightly more top-face visibility.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | Added `FACE_TOP_MULT`, `FACE_RIGHT_MULT`, `FACE_LEFT_MULT`, `FACE_BOTTOM_MULT`, `FACE_MULTS` tuple; changed `CubeTypeInfo` from `colors: dict[str, ColorRGB]` to `base_color: ColorRGB`; simplified `CUBE_TYPES` entries; raised `CAMERA_POS` Y from 12.0 to 13.0; changed ADVANTAGE edge from (0,255,0) to (0,200,0) |
| `cube_data.py` | Added `FACE_MULTS` import; rewrote `get_cube_faces()` to build face descriptors directly (bypassing `_build_faces`); updated stale comments on `_CUBE_FACES` and `_build_faces` docstring |
| `hud.py` | Fixed pre-existing ruff E501 (hint text shortened to ≤100 chars) |

No wave data, scoring, grid, gameplay logic, or rendering pipeline was changed.

---

## 2. Face shading details

| Face | Index | Multiplier | NORMAL (base 180) | ADVANTAGE (base 100,220,100) |
|------|-------|-----------|-------------------|------------------------------|
| Top (+Y) | 0 | 1.00 | (180,180,180) | (100,220,100) |
| Front (+Z) | 2 | 0.75 | (135,135,135) | (75,165,75) |
| Side +X (lit) | 5 | 0.75 | (135,135,135) | (75,165,75) |
| Side -X (shadow) | 4 | 0.55 | (99,99,99) | (55,121,55) |
| Back (-Z) | 3 | 0.55 | (99,99,99) | (55,121,55) |
| Bottom (-Y) | 1 | 0.40 | (72,72,72) | (40,88,40) |

**FORBIDDEN** base (60,30,60) is intentionally near-black — this matches the research doc's
"abyssal black texture" description. The 2px red edge (180,0,0) is the primary hazard signal,
not the body colour. The Vision Lead flagged the low luminance as a potential concern; the UX
Tester confirmed the edge-driven signal is sufficient and the dark body is the correct I.Q.
design intent. No change was made.

---

## 3. How to test

### 3a. Face shading visible

1. Run `bash run_dev.sh` → open `http://localhost:8000`.
2. Start a wave. Watch NORMAL (grey) cubes tumble across the grid.
3. Look at the lateral faces of a cube — the screen-left face should be **visibly lighter**
   than the screen-right face. Both faces are now `(135,135,135)` and `(99,99,99)`
   respectively; the lit-side is 36 units brighter.
4. The top face remains the brightest, giving a clear "light from above" reading.

### 3b. ADVANTAGE cube 3D improvement

1. Wait for a green ADVANTAGE cube to appear (Wave 2 or later, or check `wave_data.py`).
2. Previously both lateral faces were `(30,140,30)` — flat dark green. Now the lit face is
   `(75,165,75)` — a 2.5× brightness increase. The cube should look clearly 3D.
3. The green identity (top is bright green) remains intact.

### 3c. FORBIDDEN cube

1. Let a FORBIDDEN cube appear (dark purple with red outline).
2. The body should remain very dark — the red 2px outline is the primary hazard indicator.
   This is intentional per the original game design.

### 3d. Camera elevation

1. Compare the grid view to memory (or screenshot from a previous session).
2. The change is subtle (1.7° more elevation) — slightly more top-face area is visible.
   This is a minor depth-perception improvement, not a dramatic reframe.

### 3e. No regressions

- All cube types readable and distinct from each other and from the platform.
- Scoring, marking, triggering, wave advancement, menu, turbo all work exactly as before.

---

## 4. Success criteria

- [ ] **NORMAL cubes** show a visible lit/shadow side gradient — screen-left face brighter
  than screen-right face.
- [ ] **ADVANTAGE cubes** look clearly 3D — bright green top, two distinct lateral shades.
- [ ] **FORBIDDEN cubes** read as a dark danger cube with a prominent red outline.
- [ ] **All cube types** remain instantly distinguishable from each other and from the
  grey-blue platform tiles.
- [ ] **Player cube** (blue) is unchanged and still clearly distinct from wave cubes.
- [ ] No gameplay regression.

---

## 5. Expert panel findings (Step 16)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED (conditional) | FORBIDDEN body is near-invisible on black bg. Conditional: if intentional "abyssal black" design, no change needed. | Confirmed intentional per research doc "abyssal black texture". Red edge is primary signal. No change. |
| Code Quality | APPROVED | Two stale docstrings in `cube_data.py` (`_CUBE_FACES` comment, `_build_faces` docstring said "shared by game cubes and player"). | Updated both docstrings. Also fixed pre-existing E501 in `hud.py`. |
| UX Tester | APPROVED | FORBIDDEN dark body is acceptable — red edge carries the hazard signal. Advisory: NORMAL shadow face (99) is close to platform tile (90,90,110) in luminance — not an issue now but worth monitoring. | No change needed. |
| Platform Engineer | APPROVED | Advisory: add `int()` truncation comment in `get_cube_faces()`. New path (int×float) is actually faster than old (dict lookup) due to CPython integer cache. | Added inline comment. |

---

## 6. What to tell me after you review

- **"Step 16 approved, proceed"** — move on to Step 17 (HUD font render caching, A4).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel.
