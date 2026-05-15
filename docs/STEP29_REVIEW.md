# Step 29 — Stage Intro Rolling Animation

**What Step 29 covers:**
- A new `GamePhase.STAGE_INTRO` plays at the start of every stage (including the
  first) after the player presses a key on the TITLE screen.
- During STAGE_INTRO, all pending grey cubes receive a cosine-hump Y-lift (tsunami
  wave) that travels from the back wall of the grid to the front of the formation.
- The crest starts off-screen behind z=39 and sweeps forward; the front row of
  wave 0 is explicitly clamped to zero — it never lifts off the floor.
- After `STAGE_INTRO_DURATION = 2.8 s`, `_begin_wave()` is called automatically,
  activating wave 0 and entering `WAVE_ACTIVE`.
- STAGE_INTRO **replaces** the first `WAVE_RISING` pause at each stage start.
  WAVE_RISING is still used for waves 2–4 within a stage.
- Player input and wave physics are frozen during STAGE_INTRO.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | `GamePhase.STAGE_INTRO`; `STAGE_INTRO_DURATION=2.8`; `INTRO_WAVE_AMPLITUDE=1.2`; `INTRO_HUMP_WIDTH=5.0` (replaces old `INTRO_WAVE_CYCLES`) |
| `game_manager.py` | `_intro_elapsed` field + `intro_elapsed` property; `wave_front_z` property; `update()` STAGE_INTRO branch; `on_title_advance()` → STAGE_INTRO; `_on_stage_complete()` → STAGE_INTRO; `_reset_state()` zeroes `_intro_elapsed` |
| `main.py` | `STAGE_INTRO` added to `_FOLLOW_CAMERA_PHASES` and `frozen`; `_intro_y_bias()` tsunami hump helper (updated from sine to cosine); `_build_cube_faces()` accepts `z_front_limit: int`; call site passes `game.wave_front_z`; new imports |

---

## 2. Phase flow

```
[TITLE] ──key press──> [STAGE_INTRO] ──2.8 s──> [WAVE_ACTIVE]
                                                       │ (after wave 0 clears)
                                              [WAVE_RISING] ──2 s──> [WAVE_ACTIVE]
                                                       │ (after wave 1–3 clear)
                                              [WAVE_RISING] ──2 s──> [WAVE_ACTIVE]
                                                       …
                                              [STAGE_CLEAR] ──key press──> [STAGE_INTRO]
```

---

## 3. Animation formula

```python
# Crest travels from behind the back wall to in front of wave 0's front row.
crest_start = (GRID_DEPTH - 1) + INTRO_HUMP_WIDTH        # off-screen behind z=39
crest_end   = wave_front_z     - INTRO_HUMP_WIDTH - 1.0  # off-screen in front of formation
z_crest = crest_start + intro_t * (crest_end - crest_start)  # travels back → front

dist_behind = float(gz) - z_crest   # positive = cube is behind (higher z than) crest

# Clamps:
if float(gz) <= float(z_front_limit):  y_bias = 0.0  # front row ALWAYS flat
elif dist_behind < 0.0:                y_bias = 0.0  # cube ahead of crest: flat
elif dist_behind > INTRO_HUMP_WIDTH:   y_bias = 0.0  # cube past the hump: flat
else:
    y_bias = INTRO_WAVE_AMPLITUDE * cos(π/2 × dist_behind / INTRO_HUMP_WIDTH)
```

**Key properties:**

- `intro_t = game.intro_elapsed / STAGE_INTRO_DURATION` — 0.0 → 1.0.
- At `t=0`: crest is at z=44 (off-screen); all cubes (z≤39) are ahead of it → all zero.
  No pop on entry.
- At `t=1`: crest is at z=26 (Stage 1) or z=22 (Stage 2); all real cubes have
  `dist_behind > INTRO_HUMP_WIDTH` → all zero. No pop on exit.
- `wave_front_z` = `_wave_z_starts[0] - _waves[0].row_count + 1`. For Stage 1 = 32,
  Stage 2 = 28.
- Front row `gz = wave_front_z` is **explicitly clamped to 0** regardless of the
  crest position — the "floor" constraint is unconditional.
- The hump spans 5 grid rows (INTRO_HUMP_WIDTH). Profile: peak at crest (dist=0),
  smoothly decays to zero at the trailing edge (dist=5).

---

## 4. How to test

### 4a. Tsunami animation plays on game start
1. Launch the game. TITLE screen shows grey pending cube wall.
2. Press any key.
3. A single wave-crest should roll through the cube wall — starting at the back
   edge (z=39) and sweeping toward the player side.
4. **The front row of grey cubes closest to the player must stay flat on the
   floor throughout the entire animation.** No cube at the wave-0 front row
   should ever lift off.
5. After ~2.8 s, wave 0 cubes flash their real colour and start tumbling.

### 4b. Player frozen during intro
1. During the animation, press arrow keys / WASD.
2. The player cube should not move.

### 4c. Between-stage intro plays
1. Clear all Stage 1 waves.
2. On the STAGE CLEAR screen, press a key to continue.
3. The Stage 2 cube wall appears and the tsunami animation plays again.
4. Again, the front row of Stage 2's wave 0 must stay flat.

### 4d. Wave 1–3 transitions use WAVE_RISING (not STAGE_INTRO)
1. Clear wave 0.
2. A 2-second WAVE_RISING pause (with banner) should show — no animation.
3. Wave 1 activates after the pause.

### 4e. Restart works correctly
1. Die (GAME OVER) and restart.
2. Title screen appears with the grey cube wall.
3. Press a key → STAGE_INTRO tsunami plays → wave 0 starts.

---

## 5. Success criteria

- [ ] Tsunami crest travels back-to-front over ~2.8 s
- [ ] Front row of wave 0 stays flat throughout the entire animation
- [ ] No visual pop when animation starts (t=0 all cubes at floor)
- [ ] No visual pop when animation ends and wave 0 activates (t=1 all cubes at floor)
- [ ] Player cannot move during animation
- [ ] Stage 2 intro plays after STAGE_CLEAR screen
- [ ] Within-stage wave transitions still use the 2-second WAVE_RISING pause
- [ ] Restart resets correctly (no stale intro_elapsed)

---

## 6. Expert panel findings

| Reviewer | Verdict | Findings |
|---|---|---|
| Code Quality | APPROVED | All 11 rules pass. `intro_t <= 1.0` assert is a genuine invariant (clamped by `update()`). Stale docstring on module header fixed (WAVE_RISING → STAGE_INTRO). `wave_front_z` asserts guard against pre-`start_first_wave` calls. |
| Vision Lead | APPROVED | Crest velocity ~(44−26)/2.8 ≈ 6.4 tiles/s. Cosine profile: smooth peak at crest, zero at edges. `dist_behind > HUMP_W` clamp guarantees all cubes are flat at t=1 (no pop). Explicit `gz ≤ z_front_limit → 0` ensures front row is unconditionally flat. |
| UX Tester | APPROVED | 2.8 s duration appropriate. Tsunami shape is visually distinct from multi-cycle sine — reads as a single swell from the horizon. Front row staying on the floor anchors the viewer's eye and makes the approach feel grounded. |
| Platform Engineer | APPROVED | ~5040 short-lived tuple allocations/s during 2.8 s animation — same as before; no change in overhead. `intro_t > 0.0` guard ensures zero overhead outside the animation. New `wave_front_z` property is O(1) with no allocation. |
