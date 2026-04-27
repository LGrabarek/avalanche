# Step 7 — User Review (Phase B, revision 2)

**What Step 7 covers:** ADVANTAGE trap tile lifecycle and the 3×3 detonate blast (Z key), plus three behaviour corrections applied after the initial Phase B review.

**What changed in this revision (vs. revision 1):**

1. **Blast area corrected** — `_execute_blast` now checks only the single tile it was called for (the green tile itself), not a further 3×3 expansion from each green tile. The green 3×3 area already defines the blast zone; no tile is inspected twice.
2. **Cube drop-off at new front edge** — when penalty row deletions void the front rows, cubes now roll off at the new platform edge (the first non-void row). They no longer tumble over empty space to reach the original grid front.
3. **Floating inverted-cone markers** — a small hexagonal inverted cone (apex pointing down, base pointing up) now floats above every MARKED tile (blue) and every ADVANTAGE_TRAP tile (green). The cone appears and disappears in exact sync with the tile state.

---

## 1. Run the dev server

Same as prior steps. Serves on **http://localhost:8000**.

### Option A — Git Bash on Windows

```bash
cd /f/Python/Avalanche
bash run_dev.sh
```

### Option B — WSL

```bash
cd /mnt/f/Python/Avalanche
bash run_dev.sh
```

First fresh-browser load is ~30s. `Ctrl+C` to stop. **Click the canvas** so keyboard events reach the game.

---

## 2. What you should see

On load: same as Step 6 — grid, player at `(3, 21)`, 7 debug cubes tumbling. The controls hint reads:

```
Move: WASD / Arrows   Mark: SPACE   Trigger: X / Enter   Detonate: Z
```

---

## 3. Cone markers on MARKED and ADVANTAGE_TRAP tiles

### 3a. MARKED tile (SPACE)

1. Walk to any tile and press SPACE. The tile turns blue and a **small blue inverted cone** appears directly above it. The cone apex points downward, hovering roughly 25% above cube height.
2. Walk away and press SPACE on a different tile. The old cone vanishes; the new tile gets the cone.
3. Press X with no cube on the mark → tile returns to grey, cone disappears.

### 3b. ADVANTAGE_TRAP tiles (after capture)

1. Capture an ADVANTAGE cube (see §4). A **3×3 green area** appears. Each of those green tiles has a **small green inverted cone** above it — up to 9 cones visible simultaneously.
2. Press Z to detonate. All green tiles clear to grey and all cones disappear at the same moment.

### Cone visual spec
- **Shape:** inverted hexagonal cone — base (open) at the top (~y 1.5), apex (tip) pointing down at ~y 1.25.
- **Size:** small, radius ≈ 0.2 tile units (well within one tile footprint).
- **Blue cone** → MARKED tile. **Green cone** → ADVANTAGE_TRAP tile.
- **No cone** → PLATFORM, VOID, or any other state.

---

## 4. ADVANTAGE cube: mark → capture → 3×3 trap area

The debug row has ADVANTAGE cubes (green) at columns 2 and 4 (0-indexed).

1. Wait for cubes to enter the rest phase (they stop animating).
2. **Mark** the tile an ADVANTAGE cube is resting on with SPACE. A blue cone appears.
3. Press **X** to capture. The cube disappears, the blue tile+cone clear, and a **3×3 green area with 9 green cones** appears centred on the marked tile.
4. Score increases by +100 pts.

---

## 5. Detonate (Z key)

1. With one or more green trap tiles (and their cones) visible, press **Z**.
2. All green tiles and all cones clear simultaneously.
3. Each of the (up to 9) trap tiles checks for a cube sitting exactly on that tile. Any cube found is scored and removed.
4. Score increments by **200 pts per cube hit**.

**Blast area is now exact:** only cubes sitting directly on a green tile are affected. Cubes one tile outside the green area are unaffected.

**Z with no traps:** silent no-op — no crash, no score change, no visual.

---

## 6. ADVANTAGE cube hit by blast → new trap area (not immediate chain)

If the blast hits an **ADVANTAGE cube** still in the wave:

1. That cube scores 200 pts and is removed.
2. A **new 3×3 green area with cones** appears around the cube's position.
3. The new area is **NOT** immediately detonated — it waits for the next Z press.
4. Press **Z again** to fire the second blast.

---

## 7. ⚠ FORBIDDEN cube in blast range

> **Important — read before testing.**

The debug row has a FORBIDDEN cube (dark with red outline) at **column 3**, between the two ADVANTAGE cubes at columns 2 and 4. After capturing either ADVANTAGE cube, the green 3×3 area includes column 3.

**Effect:** pressing Z will check column 3 (a green tile). If the FORBIDDEN cube is resting exactly on that tile when Z is pressed, the front platform row is deleted. This is correct I.Q. behavior. It is not a bug.

---

## 8. Cube drop-off at new front edge

After any row deletion (FORBIDDEN capture or penalty threshold):

1. The front row voids. The platform edge moves back by one row.
2. Cubes still in the wave now roll off at the **new** platform edge (the first non-void row), not the original grid front.
3. You should see cubes tumble up to the new edge and disappear there — they no longer float over empty space.

To test: trigger a row deletion (e.g., capture the FORBIDDEN cube at column 3), then observe that the remaining cubes drop earlier.

---

## 9. Scoring reference

| Action | Score |
|---|---|
| Capture ADVANTAGE (X) | +100 |
| NORMAL hit by blast (Z) | +200 |
| ADVANTAGE cube hit by blast | +200 (+ new 3×3 trap area armed) |
| FORBIDDEN hit by blast | 0 pts + front row deleted |
| FORBIDDEN captured (X) | 0 pts + front row deleted |
| Missed NORMAL or ADVANTAGE | +1 penalty counter |

---

## 10. Success criteria (check each)

- [ ] **Blue cone on SPACE mark:** pressing SPACE places a blue inverted cone above the marked tile; cone disappears when the mark clears.
- [ ] **Green cones on ADVANTAGE_TRAP:** capturing a green ADVANTAGE cube turns a 3×3 area green with a cone above each tile.
- [ ] **Cone count matches tile state exactly:** no orphaned cones, no tiles without cones when state is MARKED/ADVANTAGE_TRAP.
- [ ] **Blast area is the green tiles only:** capturing ADVANTAGE at column 2, Z detonates only the 3×3 green tiles. Cubes one tile outside are unaffected.
- [ ] **Z detonates all green tiles:** all green tiles and their cones clear; flash rings appear at each cube hit; score increments by 200/cube.
- [ ] **Z with no traps is silent:** no crash, no score change, no visual.
- [ ] **Trap-tile refuses mark:** pressing SPACE while standing on a green tile does nothing (tile stays green, cone stays; no blue tile or second cone).
- [ ] **ADVANTAGE cube in blast → new armed area, not instant chain:** blast hits ADVANTAGE wave cube → that cube disappears, new 3×3 green area+cones appear, no immediate second blast; pressing Z again detonates it.
- [ ] **FORBIDDEN in blast deletes row:** front platform row disappears when FORBIDDEN is on a green tile when Z is pressed.
- [ ] **GAME_OVER if row deletion voids player tile:** GAME OVER overlay appears if the player's row is deleted.
- [ ] **Cubes drop at new front edge:** after a row deletion, cubes tumble off at the new (moved-back) platform edge, not over the voided gap.
- [ ] **Controls hint shows `Detonate: Z`:** visible at the bottom of the screen.
- [ ] **No crash or traceback** in the browser console (F12 → Console).

---

## 11. Edge cases to test

- **Detonate during avalanche:** press Z during the avalanche rush. Z should do nothing — detonation is blocked outside WAVE_ACTIVE.
- **Mark then detonate:** place a SPACE mark on a tile, then press Z. The blue cone on the mark tile should survive the detonation (green tiles/cones are on separate tiles). Press X afterward to trigger normally.
- **Two ADVANTAGE captures, one Z:** capture both ADVANTAGE cubes (cols 2 and 4). Green areas may overlap. Press Z once — blasts fire from each of the (up to 9) green tiles simultaneously.
- **Blast at grid edge:** if a trap centre is at x=0 or x=6 (edge column), the 3×3 area clips silently. No crash; edge tiles outside the grid aren't included.
- **New trap from blast hit:** after a blast hits an ADVANTAGE cube in the wave, verify the new 3×3 green area and cones appear, then press Z to fire a second blast.
- **Multiple row deletions and drop-off:** delete two rows via FORBIDDEN captures; confirm cubes now drop two rows earlier than the initial front edge.

---

## 12. Intentionally inert for this step (please do NOT report as bugs)

- **No blast AoE visual.** Individual capture-flash rings appear per cube hit, but there is no overlay showing the blast zone area. Step 10 polish.
- **No audio on detonate.** Step 10.
- **Trap tile has no animation or pulse.** Static green tile + static cone. Step 10 polish.
- **Z-with-no-traps gives no feedback.** Silent no-op. Step 10 polish.
- **Trap-tile SPACE refusal is silent.** No text/sound when mark is refused. Step 10 polish.
- **Wave does not respawn.** One debug row only. Step 9 handles wave progression.

### Carry-forward from prior steps (still open)

- **Tumble animation feel** — heave/balance/thud easing → Step 10.
- **`MOVE_COOLDOWN = 0.08s`** — user-flagged as faster than I.Q. original → Step 10 retune.
- **Static perpendicular-priority** in `_first_held_direction` → revisit after Step 9.
- **Flash color type-tinting** → Step 10 polish.
- **Font-render caching in HUD** → Step 10 polish.

---

## 13. Expert Panel findings (Phase A)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED | 3×3 trap area on capture is faithful to I.Q. original. Blast centering on trap tile correct. FORBIDDEN-in-blast indiscriminate behavior confirmed. "New trap area, not instant chain" for ADVANTAGE cube hits matches I.Q. manual-trigger design. | No action required. |
| Code Quality | (quota exhausted — manual review) | `_mark_trap_area` extracted as shared helper for both CREATE_TRAP and DETONATE_3X3 paths. `on_detonate` simplified to bounded `for` loop (Rule 2 for-loop exemption). `_execute_blast` signature simplified (no blast_queue/blasted args). Rule 5 in-bounds precondition on both `_execute_blast` and `_mark_trap_area`. All Power-of-Ten rules compliant. | No action required. |
| UX Tester | APPROVED (with Step 10 deferrals) | HUD hint includes `Detonate: Z`. Review doc §7 warns about FORBIDDEN-in-blast row deletion. New-trap-area mechanic requires a second Z press — documented in §6. | Applied. |
| Platform Engineer | (quota exhausted — manual review) | O(~11k ops) on a discrete Z keypress is negligible under WASM. `_mark_trap_area` O(9) per call. No per-frame cost. No Pygbag compatibility concerns. | No action required. |

**Carry-forward panel deferrals:**
- Step 9 — wave progression; restart after GAME_OVER; row restoration.
- Step 10 — blast AoE visual; trap tile animation/pulse; Z-no-traps feedback; trap-mark-refusal feedback; HUD polish; audio; `MOVE_COOLDOWN` retune; tumble easing.

---

## 14. What to tell me after you review

Any one of:

- **"Step 7 approved, proceed to Step 8"** — I'll start Step 8 Phase A (FORBIDDEN full behavior verification).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify before Step 8.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel on the fixes.
- **"I can't run it because [error]"** — paste the terminal/console output.

---

## 15. Files changed in Step 7 (revision 2)

```
renderer.py        (updated) — TriFaceDescriptor type alias added.
                               project_triangle(): new method for triangular faces;
                               shares ProjectedFace output type with project_face so
                               triangles and quads sort together in the painter's algorithm.

cube_data.py       (updated) — import math added.
                               TriFaceDescriptor imported from renderer.
                               CONE_SIDES, CONE_APEX_Y, CONE_BASE_Y, CONE_RADIUS constants.
                               _CONE_COLORS: per-state fill+edge colors for MARKED and
                               ADVANTAGE_TRAP cones.
                               get_marker_cone_faces(grid_x, grid_z, tile_state): returns 6
                               triangular side faces for an inverted hexagonal cone marker;
                               returns [] for PLATFORM and other non-cone states.

game_manager.py    (updated) — _execute_blast: no longer iterates 3×3; checks only the
                               single tile (cx, cz). The green ADVANTAGE_TRAP tiles already
                               define the blast area; no further expansion.

wave_manager.py    (updated) — update(dt, front_drop_z=0): new front_drop_z parameter.
                               _advance_tick(front_drop_z=0): drops cubes whose grid_z falls
                               below front_drop_z (instead of hardcoded 0), so cubes roll
                               off at the new platform edge after row deletions.

grid_manager.py    (updated) — front_edge_z property: scans from z=0 to find the first
                               non-void row; returns 0 normally, positive value after row
                               deletions. Used by main.py to feed wave.update().

main.py            (updated) — CONE_SIDES and get_marker_cone_faces imported from cube_data.
                               _build_marker_faces(renderer, grid): new function; projects
                               cone triangles for all MARKED and ADVANTAGE_TRAP tiles.
                               wave.update(dt) → wave.update(dt, grid.front_edge_z).
                               face_list.extend(_build_marker_faces(renderer, grid)) added
                               to the frame build loop.

hud.py             (unchanged from revision 1) — Detonate: Z already present.
docs/STEP7_REVIEW.md  (this file)
```
