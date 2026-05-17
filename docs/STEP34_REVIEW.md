# Step 34 — Opening feel (PLAYER_SPAWN_Z 21 → 37)

## What changed

Two constants adjusted, one method updated — no logic changes, no new files.

| Change | Old value | New value | Effect |
|--------|-----------|-----------|--------|
| `PLAYER_SPAWN_Z` | 21 | 37 | Player spawns 16 tiles deeper toward the wave |
| `CAMERA_EYE_Z_OFFSET` | 19.5 | 35.5 | Camera eye Z tracks player with same offset |
| `clamp_z_before_wave` scan start | `wave_front_z − 1` | `wave_front_z − 2` | 2-tile buffer between clamped player and wave face |

### Why the numbers

**PLAYER_SPAWN_Z = 37:**
- Stage 1 wave 0 front is at z = 52 (back-packed from z = 59 with 2-row waves).
- Gap at spawn: 52 − 37 = **15 tiles** of open space before the first cube arrives.
- Was 31 tiles — playtesters found it too long before anything happened.
- Stage 10 wave 0 front is at z = 32. Gap at spawn: 32 − 37 = −5 (player spawns
  inside the wave zone → `clamp_z_before_wave` fires, placing player at z = 30).

**CAMERA_EYE_Z_OFFSET = 35.5:**
- Derived as `PLAYER_SPAWN_Z + 0.5 − CAMERA_FOLLOW_EYE[2]` = 37.5 − 2.0 = 35.5.
- Maintains the same visual angle (12.4° elevation) as before.

**2-tile buffer in `clamp_z_before_wave`:**
- During STAGE_INTRO the game is frozen for ≈2.8 s.
- At Stage 8–10, `wave_front_z − PLAYER_SPAWN_Z` is negative — the player must be
  clamped. The 1-tile buffer (old behaviour) placed the player immediately adjacent
  to the wave face with no visual breathing room.
- 2-tile buffer (new): player lands at z = wave_front_z − 2, giving one empty tile
  between themselves and the cube wall before the countdown ends.

---

## How to test

### 1 — Desktop smoke test

```bash
cd F:/Python/Avalanche
uv run python main.py
```

Expected: game window opens, no console errors.

### 2 — Stage 1 opening gap

1. Start a new game. Note the player's starting row and the first visible cube row.
2. Count the open tiles between them. Should be **≈15 tiles** of clear space.
   (If you see ≈31 tiles, `PLAYER_SPAWN_Z` has not changed.)
3. Wave cubes should be visible from the very first frame — they are not off-screen
   at the far end.

### 3 — Camera follows player from new spawn depth

1. At spawn the camera angle should look similar to the old game — not dramatically
   more top-down or more cinematic.
2. Walk toward the wave (Up / W). Camera eye Z should track you smoothly; the
   distance between player and camera remains constant.
3. Walk back (Down / S). Camera retreats with you.

### 4 — Stage 8–10 Z-clamp gives 2-tile buffer

This test requires advancing to Stage 8 (or editing `_stage_index` in a debug
session). At Stage 8+ the wave front is closer to the player than `PLAYER_SPAWN_Z`,
so `clamp_z_before_wave` fires.

1. Clear Stage 7 without walking deep into the grid (stay near spawn).
2. Stage 8 STAGE_INTRO starts. Player should be repositioned to 2 tiles clear of
   the wave 0 front face.
3. During the countdown the wave face should be **2 empty tiles** in front of the
   player — not 1, not 0.
4. Countdown finishes → first tick fires → player can move normally.

### 5 — No regression: player Z clamp at stage boundary (from Step 33)

1. In Stage 1, walk deep into the grid — try to reach z = 50+.
2. Clear all 4 waves while standing deep.
3. Stage 2 starts. Player should be clamped below Stage 2's wave 0 front (z ≈ 48)
   and have a 2-tile buffer.

### 6 — No regression: X-boundary, smooth camera pitch, grid persistence

Covered by Step 33 tests 4, 8, and 5 respectively. These must still pass with no
change to behaviour.

### 7 — Browser / WASM test (optional but recommended)

```bash
bash run_dev.sh
# Open http://localhost:8000
```

All above behaviours should work identically in the browser.

---

## Expert panel summary

| Reviewer | Verdict | Notes |
|----------|---------|-------|
| Vision Lead | APPROVED WITH CONCERNS | Camera geometry comment block needed updating — fixed in session |
| Code Quality | APPROVED | Constants-only change; no logic paths added; ruff + mypy clean |
| Platform Engineer | APPROVED | No new imports, no WASM-incompatible patterns |
| UX Tester | BLOCKER FOUND (fixed) | 1-tile clamp buffer too tight at Stages 8–10 → updated to 2-tile buffer |

---

## Known advisories (non-blocking)

1. **15-tile gap still more open than the original I.Q.** — The original game
   spawns the player very close to the first wave. 15 tiles is still generous.
   If playtesting reveals the game still feels slow to start, reducing
   `PLAYER_SPAWN_Z` to 31–35 is the next lever to pull (Step 36 difficulty audit).

2. **Clamp fires silently at Stages 8–10** — The player is repositioned with no
   visual indication. A future step could flash the player tile or show a brief
   status message.

---

## Approval

Once you have verified the items above, reply **"Step 34 approved"** to proceed to
Step 35 (wave variety — distinct openers, Stages 4–10).
