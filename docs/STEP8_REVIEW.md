# Step 8 — User Review (Phase B)

**What Step 8 covers:** FORBIDDEN cube full behavior verification.

All three FORBIDDEN paths were already wired in earlier steps; Step 8 focused
self-tests, expert-panel review, and targeted code fixes. Changes applied in
Phase A:

1. **No flash on FORBIDDEN capture** — direct capture (X) no longer emits a
   white success ring. NORMAL and ADVANTAGE captures still flash. Row-deletion
   is a mistake, not a success; a "success" ring would mislead the player.
   (`spawn_flash` moved inside `_dispatch_capture` for SCORE/CREATE_TRAP only.)

2. **Closed-set guard in `_count_wave_misses` / `_count_avalanche_misses`** —
   a new `on_missed` behavior added to `CUBE_TYPES` without a dispatch branch
   now fails loudly with an `assert`. Previously it would have silently skipped
   the cube.

3. **`_mark_trap_area` docstring corrected** — now accurately states "raises
   ValueError on the origin; clips neighbors silently."

4. **`delete_front_row` inline comment** — clarifies why `_marked` is zeroed
   directly rather than via `clear_mark()`.

---

## 1. Run the dev server

```bash
cd /f/Python/Avalanche
bash run_dev.sh
```

Serves on **http://localhost:8000**. First fresh-browser load ~30 s.
**Click the canvas** to focus keyboard events.

---

## 2. Debug wave layout

```
Column:   0       1       2         3           4         5       6
Type:   NORMAL  NORMAL  ADVANTAGE  FORBIDDEN  ADVANTAGE  NORMAL  NORMAL
```

- FORBIDDEN (dark purple/black, **red outline**) is at **column 3**.
- Two ADVANTAGE cubes at columns 2 and 4 flank the FORBIDDEN.
- Player spawns at `(3, 21)` — same column as the FORBIDDEN cube.

---

## 3. Visual identification

Walk around the grid and observe the tumbling wave from a distance.

- **NORMAL cubes**: solid gray body, thin dark-gray edge.
- **ADVANTAGE cubes**: green body, bright-green edge.
- **FORBIDDEN cube**: very dark purple body, **thick red edge (2 px)**.

The red outline is the primary distinguisher. Confirm you can reliably spot the
FORBIDDEN cube from back-row spawn distance (it starts at z=24) as it tumbles
toward you.

---

## 4. FORBIDDEN falling off — no penalty

> **Correct play is to do nothing and let it fall.**

1. Wait for the wave to reach rest phase. Do NOT mark or trigger anything.
2. Let the wave continue. The FORBIDDEN cube at column 3 will tumble off the
   front edge.
3. The penalty counter **must not increment**. Verify the `Penalty: N/3` HUD
   line is unchanged after the FORBIDDEN cube disappears.

---

## 5. FORBIDDEN direct capture (X) → row deletion, no flash

1. Walk to column 3 and press **SPACE** to mark the tile. A blue cone appears.
2. Wait for the FORBIDDEN cube to enter rest phase (stops tumbling). The tile
   under the cube will be at column 3 — same column you are standing on.
3. Press **X** to trigger.

**Expected:**
- The FORBIDDEN cube disappears.
- The **front row (row 0) immediately voids** — the edge of the visible platform
  moves back by one row.
- **No white flash ring** appears. (NORMAL captures show a ring; FORBIDDEN
  captures do not.)
- Score does not change.
- Phase stays WAVE_ACTIVE.

**If the player is standing at row 0 when this happens:** GAME OVER overlay
appears. (See §7.)

---

## 6. NORMAL capture — flash contrast reference

Before testing FORBIDDEN, capture a NORMAL cube so you know what the success
flash looks like.

1. Walk to column 0 (or 1 or 5 or 6) and press **SPACE**.
2. Wait for the NORMAL cube to reach rest phase.
3. Press **X**.

**Expected:** white expanding ring, score +100. This is the ring you should
**not** see on a FORBIDDEN capture.

---

## 7. FORBIDDEN direct capture on front row → GAME OVER

To reproduce:

1. Walk to any tile in **row 0** (front row — the very bottom edge of the
   visible platform).
2. Press SPACE to mark it.
3. Let the FORBIDDEN cube tumble. (You may need to let prior cubes pass or
   spawn a new debug row with the page reload.)
4. When the FORBIDDEN cube rests on row 0 (or the first non-void row that
   is row 0), press X.
5. The row is deleted; since you were standing on it, **GAME OVER** overlay
   appears immediately.

---

## 8. FORBIDDEN in blast (Z) → row deletion, no flash

> The ADVANTAGE cubes at columns 2 and 4 both have 3×3 green areas that
> overlap column 3. Capturing either one arms a trap that includes the
> FORBIDDEN cube.

1. Walk to column 2 and press **SPACE** to mark it.
2. Wait for the ADVANTAGE cube (green) to reach rest phase.
3. Press **X** to capture. The ADVANTAGE cube disappears; a **3×3 green area**
   appears with green cones above each tile. Column 3 (FORBIDDEN's tile) turns
   green.
4. Now press **Z** to detonate.

**Expected for the FORBIDDEN tile (column 3):**
- FORBIDDEN cube disappears.
- **Front row deleted** — the platform edge moves back.
- **No white flash ring** at column 3.
- Score unchanged for the FORBIDDEN hit (0 pts).

**Expected for any NORMAL cubes on other green tiles:**
- Each one scores +200 pts and shows a white flash ring.

**Z with no traps present:** silent no-op. Score and grid unchanged.

---

## 9. Scoring reference

| Action                        | Score   | Flash ring |
|-------------------------------|---------|------------|
| Capture NORMAL (X)            | +100    | yes        |
| Capture ADVANTAGE (X)         | +100    | yes        |
| Capture FORBIDDEN (X)         | 0       | **no**     |
| NORMAL hit by blast (Z)       | +200    | yes        |
| ADVANTAGE hit by blast (Z)    | +200    | yes        |
| FORBIDDEN hit by blast (Z)    | 0       | **no**     |
| FORBIDDEN falls off           | 0       | —          |
| NORMAL/ADVANTAGE falls off    | +1 penalty | —       |

---

## 10. Success criteria (check each)

- [ ] **FORBIDDEN visually distinct**: red-outlined dark cube identifiable from
      back-row spawn distance.
- [ ] **FORBIDDEN falls off → no penalty**: penalty counter unchanged after fall.
- [ ] **FORBIDDEN direct capture → row deleted**: front row voids immediately
      on X; no flash ring; score unchanged.
- [ ] **FORBIDDEN capture → no flash**: white ring does NOT appear (contrast
      against NORMAL capture which does show a ring).
- [ ] **FORBIDDEN in blast → row deleted**: pressing Z while FORBIDDEN is on a
      green tile voids the front row; no flash at the FORBIDDEN tile; other hit
      cubes still flash normally.
- [ ] **GAME_OVER when player's row is deleted**: GAME OVER overlay appears if
      the deleted row was the player's row.
- [ ] **FORBIDDEN escape is silent**: no score change, no penalty, no visual.
- [ ] **Controls hint shows Detonate: Z**: visible at the bottom of the screen.
- [ ] **No crash or traceback** in the browser console (F12 → Console).

---

## 11. Edge cases to test

- **Mark column 3, then move away**: Press SPACE on column 3 (blue cone
  appears), then move to a different column. The mark stays on column 3. When
  the FORBIDDEN cube rests there, pressing X from your new position does nothing
  (trigger resolves the marked tile, not the player's current tile). This is
  correct; the mark persists until you re-mark or trigger.
- **FORBIDDEN and NORMAL both in blast**: arm trap at column 3 (FORBIDDEN) and
  column 2 (NORMAL). Press Z. NORMAL gets flash and +200 pts; FORBIDDEN gets
  no flash and row deletion. Both effects happen on the same Z press.
- **Multiple row deletions**: capture FORBIDDEN directly (row 0 deleted), then
  trigger another FORBIDDEN in blast (row 1 deleted). Cubes should now tumble
  off at the new front edge (row 2), not over the empty gap.

---

## 12. Intentionally inert for this step (do NOT report as bugs)

- **No audio** on row deletion or FORBIDDEN capture. Step 10.
- **No collapse animation** — row disappears instantly. Step 10.
- **No distinct red flash** on FORBIDDEN capture. The current "no flash"
  behavior is correct for now; a red ring is planned for Step 10.
- **No "Forbidden captured" text** notification. Step 10 polish.
- **Wave does not respawn.** One debug row only. Step 9 handles wave
  progression.

### Carry-forward from prior steps (still open)

- **Tumble animation feel** — heave/balance/thud easing → Step 10.
- **`MOVE_COOLDOWN = 0.08s`** — user-flagged as faster than I.Q. original →
  Step 10 retune.
- **Static perpendicular-priority** in `_first_held_direction` → Step 9+.
- **Flash color type-tinting** → Step 10 polish.
- **Font-render caching in HUD** → Step 10 polish.

---

## 13. Expert Panel findings (Phase A)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED | All three FORBIDDEN paths faithful to I.Q. design. No-penalty fall-off is the most critical rule and is correct. Blast-catch indiscriminate behavior correct. Two FORBIDDEN in single blast (double-row deletion) is mechanically consistent; noted for Step 9 wave design to gate FORBIDDEN density by difficulty. | No action required. |
| Code Quality | APPROVED | `_mark_trap_area` docstring contradicted the code ("silently clipped" vs. `raise ValueError`). Duplicate `delete_front_row + _check_game_over` pattern is below refactor threshold (two call sites, different obligations). No `else`-branch sentinel in `_count_wave_misses` / `_count_avalanche_misses` leaves unrecognised `on_missed` behaviors silently skipped. `_marked = None` bypass in `delete_front_row` lacked an explanatory comment. | Docstring corrected. Closed-set assert added to both miss-counter methods. Inline comment added to `delete_front_row`. |
| UX Tester | CONCERNS (resolved) | `spawn_flash` was called unconditionally in `on_trigger` for all cube types including FORBIDDEN, producing a white "success" ring on a FORBIDDEN capture — actively misleading (mistake reads as success). FORBIDDEN dark body near-black against black background — red outline carries all identification weight; verify readability at spawn distance in Phase B. Falls-off-is-correct is unintuitive without confirming feedback; document for tester. | `spawn_flash` moved inside `_dispatch_capture` for SCORE and CREATE_TRAP branches only; ROW_DELETE branch explicitly does not flash. Flash-at-spawn-distance flagged in §3 for Phase B verification. Falls-off scenario documented in §4 and checklist §10. |
| Platform Engineer | APPROVED | O(~200 ops) per keypress well within WASM budget. No per-frame cost regression. No Pygbag compatibility concerns. `delete_front_row` double-pass over 175 tiles is microseconds. | No action required. |

**Panel carry-forward deferrals:**
- Step 9 — FORBIDDEN density gating by difficulty level in wave data.
- Step 10 — distinct red flash on FORBIDDEN capture; collapse animation; row-deletion audio.

---

## 14. What to tell me after you review

Any one of:

- **"Step 8 approved, proceed to Step 9"** — I'll start Step 9 Phase A (wave
  progression, wave data, Perfect bonus).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel.
- **"I can't run it because [error]"** — paste the terminal/console output.

---

## 15. Files changed in Step 8 (Phase A)

```
game_manager.py   (updated) — spawn_flash moved from on_trigger (unconditional)
                               into _dispatch_capture for SCORE and CREATE_TRAP
                               branches only. ROW_DELETE (FORBIDDEN) branch
                               explicitly does not flash — mistake ≠ success.
                               Closed-set assert added to _count_wave_misses and
                               _count_avalanche_misses: any new on_missed behavior
                               not in {PENALTY, NONE} will fail loudly.
                               _mark_trap_area docstring corrected.

grid_manager.py   (updated) — Inline comment in delete_front_row clarifies why
                               _marked is zeroed directly rather than via
                               clear_mark() (tile is voided, not restored to
                               PLATFORM).

docs/STEP8_REVIEW.md  (this file)
```
