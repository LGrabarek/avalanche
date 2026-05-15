# Step 33 — Camera / grid / player persistence redesign

## What changed

Five user-requested changes, plus one BLOCKER fix from the expert panel:

| Change | Summary |
|--------|---------|
| Back-packed waves | Waves spawn from z=59 backward; wave 0 closest to player |
| Grid persistence | Tile state (deleted rows) carries across stage boundaries |
| Player position | X and Z preserved at wave/stage transitions (uncrush only) |
| Camera Z tracking | Eye Z = player world_z − 19.5 (fixed offset, always same distance) |
| Smooth camera pitch | Eye Y interpolates toward wave-index target at 1.5 rad/s |
| Z-clamp at stage start | Player Z clamped below new wave 0 front if they advanced too deep |

### Back-packed z positions (WAVE_GAP_ROWS=0, GRID_DEPTH=60)

| Stage | Rows/wave | z_back[wave 0..3] |
|-------|-----------|-------------------|
| 1 | 2 | 53, 55, 57, 59 |
| 2 | 3 | 50, 53, 56, 59 |
| 3 | 3 | 50, 53, 56, 59 |
| 4 | 4 | 47, 51, 55, 59 |
| 5 | 4 | 47, 51, 55, 59 |
| 6 | 5 | 44, 49, 54, 59 |
| 7 | 5 | 44, 49, 54, 59 |
| 8 | 6 | 41, 47, 53, 59 |
| 9 | 6 | 41, 47, 53, 59 |
| 10 | 7 | 38, 45, 52, 59 |

### Player X-boundary (Stage 33 addition)
The grid is always 11 wide, but movement is restricted to the active wave
columns so the player cannot safely camp on wave-free outer tiles:

| Stage | Wave width | Max column (0-indexed) |
|-------|-----------|------------------------|
| 1–4 | 7 | 6 |
| 5–8 | 9 | 8 |
| 9–10 | 11 | 10 |

---

## How to test

### 1 — Desktop smoke test

```bash
cd F:/Python/Avalanche
uv run python main.py
```

Expected: game window opens, no errors in console.

### 2 — Wave positions at Stage 1

1. Start a game, let Stage 1 wave 1 spawn.
2. Count empty tiles between player (z≈21) and the first cube row. Should be
   **≈31 tiles** of open space before any cube appears.
3. Waves should be visible at the far end of the grid, marching forward.

### 3 — Camera follows player Z

1. Walk toward the wave (arrow Up / W). The camera should move with you —
   the distance from player to camera eye should remain constant.
2. Walk back toward the camera (arrow Down / S). The camera pulls back with
   you — it does not stay at a fixed position.
3. At any Z position the cubes should remain in view and the grid should not
   look clipped.

### 4 — Smooth camera pitch between waves

1. Complete Stage 1 wave 1. During the WAVE_RISING pause (≈2 s), the camera
   should smoothly tilt upward (more top-down view) rather than snapping.
2. By wave 4, the camera should be noticeably more top-down than at wave 1.
3. No jarring snap at any wave transition.

### 5 — Grid persistence across stages

1. Play through Stage 1, intentionally fail a few cubes (collect a penalty row
   deletion or two).
2. Clear Stage 1 → Stage 2 starts. **The deleted rows should still be missing.**
   The grid front edge has not been restored.

### 6 — Player position preserved between waves (same stage)

1. During Stage 1 wave 1, move the player to column 3, z≈30.
2. Clear all cubes. The WAVE_RISING pause plays.
3. Wave 2 starts. **Player should still be at column 3, z≈30** (not teleported
   back to spawn).

### 7 — Player Z reset only when deep (stage transition safety)

1. In Stage 1, walk as far toward the waves as possible — try to reach z≈50–55.
2. Clear all wave 1 cubes (you're now standing where the cubes were).
3. Continue clearing waves until Stage Clear.
4. Stage 2 starts. **Player should be pulled back** to just below Stage 2 wave 0
   front row (z≈47). They should NOT be inside the new wave stack.
5. Verify: no instant crush at the start of Stage 2, and the player can see
   incoming cubes before the first tick fires.

### 8 — Player X-boundary (invisible wall)

1. In Stage 1 (7-wide wave patterns), try to move the player right past column 6.
2. The player should **stop at column 6** and cannot reach columns 7–10 (which
   are visible as platform tiles but have no wave cubes).
3. At Stage 5, the boundary should shift to column 8. Confirm moving right
   reaches column 8 but not column 9 or 10.
4. At Stage 9, the boundary should disappear (11-wide patterns fill the full grid).

### 9 — Camera X tracks grid centre

1. At Stage 1 (7-wide, grid_center_x = 3.0), the camera should be centred over
   column 3. Columns 0–6 should all be visible.
2. At Stage 5+ (9-wide, grid_center_x = 4.0), the camera centres over column 4.

### 10 — Restart resets everything

1. Play to Stage 5 (grid is still 11 wide but you may have deleted rows).
2. Open Esc menu → Restart.
3. Confirm: grid restored to full 11 wide with no void rows, player at column 5
   (grid.width // 2), Stage 1 starts fresh.

### 11 — Browser / WASM test (optional but recommended)

```bash
bash run_dev.sh
# Open http://localhost:8000
```

All above behaviours should work identically in the browser.

---

## Expert panel summary

| Reviewer | Verdict | Notes |
|----------|---------|-------|
| Vision Lead | APPROVED WITH CONCERNS | Right column clamp asymmetry (waves start at col 0 so no actual gap on left); stale WAVE_GAP_ROWS comment (fixed) |
| Code Quality | APPROVED WITH CONCERNS | assert→raise ValueError in `_update_smooth_camera` (fixed); positional→keyword `max_col=` (fixed) |
| UX Tester | BLOCKER FOUND (fixed) | Player Z persistence into new wave stack → `clamp_z_before_wave()` added; 31-tile gap at Stage 1 (non-blocking); invisible X-wall (non-blocking) |
| Platform Engineer | APPROVED WITH CONCERNS | `_GRID_CENTER_Z` stale comment (fixed); deprecated constants harmless |

---

## Known advisories (non-blocking)

1. **31-tile empty gap at Stage 1 start:** Wave 0 front is at z=52 with the player at
   z=21. This gives ≈31 clear rows before the first cube arrives — more open space than
   the original I.Q. The game remains challenging because the gap closes quickly and all
   4 waves are stacked at the far end. If it feels too gentle in playtesting, the fix is
   to increase `PLAYER_SPAWN_Z` or reduce `GRID_DEPTH`.

2. **Invisible X-boundary for outer columns:** In Stages 1–4, columns 7–10 are visible
   platform tiles but the player hard-stops at column 6 (no visual indicator). This is
   an inherent consequence of the 11-wide grid with 7-wide wave patterns. A future step
   could VOID the outer columns or add a subtle tint to communicate the boundary.

3. **Left-boundary asymmetry in `try_move`:** `max_col` only enforces the right edge.
   The left edge (column 0) is always part of every wave pattern, so no gap exists there.
   The asymmetry is benign but worth noting if wave patterns are ever centred rather than
   left-anchored.

---

## Approval

Once you have verified the items above, reply **"Step 33 approved"** to proceed.
