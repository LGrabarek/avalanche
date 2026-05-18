# Step 36 — Wave pool system, wave codes, and crush-retry gate (rev7b)

## What changed

Five inter-related gameplay systems added in `wave_data.py`, `game_manager.py`,
and `wave_manager.py`, with wire-up in `main.py` and display in `hud.py`.

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
- `STAGES` backward-compat alias — built from A-variants only.

### 2 — Unique wave codes

Every `WaveData` now carries a `code: str` field (e.g. `"S3W2B"`):

- Format: `S{stage}W{slot}{variant}` where stage is 1-based, slot is 0-based,
  variant is `A` or `B`.
- `WaveData.__init__` rejects empty codes (raises `ValueError`).
- `GameManager.wave_code` property — returns the active wave's code, or `"---"`
  before the first wave is loaded.

### 3 — Crush-retry gate with life system (rev7 mechanics)

The stage ends only when the player accumulates **4 clean clears** (one per wave
slot). On a crush, the same wave **replays identically** — same pattern, same
mirror, same z position. Each crush consumes the **back-most pending wave** as a
"life" (its pending cubes are removed from the grid; the visible row count shrinks
by one wave). When all pending lives are exhausted, `_reload_remaining_waves` fires
a full STAGE_INTRO animation with the remaining needed waves.

**Behavioral table for Stage 1:**

| Event                     | `_wave_index` | `_clean_clears` | Visible rows        | Counter | Banner      |
|---------------------------|---------------|-----------------|---------------------|---------|-------------|
| Stage start               | 0             | 0               | 8 (W0+W1+W2+W3)     | 1/4     | —           |
| W0 crushed (3 lives left) | 0             | 0               | 6 (W0+W1+W2)        | 1/4     | AGAIN!      |
| W0 crushed (2 lives left) | 0             | 0               | 4 (W0+W1)           | 1/4     | AGAIN!      |
| W0 crushed (1 life left)  | 0             | 0               | 2 (W0)              | 1/4     | AGAIN!      |
| W0 crushed→reload         | (STAGE_INTRO) | 0               | 8 (fresh batch)     | 1/4     | AGAIN!→INTRO|
| W0 cleaned                | →1            | 1               | 6 (W1+W2+W3)        | 2/4     | —           |
| W1 cleaned                | →2            | 2               | 4 (W2+W3)           | 3/4     | —           |
| W2 cleaned                | →3            | 3               | 2 (W3)              | 4/4     | —           |
| W3 cleaned                | —             | 4≥4             | —                   | 4/4     | STAGE CLEAR |

**Key mechanics:**

- **Crush (lives remain):** The back-most pending wave is removed (`remove_pending_in_range`);
  `_waves`, `_wave_z_starts`, and `_wave_mirrors` shrink by one entry. The current
  slot is then respawned at the **same z position** with the **same WaveData and
  mirror flag** (no re-roll — byte-identical pattern). `_retry_pending = True` →
  AGAIN! banner + `[AGAIN]` HUD tag during WAVE_RISING. `_wave_index` is **not**
  advanced; the player faces the same wave that crushed them.

- **Crush (all lives exhausted):** `_post_rising_reload = True` is set. After the
  WAVE_RISING pause (AGAIN! still visible), `_reload_remaining_waves` fires, spawning
  `_waves_per_stage - _clean_clears` fresh waves from pool slots `[_clean_clears:]`
  and entering STAGE_INTRO for the rolling-wave animation.

- **Clean (not stage complete, non-last slot):** `_clean_clears += 1`, `_wave_index`
  advances, WAVE_RISING (may show PERFECT!).

- **Clean (not stage complete, last slot):** same as crush-last-slot but
  `_retry_pending` stays False (no AGAIN! during WAVE_RISING). After WAVE_RISING
  timer, `_reload_remaining_waves` fires → STAGE_INTRO.

- **Clean (stage complete):** `_clean_clears >= _waves_per_stage` → STAGE_CLEAR /
  VICTORY immediately. The `_wave_index` increment is never reached.

**New fields:**

- **`_post_rising_reload: bool`** — deferred flag set when all lives are exhausted.
  Checked and cleared at WAVE_RISING expiry in `update()`.
- **`_wave_mirrors: list[bool]`** — stores the mirror decision for each wave at
  spawn time (in `_spawn_all_waves_pending`). Allows `_respawn_current_slot` to
  reproduce the exact same cube layout without re-randomising.
- **`_consume_last_pending_life()`** — removes the back-most pending wave's cubes
  via `remove_pending_in_range`; shrinks `_waves`, `_wave_z_starts`, and
  `_wave_mirrors` by one entry.
- **`_respawn_current_slot()`** — re-places the current wave using
  `_waves[_wave_index]` (same A/B variant) and `_wave_mirrors[_wave_index]` (same
  mirror orientation) at the same z depth. Zero new randomness.
- **`_reload_remaining_waves(player)`** — builds wave list from
  `STAGE_POOL_SLOTS[stage][_clean_clears:]`, resets wave manager, spawns all pending
  cubes, enters STAGE_INTRO. `_retry_pending` and `_perfect_display` cleared here.

**`WaveManager.remove_pending_in_range(z_front, z_back)`** — new method that
removes all pending cubes in the z range `[z_front, z_back]` and returns the count
removed. Used by `_consume_last_pending_life`.

### 4 — Wave counter display

`GameManager.wave_index` property:
```python
max_idx = max(0, self._waves_per_stage - 1)
return min(self._clean_clears, max_idx)
```
- Returns `_clean_clears`, capped at 3 (never 4/4 becomes 5/4).
- Counter stays fixed on crush (no clean clear counted; `_wave_index` does not advance).
- Advances to N+1 only after a clean.

### 5 — `start_game` — full-run entry point

`GameManager.start_game(player, all_stage_waves)`:

- Stores the complete run selection in `self._all_stage_waves`.
- Stage transitions in `_on_stage_complete` read from `_all_stage_waves`.
- `_do_restart` draws a fresh pool selection via `select_all_waves`.

### 6 — HUD wave code display

`hud.py`:

- 5th stat line: `Code: S3W2A` (or `Code: S3W2A  [AGAIN]` after a crush).
- `MAX_HUD_CACHE_ENTRIES` = 6.

---

## Files changed

| File | Change |
|------|--------|
| `wave_data.py` | Full rewrite: 80 WaveData objects (40 A + 40 B), `WAVE_POOLS`, `STAGE_POOL_SLOTS`, `select_all_waves`, `STAGES` alias, `code` param |
| `game_manager.py` | `start_game`, `_reload_remaining_waves`, `_consume_last_pending_life`, `_respawn_current_slot` (exact-replay), `_post_rising_reload` flag, `_wave_mirrors` list, `_clean_clears`, `wave_index`/`wave_count` properties, `_on_wave_cleared` revised crush+clean paths, `_on_stage_complete` + `_reset_state` zero new fields |
| `wave_manager.py` | `remove_pending_in_range` method |
| `main.py` | `import random`; `from wave_data import select_all_waves`; startup uses `start_game`; WAVE_RISING overlay shows `AGAIN!` in orange when `game.retry_pending` |
| `hud.py` | `MAX_HUD_CACHE_ENTRIES` 5→6; 5th stat line (wave code + `[AGAIN]` tag); assertion 4→5 |

---

## How to test

### 1 — Desktop smoke test

```bash
cd F:/Python/Avalanche
uv run python main.py
```

Expected: game window opens, no console errors, HUD shows `Code: S1W0A` or
`Code: S1W0B` in the top-left stat block. Counter shows `Wave: 1/4`.

### 2 — Crush respawns the SAME wave (no advance, no variation)

1. Play Wave 1 (S1W0) and deliberately let a cube crush you.
2. After the avalanche clears, verify during WAVE_RISING:
   - HUD shows `Code: S1W0X  [AGAIN]` — the **same** wave's code (not S1W1).
   - The centred `AGAIN!` banner appears in orange.
   - The **wave counter stays at 1/4** (no clean clear counted).
   - The grid shows **3 waves of cubes** (one pending wave was consumed as a life).
3. After the rising pause, **the same Wave 0 pattern** begins — identical cube
   positions and mirror orientation to the one that crushed you.

### 3 — Each crush consumes one life (back-most row)

1. Start Stage 1. Verify: 4 waves visible (8 rows of cubes if each wave is 2 rows).
2. Get crushed on Wave 0. Verify: **3 waves visible** (6 rows). Counter: **1/4**.
3. Get crushed again. Verify: **2 waves visible** (4 rows). Counter: **1/4**.
4. Get crushed again. Verify: **1 wave visible** (2 rows). Counter: **1/4**.
5. Get crushed one more time. Verify during WAVE_RISING:
   - `AGAIN!` banner still visible. HUD shows `[AGAIN]`.
   - After WAVE_RISING, **STAGE_INTRO plays** with a fresh 4-wave batch.
   - Counter resets to `Wave: 1/4` (still 0 clean clears).

### 4 — Exact replay — no variation on consecutive retries

1. Deliberately memorise the cube layout of Wave 0 (which columns have Normal vs
   Advantage vs Forbidden, left/right mirror orientation).
2. Get crushed. Observe the replayed wave:
   - **Identical column layout** to the wave that crushed you.
   - **Same mirror orientation** (not flipped).
   - **Same z position** (cubes appear at the same depth).
3. Get crushed again on the replay. The third attempt must be **identical** to the
   first and second.

### 5 — Counter tracks clean clears only

1. Start Stage 1. Counter: `Wave: 1/4`.
2. Get crushed on W0. Retry — counter: **still 1/4**.
3. Clear W0 cleanly. Counter: **2/4**.
4. Clear W1 cleanly. Counter: **3/4**.
5. Clear W2 cleanly. Counter: **4/4**. Batch exhausted (3 clears done, W3 unplayed).
6. WAVE_RISING (no AGAIN!) → STAGE_INTRO (1 wave: W3 from pool slot [3]).
7. Clear W3 cleanly → STAGE CLEAR.

### 6 — Progress carries across batch reload

1. Clear Waves 0 and 1 cleanly (`_clean_clears = 2`), then get crushed repeatedly
   until all lives are exhausted.
2. Batch reloads via STAGE_INTRO with **2 waves** (slots [2] and [3]).
3. Clear Wave 0 of the new batch cleanly (`_clean_clears = 3`). Counter: 4/4.
4. Clear Wave 1 of the new batch cleanly (`_clean_clears = 4`).
5. Verify the **STAGE_CLEAR** screen appears immediately.

### 7 — Counter never shows 5/4

1. Clear all 4 waves of Stage 1 without any crush.
2. When the final wave clears, verify the HUD shows `Wave: 4/4` (not `Wave: 5/4`)
   before the STAGE_CLEAR overlay appears.

### 8 — Stage transition reads pool selection

1. Clear all 4 waves of Stage 1 cleanly.
2. Advance to Stage 2 (press any key at STAGE CLEAR screen).
3. Verify HUD wave code in Stage 2 uses the Stage 2 pool (code starts `S2W0`).

### 9 — Restart re-rolls pool selection

1. Play to Stage 2. Note the wave codes.
2. Press any key on GAME_OVER to restart.
3. Play Stage 2 again. The codes may differ from the first run.

---

## Expert panel summary (rev7c)

| Reviewer | Verdict | Notes |
|----------|---------|-------|
| Vision Lead | APPROVED | All 7 points pass. `_wave_mirrors` safely reset in `_spawn_all_waves_pending` (unconditional `= []` before loop). No blocking issues. |
| Code Quality | APPROVED | Fixed: removed unused `player` param from `_spawn_all_waves_pending` and 3 call sites. All Power of Ten rules pass. |
| Platform Engineer | APPROVED | No C extensions, no FS writes, no SysFont. `random.random()` WASM-safe. Memory pressure negligible. |
| UX Tester | APPROVED WITH ADVISORY | Fixed B2: added `trigger_shake(5.0, 0.25)` in `_consume_last_pending_life` for tactile life-consumed feedback. B1 (counter freeze) is a design choice (counter = clean clears); a lives-remaining indicator is filed as a future advisory enhancement. |

### Non-blocking advisories (carried forward)

1. **~10 A/B pool pairs have identical rows** — no actual variety for those slots. Data needs a future differentiation pass.
2. **S9W2A/B ideal step discrepancy** — `_S9W2A_IDEAL = 110` vs `_S9W2B_IDEAL = 108` for identical rows.
3. **Wave code is developer-facing** — `Code: S3W2A` opaque to casual players; could move to pause/debug screen later.
4. **No explicit lives-remaining indicator** — the wave counter stays fixed on crush; players must infer remaining lives from the shrinking visible wave stack. A "Lives: N" HUD element is a future enhancement.

---

## Approval

Once you have verified the items above, reply **"Step 36 approved"** to proceed.
