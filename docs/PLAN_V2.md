# Avalanche — v2 Plan

## Status: Step 26 approved — Step 27 (camera) is next

v2 work lives on the `v2` branch. All changes are localhost-tested and panel-reviewed
before merging to `master` / deploying to GitHub Pages.

---

## Resumption notes

When starting a new v2 session:
1. Read `docs/PROGRESS.md` for the v1 history and the full step tracker (Steps 1–25).
2. Read **this file** for the v2 roadmap and the current step.
3. Check the v2 step tracker below, then read the corresponding spec section.
4. The review pipeline from `CLAUDE.md` hard rule 4 is mandatory for every step:
   self-test → expert panel → `docs/STEP<N>_REVIEW.md` → await user approval.
5. v2 branch policy: all work on `v2`; merge to `master` (and push to GitHub Pages)
   only when the user explicitly approves.

---

## v2 Step tracker

Step numbering continues from v1 (Steps 1–25).

| Step | ID  | Description                          | Phase A (Dev)    | Phase B (Test) | Status               |
|------|-----|--------------------------------------|------------------|----------------|----------------------|
| 26   | BF1 | Turbo freeze exploit fix             | APPROVED         | APPROVED       | APPROVED 2026-05-06  |
| 27   | V1  | Player-following camera + zoom       | NOT STARTED      | NOT STARTED    | NOT STARTED          |
| 28   | V2  | All waves visible + activation system | NOT STARTED      | NOT STARTED    | NOT STARTED          |
| 29   | V3  | Stage intro rolling animation        | NOT STARTED      | NOT STARTED    | NOT STARTED          |
| 30   | V4  | Stages 3–10 (full speed progression) | NOT STARTED      | NOT STARTED    | NOT STARTED          |
| 31   | V5  | Graphics rework (AA + resolution)    | NOT STARTED      | NOT STARTED    | NOT STARTED          |

**Phase A values:** `NOT STARTED` → `IN PROGRESS` → `AWAITING USER`
**Phase B values:** `NOT STARTED` → `IN PROGRESS` → `APPROVED <date>`

---

## Outstanding deferred items (carry-forward from v1)

### OD1 — Stage 3+ wave data
Subsumed by Step 30. Stages 3–10 are the primary v2 content deliverable.

### OD2 — Lighthouse 100 PWA score
A `screenshots` manifest entry is needed for a perfect Lighthouse score.
Requires a real screenshot taken after the game is deployed.
**File:** `static/manifest.json`.

### OD3 — Custom domain
Add a `CNAME` file to `static/` and configure GitHub Pages when desired.

### OD4 — Mobile / touchscreen controls
Game is `orientation: landscape`, keyboard-only by design. Not planned for v2.

---

## v2 Feature specs

---

### Step 27 — Player-following camera + zoom (V1)

**Goal:** The camera centres on the player cube at all times, at the same
isometric angle but significantly closer. When the player moves right, the
world scrolls left; when the player moves toward the back, the world scrolls
toward the camera. The title/game-over/victory screens continue to use a fixed
overview camera.

**Design:**

*Constants (`constants.py`):*
```python
# Offset from camera target (player world pos) to camera eye, in world space.
# Same elevation angle as the current Step 24 tuning (~28°); distance halved.
CAMERA_FOLLOW_OFFSET: tuple[float, float, float] = (0.0, 10.0, -18.0)
# Narrower FOV for the follow camera gives a less fish-eye look at close range.
CAMERA_FOLLOW_FOV: float = 42.0
# Existing CAMERA_POS / CAMERA_TARGET / CAMERA_FOV kept as the overview camera
# used for TITLE / GAME_OVER / VICTORY screens.
```

*Renderer (`renderer.py`):*
- The `vp_matrix` is currently computed once in `__init__` (camera is fixed).
- Add `rebuild_vp(eye: Vec3, target: Vec3) -> None` that recomputes `view`,
  `proj`, and `vp_matrix` in-place. Called every frame during gameplay; called
  once at startup and on title/end-screen transitions.
- Existing `project_vertex` / `project_face` / `project_triangle` are unchanged.

*Player (`player.py`):*
- Add `world_pos` property: `(self._grid_x + 0.5, 0.0, self._grid_z + 0.5)`.
  The +0.5 centres the camera on the tile, not the tile origin.

*Main loop (`main.py`):*
```python
# Every frame before building the face list:
if game.phase in _FOLLOW_CAMERA_PHASES:
    wx, wy, wz = player.world_pos
    ox, oy, oz = CAMERA_FOLLOW_OFFSET
    renderer.rebuild_vp(
        eye=(wx + ox, wy + oy, wz + oz),
        target=(wx, wy, wz),
    )
else:
    renderer.rebuild_vp(CAMERA_POS, CAMERA_TARGET)
```
`_FOLLOW_CAMERA_PHASES = {GamePhase.WAVE_ACTIVE, GamePhase.AVALANCHE,
GamePhase.WAVE_RISING, GamePhase.WAVE_CLEARING, GamePhase.PERFECT_CHECK,
GamePhase.STAGE_CLEAR, GamePhase.MENU, GamePhase.STAGE_INTRO}`.

*Effect on view:* When the player stands at (3, 21) (centre front), the camera
looks from (3, 10, 3) toward (3, 0, 21) — the back rows fill the upper screen.
When the player moves to x=0 (left edge), the camera shifts left and the grid
appears to scroll right — exactly the "opposite direction" behaviour described.

**Key files:** `constants.py`, `renderer.py`, `player.py`, `main.py`.

**Acceptance:** The grid no longer appears centred on the screen when the player
is off-centre. Moving the player left causes the terrain to visibly shift right.
The overall view is noticeably closer / more intimate than v1.

---

### Step 28 — All waves visible + activation system (V2)

**Goal:** At the start of each stage, all waves appear simultaneously as static
grey blocks extending back from the active play area. Only the active wave's cubes
have their real colours and are tumbling. When a wave is cleared, the next wave's
cubes activate in place and start tumbling; the game does not "re-spawn" them from
scratch.

**Design:**

*Big picture grid layout for a 4-wave stage:*
```
z = 0               ← player's front edge (fall-off line)
z = 1–20            ← play area / player zone
z = 21              ← PLAYER_SPAWN_Z
z = 22–24           ← active wave (Wave 1, 2–3 rows, tumbling toward z=0)
z = 25              ← gap row (visual separator)
z = 26–28           ← Wave 2 pending (3 rows, static grey)
z = 29              ← gap row
z = 30–32           ← Wave 3 pending
z = 33              ← gap row
z = 34–36           ← Wave 4 pending
```
`GRID_DEPTH` must be at least `max_z + 2`. For a 4-wave stage with 3 rows
each and `WAVE_GAP_ROWS = 1`:
`GRID_DEPTH = 22 + 4*3 + 3*1 + 2 = 39`. Rounded up to 45 for headroom.

`GRID_DEPTH` becomes a dynamically computed value at stage start rather than a
compile-time constant. Alternative: hard-code `GRID_DEPTH = 60` which
accommodates up to 10 waves of 3 rows each with comfortable gaps.

*New constant (`constants.py`):*
```python
GRID_DEPTH: int = 60        # Increased from 25; accommodates full stage lineup
WAVE_GAP_ROWS: int = 2      # Empty rows between consecutive pending waves
PENDING_CUBE_COLOR: ColorRGB = (90, 90, 90)   # Grey used for all pending cubes
```

*`WaveData.spawn_positions(mirror, z_start)` (`wave_data.py`):*
- Add `z_start: int = 0` parameter.
- Row 0 (back of this wave) maps to `z = z_start + row_count - 1 - row_idx`
  instead of the current `GRID_DEPTH - 1 - row_idx`.
- `z_start` is supplied by `GameManager._compute_wave_z_starts()`.

*Pending cube representation:*
- Add `Cube.pending: bool` field (default `False`). Pending cubes exist in the
  `WaveManager._cubes` list but do not participate in tumbling: `_advance_tick`
  skips cubes with `pending == True`. They hold their initial grid position.
- Add `WaveManager.activate_wave_cubes(wave_idx_z_range)` or simpler:
  `WaveManager.activate_pending(grid_z_min, grid_z_max)` which clears
  `pending = False` on cubes whose `grid_z` falls in that range and whose
  `_tumble_elapsed` / position are reset to the correct initial tumble state.

*`GameManager` changes:*
```python
def _compute_wave_z_starts(self) -> list[int]:
    """Return [z_start_0, z_start_1, …] for each wave in the current stage.

    Wave 0 (first to activate) occupies the lowest z range (closest to player).
    Wave N occupies z = sum(rows[0..N-1]) + N*WAVE_GAP_ROWS + BASE_Z.
    BASE_Z = PLAYER_SPAWN_Z + 1 (one tile behind player spawn).
    """

def _spawn_all_waves(self, player: Player) -> None:
    """Place all waves on the grid as pending (grey, static).

    Computes z_starts via _compute_wave_z_starts(), calls
    wave.spawn_positions(mirror=..., z_start=...) for each, places cubes
    in the WaveManager with pending=True. Activates wave 0 immediately.
    """

def _activate_wave(self, wave_idx: int) -> None:
    """Activate pending cubes for wave `wave_idx`.

    Reads _z_starts[wave_idx], calls wave_manager.activate_pending(...) which
    clears pending flags and initialises tumble state on those cubes.
    Sets wave.tick_interval from _cur_tick_interval.
    """
```

*Renderer changes:*
- `_render_cube_faces(cube)`: if `cube.pending`, use `PENDING_CUBE_COLOR` for all
  faces regardless of `cube.cube_type`. Edge colour is `(50, 50, 50)`.
- Pending cubes are included in the face list and sorted by depth normally;
  they just always appear grey.

*`_on_wave_cleared` change:*
- Instead of spawning fresh cubes, call `_activate_wave(wave_idx + 1)`.

**Key files:** `constants.py`, `wave_data.py`, `wave_manager.py`,
`game_manager.py`, `renderer.py`.

**Acceptance:** At stage start, the full layout of all waves is visible as
grey blocks extending toward the back. Active cubes have their correct colours
and tumble. When wave 1 clears, the grey cubes of wave 2 immediately take on
their real colours and begin tumbling.

---

### Step 29 — Stage intro rolling animation (V3)

**Goal:** When a stage begins (all waves now visible on the grid), a sinusoidal
wave propagates along the z-axis, causing cubes to rise and fall in sequence
("stadium wave" effect). After the animation completes, wave 0 activates.

**Design:**

*New `GamePhase.STAGE_INTRO` (`constants.py`):*
- Inserted between `TITLE` and `WAVE_ACTIVE` in the enum. Added to
  `_FOLLOW_CAMERA_PHASES` in `main.py`.

*New constants:*
```python
STAGE_INTRO_DURATION: float = 2.8    # Seconds the animation plays
INTRO_WAVE_AMPLITUDE: float = 1.2   # Peak Y rise above base (world units)
INTRO_WAVE_SPEED: float = 2.5       # Wave propagation speed (grid rows/second)
INTRO_WAVE_CYCLES: float = 1.5      # Spatial frequency (cycles across full grid)
```

*Animation formula (applied in `renderer.py` `_render_cube_faces`):*
```python
# Only during GamePhase.STAGE_INTRO
y_bias = INTRO_WAVE_AMPLITUDE * max(
    0.0,
    math.sin(
        math.pi * (cube.grid_z / total_z - elapsed / STAGE_INTRO_DURATION)
        * INTRO_WAVE_CYCLES * 2
    )
)
# y_bias is added to every vertex y-coordinate of the cube before projection.
```
All cubes (pending and would-be active wave 0) receive the animation. Input is
ignored during `STAGE_INTRO` (the wave is not yet moving, player cannot move).

*Transition:*
- `GameManager` tracks `_intro_elapsed: float`.
- When `_intro_elapsed >= STAGE_INTRO_DURATION`, call `_activate_wave(0)` and
  transition phase to `WAVE_ACTIVE`.

*`_on_stage_complete` / `start_first_wave`:*
- Both transition to `STAGE_INTRO` (not `WAVE_ACTIVE` directly).
- First-stage start also goes through `STAGE_INTRO`.

**Key files:** `constants.py`, `game_manager.py`, `renderer.py`, `main.py`.

**Acceptance:** Stage start shows all grey cubes, then a visible sine wave
ripples through them. After ~3 seconds the wave settles, then wave 0's cubes
flash to their real colours and begin tumbling.

---

### Step 30 — Stages 3–10 (V4)

**Goal:** Extend the game from 2 stages to 10. Each stage increases tumble speed
by 10 % (×0.9) and introduces harder wave patterns — more forbidden cubes, more
complex ADVANTAGE/FORBIDDEN interplay, and more rows per wave. The total stage
count matches the number of meaningful tick-speed increments before the interval
becomes punishingly fast (≈ 0.52 s).

**Tick-speed progression:**
| Stage | Normal interval | Avalanche interval |
|-------|----------------|--------------------|
| 1 | 1.20 s | 0.15 s |
| 2 | 1.08 s | 0.14 s |
| 3 | 0.97 s | 0.13 s |
| 4 | 0.87 s | 0.12 s |
| 5 | 0.79 s | 0.11 s |
| 6 | 0.71 s | 0.10 s* |
| 7 | 0.64 s | 0.10 s* |
| 8 | 0.57 s | 0.10 s* |
| 9 | 0.52 s | 0.10 s* |
| 10 | 0.46 s | 0.10 s* |

*Floored at 0.10 s + ε to satisfy the `DT_CLAMP < interval` assertion
(DT_CLAMP = 0.1 s). Minimum reachable is 0.101 s.*

*Constants (`constants.py`):*
```python
STAGE_TICK_INTERVALS: list[float] = [
    1.20, 1.08, 0.97, 0.87, 0.79, 0.71, 0.64, 0.57, 0.52, 0.46
]
STAGE_AVALANCHE_TICK_INTERVALS: list[float] = [
    0.15, 0.14, 0.13, 0.12, 0.11, 0.101, 0.101, 0.101, 0.101, 0.101
]
IQ_DIFFICULTY_MULTIPLIERS: list[float] = [
    1.00, 1.10, 1.21, 1.33, 1.46, 1.61, 1.77, 1.94, 2.14, 2.35
]
```
`TICK_SPEED_DECAY` is no longer used (explicit table replaces it); the constant
is kept but marked deprecated to avoid breaking the `_cur_tick_interval` property
in `game_manager.py` until that property is updated to use the table directly.

*Wave data design goals per stage (cumulative from Stage 1):*

| Stage | Waves | Max rows | Forbidden density | Notes |
|-------|-------|----------|-------------------|-------|
| 1 | 4 | 2 | low | Exists |
| 2 | 4 | 3 | medium | Exists |
| 3 | 5 | 3 | medium | New: first 5-wave stage |
| 4 | 5 | 3 | high | New: paired FOREBIDDENs in every wave |
| 5 | 5 | 4 | high | New: 4-row waves introduced |
| 6 | 6 | 4 | high | New: first 6-wave stage |
| 7 | 6 | 4 | very high | New: checkerboard FORBIDDEN patterns |
| 8 | 6 | 5 | very high | New: 5-row waves |
| 9 | 7 | 5 | extreme | New: ADVANTAGE surrounded by FORBIDDEN |
| 10 | 7 | 5 | extreme | New: minimal safe paths, all FORBIDDEN perimeter |

*`wave_data.py`* gains `STAGE_3_WAVES` through `STAGE_10_WAVES` tuples, each
following the same `WaveData` structure. `STAGES` is extended to 10 entries.

*`game_manager._on_stage_complete`* assertion update:
```python
# Old: assert self._stage_index < len(STAGES)
# New: after last stage, transition to VICTORY instead of asserting.
if self._stage_index >= len(STAGES):
    self._phase = GamePhase.VICTORY
    return
```

**Key files:** `wave_data.py`, `constants.py`, `game_manager.py`.

**Acceptance:** The game progresses from Stage 1 through Stage 10, each faster
than the last. Clearing Stage 10 shows the VICTORY screen. IQ multipliers scale
correctly — a perfect Stage 10 run scores ~2.35× a perfect Stage 1 run.

---

### Step 31 — Graphics rework (V5)

**Goal:** Higher apparent resolution (larger cubes on screen) and visually
smoother geometry (anti-aliased polygon edges). The isometric aesthetic and
retro colour palette are preserved.

**Design:**

*Screen resolution (`constants.py`):*
```python
SCREEN_WIDTH: int = 1280    # Up from 960
SCREEN_HEIGHT: int = 720    # Up from 640
```
The perspective projection uses `aspect = width / height`, so no other math
changes. HUD layout uses `SCREEN_WIDTH`/`SCREEN_HEIGHT` and reflows automatically.

*Anti-aliased cube edges (`renderer.py`):*
- `project_face` and `project_triangle` currently call `pygame.draw.polygon`
  twice — once for fill, once for edge outline.
- Replace the edge-outline draw with `pygame.draw.aalines(surface, color,
  closed=True, points)`. This gives sub-pixel smooth edges on the projected
  polygons, which are the primary source of the "jagged" appearance.
- `pygame.draw.aalines` is available in pygame-ce on all platforms including
  WASM; it does not require `gfxdraw`.
- The fill polygon (flat-shaded) remains `pygame.draw.polygon` — only the
  outlines switch to anti-aliased.

*Cube edge width:*
- `edge_width` in `CUBE_TYPES` currently defaults to 1. With anti-aliased
  `aalines`, `edge_width` has no effect (aalines is always 1px). Update
  `CUBE_TYPES` accordingly; widen the FORBIDDEN edge by drawing it twice
  (two offset passes) to preserve the distinctive thick red outline.

*Incidental zoom:*
- The Step 27 `CAMERA_FOLLOW_OFFSET` of `(0, 10, -18)` already renders cubes
  roughly 1.6× larger in screen pixels than the current fixed camera.
  Combined with the resolution bump, effective cube pixel size increases ~2×
  compared to v1 — the primary driver of the "higher resolution" appearance.

**Key files:** `constants.py`, `renderer.py`.

**Acceptance:** Cube edges appear smooth (no staircasing). Screen is 1280×720.
The game looks noticeably crisper than v1 at the same monitor size.
No framerate regression in the browser (aalines is O(n vertices), same as
the outline polygon draw it replaces).

---

## Implementation order and dependencies

```
Step 27 (camera)
    ↓
Step 28 (all waves visible)   ← depends on camera being closer (Step 27
    ↓                           confirms the grid layout is visible)
Step 29 (intro animation)     ← depends on all-waves architecture (Step 28)
    ↓
Step 30 (stages 3–10)         ← depends on activation system (Step 28)
    ↓
Step 31 (graphics rework)     ← independent; can apply to any prior state
```

Step 31 is independent and can be interleaved with Steps 28–30, but is listed
last so the review build reflects the final visual appearance before merging
to `master`.

---

## Outstanding deferred items (v3 candidates)

- **Lighthouse 100 PWA score** — needs `screenshots` manifest entry; requires
  live deployment screenshot.
- **Custom domain** — `CNAME` file in `static/`.
- **Stage 11+** — extend beyond Stage 10 once playtesting determines the
  difficulty ceiling.
- **Mobile / touchscreen** — not planned.

---

## Session log

### Session 2026-05-06 — v2 branch created + Step 26 implemented

- v2 branch created from `v1.0` tag (post-audio, dev-overlay-removed).
- Codebase audit: no TODO/FIXME comments; `STAGES` bounded to 2; deferred
  items catalogued above.
- Turbo freeze bug analysed in full. Fix designed and applied to
  `wave_manager.py` `tick_interval.setter`.
- ruff + mypy --strict: clean.
- Expert panel: all 4 reviewers APPROVED.
- `docs/STEP26_REVIEW.md` written. User approved 2026-05-06.
- Not yet merged to master (user's explicit instruction).

### Session 2026-05-06 — v2 vision specified; full plan written

- User specified v2 vision: player-following closer camera; all waves visible
  at stage start with grey pending cubes; stage intro rolling animation; as
  many stages as tick speed increases (~10); smoother/higher-resolution graphics.
- Steps 27–31 designed in full (see feature specs above).
- Step 27 is next.
