# Step 10 — User Review (Phase A)

**What Step 10A covers:**
- 4-phase tumble easing (heave → balance → thud → rest)
- TITLE screen on game start
- WAVE_RISING between-wave pause (2 s) with optional PERFECT! banner
- MOVE_COOLDOWN tuned from 0.08 s → 0.12 s

---

## 1. Run the dev server

```bash
cd F:/Python/Avalanche
bash run_dev.sh
```

Serves on **http://localhost:8000**. First fresh-browser load ~30 s.
**Click the canvas** to focus keyboard events.

---

## 2. TITLE screen

When the game loads, you should see the 3D grid in the background overlaid with a dark
semi-transparent veil containing:

```
    AVALANCHE                 ← large yellow/gold text
    Press any key to begin    ← small grey text below center
```

- **No cubes are tumbling yet.**
- **No player input is accepted** (WASD, SPACE, X, Z are all inert).
- Pressing **any key** dismisses the title and starts the 2-second WAVE_RISING pause.

---

## 3. WAVE_RISING between-wave pause

After pressing a key on the TITLE screen (and after each wave clears), a semi-transparent
banner appears in the center of the screen.

### Normal wave transition (no Perfect)
The banner shows only:
```
Wave 1 / 4
```
(or the appropriate wave number.)

### After a Perfect wave
The banner shows:
```
PERFECT!
Wave 2 / 4
```
"PERFECT!" is in gold. "Wave N/4" is in white below it.

The banner lasts **2 seconds**. During this time:
- Player **cannot move** (WASD inert).
- **No cubes are tumbling** (wave hasn't spawned yet).
- After 2 s the banner disappears and Wave N cubes appear at the back row.

---

## 4. MOVE_COOLDOWN tuning

The player auto-repeat speed has been slowed from 80 ms to 120 ms per step. This is
a subtle change — confirm that movement still feels responsive but slightly less
hair-trigger than before.

---

## 5. 4-phase tumble easing

Each cube tick (1.2 s total) now has four distinct phases:

| Phase | Fraction | Degrees | Description |
|-------|----------|---------|-------------|
| Heave | 0 → 40% (0.48 s) | 0° → 45° | Slow smoothstep, cube gains momentum |
| Balance | 40% → 48% (0.10 s) | 45° | Brief hold at the tipping point |
| Thud | 48% → 65% (0.20 s) | 45° → 90° | Fast quadratic fall |
| Rest | 65% → 100% (0.42 s) | 90° | Cube at rest — capture window |

**What to look for:**
- Cubes should **visibly hesitate** at 45° before falling.
- The **fall** from 45° to 90° should look noticeably faster than the rise to 45°.
- The cube should **sit still** for a noticeable window (0.42 s) after landing —
  this is when capture is valid.

The capture and crush mechanics are **unchanged**:
- Crush still fires at the 40% balance point (the cube passing vertical — same moment
  as before, now clearly visualised as the end of the heave phase).
- Capture is only valid during the rest phase (≥ 65% of the tick).

---

## 6. Full playthrough test

1. Load the game. **TITLE screen** appears.
2. Press any key. **WAVE_RISING** shows `Wave 1 / 4` for 2 s.
3. Wave 1 cubes appear. Play normally.
4. When the last Wave 1 cube falls/is captured, **WAVE_RISING** appears with:
   - `PERFECT!` + `Wave 2 / 4` if you captured all cubes with no avalanche/FORBIDDEN
   - `Wave 2 / 4` only otherwise
5. After 2 s, Wave 2 cubes appear. Continue through all 4 waves.
6. After Wave 4 clears, the **STAGE CLEAR** overlay (unchanged from Step 9) appears.

---

## 7. Edge cases to test

- **Focus loss during WAVE_RISING** — defocus the browser tab while the banner is up.
  The timer should **pause** (ACTIVEEVENT pause logic applies). Refocus → timer resumes.
- **Let all cubes fall without capturing** — simplest way to chain through all 4 waves.
  The WAVE_RISING banner should appear between each wave with no PERFECT!.
- **Perfect Wave 1** — capture all 7 NORMAL cubes (no misses, no avalanche). The
  WAVE_RISING banner after Wave 1 should show PERFECT! in gold.
- **Avalanche then wave clears** — get crushed, let remaining cubes tumble off. The
  WAVE_RISING banner should appear without PERFECT!, and the player should be
  **standing upright** (uncrushed) during the banner.

---

## 8. Success criteria (check each)

- [ ] **TITLE screen appears** on load — dark veil, large "AVALANCHE" text, press-any-key prompt.
- [ ] **Any key advances** from TITLE to WAVE_RISING.
- [ ] **No cubes tumble** during TITLE or WAVE_RISING — wave spawns after the timer.
- [ ] **Input blocked** during TITLE and WAVE_RISING (WASD, SPACE, X, Z all inert).
- [ ] **Wave counter correct** — banner shows `Wave 1/4` on first start, then `Wave 2/4` etc.
- [ ] **PERFECT! shown** in gold above the wave counter after a Perfect wave.
- [ ] **PERFECT! absent** after a non-Perfect wave (any miss, avalanche, or FORBIDDEN).
- [ ] **2-second pause** — banner visible for roughly 2 seconds before wave spawns.
- [ ] **Tumble feel** — visible heave hesitation at 45°, fast thud fall, clear rest window.
- [ ] **Movement slightly slower** — 120 ms auto-repeat is noticeable vs. old 80 ms.
- [ ] **No crash or traceback** in the browser console (F12 → Console).

---

## 9. Intentionally inert for this step (do NOT report as bugs)

- **No sound** — audio metronome, capture sound, row crack — Step 10B+.
- **No Perfect celebration beyond the banner** — no screen flash, no fanfare. Step 10B.
- **No VICTORY → restart** — game freezes on STAGE CLEAR. Step 11.
- **No per-wave delay animation** (rising cubes) — cubes appear instantly after the 2 s
  pause. A rising-entrance animation was deprioritized; Step 10B may revisit.
- **Static perpendicular priority** — carry-forward from Step 2 review.

### Carry-forward from prior steps (still open)

- **Camera rework** — platform scroll + angle — future stage.
- **Font-render caching in HUD** — Step 10 polish.
- **Flash color type-tinting** — Step 10 polish.

---

## 10. Expert Panel findings (Phase A)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED | 4-phase easing profile matches the heavy-cube feel documented in `feedback_tumble_feel.md`. Balance-point hold at 40–48% (≈0.10 s) is authentic. Thud ease-in from 45°→90° in 0.20 s reads as the weight the original had. | No action required. |
| Code Quality | APPROVED | All Power-of-Ten rules satisfied. `update(dt, player)` guard on `dt < 0` is the Rule-5 precondition. `WAVE_RISING_DURATION` in constants prevents the 2 s magic number. `_wave_rising_timer = max(0, ...)` clamps before the assert — ordering is correct. `_perfect_display` reset in `_spawn_wave` prevents stale True carrying to the next wave. | No action required. |
| UX Tester | APPROVED | TITLE screen provides clear game-start affordance. 2 s between-wave pause gives the player time to read the PERFECT! result before the next challenge. 120 ms move cooldown is noticeably less frantic. One note: the wave-rising banner shows "Wave N / 4" with the NEW wave number (correct — player is about to play wave N). | No action required; confirmed intentional. |
| Platform Engineer | APPROVED | `pygame.SRCALPHA` surface creation is Pygbag-compatible (uses SDL2 `SDL_BLENDMODE_BLEND`). `overlay_font = pygame.font.Font(None, 64)` uses the bundled freesansbold.ttf — no filesystem access. `game.update(dt, player)` called outside the `frozen` guard — correct; WAVE_RISING timer must tick even while player input is blocked. | No action required. |

---

## 11. What to tell me after you review

Any one of:

- **"Step 10 approved, proceed to Step 10B"** — I'll start 10B (audio, VICTORY restart, remaining polish).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel.
- **"I can't run it because [error]"** — paste the terminal/console output.

---

## 12. Files changed in Step 10A

```
constants.py      MOVE_COOLDOWN 0.08 → 0.12.
                  WAVE_RISING_DURATION = 2.0 (new).
                  TUMBLE_HEAVE_END = 0.40, TUMBLE_BALANCE_END = 0.48 (new).
                  TUMBLE_REST_FRACTION 0.55 → 0.65.
                  CRUSH_TUMBLE_THRESHOLD = TUMBLE_HEAVE_END (was REST/2).

cube_data.py      _lut_sin_cos(): replaced linear remap with 4-phase easing
                  (smoothstep heave → hold → quadratic thud). Imports
                  TUMBLE_HEAVE_END, TUMBLE_BALANCE_END from constants.

game_manager.py   start_first_wave(): enters GamePhase.TITLE instead of
                  spawning immediately.
                  on_title_advance(): TITLE → WAVE_RISING, sets timer.
                  update(dt, player): per-frame WAVE_RISING countdown.
                  perfect_display property: True after a Perfect wave.
                  _on_wave_cleared(): player.uncrush() + clear_mark() before
                  the between-wave pause; stores _perfect_display; transitions
                  to WAVE_RISING instead of spawning directly.
                  _spawn_wave(): resets _perfect_display = False.
                  Imports WAVE_RISING_DURATION.

main.py           _draw_title_overlay(screen, big_font, small_font): dark
                  veil + "AVALANCHE" title + press-any-key prompt.
                  _draw_wave_rising_overlay(screen, big_font, small_font,
                  game): semi-transparent banner; PERFECT! in gold if
                  game.perfect_display; wave counter.
                  _drain_events(): TITLE key → game.on_title_advance().
                  Main loop: game.update(dt, player) before frozen check.
                  frozen now includes TITLE and WAVE_RISING.
                  overlay_font = pygame.font.Font(None, 64) added.
                  Overlay dispatch extended for TITLE and WAVE_RISING.

docs/STEP10_REVIEW.md  (this file)
```
