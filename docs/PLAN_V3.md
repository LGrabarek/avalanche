# Avalanche — v3 Plan

## Status: COMPLETE ✓

All Steps 34–45 implemented and approved. v3 branch ready to merge to `master`.

---

## Resumption notes

When starting a new v3 session:
1. Read `docs/PROGRESS.md` for the full step history (Steps 1–33).
2. Read **this file** for the v3 roadmap and the current step.
3. Check the v3 step tracker below, then read the corresponding spec section.
4. The review pipeline from `CLAUDE.md` hard rule 4 is mandatory for every step.

---

## v3 Themes

**Feel & Balance** — tighten the opening gap, differentiate wave openers, audit the
difficulty curve so each of the 10 stages feels distinct.

**Visual Depth** — extend the grid platform downward as an imposing table; replace
the player cube with an animated character.

**Replayability** — multiple hand-designed arrangement variants per wave, randomly
selected at game start; the selection is recorded as a seed and shown on the leaderboard
so players can compare "same-seed" scores.

**Live Feedback** — row gained/lost counter in the HUD; Stage Clear stats screen;
high-score table persisted in browser localStorage.

---

## v3 Step tracker

Step numbering continues from v2 (Steps 1–33).

| Step | ID  | Description                                  | Phase A (Dev)       | Phase B (Test) | Status               |
|------|-----|----------------------------------------------|---------------------|----------------|----------------------|
| 34   | F1  | Opening feel — PLAYER_SPAWN_Z tuning         | APPROVED 2026-05-17 | NOT STARTED    | APPROVED 2026-05-17  |
| 35   | F2  | Wave variety — distinct openers, Stages 1–10 | APPROVED 2026-05-08 | NOT STARTED    | APPROVED 2026-05-08  |
| 36   | F3  | Wave pool system + crush-retry gate          | APPROVED 2026-05-18 | NOT STARTED    | APPROVED 2026-05-18  |
| 37   | H1  | High score table (localStorage bridge)       | APPROVED 2026-05-19 | NOT STARTED    | APPROVED 2026-05-19  |
| 38   | U1  | Stage Clear stats screen                     | APPROVED 2026-05-19 | NOT STARTED    | APPROVED 2026-05-19  |
| 39   | U2  | Row gained/lost HUD counter                  | APPROVED 2026-05-19 | NOT STARTED    | APPROVED 2026-05-19  |
| 40   | V1  | Platform depth (grid table walls)            | APPROVED 2026-05-20 | NOT STARTED    | APPROVED 2026-05-20  |
| 41   | V2  | Animated player character                    | APPROVED 2026-05-21 | NOT STARTED    | APPROVED 2026-05-21  |
| 42   | R1  | Wave arrangement variants (pool + shuffle)   | APPROVED 2026-05-21 | NOT STARTED    | APPROVED 2026-05-21  |
| 43   | V3  | Kneel on mark; arm raise on detonate/trigger | APPROVED 2026-05-21 | NOT STARTED    | APPROVED 2026-05-21  |
| 44   | R2  | Wave back-wall + WaveManager depth caps      | APPROVED 2026-05-21 | NOT STARTED    | APPROVED 2026-05-21  |
| 45   | V4  | Row crumble/arrival anims, wave COM camera   | APPROVED 2026-05-23 | NOT STARTED    | APPROVED 2026-05-23  |

---

## Deferred items (carry-forward from v2)

| ID | Item | Notes |
|----|------|-------|
| OD2 | Lighthouse 100 PWA score | Needs `screenshots` in manifest.json after live deploy |
| OD3 | Custom domain | `CNAME` in `static/`; configure GitHub Pages |
| OD4 | Mobile touch controls | Not planned |
| OD5 | GitHub Pages live deploy | CI/CD workflow written (Step 12); user needs to create repo and enable Pages |

---

## Implementation order rationale

```
34 (spawn tuning)  ─┐
35 (wave variety)  ─┤─ feel & balance foundation ──────────────────────────────────┐
36 (diff audit)    ─┘                                                               │
                                                                                    │
37 (high score)    ─┐─ scoring UI ─────────────────────────────────────────────────┤
38 (stage stats)   ─┘                                                               │
                                                                                    │
39 (row counter)   ─── live HUD feedback (independent, could slot anywhere) ────────┤
                                                                                    │
40 (table walls)   ─┐─ visual depth (renders before player character change) ───────┤
41 (player char)   ─┘                                                               │
                                                                                    │
42 (variants)      ─── needs 35 (variant patterns) + 37 (leaderboard infra) ───────┘
```

Steps 34–36 are constants/wave-data changes with no new phases.
Steps 37–39 add UI state and HUD elements; can be interleaved if desired.
Steps 40–41 are pure rendering; 40 before 41 so the scene composition is stable when
the player character geometry changes.
Step 42 is the capstone — requires the variant pattern library from Step 35 and the
leaderboard infrastructure from Step 37.

---

## v3 Feature specs

---

### Step 34 — F1: Opening feel (PLAYER_SPAWN_Z tuning)

**Problem:** Stage 1 wave 0 front sits at z=52; player spawns at z=21 — 31 empty
tiles before the first cube. This makes the opening feel quiet and unintimidating,
the opposite of I.Q.'s characteristic tension (original had ~10–15 clear tiles).

**Fix:** Raise `PLAYER_SPAWN_Z: int = 21 → 37` in `constants.py`.

Gap analysis after change:

| Stage | Wave 0 front z | Gap from spawn (z=37) | Feel |
|-------|---------------|-----------------------|------|
| 1 | 52 | 15 tiles | Comfortable opener |
| 2 | 48 | 11 tiles | Tighter |
| 4 | 44 | 7 tiles | Immediate |
| 6 | 40 | 3 tiles | Near-instant pressure |
| 8 | 36 | clamp → z=35 | Adjacent to wave |
| 10 | 32 | clamp → z=31 | Zero-gap, maximum danger |

Stages 8–10 trigger `clamp_z_before_wave` automatically — appropriate for the
hardest stages.

**Knock-on checks:**

1. `CAMERA_EYE_Z_OFFSET` is derived from `PLAYER_SPAWN_Z + 0.5 − CAMERA_FOLLOW_EYE[2]`.
   Old: `21.5 − 2.0 = 19.5`. New: **`37.5 − 2.0 = 35.5`**.
   Update `CAMERA_EYE_Z_OFFSET: float = 35.5`.
2. `PLAYER_SPAWN_X = 3` — still correct for 7-wide Stage-1 grid. ✓
3. Stage intro `_intro_y_bias` in `main.py` is z-independent. ✓
4. `player.reset()` reads `PLAYER_SPAWN_Z` directly. ✓
5. `player.clamp_z_before_wave` fires at Stages 8+ (designed behaviour). ✓

**Files:** `constants.py` only.

---

### Step 35 — F2: Wave variety (distinct openers, Stages 4–10)

**Problem:** Stages 4–10 all open with the identical pattern: one Advantage cube in
the centre column, all other cubes Normal. The opener is fully predictable after one
playthrough.

**Fix:** Redesign the Wave 1 pattern for each of Stages 4–10 so each stage's opener
has a distinct signature. These patterns also become the first "variant slot" in the
wave arrangement library used by Step 42.

**Design rules for each W1:**
- One clearly recognisable signature (specific A/F placement, gaps, corner plays).
- A/F blast-safety: any A and F in the same row must be ≥ 2 columns apart.
- Mirror-safe: pattern must be legal in both un-mirrored and X-mirrored form.
- `ideal_steps` recomputed for the new layout.

**Proposed signatures (preliminary — exact rows set during implementation):**

| Stage | Width | W1 signature |
|-------|-------|--------------|
| 4 | 7 | A at col 1 (left-skewed), sparse back row — introduces off-centre blasting |
| 5 | 9 | Dual A at cols 2 & 6, Normal fill — teaches chain detonate on wider grid |
| 6 | 9 | F at col 4 (centre), A flanking at cols 1 & 7 — forbidden trap in the middle |
| 7 | 9 | Dense Normal grid, no A or F — pure efficiency test |
| 8 | 9 | A at col 0 (far-left corner) — corner control under time pressure |
| 9 | 11 | F flanking at cols 1 & 9, A at col 5 — wide grid with lethal edges |
| 10 | 11 | Triple A at cols 2, 5, 8 — chain-detonate opener across the full width |

**Files:** `wave_data.py` — 7 W1 redefinitions and `ideal_steps` updates.

---

### Step 36 — F3: Difficulty curve audit

**Problem:** Tick speed, avalanche speed, and penalty thresholds were set during early
implementation and have never been tuned against live play.

**Scope:** Read `constants.py` and verify/adjust:

1. `STAGE_TICK_INTERVALS` — base 1.2 s, −10% every 2 stages. Stage 10 = 0.78 s.
   Is that tight enough for a 7-row wave? Check against original I.Q. timings.
2. `STAGE_AVALANCHE_TICK_INTERVALS` — per-stage avalanche speed table.
3. `PENALTY_THRESHOLD` — missed-cube count before a row deletion. Should this increase
   per stage (harder to save yourself in later stages)?
4. `MOVE_COOLDOWN` — movement feel at high tick speeds. Does it still allow dodging at
   Stage 10 0.78 s intervals?

**Deliverable:** Updated constants with justification comments. Constants-only change;
no code or wave-data edits.

**Files:** `constants.py` only.

---

### Step 37 — H1: High score table (localStorage bridge)

**Goal:** Persist the player's top-5 scores across browser sessions, show on title
screen, prompt for 3-letter name on new record.

**Architecture:**

*Storage layer — new `hiscores.py`:*
```python
load_scores() -> list[dict]           # read from localStorage (WASM) or [] (desktop)
save_scores(scores: list[dict]) -> None  # write to localStorage or no-op
is_high_score(score: int, scores: list[dict]) -> bool
insert_score(name: str, score: int, scores: list[dict]) -> list[dict]  # top-5 sorted
```

WASM guard:
```python
try:
    import platform
    _ls = platform.window.localStorage   # Pygbag JS bridge
except Exception:
    _ls = None                            # desktop: silent no-op
```

localStorage key: `"avalanche_hiscores"`. Value: JSON string of up to 5 entries.
Each entry: `{"name": "AAA", "score": 12345}`. Step 42 will extend entries with
a `"seed"` field when wave variants are introduced.

*New `GamePhase.NAME_ENTRY`:*
- Entered from VICTORY when `is_high_score(final_score, scores)` is True.
- 3-letter name cursor: LEFT/RIGHT to select position; UP/DOWN to cycle A–Z; ENTER
  to confirm. Rendered by `renderer.py`; key routing in `main.py`.
- On confirm: `insert_score` → `save_scores` → back to VICTORY display.

*Title screen changes (`renderer.py`):*
- Below "PRESS ANY KEY": render top-5 table (rank, name, score).
- If no entries yet: "NO SCORES YET".

*VICTORY screen changes:*
- "NEW HIGH SCORE!" banner if applicable.
- "Rank N of 5" display.

**Files:** new `hiscores.py`, `constants.py` (GamePhase.NAME_ENTRY), `game_manager.py`
(NAME_ENTRY transitions), `renderer.py` (title + VICTORY + name-entry overlays),
`hud.py` (name-entry cursor), `main.py` (event routing for NAME_ENTRY keys).

---

### Step 38 — U1: Stage Clear stats screen

**Goal:** Show per-stage performance stats during the STAGE_CLEAR hold, giving players
feedback before advancing rather than waiting until the VICTORY screen.

**Stats panel (rendered over the existing STAGE CLEAR overlay):**

```
── STAGE 3 CLEAR ──────────────────
  Perfect waves    3 / 4
  IQ this stage    +1,240
  Rows lost           2
  Rows surviving     58
───────────────────────────────────
```

**Implementation:**
- `GameManager` gains: `_stage_perfect_waves: int`, `_stage_rows_lost: int`,
  `_score_at_stage_start: int`. All reset in `_on_stage_complete` and
  `start_first_wave`.
- `_stage_rows_lost` incremented wherever `grid.delete_front_row()` is called
  (wave penalty, forbidden capture, avalanche penalty).
- `renderer.py` `_draw_stage_clear_overlay` reads these values via new properties.
- Hold: separate `STAGE_CLEAR_HOLD: float = 4.0` constant (longer than wave-rising;
  gives time to read the stats).

**Files:** `game_manager.py`, `constants.py` (STAGE_CLEAR_HOLD), `renderer.py`.

---

### Step 39 — U2: Row gained/lost HUD counter

**Goal:** Show a live, animated +/− row counter on screen whenever a row is gained
or lost. Green for gains (Perfect restore), red for losses (penalty, forbidden,
avalanche).

**Design:**

```
  [+1 ▲]   ← green, fades over 1.5 s, floats upward
  [−1 ▼]   ← red, fades over 1.5 s, floats downward
```

Multiple events can stack: if 2 rows are lost in quick succession, two separate
floating labels appear. Each fades independently.

**Implementation:**
- New `RowDeltaEvent` dataclass in `effects.py`:
  ```python
  @dataclass
  class RowDeltaEvent:
      delta: int       # +1 or -1
      elapsed: float   # seconds since spawn
      screen_y: float  # current vertical position (floats)
  ```
- `FlashEffects` gains `spawn_row_delta(delta: int)` and `update_row_deltas(dt)`
  methods. Bound: `assert len(self._row_deltas) < 16` (Rule 3 guard).
- Call sites in `game_manager.py`: wherever `grid.delete_front_row()` is called →
  `effects.spawn_row_delta(-1)`; wherever `grid.restore_front_row()` is called →
  `effects.spawn_row_delta(+1)`.
- `main.py` renders `effects.row_deltas` as floating text using `renderer.draw_row_delta`
  or direct `pygame.font` calls (HUD layer, not 3D layer).

**Position:** Fixed screen position (e.g. top-right of play area), floating up for
gains and down for losses. Always in HUD layer (drawn after 3D scene).

**Files:** `effects.py`, `game_manager.py` (call sites), `main.py` (render loop).

---

### Step 40 — V1: Platform depth (grid table walls)

**Goal:** Extend the visible edges of the grid platform downward to create the
impression of an impossibly tall table — the player cube stands on top of a towering
stack that extends far below the screen. This is a pure rendering addition: no game
logic changes.

**What to render:**

For each visible edge of the grid (left edge column, right edge column, front edge
row), extend the tile face downward by `TABLE_DEPTH` world units. The result is a
set of rectangular quads that hang below each edge tile, forming the side walls of
the table.

```
  ┌────────────────────────┐  ← grid top (existing tiles)
  │  . . . . . . . . . .  │
  │  . . . . . . . . . .  │
  │  . . . . . . . . . .  │
  └────────────────────────┘
  │                        │  ← new side walls (TABLE_DEPTH tall)
  │  ░░░░░░░░░░░░░░░░░░░░  │    darker shade of tile colour
  │  ░░░░░░░░░░░░░░░░░░░░  │
  ▼  (extends below viewport)
```

**Implementation:**

- New constant: `TABLE_DEPTH: float = 8.0` in `constants.py`. Tunable — 8 units
  creates a dramatic drop without overloading the painter's-algorithm face list.
- New constant: `TABLE_SIDE_COLOR: ColorRGB = (40, 40, 55)` — darker than the grid
  top to suggest depth.
- `cube_data.py` — add `get_table_edge_faces(grid_width, grid_depth, front_edge_z,
  table_depth)` returning a list of `(4 world vertices, color)` quads. Generates:
  - Left wall: x=0 downward strip from z=front_edge_z to z=grid_depth-1.
  - Right wall: x=grid_width downward strip.
  - Front wall: z=front_edge_z downward strip (width of the grid).
  - Back wall: optional, usually occluded.
- `renderer.py` `render_frame` — call `get_table_edge_faces(...)` and add to the face
  list before the painter's-algorithm sort. These faces integrate with existing depth
  sorting automatically.
- Front wall z-position updates when `grid.front_edge_z` changes (row deletions).

**Acceptance test:**
- The platform visually hangs over a dark void below.
- The front wall recedes correctly when rows are deleted.
- No Z-fighting or painter's-algorithm artifacts at the join between grid tiles and
  table walls.
- No performance regression (wall face count is O(grid_width + grid_depth), bounded).

**Files:** `constants.py` (TABLE_DEPTH, TABLE_SIDE_COLOR), `cube_data.py`
(`get_table_edge_faces`), `renderer.py` (call site + face list inclusion).

---

### Step 41 — V2: Animated player character

**Goal:** Replace the static player cube with a small animated humanoid figure whose
limbs move as they walk and who visibly reacts to being crushed.

**Scope and constraint:** The game renders in software 3D (manual polygon projection,
painter's algorithm, ~300 faces/frame budget). The character must be low-poly enough
to stay within that budget while still reading clearly as a running figure. Target:
≤ 20 additional faces per frame.

**Character design (low-poly, isometric-friendly):**

```
    ○          ← head (square or sphere approximated as cube)
   ═╪═         ← torso (rectangular prism)
   / \         ← legs (two rectangular prisms, animated by rotation)
  /   \
```

Rendered as a collection of convex prisms (same projection pipeline as cubes):
- Head: small cube, 6 faces, player blue colour.
- Torso: taller rectangle, 6 faces, darker blue.
- Left leg / Right leg: each a small rectangle, 6 faces, darkest blue. Animated.
- Optional arms: 2 × 4 faces each.

Total: ~26–34 faces. Replaces the current 6-face player cube.

**Animation states:**

| State | Trigger | Animation |
|-------|---------|-----------|
| Idle | Player not moving | All parts stationary |
| Walking | Movement cooldown ticking | Legs swing alternately, ±15° hip rotation |
| Crushed | `player.is_crushed` | Character flattened (squash-and-stretch on y-axis) |

Leg swing uses the same `tumble_progress`-style interpolation already in `cube_data.py`
— driven by `player._cooldown / MOVE_COOLDOWN` (0→1 per step).

Walk direction: when moving in −Z (toward wave) the character faces forward; +Z
backward; ±X sideways. Four facing orientations; no sub-tile interpolation needed.

**Architecture:**

- New `player_visual.py` (or extend `cube_data.py`): `get_player_character_faces(
  grid_x, grid_z, walk_progress, facing, is_crushed)` returning face list.
- `player.py` exposes `walk_progress: float` (0→1 over move cooldown) and
  `facing: Direction | None` (last move direction).
- `renderer.py` replaces `get_player_faces(...)` call with
  `get_player_character_faces(...)`.
- `main.py` passes `player.walk_progress` and `player.facing` to renderer.

**Acceptance test:**
- Legs visibly swing when the player moves; stop when idle.
- Crush state clearly different from normal (flattened, red tint).
- Character reads clearly against the grid and cube colours at 1280×720.
- Frame rate unchanged (face count within budget).

**Files:** new or extended `cube_data.py` / `player_visual.py`, `player.py`
(walk_progress, facing), `renderer.py` (character face call), `main.py`.

---

### Step 42 — R1: Wave arrangement variants + seeded leaderboard

**Goal:** Each wave slot in each stage has multiple hand-designed pattern variants.
At game start, one variant is randomly selected per wave slot. The selection is
recorded as a run "seed" and stored in the leaderboard alongside the score — enabling
players to compare "same-seed" results and giving every playthrough a fresh feel.

**Why Step 42 depends on earlier steps:**
- Needs Step 35: the variant pattern library starts with the distinct W1 openers
  designed there. Step 42 adds W2–W4 variants for all 10 stages.
- Needs Step 37: the leaderboard infrastructure (`hiscores.py`, localStorage) already
  exists. Step 42 extends it with a `"seed"` field.

**Architecture:**

*Wave data structure change (`wave_data.py`):*

Current:
```python
STAGE_1_WAVES: tuple[WaveData, ...] = (W1, W2, W3, W4)
```

New:
```python
# Each wave slot is a tuple of 2–4 variants. Game picks one randomly at stage start.
STAGE_1_WAVE_VARIANTS: tuple[tuple[WaveData, ...], ...] = (
    (W1_v1, W1_v2, W1_v3),   # wave slot 0: 3 variants
    (W2_v1, W2_v2),           # wave slot 1: 2 variants
    (W3_v1, W3_v2, W3_v3),   # wave slot 2: 3 variants
    (W4_v1, W4_v2),           # wave slot 3: 2 variants
)
```

`STAGES` becomes `tuple[tuple[tuple[WaveData, ...], ...], ...]` (stages → wave slots
→ variants).

*Seed:*
A seed is a flat list of variant indices, one per wave across all stages:
`[v0_s1, v1_s1, v2_s1, v3_s1,  v0_s2, ...,  v3_s10]` — 40 integers (10 stages × 4
waves). At game start, `random.randint(0, len(variants)-1)` per slot. Stored as a
compact string (e.g. `"2,0,1,2,1,0,2,1,..."`) in the leaderboard entry.

*`game_manager.py` changes:*
- `start_first_wave` selects variants and records the seed.
- `_on_stage_complete` selects the next stage's variants using the pre-rolled seed.
- New property `run_seed: str` exposed to `hiscores.py` on VICTORY.

*Leaderboard entry (extended from Step 37):*
```json
{"name": "AAA", "score": 12345, "seed": "2,0,1,2,1,0,2,1,..."}
```

*Title screen leaderboard:*
Adds a small "seed" column (abbreviated, e.g. first 6 digits) so players can identify
matchable runs.

**Design constraint on variants:**
- Every variant must pass the same blast-safety rule (A/F distance ≥ 2 in same row).
- Variants within a stage should be meaningfully different (not just mirrored copies
  — mirroring already exists as a separate random flip at spawn time).
- Minimum 2 variants per wave slot; target 3 for waves 1–3, 2 for wave 4 (hardest).
- All `ideal_steps` recalculated per variant.

**Total new patterns required:** 10 stages × ~4 waves × ~2.5 avg variants ≈ 100
additional WaveData objects on top of the existing 40 canonical patterns.

**Files:** `wave_data.py` (structural change + 100 new patterns), `game_manager.py`
(variant selection, seed tracking), `hiscores.py` (seed field), `renderer.py`
(seed display on title/VICTORY).

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
