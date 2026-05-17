# Avalanche — v3 Plan

## Status: Step 34 (opening feel) — NOT STARTED

v3 work lives on the `v3` branch. All changes are localhost-tested and panel-reviewed
before merging to `master`.

---

## Resumption notes

When starting a new v3 session:
1. Read `docs/PROGRESS.md` for the full step history (Steps 1–33).
2. Read **this file** for the v3 roadmap and the current step.
3. Check the v3 step tracker below, then read the corresponding spec section.
4. The review pipeline from `CLAUDE.md` hard rule 4 is mandatory for every step.

---

## v3 Themes

**Primary: Feel & Balance** — the existing 10-stage game needs tuning so each stage
feels distinct and the difficulty curve is satisfying from the first wave through the
final Stage 10 wall.

**Secondary: High Score Table** — browser-persistent leaderboard (localStorage) with
name entry on new records, displayed on the title and VICTORY screens.

---

## v3 Step tracker

Step numbering continues from v2 (Steps 1–33).

| Step | ID  | Description                              | Phase A (Dev) | Phase B (Test) | Status      |
|------|-----|------------------------------------------|---------------|----------------|-------------|
| 34   | F1  | Opening feel — PLAYER_SPAWN_Z tuning     | NOT STARTED   | NOT STARTED    | NOT STARTED |
| 35   | F2  | Wave 1 variety — Stages 4–10 openers    | NOT STARTED   | NOT STARTED    | NOT STARTED |
| 36   | F3  | Difficulty curve audit                   | NOT STARTED   | NOT STARTED    | NOT STARTED |
| 37   | H1  | High score table (localStorage bridge)   | NOT STARTED   | NOT STARTED    | NOT STARTED |
| 38   | U1  | Stage Clear stats screen                 | NOT STARTED   | NOT STARTED    | NOT STARTED |

---

## Deferred items (carry-forward from v2)

| ID | Item | Notes |
|----|------|-------|
| OD2 | Lighthouse 100 PWA score | Needs `screenshots` in manifest.json after live deploy |
| OD3 | Custom domain | `CNAME` in `static/`; configure GitHub Pages |
| OD4 | Mobile touch controls | Not planned |
| OD5 | GitHub Pages live deploy | CI/CD workflow written (Step 12); user needs to create repo and enable Pages |

---

## v3 Feature specs

---

### Step 34 — F1: Opening feel (PLAYER_SPAWN_Z tuning)

**Problem:** Stage 1 wave 0 front sits at z=52; player spawns at z=21. The 31-tile
gap makes the opening feel empty and unintimidating — the opposite of I.Q.'s
characteristic tension. The original game had roughly 10–15 clear tiles before the
first cube.

**Fix:**

Raise `PLAYER_SPAWN_Z: int = 21 → 37` in `constants.py`.

- Stage 1 gap: `52 − 37 = 15` tiles. Comfortable opening, close to I.Q. feel.
- Stage 2 gap (from spawn, if restarted): `48 − 37 = 11` tiles. Tighter already.
- Stage 6: wave 0 front = 40. `40 − 37 = 3` tiles. Immediate pressure.
- Stage 8+: wave 0 front ≤ 36 < 37 → `clamp_z_before_wave` fires; player starts
  adjacent to wave. Appropriate max-difficulty feel for late stages.
- Stage 10: wave 0 front = 32 → clamp to z=31. Zero-gap opening. Most difficult.

**Knock-on checks required:**

1. `CAMERA_EYE_Z_OFFSET = 19.5` is derived from `PLAYER_SPAWN_Z + 0.5 − CAMERA_FOLLOW_EYE[2]
   = 21.5 − 2.0 = 19.5`. With PLAYER_SPAWN_Z=37: correct offset would be `37.5 − 2.0 = 35.5`.
   **Update `CAMERA_EYE_Z_OFFSET: float = 35.5`** so the camera sits the same distance
   behind the player at spawn as before.
2. `PLAYER_SPAWN_X = 3` — still correct for 7-wide Stage-1 grid (grid.width // 2 = 3). ✓
3. Stage intro animation uses `wave_front_z` as the Y-bias clamp. Recheck
   `_intro_y_bias` in `main.py` — logic is position-independent, no change needed.
4. `player.reset()` uses `PLAYER_SPAWN_Z` directly → moves with the constant. ✓
5. `player.clamp_z_before_wave` fires at Stage 8+ transitions (expected; see above).

**Files:** `constants.py` only (constants change; code is already position-agnostic).

**Acceptance test:**
- Stage 1 wave 0 spawns ~15 tiles away from the player at game start.
- Restarting always places player at (3, 37).
- Camera is still the same visual distance behind the player at spawn.
- Stage 8 and 10 correctly start with player adjacent to the wave front.

---

### Step 35 — F2: Wave 1 variety (Stages 4–10 openers)

**Problem:** Stages 4, 5, 6, 7, 8, 9, and 10 all open with wave 1 using the same
pattern: one Advantage cube in the centre column and all remaining cubes Normal.
After two or three playthroughs the opener is entirely predictable.

**Fix:** Redesign the W1 patterns for Stages 4–10 so each stage's opener is distinct
while remaining achievable (not a sudden spike in difficulty).

Design principles for each W1:
- One recognisable signature element (specific A/F placement, gap in the row, etc.)
- Blast-safety rule: A and F must be ≥ 2 columns apart in the same row.
- Ideal-step count updated to match the new pattern.
- Mirror-safe: any pattern must be valid in both its forward and X-mirrored form.

**Proposed W1 signatures:**

| Stage | Width | New W1 signature |
|-------|-------|------------------|
| 4 | 7 | Left-skewed A (col 1), sparse back row |
| 5 | 9 | Two A cubes at cols 2 & 6, Normal fill |
| 6 | 9 | F in centre (col 4), A flanking at cols 1 & 7 |
| 7 | 9 | Checkerboard Normal, no A or F |
| 8 | 9 | A at col 0 (far left), rest Normal — corner control challenge |
| 9 | 11 | Two F cubes flanking (cols 1 & 9), A at col 5 |
| 10 | 11 | Three A cubes (cols 2, 5, 8), all other Normal — chain detonate opener |

All signatures above are preliminary; exact row layouts are determined during
implementation with full blast-safety verification.

**Files:** `wave_data.py` — update 7 wave W1 definitions and their `ideal_steps`.

**Acceptance test:**
- Stage 4 W1 looks visually different from Stage 5 W1 in the game.
- No A/F pair is within 1 column of each other in any new row.
- Ideal-step counts correctly reflect the new patterns.

---

### Step 36 — F3: Difficulty curve audit

**Problem:** The tick-speed curve was set during initial implementation and has never
been tuned against live play. Several constants may be misaligned:

1. `STAGE_TICK_INTERVALS` — base = 1.2 s, decays 10% every 2 stages. Stage 10 = 0.78 s.
   Is Stage 10 hard enough? Is Stage 1 slow enough to onboard new players?
2. `STAGE_AVALANCHE_TICK_INTERVALS` — avalanche tick speed per stage. Currently a flat
   table; may be too uniform.
3. `PENALTY_THRESHOLD` — how many missed cubes trigger a row deletion. Currently the
   same value for all stages.
4. Perfect bonus thresholds — `ideal_steps` counts in `wave_data.py` are hand-computed
   per wave; audit whether the 4-tier bonus distribution is correct given real-play step
   counts.

**Scope:** Constants-only pass. Read `constants.py`, identify any values that are
clearly wrong (e.g. Stage 1 and Stage 2 tick intervals being identical when the
stages should feel clearly different), and update with justification.

**No wave-data or code changes** — if a wave's `ideal_steps` needs correction that
is handled in Step 35 (wave variety).

**Deliverable:** Updated constant values with comments explaining the rationale for
each change. At minimum, verify the Stage 10 tick interval creates genuine time
pressure.

**Files:** `constants.py` only.

---

### Step 37 — H1: High score table (localStorage bridge)

**Goal:** Persist the player's top-5 scores across browser sessions. Show scores on
the title screen. Prompt for 3-letter initials when a new high score is achieved.

**Architecture:**

*Storage:*
- Under WASM (`sys.platform == "emscripten"`): read/write `window.localStorage` via
  `platform.window.localStorage.getItem` / `setItem`. Key: `"avalanche_hiscores"`.
  Value: JSON string of `[{"name": "AAA", "score": 12345}, ...]` (up to 5 entries).
- Under desktop Python: in-memory only (no filesystem writes — WASM constraint). Scores
  display during the current session but are not persisted. Silent no-op on save.

*New module `hiscores.py`:*
```
load_scores() -> list[dict]     # read from localStorage or return []
save_scores(scores: list[dict]) # write to localStorage or no-op on desktop
is_high_score(score: int, scores: list[dict]) -> bool
insert_score(name: str, score: int, scores: list[dict]) -> list[dict]
```

*Name entry phase:*
- New `GamePhase.NAME_ENTRY` added to `constants.py`.
- After VICTORY, if score qualifies, enter `NAME_ENTRY` phase.
- HUD shows a 3-letter cursor; LEFT/RIGHT select letter position; UP/DOWN cycle A–Z;
  ENTER confirms.
- On confirm: `insert_score`, `save_scores`, transition to VICTORY display.

*Title screen:*
- `renderer.py` `_draw_title_overlay`: render the top-5 table below the "PRESS ANY KEY"
  prompt. If no scores yet, show "NO SCORES YET".

*VICTORY screen:*
- Show "NEW HIGH SCORE" banner if applicable.
- Display final score rank ("3rd place" etc.).

**WASM guard pattern:**
```python
try:
    import platform
    _ls = platform.window.localStorage
except Exception:
    _ls = None  # desktop — silent fallback
```

**Files:** new `hiscores.py`, `constants.py` (new GamePhase), `game_manager.py`
(NAME_ENTRY transitions), `renderer.py` (title + VICTORY overlays), `hud.py`
(name-entry cursor display), `main.py` (event routing for NAME_ENTRY).

---

### Step 38 — U1: Stage Clear stats screen

**Goal:** When the player clears all 4 waves in a stage, show a brief stats screen
before advancing to the next stage (or VICTORY). This gives players feedback on their
performance per stage rather than only at the end of the full run.

**Stats to display:**
- **Perfect waves:** N / 4 (how many waves were Perfect this stage)
- **IQ earned this stage:** cumulative IQ change attributable to this stage's scoring
- **Rows lost:** row deletions that occurred during this stage
- **Stage bonus:** any multiplier applied

**Implementation:**
- `GameManager` tracks per-stage perfect count (`_stage_perfect_waves: int`),
  row deletions (`_stage_rows_lost: int`), and score at stage start (`_score_at_stage_start: int`).
- These reset at each stage start (`_on_stage_complete`, `start_first_wave`).
- `GamePhase.STAGE_CLEAR` already exists; currently it just shows "STAGE CLEAR" text.
- Extend `renderer.py` `_draw_stage_clear_overlay` to show the stat table.
- Hold duration: `END_SCREEN_HOLD` (same as GAME_OVER/VICTORY) or a separate
  `STAGE_CLEAR_HOLD = 3.0` constant.

**Files:** `game_manager.py`, `renderer.py`, `constants.py` (new hold constant).

---

## Implementation order

The steps are sequenced so each build on a stable base:

```
34 (PLAYER_SPAWN_Z) → 35 (wave variety) → 36 (difficulty audit)
→ 37 (high score) → 38 (stage clear stats)
```

Steps 34–36 are pure-game-feel changes with no new UI state. Steps 37–38 add UI
phases and can be implemented together if desired (both touch `renderer.py`).

---

## Verification approach (all steps)

1. Desktop smoke test — `uv run python main.py`; confirm no errors.
2. Self-test — invariant assertions / manual scenario walk-through.
3. Browser test — `bash run_dev.sh`, open `http://localhost:8000`.
4. Expert panel — 4 parallel agents per `.claude/memory/project_expert_panel.md`.
5. User review — `docs/STEP<N>_REVIEW.md` + await explicit approval.

---

## Out of scope for v3

- Mobile touch controls
- Custom domain / CNAME
- Lighthouse 100 score (OD2) — do after live GitHub Pages deploy
- New cube types or game modes
- Multiplayer
