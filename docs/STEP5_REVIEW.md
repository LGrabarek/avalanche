# Step 5 — User Review (Phase B)

**What Step 5 covers:** crush detection, pre-crush telegraph, avalanche phase, screen shake, and missed-normal penalty counting. This is the first step where the game can *punish* the player.

**What's new vs. Step 4:** getting hit by a cube squashes the player flat and turns it dark red; the wave accelerates dramatically and the screen shakes; marks and triggers are blocked during avalanche; missed NORMAL/ADVANTAGE cubes accumulate a penalty counter (used by Step 6's row deletion). There is no visual warning before the crush — the player must anticipate incoming cubes themselves.

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

On load: same as Step 4 — grid, player at `(3, 1)`, 7 debug cubes tumbling from the back row on a 1.2s tick.

The `Score: 0  Mark: ---` HUD line is still there. You are watching for the new behaviors below.

---

## 3. Crush and avalanche

1. **Stand in a column and let a cube roll into you.** There is no warning.
2. Immediately after the tick that delivers the cube:
   - **Player squashes flat** (collapses to ~15% of normal height) and turns dark red.
   - **Screen shakes** for ~0.6 seconds (±10px Lissajous oscillation, decays to zero).
   - **Wave accelerates** to ~0.15s per tick (was 1.2s — 8× faster). You should see the remaining cubes rushing forward rapidly.
   - **Mark is cleared** if one was active.
3. While in avalanche mode:
   - Player cannot move (WASD/arrows are locked out).
   - SPACE (mark) and X/Enter (trigger) do nothing.
4. The avalanche ends when all cubes have fallen off the front edge — the wave empties and the phase transitions internally to WAVE_CLEARING (no visible change yet — that's Step 6).

**Expected HUD:** The HUD `Tick:` value updates to ~0.15 during avalanche (you can see it in the top stat block). Score display is unchanged.

---

## 4. Success criteria (check each)

- [ ] **Player always blue:** the player cube stays blue at all times until the moment of crush — there is no warning color change.
- [ ] **Crush → squash:** letting the cube reach you squashes the player to a thin flat slab (clearly visible collapse) and changes color to dark red.
- [ ] **Screen shakes** on crush and settles to zero within ~0.6 seconds. The shake does not affect the HUD text (HUD stays still; only the 3D scene shakes).
- [ ] **Wave accelerates** after crush: you can see cubes rushing forward much faster (sub-second ticks).
- [ ] **Player frozen:** after crush, WASD/arrows do nothing. Player stays on the tile it was on when crushed.
- [ ] **Marks/trigger blocked:** SPACE and X/Enter do nothing during avalanche (no mark appears, no flash fires).
- [ ] **Avalanche clears:** watch the wave finish — all remaining cubes fall off the front edge. Game continues running (player stays squashed, phase is internally WAVE_CLEARING — visible change in Step 6).
- [ ] **No crash or traceback** in the browser console (F12 → Console) during any of the above.

---

## 5. Edge cases to test

- **Dodge by moving sideways:** while a cube is tumbling in your column, move to a different column before it reaches the halfway point of its tumble. The player should stay blue and the cube should pass safely.
- **No capture escape:** mark the tile in front of you and attempt to trigger while the cube is tumbling toward your tile. The crush fires mid-tumble (before the rest window opens), so the capture should NOT save you — you will be crushed regardless.
- **Multiple cubes in the same column:** after the first row clears, subsequent rows approach the same column. Each should trigger the crush if you stay in place.

---

## 6. Intentionally inert for this step (please do NOT report as bugs)

- **Player can walk through wave cubes.** In I.Q. the cubes are solid obstacles; the player should be blocked from stepping into a tile that contains a cube. This is a known gap — cube collision blocking is tracked in `PLAN.md` Step 6 and will be wired into `Player.try_move()` in a future step.
- **No "AVALANCHE" label on the HUD.** The HUD doesn't yet display the phase name. *Step 10 polish.*
- **No "CRUSHED" screen flash or audio.** The squash + shake is the only feedback. *Audio cue lands in Step 10.*
- **No movement-locked indicator.** Keys silently do nothing when crushed. *Step 10 polish.*
- **Penalty counter not yet visible.** Missed NORMAL/ADVANTAGE cubes during avalanche increment an internal counter (`game.avalanche_penalty`) but nothing displays it. *Step 6 wires row deletion against this counter.*
- **WAVE_CLEARING has no visible effect.** When the wave empties the game internally transitions to WAVE_CLEARING but nothing visually changes — no new wave spawns, no score bonus, no row deletion. *Step 6 adds row deletion; Step 9 adds wave progression.*
- **The wave does not respawn.** There is only one debug row and it does not cycle. *Step 9 handles wave progression.*

### Carry-forward from prior steps (still open)

- **Tumble animation feel** — heave/balance/thud easing → Step 10.
- **`MOVE_COOLDOWN = 0.08s`** — user-flagged as faster than I.Q. original → Step 10 retune.
- **Static perpendicular-priority** in `_first_held_direction` → revisit after Step 9.
- **Flash color type-tinting** → Step 10 polish.
- **Font-render caching in HUD** → Step 10 polish.

---

## 7. Expert Panel findings (Phase A)

All four reviewers returned **APPROVED**. One minor docstring clarification was applied inline.

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED | Crush/avalanche speed, telegraph timing, penalty logic, and WAVE_CLEARING state all faithful to I.Q. design. Phase machine ready for Steps 6–9. | No action required. |
| Code Quality | APPROVED | One docstring improvement: `on_tick` was ambiguous about phase-dependent behavior. | **Fixed:** `on_tick` docstring now explicitly describes WAVE_ACTIVE and AVALANCHE branches. |
| Code Quality | | All Power-of-Ten rules satisfied; modularity clean; edge cases (front row, back row, wave emptiness, penalty ordering) all handled correctly. | No action. |
| UX Tester | APPROVED with polish notes | Telegraph contrast (red vs. blue-gray) is legible. Crush squash + shake are clear failure feedback. Gaps: no HUD phase label, no movement-locked indicator, silent mark-blocking during avalanche. | All flagged for Step 10 polish — out of scope for Step 5. |
| Platform Engineer | APPROVED | `scene_surf` double-blit pattern is standard Pygbag idiom; `sin`/`cos` in `shake_offset()` negligible overhead (~1µs at WASM 3–5× penalty); DT_CLAMP=0.1 vs AVALANCHE_TICK_INTERVAL=0.15 margin is sufficient; O(n) `cube_at()` scans acceptable at n≤175. | No action required. |

**Carry-forward panel deferrals tracked for their target step:**
- Step 6 — penalty counter threshold → row deletion.
- Step 7 — DETONATE wiring; trap-tile-refuses-mark policy revisit.
- Step 8 — FORBIDDEN full row-delete side effect.
- Step 10 — HUD phase label; movement-locked indicator; mark-blocking visual; audio cue dispatch; font-render caching; `MOVE_COOLDOWN` retune; tumble easing.

---

## 8. Known dev-tooling quirks (carry-over)

- Use **`http://localhost:8000`**, not `http://0.0.0.0:8000`.
- Port 8000 squatter: Windows `netstat -ano | findstr :8000` → `taskkill /F /PID <PID>`.
- WSL2 localhost forwarding via `wslrelay.exe` works.
- Hidden-tab rAF pause: wave correctly pauses while tab is hidden.

---

## 9. What to tell me after you review

Any one of:

- **"Step 5 approved, proceed to Step 6"** — I'll start Step 6 Phase A (penalty threshold + row deletion).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify before Step 6.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel on the fixes.
- **"I can't run it because [error]"** — paste the terminal/console output.

---

## 10. Files changed in Step 5 Phase A

```
constants.py       (updated) — AVALANCHE_TICK_INTERVAL=0.15; CRUSH_TUMBLE_THRESHOLD=TUMBLE_REST_FRACTION/2; PLAYER_CRUSH_COLORS/EDGE (no telegraph colors).
cube_data.py       (updated) — PlayerVisual class (NORMAL/CRUSHED only); scale_y param in get_player_vertices; visual dispatch in get_player_faces.
player.py          (updated) — _crushed state; is_crushed property; crush() method; update() early-return guard.
wave_manager.py    (updated) — tick_interval setter (validates > 0); _last_dropped list populated in _advance_tick; last_dropped property; capturable_at updated (already in Step 4).
game_manager.py    (updated) — _phase + _avalanche_penalty state; check_mid_tumble_crush() per-frame; on_tick(); _trigger_avalanche(); _count_avalanche_misses(); TriggerOutcome.BLOCKED; phase guards on try_mark/on_trigger.
effects.py         (updated) — trigger_shake(amplitude, duration); shake_offset() → tuple[int,int]; shake state advanced in update().
main.py            (updated) — scene_surf allocated once; tick_fired → game.on_tick() wired; game.check_mid_tumble_crush() per-frame; player_visual (CRUSHED/NORMAL only); _build_player_faces gains visual+scale_y; scene blit with shake offset; HUD draws to screen (stays fixed).
wave_manager.py    (updated) — tick_interval setter resets tick_elapsed when new interval < current elapsed (prevents overshoot assertion on mid-tumble crush).
```
