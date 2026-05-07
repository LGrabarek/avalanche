# Step 20 — User Review (Stage 2 + STAGE_CLEAR Phase)

**What Step 20 covers (B5 — Additional stages):**
- **`GamePhase.STAGE_CLEAR`** — new phase entered after clearing all waves of a non-final
  stage. All gameplay is frozen; wave ticks are suppressed.
- **Stage 2 wave patterns** — four hand-designed waves in `wave_data.py`, harder than
  Stage 1 (more FORBIDDEN, denser rows, one 3-row wave). `STAGES` master tuple added.
- **Stage tracking** — `GameManager` gains `_stage_index`, `stage_index` property,
  `on_stage_clear_key()`, and `_on_stage_complete()`.
- **HUD** — "Stage: N" line added (8th stat, before the Wave line).
- **Stage-clear overlay** — `_draw_stage_clear_overlay()`: "STAGE N CLEAR / Score / Next: Stage N+1 / key prompt".
- **VICTORY overlay** — title changed from "STAGE CLEAR" (ambiguous) to "GAME CLEAR".
- **WAVE_RISING banner** — now shows "Stage N — Wave X / Y" to orient the player after a stage transition.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | Added `GamePhase.STAGE_CLEAR = "stage_clear"` |
| `wave_data.py` | Added `_S2W1`–`_S2W4` rows/ideals; `STAGE_2_WAVES`; `STAGES` master tuple |
| `game_manager.py` | `_stage_index` field; `stage_index` property; `on_stage_clear_key()`; `_on_stage_complete()`; `_on_wave_cleared()` branches on stage boundary; `_calculate_final_iq()` uses stage-indexed multipliers; `_reset_state()` resets `_stage_index`; `_do_restart()` simplified (no `waves` param, always uses `STAGES[0]`); `_MENU_BLOCKED` + `update()` extended to cover `STAGE_CLEAR` |
| `hud.py` | Added `("stage", f"Stage: {stage_num}")` as 7th stat; `assert len(stats) == 8`; `MAX_HUD_CACHE_ENTRIES = 9` |
| `main.py` | `STAGES` import; `start_first_wave(player, STAGES[0])`; `_draw_stage_clear_overlay()`; VICTORY title → "GAME CLEAR"; WAVE_RISING banner → "Stage N — Wave X / Y"; STAGE_CLEAR in `frozen` set and overlay dispatch; `on_stage_clear_key` in `_drain_events` |

No physics, scoring formula, capture mechanics, or existing wave data was changed.

---

## 2. Design details

### Stage flow

```
TITLE → WAVE_RISING → WAVE_ACTIVE → … → (last wave of Stage 1 clears)
  → STAGE_CLEAR (hold 2s) → player key → WAVE_RISING (Stage 2) → WAVE_ACTIVE → …
  → (last wave of Stage 2 clears) → VICTORY (hold 2s) → player key → TITLE
```

Restart (Esc → Restart or any key on GAME_OVER/VICTORY) always returns to Stage 1.

### Stage 2 wave patterns

| Wave | Layout | Capturable | Ideal |
|---|---|---|---|
| S2W1 | 2 rows: 4N+1A+1F / 4N (sparse) | 10 | 13 |
| S2W2 | 2 rows: 4N+2A+1F / 6N (dense) | 12 | 17 |
| S2W3 | 2 rows: 4N+3A / 4N (sparse) | 11 | 15 |
| S2W4 | 3 rows: 2N+2A+2F / 5N / 4N | 14 | 20 |

S2W4 is the first 3-row wave in the game. Row 2 spawns at z=22; `PLAYER_SPAWN_Z = 21`.
All rows are safely behind the player at spawn.

### Stage-clear overlay colors

```
"STAGE 1 CLEAR"            (100, 220, 100)  green — positive reward
"Score: {score}"           (220, 220, 220)  white
"Next: Stage 2"            (180, 180, 220)  muted blue
"Press any key to continue" dimmed until END_SCREEN_HOLD (2s), then (140,140,140)
```

### GAME CLEAR vs STAGE CLEAR

The VICTORY overlay (all stages complete) now reads "GAME CLEAR" in yellow `(255, 240, 100)`.
This is visually and lexically distinct from the green "STAGE N CLEAR" between-stage screen.

### Score carry-over

`_score` is NOT reset in `_on_stage_complete`. The running total persists through the
stage transition and is shown in the STAGE_CLEAR overlay. The VICTORY overlay shows the
same total + the final I.Q. calculation using Stage-2 multipliers
(`IQ_DIFFICULTY_MULTIPLIERS[1] = 1.25`, `IQ_PERCENTAGE_MULTIPLIERS[1] = 0.00055`).

---

## 3. How to test

### 3a. Stage 1 → Stage 2 transition

1. Run `bash run_dev.sh` → open `http://localhost:8000`.
2. Start a game and clear all four Stage 1 waves.
   - Fastest path: ignore the cubes and let them all drop off the front (they'll miss,
     triggering row deletions, but the wave eventually empties and advances).
   - Or play normally.
3. After Wave 4 clears, the **STAGE 1 CLEAR** overlay should appear (green title,
   current score, "Next: Stage 2", dimmed prompt).
4. Wait 2 seconds — the prompt brightens to grey.
5. Press any key. The STAGE_CLEAR overlay vanishes and the WAVE_RISING banner appears
   showing **"Stage 2 — Wave 1 / 4"**.
6. After 2 seconds the Stage 2 Wave 1 cubes spawn. Confirm the board is fresh (no
   voided rows carry over from Stage 1).

### 3b. Stage 2 wave verification

1. Complete Stage 1 and enter Stage 2 (or use turbo mode: hold F to advance waves faster).
2. Verify four distinct wave patterns appear — denser than Stage 1, with more FORBIDDEN cubes.
3. Stage 2 Wave 4 (the hardest) should spawn **three rows** simultaneously at z=24, z=23, z=22.
4. The player starts at z=21, safely in front of the three rows.

### 3c. GAME CLEAR screen

1. Complete all four Stage 2 waves.
2. The **GAME CLEAR** overlay should appear (yellow title, final Score, I.Q. score, restart prompt).
3. Confirm the title says "GAME CLEAR" — not "STAGE CLEAR".
4. Press any key after 2s → returns to TITLE → Stage 1 starts fresh.

### 3d. HUD Stage line

1. During Stage 1 gameplay, the HUD top-left block should show "Stage: 1".
2. After transitioning to Stage 2, the HUD should show "Stage: 2".

### 3e. Restart always returns to Stage 1

1. Get into Stage 2.
2. Open the Esc pause menu → Restart.
3. Confirm the game returns to TITLE and resets to Stage 1 (HUD "Stage: 1").

### 3f. No regressions

- Title screen, pause menu, GAME OVER screen all work as before.
- MARKED cone markers, player shadow, danger telegraph, checkerboard tiles still show correctly.
- PERFECT! bonus still works within Stage 2 waves.

---

## 4. Success criteria

- [ ] STAGE 1 CLEAR overlay appears after Wave 4 (green text, correct stage/score).
- [ ] 2-second hold before "Press any key" activates.
- [ ] After key press: WAVE_RISING banner shows "Stage 2 — Wave 1 / 4".
- [ ] Fresh grid at Stage 2 start (no voided rows from Stage 1).
- [ ] Stage 2 Wave 4 has three visible rows at spawn.
- [ ] GAME CLEAR overlay (not "STAGE CLEAR") appears after clearing all Stage 2 waves.
- [ ] I.Q. score shown on GAME CLEAR uses Stage-2 multipliers (≈ 1.25× Stage-1 value for same score).
- [ ] HUD shows "Stage: 1" / "Stage: 2" correctly.
- [ ] Restart from Esc menu or GAME OVER returns to Stage 1.
- [ ] No gameplay regression (scoring, captures, avalanche, Perfect bonus).

---

## 5. Expert panel findings (Step 20)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED (conditional) | VICTORY overlay "STAGE CLEAR" indistinguishable from STAGE_CLEAR overlay when player expects to keep going | Changed VICTORY title to "GAME CLEAR" |
| Vision Lead | APPROVED | STAGE_CLEAR green `(100,220,100)` matches ADVANTAGE cube color — minor palette collision, not blocking | No change (overlay covers board; no in-play confusion) |
| Code Quality | APPROVED | All Power of Ten rules satisfied; mypy --strict + ruff clean; assert/Rule-7/Rule-9 all correct | No change needed |
| UX Tester | APPROVED (conditional) | Same VICTORY title issue (confirmed) | Same fix |
| UX Tester | APPROVED (conditional) | Advisory: WAVE_RISING banner lacked stage context after stage transition | Added "Stage N — " prefix to wave label |
| Platform Engineer | APPROVED | All 7 boundary checks clean: re-entrancy safe, reset order correct, WASM budget safe, S2W4 validation correct, STAGES import-time safe, assert/ValueError downgrade safe, hold-threshold semantics correct | No change needed |
| Platform Engineer | APPROVED | Note: `_draw_stage_clear_overlay` uses `stage_index + 2` for "Next: Stage N" — assumes sequential stages. Safe now; revisit if/when Stage 3 is non-sequential | No change; noted for Step 21 |

---

## 6. What to tell me after you review

- **"Step 20 approved, proceed"** — move on to Step 21 (per-stage tick interval table, A2).
- **"Approved, plus this fix: [specific change]"** — apply and re-verify.
- **"Stage 2 too easy — bump difficulty"** — raise FORBIDDEN count or reduce ideal values.
- **"Changes needed: [X, Y, Z]"** — address and re-run panel.
