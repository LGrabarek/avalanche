# Step 15 — User Review (Particle Burst + Flash Colour Tinting)

**What Step 15 covers:** Replaces the old single-frame expanding-ring flash with a
multi-frame particle burst system. Each capture now emits 10 (NORMAL) or 16 (ADVANTAGE)
particles that radiate outward from the tile centre, are coloured by cube type, and
fade to black over 0.30–0.55 s. Also wires `cube_type` into all four `spawn_flash()`
call sites in `game_manager.py`.

---

## 1. What changed

| File | Change |
|---|---|
| `effects.py` | Full rewrite: `_Particle` dataclass, updated `_Flash` dataclass (adds `cube_type`, `particles`), new `spawn_flash(grid_x, grid_z, cube_type)` signature, rewritten `update()` (particle eviction), rewritten `draw()` (radial scatter + fade), added `oy` bounds assert in `shake_offset()` |
| `game_manager.py` | 4 call sites updated: `_execute_blast` SCORE + DETONATE_3X3, `_dispatch_capture` SCORE + CREATE_TRAP — each now passes `cube.cube_type` as third argument |

No wave data, scoring, grid, HUD, or gameplay logic was changed.

---

## 2. Particle system design

| Parameter | NORMAL / FORBIDDEN | ADVANTAGE |
|---|---|---|
| Particle count | 10 | 16 |
| Max speed | 150 px/s | 220 px/s |
| Lifetime | 0.30–0.55 s | 0.30–0.55 s |
| Colour | (240, 240, 255) white-blue | (160, 255, 100) yellow-green |
| Radius | 2 px | 2 px |

The ADVANTAGE particle colour (160, 255, 100) was deliberately chosen to separate from
the ADVANTAGE_TRAP tile colour (80, 200, 80) — measured colour delta is 155 points,
which provides clear visual distinction.

FORBIDDEN captures emit **no flash** — a success ring on a penalty event would mislead
the player. The row deletion event provides its own unambiguous feedback.

---

## 3. How to test

### 3a. Basic capture flash

1. Run `bash run_dev.sh` → open `http://localhost:8000`.
2. Start a wave. Press `SPACE` to mark a **NORMAL** (grey/white) cube, then `X` to
   trigger. A small burst of **white-blue** dots should radiate outward from the
   captured tile and fade over ~0.4 s.

### 3b. ADVANTAGE flash

1. Mark and trigger a **green ADVANTAGE** cube (or wait for one to appear).
2. The burst should be **visibly larger and faster** than a NORMAL capture, with
   **bright yellow-green** particles.
3. The ADVANTAGE_TRAP tiles that appear underneath (green) should be clearly
   distinguishable from the yellow-green particles.

### 3c. FORBIDDEN silence

1. Deliberately capture a **red FORBIDDEN** cube (mark it, trigger).
2. The front row disappears — **no particle burst** should appear. The silence is
   intentional: a red flash would signal "success" when it is actually a penalty.

### 3d. 3×3 blast

1. Capture an ADVANTAGE cube to create traps, then press `Z` to detonate.
2. Each cube in the blast area should produce its own burst simultaneously. With a
   full ADVANTAGE 3×3 blast you should see a dense multi-burst explosion covering
   the trap area.

### 3e. Particle cap / stress

Normal gameplay never approaches the 32-flash cap. The cap is a safety bound and
will not be visible in regular play.

### 3f. Shake + particles coexist

1. Let the avalanche crush the grid enough to trigger a shake (if implemented) or
   observe that particle bursts appear correctly while the scene may be shaking.
   Particles should displace with the rest of the scene (they are drawn to
   `scene_surf` before the shake blit, so they move with it).

---

## 4. Success criteria

- [ ] **NORMAL capture** → small white-blue particle burst, fades in ~0.4 s.
- [ ] **ADVANTAGE capture** → larger, faster yellow-green burst; clearly distinct
  from the green ADVANTAGE_TRAP tiles that appear.
- [ ] **FORBIDDEN capture** → no burst; front row deletion is the only visual event.
- [ ] **3×3 ADVANTAGE blast** → multiple simultaneous bursts from each trap tile.
- [ ] **Particles fade smoothly** to black (not a sudden pop).
- [ ] **No regression** — scoring, marking, triggering, wave advancement, menu, turbo
  all work exactly as before.

---

## 5. Expert panel findings (Step 15)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED (with fix) | ADVANTAGE particle colour (80,220,80) too close to ADVANTAGE_TRAP tile (80,200,80). Recommended shifting to a brighter yellow-green. | Changed to (160,255,100); colour delta from trap tile = 155 points. |
| Code Quality | APPROVED (after fix) | Line 54 was 116 chars, over the 100-char ruff limit (comment was inline on the dict entry). | Moved comment to preceding line. ruff + mypy --strict pass cleanly. |
| UX Tester | APPROVED | Particle duration (0.30–0.55 s) reads cleanly at 1.2 s tick; turbo overlap is acceptable. Colour semantics are correct. FORBIDDEN silence is the right call. | No change needed. |
| Platform Engineer | APPROVED (with fix) | `shake_offset()` asserted the `ox` bounds but not `oy` (Rule 5 gap). | Added `assert -self._shake_amplitude <= oy <= self._shake_amplitude` before the return. |

---

## 6. What to tell me after you review

- **"Step 15 approved, proceed"** — move on to Step 16 (face shading + camera tuning — B3a+b).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel.
