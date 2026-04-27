# Step 6 — User Review (Phase B)

**What Step 6 covers:** missed-normal penalty counting, row deletion, GAME_OVER detection, cube-player collision blocking, and focus-loss pause.

**What's new vs. Step 5:** missing NORMAL or ADVANTAGE cubes now increments a penalty counter. At 3 misses the back-most platform row is voided. If your tile is ever voided, the game ends. Avalanche misses accumulate during the rush and are applied as row deletions when the wave clears. You can no longer walk through tumbling cubes. Alt-tabbing pauses the game.

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

> **Port-8000 squatter:** `netstat -ano | findstr :8000` then `taskkill /F /PID <PID>` if needed.

---

## 2. What you should see

On load: same as Step 5 — grid, player at `(3, 21)` (3 rows from the back edge), 7 debug cubes tumbling from the back row.

New HUD line: `Penalty: 0/3` in the top-left stat block (6 lines now, was 5).

---

## 3. Penalty counter and row deletion

1. **Let a cube pass without capturing it.** Watch the HUD — `Penalty:` should increment from `0/3` to `1/3`.
2. Let **three** non-FORBIDDEN cubes escape (any NORMAL or ADVANTAGE cube counts; FORBIDDEN does NOT). The moment the 3rd miss is processed, the **front-most** platform row (closest to the camera, bottom of screen) disappears and the counter resets.
3. The counter resets by subtracting 3 (remainder carries over). Miss three more and the next front row deletes.

**Expected HUD behavior:** `Penalty: 0/3 → 1/3 → 2/3 → 0/3` (row deleted on the 3rd miss — counter never displays `3/3` because the deletion and reset happen in the same tick before the next render).

### 3a. FORBIDDEN capture penalty

**Capturing** a FORBIDDEN cube (dark with red outline) immediately deletes the front row — same outcome as filling the penalty counter to 3. The `Penalty:` counter itself is not touched; the row deletion is a direct consequence of the capture.

1. Mark the tile in front of the FORBIDDEN cube and trigger when it rests.
2. The FORBIDDEN cube disappears AND the front row vanishes in the same frame.
3. If that deletion voids the player's tile, GAME_OVER fires immediately.

---

## 4. Avalanche penalties

1. Let a cube crush you (stand in its column, don't move).
2. During the avalanche rush, NORMAL cubes that fall off count toward `_avalanche_penalty` internally.
3. When the rush ends (all cubes gone), any accumulated avalanche misses that crossed the threshold (3 per row) delete rows at that point.
4. You should see rows disappear at the end of the avalanche if enough cubes escaped during the rush.

---

## 5. GAME_OVER

1. Stand in the **back-most rows** of the platform and let cubes escape repeatedly until row deletions reach your position.
2. When the row under you is deleted, the game **freezes** and a red **GAME OVER** label appears in the center of the screen.
3. The wave stops, the player stops responding to input. There is no restart yet (Step 9).

**Alternative:** stand in the last remaining row and deliberately let cubes escape. Faster path to GAME_OVER.

---

## 6. Cube-player collision blocking

1. **Cubes now physically block the player.** Walk toward an oncoming cube — you should be stopped from entering the tile it currently occupies (its logical grid position).
2. During the tumble animation, the cube's logical tile is one behind its visual position. You can walk "under" the visually-animating cube but cannot enter the tile it came from.
3. During the rest phase (cube visually landed), the cube's logical tile is one behind where it looks. Walking into the visual rest position is possible, but walking further back (into the logical tile) is blocked.

This is the I.Q.-faithful blocking model: cubes block their committed grid tile; visual/animation overlap is not blocked.

---

## 7. Focus-loss pause

1. **Click away** from the browser window (alt-tab, click another app, etc.).
2. The game should pause — a centered **PAUSED** label appears over the scene.
3. Game updates freeze (wave doesn't advance, player can't move, marks/triggers do nothing).
4. **Click back on the browser window.** Pause clears automatically and the game resumes.

---

## 8. Success criteria (check each)

- [ ] **Penalty counter increments** when a NORMAL or ADVANTAGE cube falls off the front edge.
- [ ] **Penalty counter does NOT increment** when a FORBIDDEN cube falls off.
- [ ] **Row deletion at 3 misses:** front row (bottom of screen) visibly disappears; counter resets from 2/3 to 0/3 (never shows 3/3).
- [ ] **Counter resets after deletion:** counter returns to 0 (or remainder if multiple thresholds crossed).
- [ ] **FORBIDDEN capture deletes front row:** capturing a FORBIDDEN cube immediately voids the front-most row (same outcome as 3 misses); penalty counter unchanged.
- [ ] **Avalanche penalties apply:** rows delete at end of avalanche rush (proportional to missed cubes during rush).
- [ ] **GAME_OVER fires:** tile under player becomes void → game freezes, GAME OVER overlay appears.
- [ ] **Cube collision blocking:** player cannot enter a tile occupied by a wave cube.
- [ ] **Pause overlay on focus loss:** PAUSED label appears; game freezes; resumes when window regains focus.
- [ ] **No crash or traceback** in the browser console (F12 → Console) during any of the above.

---

## 9. Edge cases to test

- **Stand in the back row:** let cubes escape until your row is deleted while you're standing on it. GAME_OVER should fire immediately.
- **Three escapes, one tick:** if an entire row falls off at once (7 cubes, all NORMAL/ADVANTAGE), `7 // 3 = 2` rows should be deleted and counter stays at `7 % 3 = 1`. (Debug row has 4 penalty-type cubes — can't trigger this with 1 row, but good to understand the math.)
- **FORBIDDEN escape:** let the FORBIDDEN cube (dark with red outline) fall off without capturing. Penalty counter must stay the same — FORBIDDEN doesn't penalize on miss.

---

## 10. Intentionally inert for this step (please do NOT report as bugs)

- **No visual flash or shake on row deletion.** Tiles just vanish. Audio + visual feedback for row deletion is Step 10 polish.
- **No restart after GAME_OVER.** The game freezes permanently. Step 9 adds wave progression and a restart path.
- **No GAME_OVER shake or audio.** The game just stops. Step 10 polish.
- **No row-restoration or Perfect bonus.** Step 9.
- **The wave does not respawn.** There is only one debug row. Step 9 handles wave progression.
- **Penalty counter has no visual drama** (no pulse or flash). Step 10 polish.
- **HUD line reads `Penalty: N/3`** — the `/ 3` denominator makes it machine-readable but doesn't explain what it means in plain English. Step 10 will add clearer labeling.

### Carry-forward from prior steps (still open)

- **Tumble animation feel** — heave/balance/thud easing → Step 10.
- **`MOVE_COOLDOWN = 0.08s`** — user-flagged as faster than I.Q. original → Step 10 retune.
- **Static perpendicular-priority** in `_first_held_direction` → revisit after Step 9.
- **Flash color type-tinting** → Step 10 polish.
- **Font-render caching in HUD** → Step 10 polish.
- **No "AVALANCHE" HUD label** → Step 10 polish.

---

## 11. Expert Panel findings (Phase A)

All four reviewers returned **APPROVED**.

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED | PENALTY_THRESHOLD=3, avalanche penalty application, and GAME_OVER timing all match I.Q. original. Collision blocking uses committed tile — correct for the I.Q. design. | No action required. |
| Code Quality | APPROVED | `type: ignore[comparison-overlap]` at `on_tick` line 149 is justified — mypy can't see `_apply_avalanche_penalties` mutates `_phase`. Structural fix (return bool from that method) possible in a future step. | No action for Step 6. |
| UX Tester | APPROVED with polish notes | Penalty counter clarity (`Penalty: N/3` lacks context), row deletion is silent (no shake/flash), GAME_OVER transition is abrupt. All flagged for Step 10 polish. | Deferred to Step 10. |
| Platform Engineer | APPROVED | `frozenset` creation per frame (max 175 elements) is negligible under WASM. `pygame.ACTIVEEVENT` works correctly in Pygbag. `delete_front_row` O(21) per call is trivial. | No action required. |

**Carry-forward panel deferrals tracked for their target step:**
- Step 7 — DETONATE wiring; trap-tile-refuses-mark policy revisit.
- Step 9 — wave progression; restart after GAME_OVER; row restoration.
- Step 10 — row deletion feedback (shake + flash); GAME_OVER intensity; penalty counter UX clarity; HUD polish; audio cue dispatch; font-render caching; `MOVE_COOLDOWN` retune; tumble easing.

*(FORBIDDEN full row-delete side effect resolved in Step 6 — no longer deferred to Step 8.)*

---

## 12. What to tell me after you review

Any one of:

- **"Step 6 approved, proceed to Step 7"** — I'll start Step 7 Phase A (Advantage cubes + 3×3 blast).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify before Step 7.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel on the fixes.
- **"I can't run it because [error]"** — paste the terminal/console output.

---

## 13. Files changed in Step 6 Phase A

```
grid_manager.py    (updated) — delete_front_row(): voids front-most (z=0-side) non-void row; clears mark if in that row.
game_manager.py    (updated) — _wave_penalty counter; wave_penalty property; _count_wave_misses (per-tick during WAVE_ACTIVE); _apply_avalanche_penalties (at WAVE_CLEARING); _check_game_over (GAME_OVER when player tile voided); on_tick updated; PENALTY_THRESHOLD imported; on_trigger(player) and _dispatch_capture(…, player) updated — FORBIDDEN capture now calls delete_front_row() + _check_game_over().
wave_manager.py    (updated) — blocked_tiles() -> frozenset[tuple[int, int]]: committed positions of all live cubes.
player.py          (updated) — wave_blocked param (frozenset | None) on try_move and update; blocks entry into cube-occupied tiles.
hud.py             (updated) — 6th stat line: "Penalty: N/3"; PENALTY_THRESHOLD imported; assert updated to 6.
main.py            (updated) — _drain_events returns tuple[bool, bool] with ACTIVEEVENT pause handling; _draw_pause_overlay; _draw_game_over_overlay; main loop gates updates on not-paused and not-GAME_OVER; wave.blocked_tiles() passed to player.update(); GamePhase imported.
constants.py       (updated) — camera elevation reduced ~22° (pos y: 18→12, z: -8→-16; FOV: 45→50°; target at grid-centre z=12); _GRID_CENTER_Z added; TODO(camera) note for future full rework.
```
