# Step 9 — User Review (Phase B)

**What Step 9A covers:** Wave progression, Perfect bonus, I.Q. scoring, and VICTORY overlay.

Changes applied in Phase A:

1. **4-wave Stage-1 sequence** — `wave_data.py` defines the four hand-crafted puzzle waves
   (`STAGE_1_WAVES`). Each wave spawns with a 50% random X-axis mirror, so column
   positions may differ from the layouts below.

2. **Automatic wave advancement** — when all capturable cubes are gone the game
   transitions directly to the next wave (`_on_wave_cleared`). No manual reset needed.

3. **Perfect detection** — a wave is Perfect when the player took no avalanche, captured
   no FORBIDDEN cube, and let no NORMAL/ADVANTAGE fall off. On Perfect, a step-efficiency
   bonus is added (up to 10,000 pts) and the front-most voided row is restored.

4. **VICTORY overlay** — after Wave 4 clears, the game freezes and shows:
   ```
   STAGE CLEAR
   Score: N
   I.Q.: N
   ```
   The I.Q. figure is computed from final score + surviving-row bonus × Stage-1 multipliers.

5. **HUD wave counter** — stat block line 7: `Wave: N/4`.

---

## 1. Run the dev server

```bash
cd /f/Python/Avalanche
bash run_dev.sh
```

Serves on **http://localhost:8000**. First fresh-browser load ~30 s.
**Click the canvas** to focus keyboard events.

---

## 2. Wave layout reference

Each wave spawns at z=24 (back row) and z=23 (front row of the wave). Because
of the random 50% mirror, columns may be left–right flipped vs. the table below.
Use the cube color/outline to identify type regardless of column.

**Wave 1 — Intro (7 NORMAL, ideal 14 steps)**

```
z=24:   N  .  N  .  N  .  N     (cols 0,2,4,6)
z=23:   .  N  .  N  .  N  .     (cols 1,3,5)
```

**Wave 2 — First ADVANTAGE (8 NORMAL + 1 ADVANTAGE, ideal 13 steps)**

```
z=24:   N  N  .  A  .  N  N     (cols 0,1,3,5,6; ADVANTAGE at col 3)
z=23:   N  .  N  .  N  .  N     (cols 0,2,4,6)
```

**Wave 3 — FORBIDDEN introduced (6 NORMAL + 2 ADVANTAGE + 1 FORBIDDEN, ideal 14 steps)**

```
z=24:   N  A  .  F  .  A  N     (ADVANTAGE at 1,5; FORBIDDEN at 3)
z=23:   N  .  N  .  N  .  N     (cols 0,2,4,6)
```

**Wave 4 — Full challenge (8 NORMAL + 2 ADVANTAGE + 2 FORBIDDEN, ideal 16 steps)**

```
z=24:   A  N  F  N  F  N  A     (ADVANTAGE at 0,6; FORBIDDEN at 2,4)
z=23:   N  N  .  N  .  N  N     (cols 0,1,3,5,6)
```

---

## 3. Wave progression test (basic)

This verifies that advancing through all four waves works without errors.

1. Load the game. HUD shows **`Wave: 1/4`**. Wave 1 cubes begin tumbling.
2. Let all cubes fall off without capturing anything. Penalty rows may be deleted
   but that is fine for this test — we just need the wave to clear.
3. When the last cube drops, the HUD should show **`Wave: 2/4`** and fresh Wave 2
   cubes appear at the back row.
4. Repeat through waves 2, 3, and 4.
5. After Wave 4 clears, the **STAGE CLEAR** overlay appears.

**Expected per wave transition:**
- Cubes counter resets to the new wave's cube count.
- Penalty counter resets to 0.
- Player is uncrushed (if they were crushed in the previous wave, they stand upright again).
- Any active mark from the previous wave is cleared.

---

## 4. Perfect wave test (single wave)

A Perfect wave requires **all three conditions** to hold simultaneously:

| Condition | Meaning |
|-----------|---------|
| No avalanche | Player was never crushed |
| No FORBIDDEN captured | Neither direct (X) nor blast (Z) triggered FORBIDDEN |
| Zero misses | Every NORMAL and ADVANTAGE cube was captured |

### Wave 1 Perfect (recommended starting point)

Wave 1 is all-NORMAL, so no FORBIDDEN risk and no blast mechanics to worry about.

1. Start the game. Wait for Wave 1 to begin.
2. Mark and capture every cube as it arrives in rest phase. You must capture all 7.
   - Mark: **SPACE** at the target column.
   - Capture: **X** or **Enter** during rest phase (blue cone gone, cube at rest).
3. Make sure no cube falls off the front edge — if the Penalty counter advances,
   Perfect is lost for this wave.
4. When the last cube is captured, verify:
   - **Score jumped by 10,000 pts** (or 5,000 / 2,500 if you used more steps than
     the ideal — see §7 scoring reference).
   - If the platform had any voided rows (from previous waves), **one front row is
     restored** (platform grows wider). On a fresh game with an intact grid this
     restoration is a no-op; void a row first to observe it (see §6).

---

## 5. VICTORY overlay test

1. Complete all four waves (capture all cubes or let them fall — mix as desired).
2. After Wave 4 clears, the game freezes and the **STAGE CLEAR** overlay appears:
   ```
   STAGE CLEAR
   Score: N
   I.Q.: N
   ```
3. Verify:
   - The overlay text is visible and readable.
   - The game is frozen — WASD / SPACE / X / Z do nothing.
   - Both the score and the I.Q. numbers are non-negative.
   - The I.Q. number is smaller than the score (Stage-1 multiplier ≈ 0.06%).

---

## 6. Row restoration test (Perfect reward)

To clearly observe the row restoration:

1. Deliberately let a few NORMAL cubes fall off the front edge until the penalty
   counter reaches 3 and the front row is deleted. The grid shrinks visibly.
2. Note the current front row.
3. Now play the rest of that wave perfectly — capture every remaining cube, no
   further misses, no avalanche, no FORBIDDEN.
4. When the wave clears, **one voided row should be restored** — the platform
   extends forward again by one row.

> **Note:** Row restoration only happens when the wave is Perfect AND at least
> one row was previously voided. If the grid is fully intact, the call is a
> silent no-op.

---

## 7. Scoring reference

### Per-cube points

| Action                        | Score |
|-------------------------------|-------|
| Capture NORMAL (X)            | +100  |
| Capture ADVANTAGE (X)         | +100  |
| Capture FORBIDDEN (X)         | 0 (+ row deletion) |
| NORMAL hit by blast (Z)       | +200  |
| ADVANTAGE hit by blast (Z)    | +200  |
| FORBIDDEN hit by blast (Z)    | 0 (+ row deletion) |
| NORMAL/ADVANTAGE falls off    | +1 penalty (no score) |

### Perfect bonus (awarded when wave clears without avalanche, FORBIDDEN, or misses)

| Steps used vs. ideal                 | Bonus    |
|--------------------------------------|----------|
| ≤ ideal (most efficient)             | +10,000  |
| ideal + 1 … ideal + 20               | +5,000   |
| ideal + 21 … ideal + 40              | +2,500   |
| ideal + 41 or more                   | 0 *(row still restored)* |

One "step" = one mark (SPACE), one trigger (X/Enter), or one detonation (Z).

### I.Q. score (computed at VICTORY)

```
surviving_rows = number of non-void rows remaining in the grid
raw_total = final_score + surviving_rows × 1000
I.Q. = int(raw_total × 1.00 × 0.00060)
```

Stage-1 multipliers: difficulty × 1.00, I.Q. percentage × 0.00060 (i.e. 0.06%).

**Example:** score 12,500 with 24 intact rows →
`int((12,500 + 24 × 1,000) × 0.00060)` = `int(36,500 × 0.00060)` = `int(21.9)` = **21**.

---

## 8. Success criteria (check each)

- [ ] **Wave counter advances** correctly — HUD shows `Wave: 1/4` through `Wave: 4/4` as each
      wave clears.
- [ ] **Fresh cubes spawn** at the back row immediately after the previous wave clears,
      matching the expected cube count for each wave.
- [ ] **Per-wave state resets** on each wave start: penalty counter → 0, player uncrushed,
      previous mark cleared.
- [ ] **Perfect bonus awarded** when a wave is cleared with no avalanche, no FORBIDDEN, and
      no missed cubes.
- [ ] **Row restored on Perfect** — a previously-voided front row returns to PLATFORM after a
      Perfect wave (test with a pre-voided row as described in §6).
- [ ] **Perfect bonus NOT awarded** when any one of the three conditions is violated:
      avalanche, FORBIDDEN capture, or a missed cube.
- [ ] **STAGE CLEAR overlay** appears after Wave 4 clears; shows score and I.Q.
- [ ] **Game freezes on VICTORY** — no input is accepted after STAGE CLEAR appears.
- [ ] **I.Q. is plausible** — positive, smaller than the final score (0.06% factor), and
      reflects surviving rows.
- [ ] **No crash or traceback** in the browser console (F12 → Console) across all four
      waves.

---

## 9. Edge cases to test

- **Let a wave clear via avalanche** — get crushed, let the remaining cubes tumble off, and
  confirm the game advances to the next wave. The wave-cleared path is also reached through
  the AVALANCHE phase, not only through clean capture.
- **Wave 3 and 4 FORBIDDEN avoidance** — let the FORBIDDEN cube(s) fall off without
  capturing them. Penalty counter must NOT increment (FORBIDDEN fall-off is silent).
- **Near-front-edge play at wave end** — stand near z=22 or z=23 when the last cube of a
  wave clears. The wave transition should occur without a spurious GAME OVER or crash.
- **Full stage with zero Perfect waves** — play carelessly; let many cubes fall, get
  crushed repeatedly. Verify VICTORY still appears after wave 4 clears and I.Q. is at
  least 0.

---

## 10. Intentionally inert for this step (do NOT report as bugs)

- **No between-wave delay or animation** — the new wave spawns immediately after the
  previous one clears. A rising-cubes entrance animation is planned for Step 10.
- **No Perfect celebration** — no special sound, screen flash, or message on Perfect.
  Step 10 will add these.
- **No audio** — no tick metronome, no capture sound, no row-deletion crack. Step 10.
- **No VICTORY -> restart flow** — the game is frozen at STAGE CLEAR. Step 10 / 11.
- **No I.Q. display in HUD during play** — I.Q. only appears on the VICTORY overlay.
  Step 10 may show running I.Q. in the HUD.
- **Wave mirror is invisible** — you cannot tell from the UI whether the current wave is
  mirrored. This is intentional; the original I.Q. also gives no mirror indicator.

### Carry-forward from prior steps (still open)

- **Tumble animation feel** — heavy-cube easing → Step 10.
- **`MOVE_COOLDOWN = 0.08s`** — user-flagged as faster than I.Q. original → Step 10.
- **Static perpendicular-priority** in `_first_held_direction` → Step 9+.
- **Flash color type-tinting** → Step 10 polish.
- **Font-render caching in HUD** → Step 10 polish.

---

## 11. Expert Panel findings (Phase A)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED | All four wave patterns faithful to I.Q. Group.Dat structure. Perfect criteria match research document. Mirror flag doubles variety without extra data — exact match to original design. Comment derivations in `wave_data.py` for W2/W3/W4 did not match the ideal values embedded in code (doc hygiene, not logic error). | Comment blocks updated: W2 "= 13", W3 "= 14", W4 "= 16" are now accurate. |
| Code Quality | APPROVED (with required fixes) | **A:** `_calc_perfect_bonus` had no Rule-5 check on `ideal`; a zero or negative ideal would produce an incorrect bonus silently. **B:** `type: ignore[comparison-overlap]` on the WAVE_ACTIVE → `_on_wave_cleared` branch was missing its explanatory reason comment (Rule 10 / house style for suppression comments). | **A:** `assert ideal > 0` added to `_calc_perfect_bonus`. **B:** Comment extended to `# type: ignore[comparison-overlap]  # _count_wave_misses may mutate _phase to GAME_OVER`. Both fixes applied before shipping this review doc. |
| UX Tester | CONCERNS (all deferred to Step 10) | No-feedback wave transition may disorient player; Between-wave delay + rising-cubes animation is the correct fix → Step 10. Perfect condition is invisible during play (player doesn't know if they're on track) → Step 10 HUD indicator. Testing instruction to stand near z=22–23 at wave end covers a real edge case. Step 10 commitment needed: Perfect celebration and VICTORY screen design. | All concerns are Step 10 scope. Documented in §9 edge cases and §10 inert items. |
| Platform Engineer | APPROVED | `random.random()` seeded by OS entropy per CPython / WASM default — acceptable for cosmetic mirror flip. `reset_for_new_wave` tick-elapsed reset means first tick of new wave fires after a full 1.2s interval even with instant transition — no race on dt budget. No WASM / Pygbag compatibility issues. | No action required. |

---

## 12. What to tell me after you review

Any one of:

- **"Step 9 approved, proceed to Step 10"** — I'll start Step 10 Phase A (HUD polish,
  Perfect celebration, between-wave animation, VICTORY screen, audio metronome).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel.
- **"I can't run it because [error]"** — paste the terminal/console output.

---

## 13. Files changed in Step 9A

```
wave_data.py      (new) — Four Stage-1 WaveData objects (STAGE_1_WAVES tuple).
                           WaveData class: rows, ideal_steps, spawn_positions(mirror),
                           target_cube_count. Comment derivations corrected.

wave_manager.py   (updated) — reset_for_new_wave(): clears cubes, resets tick timer
                               and tick interval for a clean wave start.

grid_manager.py   (updated) — restore_front_row(): inverse of delete_front_row;
                               restores the first all-void row to PLATFORM.
                               Used for Perfect reward.

game_manager.py   (updated) — start_first_wave(player, waves): initializes the wave
                               sequence and spawns wave 0.
                               _spawn_wave(player): resets all per-wave state and
                               spawns cubes with 50% random mirror.
                               _on_wave_cleared(player): checks Perfect, awards
                               bonus, restores row, advances or enters VICTORY.
                               _calc_perfect_bonus(actual, ideal): 4-tier bonus table.
                               _calculate_final_iq(): score + row bonus × multipliers.
                               Step counting added to try_mark, on_trigger, on_detonate.
                               wave_index / wave_count / iq_score properties.
                               on_tick: WAVE_ACTIVE branch now calls _on_wave_cleared
                               directly when wave.cube_count == 0.

hud.py            (updated) — 7th stat line: "Wave: N/4". Assert updated to 7 lines.

main.py           (updated) — game.start_first_wave(player, STAGE_1_WAVES) replaces
                               the debug spawn. frozen flag includes GamePhase.VICTORY.
                               _draw_victory_overlay(screen, font, game): STAGE CLEAR
                               overlay with score and I.Q. readout.

docs/STEP9_REVIEW.md  (this file)
```
