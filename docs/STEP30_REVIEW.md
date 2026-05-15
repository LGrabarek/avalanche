# Step 30 — Stages 3–10 Full Progression

**What Step 30 covers:**
- Adds 8 new stages (Stages 3–10) to `wave_data.py`, completing the 10-stage
  game arc.
- Extends `IQ_DIFFICULTY_MULTIPLIERS` from 5 to 10 entries (1.00 → 2.35).
- Extends `STAGE_AVALANCHE_TICK_INTERVALS` from 2 to 10 entries.
- Updates the `GRID_DEPTH` comment to document Stages 3–10 layout bounds.
- The existing `GameManager` machinery (`_on_stage_complete`, `_calculate_final_iq`,
  `_cur_tick_interval`, `_cur_avalanche_tick_interval`) was already designed for
  N stages — no game-logic changes required.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | `IQ_DIFFICULTY_MULTIPLIERS` → 10 entries; `STAGE_AVALANCHE_TICK_INTERVALS` → 10 entries; GRID_DEPTH comment updated. |
| `wave_data.py` | Module docstring updated; Stages 3–10 wave data added (44 new waves); `STAGES` tuple extended to 10 entries. |

---

## 2. Stage layout

| Stage | Waves | Rows/wave | Total rows | wave_front_z | Gap from player |
|-------|-------|-----------|------------|--------------|-----------------|
| 1     | 4     | 2         | 8          | 38           | 17              |
| 2     | 4     | 3         | 12         | 37           | 16              |
| 3     | 4     | 4         | 16         | 36           | 15              |
| 4–5   | 5     | 3         | 15         | 37           | 16              |
| 6–10  | 6     | 3         | 18         | 37           | 16              |

All stages fit comfortably within `GRID_DEPTH=40`. `wave_front_z` is determined
by `_wave_z_starts[0] - _waves[0].row_count + 1`, which `game_manager.py`
computes dynamically — no hardcoded per-stage z values in the engine.

---

## 3. Difficulty scaling

### Wave tick speed (TICK_SPEED_DECAY = 0.9, applied per two stages)

| Stage pair | Tick interval |
|------------|--------------|
| 1–2        | 1.200 s      |
| 3–4        | 1.080 s  (−10 %) |
| 5–6        | 0.972 s  (−19 %) |
| 7–8        | 0.875 s  (−27 %) |
| 9–10       | 0.787 s  (−34 %) |

### Avalanche tick speed

| Stage | Avalanche interval |
|-------|--------------------|
| 1     | 0.15 s             |
| 2     | 0.12 s             |
| 3–10  | 0.11 s (≫ DT_CLAMP=0.1) |

### IQ multiplier

Stages 1–10: 1.00 → 1.25 → 1.33 → 1.45 → 1.50 → 1.65 → 1.80 → 1.95 → 2.15 → 2.35.
Each stage contributes more to the final IQ score.

### Pattern difficulty (waves per stage / F density)

| Stage | Max F/row | ideal_steps range | Notes                                |
|-------|-----------|-------------------|--------------------------------------|
| 3     | 2         | 35–53             | 4-row waves; F only in back/mid rows |
| 4     | 2         | 24–38             | 5 waves; F in all rows from W4       |
| 5     | 2         | 20–33             | F in all rows every wave             |
| 6     | 2         | 19–30             | 6 waves; tight blast chains required |
| 7     | 3         | 20–29             | Alternating F/N rows appear          |
| 8     | 4         | 20–24             | Dense alternating 4F rows appear     |
| 9     | 4         | 19–22             | Two consecutive 4F rows per wave     |
| 10    | 4         | 19–22             | Hardest patterns; expert chaining    |

---

## 4. Design rules obeyed by all new wave rows

1. **ADVANTAGE blast safety:** In every row, each ADVANTAGE cube is at least 2
   columns away from any FORBIDDEN cube. This prevents an accidental blast from
   triggering the FORBIDDEN `on_detonate: ROW_DELETE` penalty.
   (The one pre-existing exception is Stage 2 Wave 1 — inherited from the original
   Stage 2 design where intentional timing-dependent play is required.)

2. **z_start bounds:** `spawn_positions` validates `0 ≤ z_start < GRID_DEPTH`.
   All packed positions fall within z=22..39 for the new stages.

3. **ideal_steps > 0:** All 44 new waves have positive ideal_steps.

---

## 5. How to test

### 5a. Stage 3 transition
1. Complete all 4 waves of Stage 2 (or use a debug shortcut).
2. The **STAGE CLEAR** screen appears.
3. Press any key → Stage 3 starts with the tsunami animation.
4. Stage 3 has **4-row waves** — the grey pending-cube wall is visibly taller.
5. Complete all 4 waves → STAGE CLEAR → Stage 4 begins.

### 5b. Stage 3 wave structure
1. In Stage 3, confirm each wave has **4 rows** visible in the pending wall.
2. Wave 1 has a single green (ADVANTAGE) cube in the back centre row.
3. Wave 4 has ADVANTAGE cubes in all 4 rows and FORBIDDEN in 3 of them.

### 5c. Stage 4–5 (5 waves × 3 rows)
1. On reaching Stage 4, the wave count resets to 1/5 (HUD shows 5 total).
2. Confirm 5 distinct wave activations before STAGE CLEAR.
3. FORBIDDEN cubes appear in the middle row from Wave 2.

### 5d. Stages 6–10 (6 waves × 3 rows, maximum pressure)
1. Stage 6 shows wave count 1/6.
2. The pending cube wall extends to z=22 — only 1 tile gap from the player.
3. Stage 10 final wave contains **4F per row** in the last two rows.
4. Completing Stage 10 → **VICTORY** screen (not STAGE CLEAR).

### 5e. Tick speed increases
1. Play through to Stage 3: cubes tick noticeably faster (1.08 s vs 1.20 s).
2. Stage 5–6: ~0.97 s — similar urgency to a fast metronome.
3. Stage 9–10: ~0.79 s — demanding routing required.

### 5f. IQ score scales
1. Complete Stage 1 perfectly → note IQ score.
2. Complete Stage 5 perfectly → IQ should be significantly higher (×1.50
   difficulty multiplier vs ×1.00 for Stage 1).
3. Stage 10 has ×2.35 multiplier.

### 5g. Restart resets stage
1. Die on Stage 7.
2. Restart → returns to Stage 1 (IQ multiplier resets to 1.00).

---

## 6. Success criteria

- [ ] Game progresses through all 10 stages without crash
- [ ] Stage 3 displays 4-row waves
- [ ] Stages 4–5 display 5 waves (wave counter shows X/5)
- [ ] Stages 6–10 display 6 waves (wave counter shows X/6)
- [ ] Stage 10 Wave 6 completes → VICTORY (not STAGE CLEAR)
- [ ] Tick speed is perceptibly faster on Stage 5+ vs Stage 1
- [ ] IQ multiplier produces higher scores on later stages
- [ ] Restart from any stage returns to Stage 1

---

## 7. Expert panel findings

| Reviewer | Verdict | Findings |
|---|---|---|
| Code Quality | ✅ APPROVED | All 11 rules pass. 44 new waves — no function exceeds 50 lines; all row tuples are literals. WaveData constructor validates row width and depth, so malformed tuples fail loudly at import. No new mutable globals. **Flagged:** `_S2W1_ROWS` A@2/F@3 adjacency — correctly identified as pre-existing Stage 2 code (unchanged by Step 30, visible in `git diff`); intentional design where the player delays detonation until F advances 2 tiles. All 44 **new** Stage 3–10 rows maintain ≥2 col separation, confirmed by automated invariant test. |
| Vision Lead | ✅ APPROVED | Stage 3's 4-row depth visually distinguishes it from Stage 2. The 6-wave packing for Stages 6–10 creates genuine spatial pressure. ADVANTAGE blast safety constraint (≥2 col separation from F) gives reliable information: blasting is safe without Z-timing. S9-W6 and S10-W6 are deliberately near-identical, reinforcing the endgame "maximum pressure" aesthetic. |
| UX Tester | ✅ APPROVED | Difficulty curve is smooth: more rows (Stage 3), more waves (Stages 4–5), 6-wave max-pressure (Stages 6–10). F density escalates gradually across 10 stages. ideal_steps values decrease naturally (53 → 19) matching expected skill growth. Stage 8 W3→W4→W5 ideal_steps sequence (22→20→22) has a minor mid-stage dip — not a blocker given the tick speed is the dominant pressure. |
| Platform Engineer | ✅ APPROVED | Zero runtime allocation added. `STAGES` is a module-level constant tuple; all `WaveData` objects are created at import time. `_cur_avalanche_tick_interval` clamped-index lookup is O(1). ~9 KB of extra Python source compresses well in the Pygbag WASM bundle. No per-frame heap pressure. |
