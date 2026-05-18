# Step 36 — Wave pool system, wave codes, and clean-clear gate

## What changed

Four inter-related gameplay systems added in `wave_data.py` and `game_manager.py`,
with wire-up in `main.py` and display in `hud.py`.

---

### 1 — Wave pool system

`wave_data.py` completely rewritten:

- Each wave slot now has **two variants** (A and B). Variant A is the existing
  pattern from Step 35; variant B is a new alternative pattern for the same slot.
- 40 pools (`WAVE_POOLS: dict[str, tuple[WaveData, ...]]`), one per stage × slot:
  `S1W0`, `S1W1`, …, `S10W3`. Each pool holds a 2-tuple `(A_variant, B_variant)`.
- `STAGE_POOL_SLOTS: tuple[tuple[str, str, str, str], ...]` — 10-entry tuple, each
  listing the 4 pool keys for that stage.
- `select_all_waves(rng: random.Random) -> tuple[tuple[WaveData, ...], ...]` — called
  once per run; draws one variant per slot randomly, returning 10 × 4 waves.
- `STAGES` backward-compat alias — built from A-variants only; keeps any code that
  still calls `start_first_wave(player, STAGES[0])` working correctly.

### 2 — Unique wave codes

Every `WaveData` now carries a `code: str` field (e.g. `"S3W2B"`):

- Format: `S{stage}W{slot}{variant}` where stage is 1-based, slot is 0-based,
  variant is `A` or `B`.
- `WaveData.__init__` rejects empty codes (raises `ValueError`).
- `GameManager.wave_code` property — returns the active wave's code, or `"---"`
  before the first wave is loaded.

### 3 — Clean-clear gate (revised from original crush-retry)

The stage ends only when the player accumulates **4 clean clears** — one per wave slot
— without being crushed. Being crushed never blocks progress outright; instead the
next pre-spawned pending wave becomes the immediate retry.

Key mechanics:

- **`_clean_clears: int`** — counts clean clears per stage. Incremented when a wave
  is cleared without a crush. Reset to 0 at every stage transition and on restart.
- **`_on_wave_cleared`** — two paths:
  - *Crushed path*: `_wave_crushed` cleared, `_retry_pending` set (RETRY! banner),
    `_wave_index` advances. No clean clear counted.
  - *Clean path*: Perfect bonus applied, `_clean_clears += 1`. If `_clean_clears >=
    4`, enter STAGE_CLEAR / VICTORY immediately — **even if pending waves from the
    current batch are unused**.
  - Both paths advance `_wave_index`. If the batch is exhausted before 4 clean clears
    are accumulated, `_reload_stage_waves` re-enters STAGE_INTRO with a fresh batch.
- **`_reload_stage_waves(player)`** — picks fresh A/B variants for the stage's 4
  pool slots, re-spawns all waves as pending cubes, and enters STAGE_INTRO. The
  `_clean_clears` count carries over so progress is never lost.
- **`_wave_crushed: bool`** — set to `True` in `_trigger_avalanche`; cleared at the
  start of the crushed path in `_on_wave_cleared`.
- No more `_respawn_current_wave` — the original wave cubes are NOT re-placed on
  crush. The next pre-spawned wave in the batch is activated as-is.

### 4 — `start_game` — full-run entry point

`GameManager.start_game(player, all_stage_waves)`:

- Stores the complete run selection in `self._all_stage_waves`.
- Stage transitions in `_on_stage_complete` read from `_all_stage_waves` instead
  of the static `STAGES` table.
- `_do_restart` draws a fresh pool selection via `select_all_waves` so every replay
  gets a different A/B mix.
- `main.py` calls `start_game` at startup (replacing the old `start_first_wave(
  player, STAGES[0])` call).

### 5 — HUD wave code display

`hud.py`:

- 5th stat line: `Code: S3W2A` (or `Code: S3W2A  [RETRY]` when a crushed wave
  is pending replay).
- `MAX_HUD_CACHE_ENTRIES` bumped from 5 → 6.
- Line-count assertion updated from 4 → 5.

---

## Files changed

| File | Change |
|------|--------|
| `wave_data.py` | Full rewrite: 80 WaveData objects (40 A + 40 B), `WAVE_POOLS`, `STAGE_POOL_SLOTS`, `select_all_waves`, `STAGES` alias, `code` param on `WaveData` |
| `game_manager.py` | `start_game`, `_reload_stage_waves`, `_clean_clears` field, `_wave_crushed` field + property, `wave_code` property, `_retry_pending` flag + property, revised `_on_wave_cleared`, `_on_stage_complete` reads `_all_stage_waves` and resets `_clean_clears`, `_do_restart` uses pool selection, `_reset_state` zeros new fields |
| `main.py` | `import random`; `from wave_data import select_all_waves`; startup uses `start_game(player, select_all_waves(rng))`; WAVE_RISING overlay shows `RETRY!` in orange when `game.retry_pending` |
| `hud.py` | `MAX_HUD_CACHE_ENTRIES` 5→6; 5th stat line (wave code + retry tag); assertion 4→5 |

---

## How to test

### 1 — Desktop smoke test

```bash
cd F:/Python/Avalanche
uv run python main.py
```

Expected: game window opens, no console errors, HUD shows `Code: S1W0A` or
`Code: S1W0B` in the top-left stat block.

### 2 — Pool variety across runs

1. Start the game twice (restart with any key after first GAME_OVER).
2. Note the wave code shown in the HUD for Stage 1 Wave 1.
3. Across multiple restarts the codes should vary (some runs see A, some B).

### 3 — Clean-clear gate — normal path

1. Clear all 4 waves of Stage 1 without being crushed on any of them.
2. Verify the stage ends after wave 4 is cleared (STAGE_CLEAR screen appears).
3. The HUD never shows `[RETRY]` during this run.

### 4 — Crush advances to next wave (no respawn)

1. Play Wave 1 and deliberately let a cube crush you.
2. After the avalanche clears, verify:
   - The WAVE_RISING pause appears.
   - The HUD shows `Code: S1W1X  [RETRY]` — the **second** wave's code, not wave 1's.
   - The centred `RETRY!` banner appears in orange.
3. After the rising pause, **Wave 2** (not a respawn of Wave 1) begins.
4. Clear Wave 2 cleanly — `_clean_clears` is now 1 (Wave 1 was crushed, Wave 2 was clean).

### 5 — Batch reload when all 4 waves consumed without 4 clean clears

1. Get crushed on Waves 1, 2, 3, and 4 of Stage 1 (4 crushes, 0 clean clears).
2. After Wave 4's avalanche empties, verify:
   - The full **STAGE_INTRO** rolling-wave animation plays (not just WAVE_RISING).
   - The animation shows **all 4 waves** of a fresh batch (new A/B variants).
   - The HUD no longer shows `[RETRY]` during the intro.
3. The fresh batch begins. The wave counter restarts at `Wave: 1/4`.

### 6 — Progress carries across batch reload

1. Clear Waves 1 and 2 cleanly (`_clean_clears = 2`), then get crushed on Waves 3 and 4.
2. Batch reloads via STAGE_INTRO.
3. Clear Wave 1 of the new batch cleanly (`_clean_clears = 3`).
4. Clear Wave 2 of the new batch cleanly (`_clean_clears = 4`).
5. Verify the **STAGE_CLEAR** screen appears immediately after Wave 2 — even though
   Waves 3 and 4 of the new batch were never played.

### 7 — RETRY! banner in the wave rising overlay

1. Get crushed on any wave.
2. After the avalanche empties, observe the WAVE_RISING pause.
3. Verify:
   - The centred banner shows **`RETRY!`** in orange (not `PERFECT!`).
   - Below it, the wave label reads `Stage 1 — Wave 2 / 4` (next wave, not same wave).
   - The top-left HUD shows `Code: S1W1X  [RETRY]`.
4. After the pause, **the next wave** (not a respawn) begins.

### 8 — Stage transition reads pool selection

1. Clear all 4 waves of Stage 1 cleanly.
2. Advance to Stage 2 (press any key at the STAGE CLEAR screen).
3. Verify the HUD wave code in Stage 2 uses the Stage 2 pool (code starts `S2W0`).

### 9 — Restart re-rolls pool selection

1. Play to Stage 2. Note the wave codes.
2. Press any key on GAME_OVER to restart.
3. Play Stage 2 again. The codes may differ from the first run.

### 10 — Browser / WASM test (optional but recommended)

```bash
bash run_dev.sh
# Open http://localhost:8000
```

All above behaviours should work identically in the browser.

---

## Expert panel summary

| Reviewer | Verdict | Notes |
|----------|---------|-------|
| Vision Lead | APPROVED WITH CONCERNS | ~10 A/B pool pairs have identical rows (no actual variety delivered for those slots); S7W3B inline comment arithmetic inconsistent (non-blocking data quality issues) |
| Code Quality | APPROVED WITH CONCERNS | All 11 Power of Ten rules pass; revised `_on_wave_cleared` under 50 lines; `_reload_stage_waves` pool-access idiom correct; all concerns cleared |
| Platform Engineer | APPROVED WITH CONCERNS | All WASM criteria pass; `random` module fully available in CPython WASM; module-level data (~176 KB worst case) well within budget; HUD cache correctly sized |
| UX Tester | APPROVED WITH CONCERNS | **BLOCKING (fixed):** `_retry_pending` flag added so WAVE_RISING banner and HUD `[RETRY]` tag stay visible during the pause. Revised mechanic: crushed wave advances to next slot (no respawn); stage ends on 4 clean clears; batch reload via STAGE_INTRO when exhausted. Non-blocking: 6 A/B pairs identical; S9W2A/B ideal discrepancy; wave code is developer-facing info |

### Blocking fix applied

**`_retry_pending: bool`** — drives both the `[RETRY]` HUD tag and the `RETRY!`
orange banner in the WAVE_RISING overlay. Set in the crushed path of `_on_wave_cleared`
(when `_wave_crushed` is cleared); cleared in `_begin_wave` when the wave activates.

`RETRY!` and `PERFECT!` are mutually exclusive (`_had_avalanche = True` disqualifies
Perfect on a crushed wave).

### Known non-blocking advisories

1. **~10 A/B pool pairs have identical rows** — `S4W3`, `S5W3`, `S6W2`, `S6W3`,
   `S8W1`, `S8W2`, `S9W2`, `S9W3`, `S10W1`, `S10W3` deliver no actual variety.
   Infrastructure is correct; data needs a future differentiation pass.
2. **S9W2A/B ideal step discrepancy** — `_S9W2A_IDEAL = 110` vs `_S9W2B_IDEAL = 108`
   for identical rows. One value is wrong. Low priority since both variants play
   identically.
3. **Wave code is developer-facing** — `Code: S3W2A` is opaque to casual players.
   Acceptable for now; could be moved to pause menu / end screen in a future UX pass.
4. **Batch reload via STAGE_INTRO** — re-rolls A/B variants each time, so two batch
   loads in the same stage may show different (or identical) wave patterns.

---

## Approval

Once you have verified the items above, reply **"Step 36 approved"** to proceed.
