# Step 37 Review — High Score Table

**Status:** AWAITING USER APPROVAL
**Date:** 2026-05-18
**Commit:** 84288da (initial) + advisory fixes (same branch)

---

## What changed

### New file: `high_score.py`

Implements the full persistence layer for the top-10 high score table.

| Symbol | Purpose |
|--------|---------|
| `MAX_ENTRIES = 10` | Hard cap on table size |
| `STORAGE_KEY = "avalanche_hs_v1"` | localStorage key (namespaced + versioned) |
| `HighScoreEntry` | Dataclass: `iq_score`, `stage_reached`, `raw_score` |
| `HighScoreTable` | Sorted list + persistence; `add()`, `qualifies()`, `entries` property |

**Persistence behaviour:**
- **Desktop (Python):** session-only. `_load()` / `_save()` detect no `platform.window` and skip silently.
- **Browser (Pygbag WASM):** serialised as JSON to `window.localStorage`. Survives page refreshes and service-worker cache clears.

**All storage errors are caught and swallowed** — a corrupt or missing localStorage entry never crashes the game; the table simply starts empty.

### `constants.py`

Added `GamePhase.HIGH_SCORE = "high_score"` — new phase between GAME_OVER/VICTORY and the next TITLE.

### `game_manager.py`

| Addition | Detail |
|----------|--------|
| `_high_score_table: HighScoreTable` | Created once in `__init__`; survives restarts (persists across runs) |
| `_last_score_rank: int` | 0-based rank of the most recent score, or -1 if it didn't qualify |
| `high_score_entries` property | Immutable tuple for the renderer to read |
| `last_score_rank` property | For the renderer to highlight the new entry |
| `_insert_score()` | Computes IQ (from `_iq_score` on VICTORY, `_calculate_final_iq()` on GAME_OVER) and calls `table.add()` |
| `on_restart_key(player)` | Now routes GAME_OVER/VICTORY → `_insert_score()` → `HIGH_SCORE` (not directly to restart) |
| `on_high_score_key(player)` | `HIGH_SCORE` → `_do_restart()` (any key dismisses the table) |
| `_MENU_BLOCKED` | `HIGH_SCORE` added — Esc menu cannot open during the score screen |
| `_reset_state()` | `_last_score_rank` reset to -1; **`_high_score_table` is NOT reset** — the table persists across restarts |
| `on_menu_select` docstring | Clarified: Esc→Restart bypasses score insertion (mid-run abandon) |

**Score insertion is intentionally skipped on Esc → Restart** — the player abandoned
a run before it ended naturally, so no score is recorded.

### `main.py`

| Addition | Detail |
|----------|--------|
| `_HS_COL_XS`, `_HS_HEADERS` | Column X positions and header labels for the table overlay |
| `_draw_high_score_overlay()` | Draws the full overlay: dark veil, gold "HIGH SCORES" title, ranked entries, new-entry highlight |
| Event routing | `HIGH_SCORE` phase: any key → `game.on_high_score_key(player)` |
| `frozen` set | `HIGH_SCORE` added — wave logic paused while table is shown |
| End-screen prompts | "Press any key to **continue**" (was "restart") on GAME_OVER and VICTORY overlays |

---

## Game flow with high scores

```
GAME_OVER / VICTORY
    │  (hold expires — ~2 s)
    │  any key
    ▼
_insert_score()       ← IQ computed and stored; rank recorded
    │
    ▼
GamePhase.HIGH_SCORE  ← table overlay rendered
    │  any key
    ▼
_do_restart()         ← full reset, TITLE screen
```

---

## Expert panel summary

Four agents reviewed the initial commit (84288da).

| Reviewer | Verdict | Key findings |
|----------|---------|-------------|
| Code Quality | APPROVED | `assert rank >= -1` vacuous — fixed to `assert rank == -1 or rank < MAX_ENTRIES` |
| Pygbag/WASM Specialist | APPROVED | `hasattr(_platform, "window")` guard correct; broad except on localStorage correct |
| Vision Lead | APPROVED | Docstring on `on_menu_select` stale ("identical to on_restart_key") — fixed |
| UX Tester | APPROVED | Advisory: IQ=0 threshold; "PERSONAL BESTS" label; prompt text ambiguity — all accepted as design decisions for v1 |

All blockers resolved. All advisories addressed or deferred by design decision.

---

## How to test

### Desktop (session-only mode)

1. `python main.py` — game opens to TITLE screen.
2. Play a wave, get crushed → GAME_OVER overlay appears.
3. Wait ~2 s, press any key → **"HIGH SCORES"** overlay appears with your entry highlighted in gold with a `>` prefix.
4. Press any key → returns to TITLE.
5. Play again, get a lower score → press any key through the score screen → your entry should NOT be highlighted (lower score; prior entry outranks it).
6. Repeat until table has 10 entries. Play again with a low score → the score is not highlighted (did not qualify for top 10).

### VICTORY path

1. Clear Stage 1 (all waves) → VICTORY overlay.
2. Wait ~2 s, press any key → score screen with VICTORY IQ shown.
3. Verify IQ shown in score table matches the IQ shown on the VICTORY overlay.

### Esc → Restart bypass

1. Start a game, let the first wave partially clear.
2. Press Esc → pause menu.
3. Select Restart (↓ Enter).
4. Game resets → TITLE. **No score screen appears** (mid-run abandon, no score recorded).
5. This is intentional: the score table should be unchanged.

### Browser persistence (requires `bash run_dev.sh`)

1. Open `http://localhost:8000`, play to GAME_OVER.
2. Press any key through score screen → table shown.
3. **Refresh the page** (F5) → play again → GAME_OVER → score screen.
4. Prior entry from step 1 should still be in the table (loaded from localStorage).
5. Open DevTools → Application → Local Storage → `http://localhost:8000`.
6. Key `avalanche_hs_v1` should contain a JSON array of score objects.

### Table full (top-10 cap)

1. Play 10+ games accumulating different scores.
2. After 10 entries, play a game with a very low IQ (e.g. 0) → score screen shows entry NOT highlighted (did not qualify).
3. Play a game with the highest IQ yet → score screen highlights the new entry.

---

## Files changed

- `high_score.py` (new)
- `constants.py` (added `HIGH_SCORE` to `GamePhase`)
- `game_manager.py` (high score integration + advisory fixes)
- `main.py` (overlay drawing, event routing, frozen set)
