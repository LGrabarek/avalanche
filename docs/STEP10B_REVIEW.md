# Step 10B — User Review (Phase B)

**What Step 10B covers:** Restart flow from GAME OVER and STAGE CLEAR back to the
TITLE screen. Score display on the GAME OVER screen. "Press any key to restart" prompt
on both end screens.

---

## 1. Run the dev server

```bash
cd F:/Python/Avalanche
bash run_dev.sh
```

Serves on **http://localhost:8000**. First fresh-browser load ~30 s.
**Click the canvas** to focus keyboard events.

---

## 2. GAME OVER screen

When the player's tile is voided (platform deleted under them) the game freezes and
shows:

```
GAME OVER
Score: N
Press any key to restart
```

- "GAME OVER" in red.
- "Score: N" shows the partial score accumulated during the current play-through.
- "Press any key to restart" in grey.
- **Any keypress** (WASD, SPACE, X, Z, arrows — anything) resets the game and
  returns to the TITLE screen.

---

## 3. STAGE CLEAR screen

After Wave 4 clears the screen shows (unchanged from Step 9, plus restart prompt):

```
STAGE CLEAR
Score: N
I.Q.: N
Press any key to restart
```

- **Any keypress** resets the game and returns to the TITLE screen.

---

## 4. What is reset

After a restart:

| Item | State |
|---|---|
| Score / I.Q. | Reset to 0 |
| Grid | All 25 rows fully restored to PLATFORM (even if rows were deleted) |
| Player position | Back at spawn (centre, row 21) |
| Player state | Uncrushed |
| Wave cubes | Cleared immediately (no stale cubes during TITLE screen) |
| Penalty counter | Reset to 0 |
| Flashes / shake | Cleared |

---

## 5. Full restart test

1. Load the game. TITLE appears.
2. Press any key. `Wave 1 / 4` banner appears for 2 s.
3. Wave 1 cubes appear. Let them all fall without capturing anything.
   - Three misses delete a row. Let the row deletion kill you (or just let all
     cubes fall and keep going to GAME OVER via platform erosion).
4. When GAME OVER appears: note the Score, then press any key.
5. **TITLE screen** appears — dark veil, large "AVALANCHE" text.
6. Press any key again. `Wave 1 / 4` banner appears.
7. Verify: the **platform is fully intact** (no voided rows), the **player is at spawn**,
   the **score starts from 0** in the HUD.

---

## 6. STAGE CLEAR restart test

1. Play through all four waves (let cubes fall — fastest path to STAGE CLEAR).
2. When **STAGE CLEAR** appears with score and I.Q., press any key.
3. TITLE screen appears. Press any key.
4. `Wave 1 / 4` banner appears — a fresh Stage 1 game begins.

---

## 7. Success criteria

- [ ] **GAME OVER shows the score** — the player's partial score is visible.
- [ ] **STAGE CLEAR still works** — score and I.Q. display unchanged from Step 9.
- [ ] **"Press any key to restart"** visible on both GAME OVER and STAGE CLEAR.
- [ ] **Any key restarts** — WASD, SPACE, X, Z, Enter, arrows all work.
- [ ] **Returns to TITLE** — not directly to wave 1; the TITLE overlay appears first.
- [ ] **Grid fully restored** — all rows are PLATFORM after restart (verify by
      letting the front rows get deleted, then restarting and confirming the
      platform looks complete).
- [ ] **Score resets** — HUD shows `Score: 0` after restart.
- [ ] **No stale cubes** — during TITLE and the 2 s WAVE_RISING banner, no cubes
      from the previous game are visible.
- [ ] **No crash or traceback** in the browser console across multiple restarts.

---

## 8. Intentionally inert for this step (do NOT report as bugs)

- **No transition animation** — GAME OVER / STAGE CLEAR disappears instantly on
  keypress and TITLE appears the next frame. A brief hold or fade is planned for
  later polish.
- **No audio** — still deferred; requires external assets and browser autoplay gating.
- **No veil behind GAME OVER text** — the text renders directly over the frozen 3D
  scene. The TITLE and WAVE_RISING overlays have a dark veil; GAME OVER does not
  yet. Future polish item.

---

## 9. Expert Panel findings (Phase B)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED | Restart-to-TITLE is faithful to I.Q. original. Score shown on GAME OVER matches original UI. Observation: no veil behind GAME OVER text — deferred to future polish. | No action. |
| Code Quality | APPROVED | Panel suggested removing the explicit `wave.reset_for_new_wave()` call from `on_restart_key` as "redundant" since `_spawn_wave` also calls it. This was **incorrect** — without it, stale cubes from the previous game remain in the wave list and are rendered during the TITLE screen and WAVE_RISING pause. The explicit early reset is necessary for visual correctness. Explanatory comment added to the code. | Call retained; comment explains why both calls are needed. |
| UX Tester | APPROVED | "Press any key to restart" is clear and correctly positioned below the result. Two-step flow (restart → TITLE → keypress → wave) is consistent with initial game start. Note: transition is abrupt (instant snap to TITLE with no hold) — deferred to polish. | No action. |
| Platform Engineer | APPROVED | Object mutation (reset in place) preferred over object recreation in WASM — avoids GC pauses. Reset is synchronous and completes within one frame. No async safety issues. | No action required. |

---

## 10. What to tell me after you review

Any one of:

- **"Step 10 approved, proceed to Step 11"** — I'll start PWA packaging (manifest,
  service worker, icons, Pygbag HTML template).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel.

---

## 11. Files changed in Step 10B

```
grid_manager.py   reset(): restore all tiles to PLATFORM, clear mark.

player.py         reset(): return to spawn, uncrush, zero cooldown.
                  Raises ValueError if grid is not intact (caller must call
                  grid.reset() first).

effects.py        reset(): clear all flashes and shake state.

game_manager.py   on_restart_key(player): resets grid/wave/effects/player/
                  self, then calls start_first_wave → TITLE phase.
                  _reset_state(): zeroes all per-game fields (score, iq,
                  phase, penalties, wave counters). Called from on_restart_key.
                  Module docstring updated for Step 10B.

main.py           _drain_events(): GAME_OVER/VICTORY any-key → on_restart_key.
                  _draw_game_over_overlay(): now takes game: GameManager;
                  shows score and "Press any key to restart".
                  _draw_victory_overlay(): added "Press any key to restart"
                  as 4th line; assert updated from 3 to 4 lines.
                  Call site updated to pass game to _draw_game_over_overlay.

docs/STEP10B_REVIEW.md  (this file)
```
