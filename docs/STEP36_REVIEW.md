# Step 36 — Wave pool system, wave codes, and clean-clear gate (rev6)

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
- `STAGES` backward-compat alias — built from A-variants only.

### 2 — Unique wave codes

Every `WaveData` now carries a `code: str` field (e.g. `"S3W2B"`):

- Format: `S{stage}W{slot}{variant}` where stage is 1-based, slot is 0-based,
  variant is `A` or `B`.
- `WaveData.__init__` rejects empty codes (raises `ValueError`).
- `GameManager.wave_code` property — returns the active wave's code, or `"---"`
  before the first wave is loaded.

### 3 — Clean-clear gate with batch reload (rev6 mechanics)

The stage ends only when the player accumulates **4 clean clears** (one per wave
slot) across any number of batch reloads. Being crushed never blocks progress; it
simply advances to the next wave in the current batch.

**Behavioral table for Stage 1 (all crushes, then all clears):**

| Event             | `_wave_index` | `_clean_clears` | Visible rows     | Counter | Banner      |
|-------------------|---------------|-----------------|------------------|---------|-------------|
| Stage start       | 0             | 0               | 8 (W0+W1+W2+W3)  | 1/4     | —           |
| W0 crushed        | →1            | 0               | 6 (W1+W2+W3)     | 1/4     | AGAIN!      |
| W1 crushed        | →2            | 0               | 4 (W2+W3)        | 1/4     | AGAIN!      |
| W2 crushed        | →3            | 0               | 2 (W3)           | 1/4     | AGAIN!      |
| W3 crushed→reload | (STAGE_INTRO) | 0               | 8 (fresh batch)  | 1/4     | AGAIN!→INTRO|
| W0 cleaned        | →1            | 1               | 6 (W1+W2+W3)     | 2/4     | —           |
| W1 cleaned        | →2            | 2               | 4 (W2+W3)        | 3/4     | —           |
| W2 cleaned        | →3            | 3               | 2 (W3)           | 4/4     | —           |
| W3 cleaned        | —             | 4≥4             | —                | 4/4     | STAGE CLEAR |

**Key mechanics:**

- **Crush (non-last slot):** `_wave_index` advances to the next slot. No clean clear
  counted. `_retry_pending = True` → AGAIN! banner + `[AGAIN]` HUD tag during
  WAVE_RISING. The next pre-placed pending wave activates (no cube respawn).

- **Crush (last slot, batch exhausted):** `_post_rising_reload = True` is set. After
  the WAVE_RISING pause (AGAIN! still visible), `_reload_remaining_waves` fires,
  spawning `_waves_per_stage - _clean_clears` fresh waves from pool slots
  `[_clean_clears:]` and entering STAGE_INTRO for the rolling-wave animation.

- **Clean (not stage complete, non-last slot):** `_clean_clears += 1`, `_wave_index`
  advances, WAVE_RISING (may show PERFECT!).

- **Clean (not stage complete, last slot):** same as crush-last-slot but
  `_retry_pending` stays False (no AGAIN! during WAVE_RISING). After WAVE_RISING
  timer, `_reload_remaining_waves` fires → STAGE_INTRO.

- **Clean (stage complete):** `_clean_clears >= _waves_per_stage` → STAGE_CLEAR /
  VICTORY immediately. The `_wave_index` increment is never reached.

**New fields:**

- **`_post_rising_reload: bool`** — deferred flag set when a batch is exhausted.
  Checked and cleared at WAVE_RISING expiry in `update()`. Avoids any flash artifact
  between WAVE_RISING and STAGE_INTRO.
- **`_reload_remaining_waves(player)`** — builds wave list from
  `STAGE_POOL_SLOTS[stage][_clean_clears:]`, resets wave manager, spawns all pending
  cubes, enters STAGE_INTRO. `_retry_pending` is cleared here so [AGAIN] is absent
  during the intro animation.

**Removed:** `_respawn_current_slot` — the single-wave silent respawn path is gone.

### 4 — Wave counter display

`GameManager.wave_index` property:
```python
max_idx = max(0, self._waves_per_stage - 1)
return min(self._clean_clears, max_idx)
```
- Returns `_clean_clears`, capped at 3 (never 4/4 becomes 5/4).
- Counter stays fixed on crush (no clean clear counted).
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
| `game_manager.py` | `start_game`, `_reload_remaining_waves`, `_post_rising_reload` flag, `_clean_clears`, `wave_index`/`wave_count` properties, `_on_wave_cleared` revised crush+clean paths, `_on_stage_complete` + `_reset_state` zero new fields; **removed** `_respawn_current_slot` |
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

### 2 — Crush advances to next wave (no respawn)

1. Play Wave 1 and deliberately let a cube crush you.
2. After the avalanche clears, verify:
   - WAVE_RISING pause appears.
   - HUD shows `Code: S1W1X  [AGAIN]` — the **second** wave's code, not wave 1's.
   - The centred `AGAIN!` banner appears in orange.
   - The **wave counter stays at 1/4** (no clean clear counted).
3. After the rising pause, **Wave 2** (not a respawn of Wave 1) begins.
4. The grid now shows 3 waves of cubes (W1 is active, W2+W3 pending behind it).

### 3 — Batch reload when all 4 waves consumed by crush

1. Get crushed on all 4 waves of Stage 1 (0 clean clears).
2. After Wave 4's avalanche empties, verify during WAVE_RISING:
   - `AGAIN!` banner still visible.
   - HUD shows `Code: S1W3X  [AGAIN]`.
   - Counter still 1/4.
3. After WAVE_RISING timer, verify **STAGE_INTRO** animation plays (not just
   WAVE_RISING → WAVE_ACTIVE). The rolling-wave animation shows all **4 waves**
   of a fresh batch.
4. During STAGE_INTRO, HUD should **not** show `[AGAIN]` tag (cleared before intro).
5. The fresh batch begins. Counter resets to `Wave: 1/4`.

### 4 — Counter tracks clean clears only

1. Start Stage 1. Counter: `Wave: 1/4`.
2. Get crushed on W0. Next wave is W1. Counter: **still 1/4**.
3. Clear W1 cleanly. Counter: **2/4**.
4. Clear W2 cleanly. Counter: **3/4**.
5. Clear W3 cleanly. Counter: **4/4**. Batch exhausted (1 clean, 3 unplayed).
6. WAVE_RISING (no AGAIN!) → STAGE_INTRO (3 waves: W1+W2+W3 from pool slots [1:]).
7. Clear all 3 remaining waves cleanly → STAGE CLEAR.

### 5 — Progress carries across batch reload

1. Clear Waves 1 and 2 cleanly (`_clean_clears = 2`), then get crushed on Waves 3 and 4.
2. Batch reloads via STAGE_INTRO with **2 waves** (slots [2] and [3]).
3. Clear Wave 1 of the new batch cleanly (`_clean_clears = 3`). Counter: 4/4.
4. Clear Wave 2 of the new batch cleanly (`_clean_clears = 4`).
5. Verify the **STAGE_CLEAR** screen appears immediately — even though only 2 waves
   were in the new batch.

### 6 — Counter never shows 5/4

1. Clear all 4 waves of Stage 1 without any crush.
2. When the final wave clears, verify the HUD shows `Wave: 4/4` (not `Wave: 5/4`)
   before the STAGE_CLEAR overlay appears.

### 7 — Stage transition reads pool selection

1. Clear all 4 waves of Stage 1 cleanly.
2. Advance to Stage 2 (press any key at STAGE CLEAR screen).
3. Verify HUD wave code in Stage 2 uses the Stage 2 pool (code starts `S2W0`).

### 8 — Restart re-rolls pool selection

1. Play to Stage 2. Note the wave codes.
2. Press any key on GAME_OVER to restart.
3. Play Stage 2 again. The codes may differ from the first run.

---

## Expert panel summary (rev6b)

| Reviewer | Verdict | Notes |
|----------|---------|-------|
| Vision Lead | APPROVED WITH CONCERNS | Concerns A+C fixed: `random.randrange(len(pool))` replaces hardcoded 0-or-1; `_perfect_display` cleared in `_reload_remaining_waves`. Concern B (effects.reset in non-last crush path) is not a regression vs pre-rev6 — left as-is. |
| Code Quality | APPROVED | All 10 Power of Ten rules pass. |
| Platform Engineer | APPROVED | All WASM criteria pass. Minor pool-size note addressed by randrange fix. |
| UX Tester | APPROVED WITH CONCERNS | Minor: counter jump on fresh batch is correct behavior matching original I.Q. `_perfect_display` hygiene note addressed. No BLOCKING issues. |

### Panel fixes applied in rev6b

1. **`_perfect_display` cleared in `_reload_remaining_waves`** — alongside `_retry_pending`, so both flags are symmetrically reset before STAGE_INTRO (prevents any stale PERFECT! flag if rendering ever reads it during the intro).
2. **`random.randrange(len(pool))` in `_reload_remaining_waves`** — replaces `0 if random.random() < 0.5 else 1`, making variant selection pool-size-agnostic.

### Non-blocking advisories (carried over)

1. **~10 A/B pool pairs have identical rows** — no actual variety for those slots. Infrastructure correct; data needs a future differentiation pass.
2. **S9W2A/B ideal step discrepancy** — `_S9W2A_IDEAL = 110` vs `_S9W2B_IDEAL = 108` for identical rows.
3. **Wave code is developer-facing** — `Code: S3W2A` opaque to casual players; could move to pause/end screen later.
4. **Batch reload re-rolls A/B variants** — two reloads in the same stage may show different or identical patterns.

---

## Approval

Once you have verified the items above, reply **"Step 36 approved"** to proceed.
