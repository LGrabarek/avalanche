# Step 32 — Multi-file stage/wave/grid redesign

## What changed

### Design rules now in effect

| Rule | Value | Effect |
|------|-------|--------|
| Rows per wave | `[2,3,3,4,4,5,5,6,6,7]` (stages 1–10) | Earlier stages are shorter; later stages are deeper |
| Grid width per stage | `[7,7,7,7,9,9,9,9,11,11]` | Platform widens at stages 5 and 9 |
| Waves per stage | **Always 4** | Fixed count (was 4, 5, or 6) |
| Player-to-wave gap | `WAVE_FRONT_GAP = 4` | Player starts 4 clear rows from the first cube |
| Camera Y rise | 15 % per wave index | Eye-Y climbs from 7.8 (wave 0) to 11.3 (wave 3) to see deeper walls |

### Files modified
- `constants.py` — new grid-width/row-count tables, WAVE_FRONT_GAP, GRID_WIDTH=11, GRID_DEPTH=60
- `grid_manager.py` — `resize(new_width)` method; `__init__` accepts optional `width`
- `wave_data.py` — WaveData validation width-agnostic; mirror formula corrected;
  all 10 stages rewritten to exactly 4 waves with correct row counts and grid widths
- `game_manager.py` — `_compute_wave_z_starts` rewritten; resize calls at stage transitions
- `player.py` — spawn X = `grid.width // 2` (centre of active grid)
- `main.py` — GridManager init at stage-1 width; camera X tracks `(grid.width−1)×0.5`

---

## How to test

### 1 — Desktop smoke test

```bash
cd F:/Python/Avalanche
uv run python main.py
```

Expected: game window opens, title screen shows, no errors in console.

### 2 — Stage 1 basics

1. Press any key at the title screen → Stage Intro animation plays (~2.8 s).
2. Wave 1 starts: you should see **2 rows** of cubes at the far end of the grid.
3. Play through all 4 waves. Wave counts should be "1/4", "2/4", "3/4", "4/4".
4. After wave 4 clears → **Stage Clear** overlay appears → press key → Stage 2.

### 3 — Grid width expansion at Stage 5

1. Play through Stages 1–4 (7-wide grid, player at column 3).
2. At Stage 5 start: grid should visibly widen from 7 to **9 columns**.
   - Player recentres to column 4 of the 9-wide grid.
   - Camera X shifts smoothly to `(9−1)×0.5 = 4.0`.
3. Verify no out-of-bounds spawns or visual artefacts at the first wave.

### 4 — Grid width expansion at Stage 9

1. Continue to Stage 9.
2. Grid widens again from 9 to **11 columns**.
   - Player recentres to column 5.
   - Camera X shifts to `(11−1)×0.5 = 5.0`.
3. Stage 9 and Stage 10 both use 11-wide patterns; confirm cubes fill the full width.

### 5 — Row count escalation

| Stage | Rows per wave | You should see |
|-------|--------------|----------------|
| 1 | 2 | Very thin back wall (2 deep) |
| 2 | 3 | Three-row wall |
| 3 | 3 | Same depth as stage 2, harder patterns |
| 4 | 4 | Four-row wall |
| 5 | 4 | Four rows, 9-wide |
| 6 | 5 | Five-row wall |
| 7 | 5 | Same depth, harder patterns |
| 8 | 6 | Six-row wall |
| 9 | 6 | Six rows, 11-wide |
| 10 | 7 | Deepest wall (7 rows) |

### 6 — Camera Y rise

At Wave 3 of any stage the camera should be noticeably higher (more top-down) than at
Wave 0. The back rows of a 6 or 7-row wall should remain visible. If the back row
clips off the top of the screen at Stage 10 Wave 3, report that here (see panel note).

### 7 — Stage 2 Wave 1 — Forbidden tutorial

In Stage 2, Wave 1:
- One Advantage cube (col 2 from left, back row) and one Forbidden cube (col 5 from
  left, back row) are present.
- Capturing the Advantage should **not** explode the Forbidden — they are 3 columns apart.
- The Forbidden should fall off the back edge if you stand clear of it.

### 8 — Stage 2 Wave 3 — Triple-Advantage back row

- Three Advantage cubes fill alternating columns of the back row.
- Detonating any one of them should blast its two neighbours, which in turn capture
  the Normal cubes between them — the entire back row clears with 3 detonations.

### 9 — Restart from Stage 9+ resets to Stage 1

1. Reach Stage 9 or 10 (11-wide grid).
2. Open the Esc menu → Restart.
3. Confirm: grid returns to **7 columns**, player at column 3, Stage 1 starts.

### 10 — Browser / WASM test (optional but recommended)

```bash
bash run_dev.sh
# Open http://localhost:8000
```

All behaviours above should work identically in the browser. First load takes ~30 s
while Pygbag downloads CPython; subsequent loads are cached.

---

## Expert panel summary

| Reviewer | Verdict | Notes |
|----------|---------|-------|
| Vision Lead | APPROVED (after fixes) | S2W1 blast-safety BLOCKER fixed; S2W3 ideal corrected; header comments corrected |
| Code Quality | APPROVED (after fixes) | Same S2W1 fix; advisory on overview camera centering (hidden under overlays) |
| UX Tester | APPROVED | Two non-blocking concerns: cam_xz drift if intro shortened; Stage 10 back-row foreshortening — verify during testing |
| Platform Engineer | APPROVED | All 6 WASM criteria pass; no blockers |

---

## Known advisories (non-blocking)

1. **Overview camera X at stages 1–8:** The static TITLE/GAME_OVER/VICTORY camera is
   centred at X=5.0 (the 11-wide centre), not the active-stage centre. It is hidden under
   full-screen overlays; no gameplay impact.
2. **cam_xz not snapped at stage transitions:** The look-at target lerps toward the new
   player spawn over ~0.5–1 s. Invisible because the STAGE_INTRO animation covers the
   window. Will become visible only if `STAGE_INTRO_DURATION` is ever reduced below ~1 s.
3. **W1 opener uniformity:** Stages 4–10 all open with "centre-A, all-Normal" Wave 1.
   Non-blocking but reduces variety. Consider differentiated W1 patterns in a future step.

---

## Approval

Once you have verified the items above, reply **"Step 32 approved"** to proceed.
