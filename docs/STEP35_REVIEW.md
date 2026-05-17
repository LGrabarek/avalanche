# Step 35 — Wave variety: distinct W1 openers for Stages 4–10

## What changed

`wave_data.py` only. The Wave 1 (first wave) back-row pattern and `ideal_steps` for
each of Stages 4–10 were redesigned. All other waves (W2–W4) are unchanged.

| Stage | Width | New W1 signature | Old ideal | New ideal |
|-------|-------|-----------------|-----------|-----------|
| 4 | 7 | A@col1 (left-skewed), gap at col3 | 53 | 51 |
| 5 | 9 | Dual A@col2 & col6 (symmetric flanks) | 69 | 66 |
| 6 | 9 | A@col1 + A@col7 flanking F@col4 (centre trap) | 87 | 82 |
| 7 | 9 | All-Normal 5 rows — pure endurance | 83 | 90 |
| 8 | 9 | A@col0 (far-left corner) | 105 | 107 |
| 9 | 11 | F@col1 & col9 (near-edge traps) + A@col5 | 129 | 125 |
| 10 | 11 | Triple A@col2, col5, col8 (full-width chain) | 151 | 145 |

### Back-row layouts

```
Stage 4 (7-wide):  N  A  N  _  N  N  N     ← A at col1, gap at col3
Stage 5 (9-wide):  N  N  A  N  N  N  A  N  N  ← dual A at col2 & col6
Stage 6 (9-wide):  N  A  N  N  F  N  N  A  N  ← centre F flanked by A
Stage 7 (9-wide):  N  N  N  N  N  N  N  N  N  ← all Normal (repeated 5×)
Stage 8 (9-wide):  A  N  N  N  N  N  N  N  N  ← A at far-left corner
Stage 9 (11-wide): N  F  N  N  N  A  N  N  N  F  N  ← near-edge F traps
Stage 10 (11-wide):N  N  A  N  N  A  N  N  A  N  N  ← triple A, evenly spaced
```

### Design rules verified

- **Blast safety:** A/F distance ≥ 2 columns in every row ✓
  - Stage 6: |1-4|=3 and |7-4|=3 ✓
  - Stage 9: |5-1|=4 and |5-9|=4 ✓
- **Mirror-safe:** all patterns valid in both mirrored and unmirrored form ✓
- **Teaching arc:** each opener introduces exactly one new concept:
  Stage 4 → asymmetry; Stage 5 → scale-up; Stage 6 → hot centre;
  Stage 7 → pure pace; Stage 8 → edge efficiency; Stage 9 → lateral scan;
  Stage 10 → mastery chain.

### Stage 7 note (ideal_steps increase)

Stage 7 W1 was redesigned from "centre A + F in mid-1" (ideal 83) to all-Normal
(ideal 90). The higher ideal_steps is correct — an all-Normal wall has no blast
shortcuts, so every cube must be captured individually. The old value of 83 applied
to the previous pattern; it is not valid for the new all-Normal design.

### Engine verification (Vision Lead concerns resolved)

- **Stage 8 corner-A (`grid_x=0` blast):** `_mark_trap_area` explicitly bounds-checks
  each neighbor position (`if not self._grid.in_bounds(tx, tz): continue`). The trap
  at col 0 never sets a tile at col -1. Only N@col1 is captured by the blast, which
  is exactly what the ideal_steps comment states. ✓
- **Stage 10 triple-A interference:** Trap areas cover x=1-3, x=4-6, x=7-9 — no
  overlap (1-column gap between each A's area). `on_detonate` clears all traps before
  any blast fires; new traps from blasts defer to the next Z press. Clean. ✓

---

## How to test

### 1 — Desktop smoke test

```bash
cd F:/Python/Avalanche
uv run python main.py
```

Expected: game window opens, no console errors.

### 2 — Stage 4 opener: off-centre A, visible gap

1. Play to Stage 4 (clear Stages 1–3, or tweak `_stage_index` in a debug session).
2. Wave 1: the back row should show a cube at column 1 (second from left) with an
   **empty gap at column 3** — the back row is visibly asymmetric.
3. Mark and capture A@col1, press Z. Verify cols 0 and 2 are cleared by the blast.
4. Column 3 should remain empty (no cube ever there). Cols 4, 5, 6 are plain Normal.

### 3 — Stage 5 opener: dual symmetric blast

1. Advance to Stage 5 (first 9-wide stage).
2. Wave 1 back row: two green Advantage cubes visible at cols 2 and 6.
3. Capture and detonate A@col2: cols 1 and 3 should be cleared.
4. Capture and detonate A@col6: cols 5 and 7 should be cleared.
5. Only cols 0, 4, and 8 require individual capture. Confirm no cubes remain.

### 4 — Stage 6 opener: forbidden trap in centre

1. Advance to Stage 6.
2. Wave 1 back row: A at col 1, **red Forbidden at col 4 (centre)**, A at col 7.
3. **Do not step on col 4.** Capture A@col1 and detonate (cols 0, 2 cleared).
4. Capture A@col7 and detonate (cols 6, 8 cleared).
5. Capture N@col3 and N@col5 individually. F@col4 should roll off the edge cleanly.
6. Confirm no row deletion and wave clears as Perfect.

### 5 — Stage 7 opener: all Normal

1. Advance to Stage 7.
2. Wave 1: **all five rows are plain Normal — no green or red cubes anywhere.**
3. Confirm this feels harder in terms of raw speed than Stages 5/6 even though
   there are no Forbidden traps — every single cube must be marked individually.

### 6 — Stage 8 opener: corner Advantage

1. Advance to Stage 8. (Player may be clamped to 2 tiles from wave front.)
2. Wave 1 back row: A at **col 0 only** (far-left corner).
3. Capture A@col0 and detonate. Only **one cube** (N@col1) should disappear — the
   blast has no left neighbour. Cols 2–8 must be captured individually.
4. Contrast with earlier stages where a centre A cleared 2 neighbours.

### 7 — Stage 9 opener: near-edge Forbidden traps

1. Advance to Stage 9 (first 11-wide stage).
2. Wave 1 back row: **red Forbidden at cols 1 and 9** (near the edges),
   green Advantage at col 5 (centre).
3. During STAGE_INTRO (frozen countdown) look at the back row carefully —
   the F cubes are close to the edge and could be mistaken for Normal.
4. Let F@col1 and F@col9 roll off. Capture A@col5 + detonate (cols 4, 6 cleared).
5. Capture the 6 remaining Normal cubes individually.
6. Confirm no penalty row deletion.

### 8 — Stage 10 opener: triple A chain

1. Advance to Stage 10.
2. Wave 1 back row: **three green Advantage cubes at cols 2, 5, and 8.**
3. Capture A@col2 + detonate (cols 1, 3 cleared).
4. Capture A@col5 + detonate (cols 4, 6 cleared).
5. Capture A@col8 + detonate (cols 7, 9 cleared).
6. Only N@col0 and N@col10 (the corners) remain — capture individually.
7. Confirm 13-step back row, then face the 6 dense Normal rows.

### 9 — Browser / WASM test (optional but recommended)

```bash
bash run_dev.sh
# Open http://localhost:8000
```

All above behaviours should work identically in the browser.

---

## Expert panel summary

| Reviewer | Verdict | Notes |
|----------|---------|-------|
| Vision Lead | APPROVED WITH CONCERNS | All ideal_steps arithmetic verified ✓; blast bounds + triple-A interference verified safe in code ✓; Stage 7 W1→W2 cliff is design intent; mirror symmetry note (S5,S6,S9,S10 symmetric, mirror roll has no effect) logged for future tuning |
| Code Quality | APPROVED | Row widths consistent; `_X: None` typing clean; all ideal_steps > 0; ruff + mypy clean |
| Platform Engineer | APPROVED | Pure-data change; WASM-safe; no new imports or side effects |
| UX Tester | APPROVED WITH CONCERNS | Stage 9: first 11-wide grid + near-edge F is a double novelty. Mitigated by STAGE_INTRO preview. If Stage 9 shows high drop-off in playtesting, consider shifting F to cols 2 & 8 |

---

## Known advisories (non-blocking)

1. **Stage 7 W1→W2 difficulty step:** W1 is all-Normal (no A or F), but W2 immediately
   introduces flanking A + inner F in the back row. The gap between W1 and W2 is wider
   than in other stages. This is intentional — W1 is the "calm before the storm" opener,
   and Stage 7 is the last stage before the 6-row Stage 8 wall appears.

2. **Four W1 openers are mirror-symmetric (S5, S6, S9, S10):** The 50% mirror roll at
   spawn time produces no additional variety for these patterns. Stage 4 (left-skewed A)
   and Stage 8 (far-left corner A) do gain real variety from mirroring (A moves to the
   opposite side). Stage 7 is trivially symmetric. This is acceptable for v3; Step 42
   (wave arrangement variants) will address variety more broadly.

3. **Stage 9 double novelty:** See UX Tester findings above.

---

## Approval

Once you have verified the items above, reply **"Step 35 approved"** to proceed to
Step 36 (difficulty curve audit).
