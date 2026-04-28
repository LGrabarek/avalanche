# Avalanche — Implementation Progress

Use this file to track what has been completed, what is in progress, and what remains.
When resuming after a break, read this file first to understand the current state.

---

## Status: Step 12 — GitHub Pages deployment — Phase A AWAITING USER

Post-v1 enhancements in progress (Steps 12–25). See `docs/PLAN.md` (post-v1 section)
for full specs; see the step tracker below for current status of all steps.

**Step 9 Phase A log:**

- New file `wave_data.py`: 4 Stage-1 `WaveData` objects in `STAGE_1_WAVES` tuple.
  `WaveData` holds rows + `ideal_steps`; `spawn_positions(mirror)` emits
  `(grid_x, grid_z, cube_type)` triples with optional X-axis flip.
- `wave_manager.py`: `reset_for_new_wave()` — clear cubes + reset tick timer.
- `grid_manager.py`: `restore_front_row()` — inverse of `delete_front_row`; scans
  from z=0, restores first all-void row. Used for Perfect reward.
- `game_manager.py`: full wave-progression state machine — `start_first_wave`,
  `_spawn_wave` (50% mirror, per-wave state reset), `_on_wave_cleared` (Perfect
  check, bonus award, row restore, next-wave or VICTORY), `_calc_perfect_bonus`
  (4-tier table), `_calculate_final_iq` (score + rows×1000 × 1.00 × 0.00060).
  Step counting wired in `try_mark`, `on_trigger`, `on_detonate`. New properties:
  `wave_index`, `wave_count`, `iq_score`.
- `hud.py`: 7th stat line — `Wave: N/4`; assert updated.
- `main.py`: `start_first_wave(player, STAGE_1_WAVES)` replaces debug spawn;
  `frozen` check includes VICTORY; `_draw_victory_overlay` added.
- Self-tests: 59/59 checks (T1–T16) — reset_for_new_wave, restore_front_row,
  start_first_wave, empty-sequence guard, Perfect bonus tiers, step counting,
  Perfect detection (clean/miss/forbidden/avalanche), mirror, wave progression,
  IQ formula, row restore, HUD properties, target_cube_count.
- **Code Quality required fixes applied**: `assert ideal > 0` in
  `_calc_perfect_bonus`; `type: ignore` comment extended with reason string.
- **Vision Lead comment fixes**: W2/W3/W4 ideal-step derivation comments in
  `wave_data.py` corrected to match the embedded ideal values (13, 14, 16).
- ruff check (excl. test file) + mypy --strict: clean.
- Expert panel: Vision Lead APPROVED, Code Quality APPROVED (fixes applied),
  UX Tester CONCERNS (all Step 10 deferred), Platform Engineer APPROVED.
- `STEP9_REVIEW.md` written. Awaiting user browser verification.

---

## Step 7 fix log (archived)

*Phase A (initial implementation):*
- `game_manager.on_detonate(player)` — collects all ADVANTAGE_TRAP tiles, clears to PLATFORM, fires blast per trap tile.
- `game_manager._execute_blast(cx, cz, player)` — single-tile blast; dispatches cube via `on_detonate` hook.
- `game_manager._mark_trap_area(cx, cz)` — shared helper; sets 3×3 non-void tiles to ADVANTAGE_TRAP.
- `main.py` — KEY_DETONATE (Z) imported and wired in `_drain_events`.
- `hud.py` — controls hint updated to include `Detonate: Z`.

*Phase B revision 1 (after first user feedback):*
- Redesigned: capturing ADVANTAGE marks the full 3×3 green area (was single tile); chain reaction removed — new trap from blast requires separate Z press.

*Phase B revision 2 (after second user feedback — three simultaneous changes):*
- `game_manager._execute_blast`: changed from 3×3 loop per trap tile to single-tile check per trap tile. The green tiles themselves ARE the blast zone; no further expansion.
- `wave_manager.update(dt, front_drop_z)` + `_advance_tick(front_drop_z)`: cubes now drop at the new platform front edge after row deletions (`grid.front_edge_z` passed each frame from `main.py`).
- `grid_manager.front_edge_z` property: scans from z=0 to return the first non-void row.
- `renderer.TriFaceDescriptor` + `project_triangle()`: new triangle projection path.
- `cube_data.get_marker_cone_faces()`: inverted hexagonal cone above every MARKED and ADVANTAGE_TRAP tile (blue/green, apex at y=1.25, base at y=1.50). Appears/disappears in exact sync with tile state.
- `main._build_marker_faces()`: integrates cone faces into the painter's-algorithm face list.
- Expert panel review: all four reviewers APPROVED revision 2.

*Phase B blast-alignment fix (after third user report — blast area appeared 4×4):*
- Root cause: `_execute_blast` called `cube_at(cx, cz)` (logical position) but trap tiles are stored at VISUAL positions. Cube visually at tile `cz` has logical `grid_z = cz + 1` — same offset `capturable_at` already uses.
- Fix: `cube_at(cx, cz)` → `cube_at(cx, cz + 1)` in `_execute_blast`. Blast now hits exactly the cubes visually on the green tiles, not cubes one row in front of them.

---

## Step Tracker

Steps 3+ are split into **Phase A (Development)** and **Phase B (Testing)** per `PLAN.md`; a step is only "complete" once both phases pass.

| Step | Description | Phase A (Dev) | Phase B (Test) | Status |
|------|-------------|---------------|----------------|--------|
| 1 | Scaffold + 3D renderer proof-of-concept | — | — | APPROVED 2026-04-16 |
| 2 | Grid platform + player movement | — | — | APPROVED 2026-04-16 |
| 3 | Cube tumbling animation | — | — | APPROVED 2026-04-17 |
| 4 | Marking + capture | — | — | APPROVED 2026-04-17 |
| 5 | Crush detection + avalanche | AWAITING USER | APPROVED | APPROVED 2026-04-17 |
| 6 | Penalty system + row deletion | APPROVED | APPROVED | APPROVED 2026-04-18 |
| 7 | Advantage cubes + 3x3 blast | APPROVED | APPROVED | APPROVED 2026-04-25 |
| 8 | Forbidden cubes | APPROVED | APPROVED | APPROVED 2026-04-25 |
| 9 | Wave progression + Perfect bonus | APPROVED | APPROVED | APPROVED 2026-04-25 |
| 10 | Polish | APPROVED 2026-04-26 | APPROVED 2026-04-26 | APPROVED 2026-04-26 |
| 11 | PWA packaging | APPROVED 2026-04-27 | APPROVED 2026-04-27 | APPROVED 2026-04-27 |
| 12 | GitHub Pages deployment (CI/CD) | AWAITING USER | NOT STARTED | IN PROGRESS |
| 13 | Turbo / accelerate key | NOT STARTED | NOT STARTED | NOT STARTED |
| 14 | Esc pause menu (restart + options) | NOT STARTED | NOT STARTED | NOT STARTED |
| 15 | Capture animation + flash colour tinting | NOT STARTED | NOT STARTED | NOT STARTED |
| 16 | Enhanced graphics — face shading + camera | NOT STARTED | NOT STARTED | NOT STARTED |
| 17 | HUD font render caching | NOT STARTED | NOT STARTED | NOT STARTED |
| 18 | Transition hold animations | NOT STARTED | NOT STARTED | NOT STARTED |
| 19 | Grid texture + player shadow + danger telegraph | NOT STARTED | NOT STARTED | NOT STARTED |
| 20 | Additional stages (Stage 2+) | NOT STARTED | NOT STARTED | NOT STARTED |
| 21 | Per-stage tick interval table | NOT STARTED | NOT STARTED | NOT STARTED |
| 22 | Bundled `.ttf` font | NOT STARTED | NOT STARTED | NOT STARTED |
| 23 | Movement perpendicular priority | NOT STARTED | NOT STARTED | NOT STARTED |
| 24 | Camera rework | NOT STARTED | NOT STARTED | NOT STARTED |
| 25 | Audio system | NOT STARTED | NOT STARTED | NOT STARTED |

**Phase A values:** `NOT STARTED` → `IN PROGRESS` → `AWAITING USER` (code done, panel clean, STEP<N>_REVIEW.md written).
**Phase B values:** `NOT STARTED` → `IN PROGRESS` (user testing / fix cycle) → `APPROVED <date>`.

---

## Resumption Notes

When starting a new session:
1. Read `../CLAUDE.md` at the project root for hard rules and layout
2. Read this file (`PROGRESS.md`) — status header + step tracker tells you exactly where to resume
3. Read `PLAN.md`:
   - Steps 1–11: original plan (architecture, game mechanics, decisions)
   - Steps 12–25: post-v1 enhancements (full spec for each step)
4. For the current step, read `STEP<N>_REVIEW.md` if it exists (tells you what was built and what to test)
5. Consult `../.claude/memory/MEMORY.md` for the expert panel definition, review process, extensibility rules, and pygbag quirks
6. Continue from where the previous session left off — do not start a new step until the user explicitly approves the current one

---

## Session Log

_Record key decisions, issues encountered, and panel findings here._

### Session 1 — 2026-04-15
- Project created with Research document
- Implementation plan designed and approved
- Stack: Pygame CE + Pygbag (browser WASM) + PWA
- Expert review panel established (Vision Lead, Code Quality, UX Tester, Platform Engineer)
- Python is managed via `uv` (not system PATH); dev server uses `uv run python -m pygbag main.py`
- **Expert Panel Review of Plan** (all 4 reviewers):
  - Vision Lead: APPROVED — added I.Q. scoring algorithm, Ideal Step values, audio metronome
  - Code Quality: APPROVED — added explicit cube type registry with behavior hooks, mark lifecycle, Avalanche sub-state machine
  - UX Tester: CONCERNS resolved — reduced movement cooldown to 0.08s, added Forbidden red outline, miss feedback, crush telegraph, focus-loss pause, controls overlay
  - Platform Engineer: APPROVED — switched to clock.tick(0) for WASM, bundled .ttf font, stale-while-revalidate SW, canvas focus management, sin/cos LUT
  - All findings incorporated into PLAN.md
- Ready to begin Step 1

### Session 2 — 2026-04-16 — Step 1 implementation
- Created `main.py`, `constants.py`, `renderer.py`, `cube_data.py`, `run_dev.sh`, `pygbag.ini`, `pyproject.toml`
- Software 3D pipeline: view matrix from camera, perspective projection, back-face culling via 2D cross product, painter's-algorithm depth sort
- Cube tumble: 90° rotation about leading bottom edge using sin/cos LUT (32 steps per tumble)
- Grid tile geometry + five demo cubes (3 Normal, 1 Advantage, 1 Forbidden) driving visual smoke-test

**Dev-tooling issues resolved during Step 1:**
- `uv run --project` on WSL failed because `/mnt/f/.../.venv` contains Windows Scripts — Linux uv can't manage it. Switched `run_dev.sh` to `uv tool run --from pygbag==0.9.3 pygbag` (uvx) which uses an ephemeral cache venv.
- Installed native Linux `uv` at `/root/.local/bin/uv` for WSL (preview tool runs as root there).
- `--bind 0.0.0.0` broke the browser load because pygbag templates the address into asset URLs and Chrome rejects `http://0.0.0.0:...`. Reverted to default `--bind localhost`; WSL2's `wslrelay.exe` natively forwards Windows localhost ↔ WSL 127.0.0.1.
- A leftover `python.exe` (PID 28464) from an earlier Bash-tool pygbag run held Windows `127.0.0.1:8000`, returning ERR_EMPTY_RESPONSE. Killed it; server came up cleanly.
- `pygame.Clock.get_fps()` returns nonsense under WASM with `clock.tick(0)`. Replaced with rolling dt average over 60 samples.
- pygbag event loop pauses when the tab is hidden (rAF-gated). Preview tool's headless tab keeps `document.hidden=true`, so fresh screenshots stall. Accepted an earlier screenshot captured while the tab was briefly visible (FPS 141–154, Polys 186, grid + 5 cubes of distinct types visible) plus desktop invariant tests as browser verification.

**Self-test (desktop invariants, passed):**
- Tumble math: rest bbox y=(0,1); half-tumble y_peak=1.414, all y ≥ 0 (cube never passes through floor); full-tumble bbox y=(0,1) and pivot edge fixed in place.
- All 3 cube types produce 6 faces with every palette key present (KeyError if a color is missing — defensive coverage check).
- Player geometry: half-extent 0.4 → cube side 0.8.
- Renderer back-face cull + near-plane clip produce ~186 polys for the demo scene.

**Expert panel findings (all resolved, see STEP1_REVIEW.md §3):**
- Game Designer: Advantage green too neon → muted (100,220,100); demo cubes tumbled in lockstep → added per-cube phase_offset.
- Code Quality: hooks were strings → introduced `CubeBehavior` enum; camera derived from grid dims; `_build_faces` now requires full palette; magic `(scale/0.5)` replaced with `PLAYER_HALF_EXTENT`; `rw` renamed to `clip_w` with docstring.
- UX Tester: Forbidden red outline thicker (width 2); FPS reading replaced with rolling-dt computation.
- Platform Engineer: confirmed `clock.tick(0)` + `await asyncio.sleep(0)` as correct pygbag idioms; caught the wrong-sign tumble rotation before the browser test (cube was rolling through the floor).

**Deferred (not Step 1 scope):**
- Bundled `.ttf` font (Step 10 polish). Current code uses pygame's built-in freesansbold.ttf — works in WASM.
- Input handling (Step 2), service worker/manifest (Step 11), audio (Step 10).

**Step 1 status:** code complete; self-test and panel review passed. Awaiting user verification per `STEP1_REVIEW.md`.

### Session 2 — 2026-04-16 — Step 1 user approval
- User ran `bash run_dev.sh`, verified Step 1 in browser against `STEP1_REVIEW.md` checklist.
- **Step 1 APPROVED by user.** `PLAN.md` Step 1 marked complete, step tracker updated.
- Holding before Step 2 — user will give explicit go-ahead to begin.

### Session 2 — 2026-04-16 — Repo reorganization
- Added project-level `CLAUDE.md` at root (auto-loaded by Claude Code; hard rules + layout + session-startup checklist).
- Moved all prior user-memory files (previously at `C:/Users/Luke/.claude/projects/F--Python-Avalanche/memory/`) into `.claude/memory/` under the project: `MEMORY.md` index + `project_avalanche.md`, `project_expert_panel.md`, `feedback_review_process.md`, `feedback_extensibility.md`, `reference_pygbag_config.md`. Removed the YAML session-ID frontmatter.
- Moved `PLAN.md`, `PROGRESS.md`, `STEP1_REVIEW.md` into `docs/`.
- Updated `pygbag.ini` to ignore `docs/` and to no longer list moved files individually.
- Deleted the old user-memory directory to avoid duplication.

### Session 2 — 2026-04-16 — Power of Ten standards compliance pass
User extended `CLAUDE.md` with 11 coding-standards rules (Power of Ten adapted for Python). Performed a full audit of existing Step-1 code and brought it into compliance.

**Tooling added**
- `ruff>=0.6.0` and `mypy>=1.11.0` added as dev dependencies in `pyproject.toml`.
- `[tool.ruff]` with rule set `E W F I N UP B SIM C4`, line length 100, target `py313`; excludes `build/`, `.venv/`, `Research/`, `__pycache__`.
- `[tool.mypy]` with `strict = true`, `warn_unused_ignores`, `warn_redundant_casts`. pygame-ce ships `py.typed` so no stub shims are needed.
- Verified: `uv run ruff check .` → all checks pass. `uv run mypy --strict main.py constants.py renderer.py cube_data.py` → success, no issues.

**Audit findings and fixes**

*Rule 10 — zero linter/type warnings*: every function in every module gained full parameter and return annotations. Added shared type aliases (`ColorRGB`, `Vec3`, `Mat4`, `ScreenPoint`, `FaceDescriptor`, `ProjectedFace`). Introduced TypedDicts (`CubeTypeInfo`, `TileColorSet`) for the registries. Sorted imports; removed the unused `CubeType` import in `cube_data.py` (put back after it was needed for an annotation).

*Rule 4 — functions ≤50 lines*: old `main()` was ~100 lines. Split into `_build_grid_faces`, `_build_demo_cube_faces`, `_drain_events`, `_update_fps`, `_draw_hud`. New `main()` is ~30 lines.

*Rule 5 — meaningful check per function*: added preconditions/invariants where missing. `_mat4_look_at` raises if `eye == target`. `_mat4_perspective` raises on invalid fov/aspect/near/far. `_mat4_mul` asserts both operands have 16 elements. `_transform_point` and `project_face` assert input arity. `Renderer.__init__` raises on non-positive dimensions. `_lut_sin_cos` asserts the quarter-circle output range. `get_cube_vertices` delegates to a new `_assert_cube_invariants` helper that bakes in the Step-1 floor-breach bug as a runtime check (8 verts, all y ≥ 0). `get_tile_face` raises if the tile state has no palette entry. Trivial getters stayed exempt per the 5-line rule.

*Rule 6 — narrow scope*: module-level `_i`/`_angle` leaks from the LUT build in `constants.py` eliminated by wrapping in `_build_tumble_luts(steps)`.

*Rule 3 — bounded collection growth*: `fps_samples.append(dt)` in the frame loop now has `assert len(samples) <= FPS_SAMPLES_MAX` before each append. `_build_grid_faces` and `_build_demo_cube_faces` assert upper bounds on their returned list sizes.

*Rule 2 — explicit bounds on `while`*: the one top-level event loop (`while running:` in `main()`) is now clearly labeled as the exempt application event loop with a comment citing Rule 2. Zero other while loops in the codebase.

*Rule 7 — handle return values*: `pygame.draw.polygon(...)` and `screen.blit(...)` return `Rect`s we don't use (no dirty-rect tracking). Each discarded return is now assigned to `_` with a comment block explaining why.

*Other*: Added `if __name__ == "__main__":` guard around `asyncio.run(main())` so the module is importable for tests (pygbag still loads it as `__main__`). Added `# noqa: SIM110 -- dispatch added in Step 2` to the event-drain loop since Step 2 will expand it beyond the `all(...)` shape ruff suggests.

*Rules 1 (recursion), 8 (metaprogramming), 9 (shallow access), 11 (I/O timeouts)*: audited and already compliant; no changes needed.

**Desktop smoke-test results after fixes**
- All Step-1 invariants still hold exactly: rest bbox y ∈ [0, 1]; full-tumble bbox y ∈ [0, 1] with pivot edge anchored; half-tumble y-peak = √2 ≈ 1.4142; every cube type produces 6 faces; player geometry yields 8 verts / 6 faces; LUT endpoints correct (sin: 0→1, cos: 1→0); Renderer rejects non-positive dims; `get_tile_face(VOID)` raises.
- `main()` runs one frame end-to-end via a QUIT-injection harness with no errors.

**Files touched**
- `constants.py`, `renderer.py`, `cube_data.py`, `main.py` — full rewrites to add annotations, checks, and split functions.
- `pyproject.toml` — added dev-deps group + `[tool.ruff]` + `[tool.mypy]`.
- `uv.lock` — regenerated by `uv sync --group dev`.

### Session 3 — 2026-04-16 — Step 2 implementation

User invoked "Resume"; I read CLAUDE.md + PROGRESS.md + PLAN.md and confirmed before proceeding.

**New files**
- `grid_manager.py` — `GridManager` class. Flat `list[TileState]` of length `width*depth`, indexed `[z*width + x]`. Public API: `in_bounds`, `is_valid_position`, `get_tile`, `set_tile`, `iter_tiles` (skips VOID), `mark_tile` (single-mark model — auto-clears previous), `clear_mark` (idempotent). Frontmatter was already scaffolded from prior session work; I added a Rule-5 invariant assertion in `iter_tiles` and an explicit no-mutation-during-iteration contract in the docstring.
- `player.py` — `Player` class (grid-snapped avatar, `MOVE_COOLDOWN`-gated, first-press-free-of-cooldown), module-level `_first_held_direction` helper with opposite-axis cancellation. WASD + arrow bindings via `MOVEMENT_KEYS`. Player invariant: always on a walkable tile — asserted after every `try_move`.

**Changed files**
- `main.py` — removed Step-1 demo cubes; now constructs `GridManager` + `Player`, polls keyboard via `pygame.key.get_pressed()` each frame, renders full grid through `iter_tiles`, player cube via `get_player_vertices` / `get_player_faces`. HUD adds `Pos: (x, z)` readout. `_update_fps` trim-first ordering and `_drain_events` event-count bound added per Code-Quality panel.
- `constants.py` — camera retuned `(3, 14, -6) → (3, 18, -8)` with `CAMERA_TARGET.z` reparameterized `GRID_DEPTH*0.5 → GRID_DEPTH*0.4` so every grid corner + player spawn + player-at-back projects on-screen (Step 1 was silently off-screen at front edge; not visible then because demo cubes sat mid-grid). `PLAYER_COLORS` luminance gradient brightened for contrast against `(90,90,110)` tile top.

**Self-test (desktop invariants, passed)**
- Grid: `in_bounds` correct at all 4 corners + all 4 off-grid positions. `get_tile`/`set_tile` raise IndexError off-grid. `iter_tiles` yields exactly `width*depth` entries full-grid; skips VOID tiles; equals `width*depth - 1` after one VOID injection.
- Mark lifecycle: `mark_tile` → `marked_position` set, tile state becomes MARKED. Second mark auto-clears the first. `clear_mark` restores PLATFORM and is idempotent. Marking a VOID tile raises ValueError.
- Player: spawn invariant (ValueError if spawn is not walkable). `try_move` succeeds in all 4 directions from mid-grid; refuses LEFT from (0,0) and FORWARD from (0,0); refuses a move onto a VOID tile. Negative dt raises.
- Cooldown: first update with held key moves immediately; second update inside 16ms does not; move resumes after ~80ms of accumulated dt. dt=0 still permits move on first press. Release-and-wait-cooldown re-press moves again.
- Input dispatch: WASD and arrow variants both resolve for every direction. Single-direction holds return the expected `Direction`. Empty held_keys → None. Empty sequence raises. **Opposite-axis holds cancel** (LEFT+RIGHT, UP+DOWN, mixed-binding LEFT+d) → None. Perpendicular conflicts collapse to insertion-order. Three-key cases work (two cancel → third wins).
- Camera framing: all 4 grid corners + player spawn + player-at-back + player at front corners all project inside the 960×640 viewport. Prior camera had front edge + player spawn projecting below SCREEN_HEIGHT.
- `main()` runs one frame end-to-end via drain injection without errors.

**Expert panel findings (all resolved or deferred with user judgment call)**
- Code Quality (APPROVED w/ CONCERNS): `_update_fps` append-before-bounds violated Rule 3 ordering → rewritten to trim-then-append-then-assert. `_drain_events` lacked Rule-5 check → added `MAX_EVENTS_PER_FRAME = 1024` assertion. `_first_pressed_direction` misnamed ("pressed" is edge-triggered in pygame) → renamed `_first_held_direction` with docstring note. `iter_tiles` mutation contract was implicit → documented explicitly.
- UX Tester (APPROVED w/ CONCERNS): opposite-axis held direction silently picked higher priority → implemented cancellation (LEFT+RIGHT → None, FORWARD+BACKWARD → None). Player contrast marginal → bumped top color to `(130,200,255)`.
- Vision Lead (APPROVED w/ CONCERNS): static priority vs original's most-recently-pressed, spawn Z=0 vs Z=1, camera pitch vs original ~25-30° — all 3 deferred as user judgment calls, documented in §5 of `STEP2_REVIEW.md` for user to decide.
- Platform Engineer (APPROVED w/ CONCERNS): confirmed `pygame.key.get_pressed()` + ScancodeWrapper handles K_* values > wrapper length under WASM. Canvas-focus quirk noted at top of STEP2_REVIEW. Pre-allocated face buffer suggested but deferred until Step 5+ profiling shows need.

**Tooling**
- `ruff check .` → all pass.
- `uv run mypy --strict main.py constants.py renderer.py cube_data.py grid_manager.py player.py` → Success, 6 files, no issues.

**Deferred (not Step 2 scope)**
- Mark/trigger/detonate action dispatch — Step 4.
- Cube tumble + wave manager — Step 3.
- HUD debug-flag gating — Step 4.
- Initial-move-delay + last-pressed priority — input polish pass.

**Step 2 status:** code complete; self-test + panel review passed. Awaiting user verification per `docs/STEP2_REVIEW.md`, including three judgment-call design decisions (spawn row, camera pitch, perpendicular-priority model).

### Session 3 — 2026-04-16 — Step 2 user feedback pass

User ran Step 2 in the browser and reported three items:

1. **Reversed controls (bug, fixed this pass).** W/A/S/D and arrow keys all moved the player in the opposite of the expected screen-relative direction. Root cause: current camera (`CAMERA_POS=(3,18,-8)`, `CAMERA_TARGET=(3,0,10)`) projects world +X onto screen-LEFT and world +Z onto screen-UP, so a `Direction.LEFT = (-1, 0)` world delta actually moved the player screen-RIGHT. Fix: flipped all four `Direction` enum value tuples to become screen-relative (`LEFT=(1,0), RIGHT=(-1,0), FORWARD=(0,1), BACKWARD=(0,-1)`) and updated the enum docstring to document the screen-relative convention + the camera dependency. `MOVEMENT_KEYS` mapping unchanged — still natural arrow/WASD bindings. No other module consumes `Direction.value` (verified via grep).
2. **Spawn position confirmed (`PLAYER_SPAWN_Z = 1`).** User: "Starting position is good. Player should start in row 1, in the center, so the player is 1 row away from the edge." Closes STEP2_REVIEW §5 item 1.
3. **`MOVE_COOLDOWN = 0.08s` feels faster than original I.Q.** User asked for a note to tune slower in the future. Added `TODO(tuning)` comment next to the constant in `constants.py`; re-evaluate once cubes land in Step 3+ and real crush pressure exists (candidate range ~0.12–0.18s).

**Tooling after fix**
- `ruff check .` → still clean.
- `mypy --strict` on all six modules → still clean.
- Player directional self-test re-run: from mid-grid, `try_move(LEFT)` now produces `+X` grid delta, `RIGHT` → `-X`, `FORWARD` → `+Z`, `BACKWARD` → `-Z`. Opposite-axis cancellation still correct.

Open STEP2_REVIEW §5 items: camera pitch (item 2) still awaiting user preference. Item 3 (static perpendicular priority) **deferred** at user request — revisit after Step 3 when real cube-pressure play exposes whether static order feels wrong; implementation note captured in `player.py` `_first_held_direction` docstring.

### Session 3 — 2026-04-16 — Step 2 APPROVED

**User approved Step 2.** Step tracker updated. Carry-forward items for later steps:
- `MOVE_COOLDOWN` tuning (currently 0.08s — user flagged as faster than original I.Q.; revisit Step 3+).
- Static perpendicular priority in `_first_held_direction` — revisit Step 3+ (candidate: last-pressed deque).
- Camera pitch judgment call (STEP2_REVIEW §5 item 2) — still open; not a blocker for Step 3.

Awaiting user go-ahead before starting Step 3 (cube tumbling animation + wave_manager scaffolding).

### Session 4 — 2026-04-17 — Step 3 Phase A (Development)

User: "Go ahead to Step 3A." First step run under the new Phase A / Phase B convention.

**New files**
- `wave_manager.py` — `WaveManager` class owning a `list[Cube]` with tick-driven advancement. `Cube` is a mutable dataclass (`grid_x`, `grid_z`, `cube_type`). Tick model: `_tick_elapsed` accumulates dt; on reaching `_tick_interval` (default TICK_INTERVAL=1.2s) all cubes' `grid_z` decrement by 1 and cubes with `grid_z < 0` are dropped. API: `spawn_cube`, `spawn_debug_row`, `update(dt)→fired`, `iter_cubes()→(gx, gz, progress, type)`, `tick_interval`/`tick_progress`/`cube_count` properties. Cap `MAX_ACTIVE_CUBES = GRID_WIDTH*GRID_DEPTH = 175` guards spawn_cube.

**Changed files**
- `main.py` — added `_build_cube_faces(renderer, wave)`; `wave.update(dt)` in frame loop (return discarded with `_` — tick-fired flag is for Step 4 hooks); HUD line 4 shows `Cubes: N  Tick: 0.NN`.
- `constants.py` — added TUNING comment above `TICK_INTERVAL` marking it as provisional Stage-1 value (Vision Lead finding; full per-stage table deferred to Step 7).

**Panel findings resolved**
- Code Quality — `_advance_tick` overshoot handling had dead code + silent truncation that broke the "cadence stays even" promise under a future bad dt. Replaced clamp with an explicit assertion: `0.0 <= overshoot < tick_interval` must hold; DT_CLAMP upstream guarantees it. Violations now fail loudly (fix + self-test with dt=2.5*interval confirms assertion fires).
- Vision Lead — TICK_INTERVAL annotated as provisional.
- UX Tester — "standing under a cube does nothing" callout baked into STEP3_REVIEW.md §4 to prevent false bug reports.

**Panel findings deferred (tracked for later steps)**
- Code Quality — `Cube` frozen=True decision → Step 4 (capture identity semantics).
- Code Quality — `cube_at(x, z)` spatial lookup → Step 4 (add when semantics defined, not speculatively).
- Platform — pre-allocated face buffer / skip rest-position allocation → Step 5 (matters at 20+ cubes).
- Platform — `operator.itemgetter` vs sort-key lambda micro-opt → Step 8.
- Platform — `TICK_INTERVAL > DT_CLAMP` cross-module assertion → Step 6 when mid-stage acceleration lands.
- Vision Lead — per-stage Wait/Speed table → Step 7.
- Vision Lead — fall-off-edge tumble animation → Step 10 polish.
- UX — FORBIDDEN "red wireframe" read on dim screens → Step 10 polish (revisit if Phase B flags it).
- UX — HUD label `Tick:` ambiguity → Step 4 when real HUD lands.

**Self-test (desktop invariants, passed)**
- WaveManager construction: empty state, tick_progress=0.0, tick_interval=1.2. Rejects zero/negative tick_interval.
- `spawn_cube` rejects off-grid coords on both axes. Cap of 175 enforced (assertion fires on the 176th spawn). `spawn_debug_row` produces exactly 7 cubes, one per column at back row.
- Tick advancement: mid-tick update returns False, cubes unchanged, `tick_progress` mid-range. Crossing the boundary returns True, all cubes grid_z -= 1, overshoot preserved as sub-interval progress.
- Full traversal: spawn at back row, 24 ticks lands at z=0, one more tick removes the cube.
- Tumble geometry: rest verts at (gx, gz) span y∈[0,1] z∈[gz-0.5, gz+0.5]; progress=1 spans the next tile forward; mid-tumble peak y=√2≈1.414; floor never breached.
- `update(dt<0)` raises ValueError. `iter_cubes` yields well-formed tuples with progress∈[0,1]. 
- Render integration: 7 debug cubes project to ~29 visible faces after back-face cull; single mid-tumble cube projects to 1-6 visible faces. `main()` runs one frame end-to-end clean.
- After fix: overshoot assertion fires when dt ≥ 2*tick_interval; legal overshoot (dt=tick_interval+0.05) preserved correctly as tick_progress≈0.042.

**Tooling**
- `ruff check .` → all pass.
- `uv run mypy --strict main.py constants.py renderer.py cube_data.py grid_manager.py player.py wave_manager.py` → Success, 7 files.

**Phase B — user observation (2026-04-17)**
User report: "Mechanically, everything works. The feel is different." The uniform 90°/tick tumble is mechanically correct but reads wrong vs. the 1997 I.Q. original, which had a heavy-cube easing profile: slow/decelerating heave to balance, brief balance-point pause, accelerating "thud" fall, brief rest pause. Captured in `.claude/memory/feedback_tumble_feel.md` with full four-stage timing profile and implementation notes at `cube_data.py:52` (`_lut_sin_cos`). A TODO(feel) comment at that call site points back to the memory file. **Natural landing:** Step 10 polish (animation feel + audio "thud" metronome co-located). Explicitly separated from `TICK_INTERVAL` tuning (different axis: tick interval = how often; tumble easing = how it moves within one tick).

Step 3 carry-forward added:
- Tumble-animation feel — heavy-cube easing → Step 10 polish. See `feedback_tumble_feel.md`.

### Session 5 — 2026-04-17 — Step 3 APPROVED + Step 4 Phase A (Development)

**Step 3 approved** ("Step 3 approved, proceed to Step 4A"). Tracker flipped to `APPROVED 2026-04-17`.

**New files**
- `game_manager.py` — `GameManager` orchestrates mark/trigger. `try_mark(x, z)` delegates to `GridManager.mark_tile` after gating on `is_valid_position` + trap-tile refusal. `on_trigger()` resolves the active mark, clears it, and dispatches via `CUBE_TYPES[...]['on_capture']` → `CubeBehavior.{SCORE, CREATE_TRAP, ROW_DELETE}`. Each branch removes the cube and emits a flash; the final `else` raises `ValueError` so a new `CubeBehavior` without a dispatch branch fails loudly. `TriggerOutcome` is a string-constants class — module-local tags for future audio-cue dispatch. Closes the Step 3 Code Quality deferrals (`Cube` frozen=True → stays mutable; `cube_at` → implemented in `wave_manager.py` as linear scan).
- `effects.py` — `FlashEffects` manager with bounded list of `_Flash` dataclasses. Expanding ring overlay (radius 6→48 px, width 5→1 px, color `(240,240,255)`) over `FLASH_DURATION=0.4s`. `MAX_ACTIVE_FLASHES=32` cap. Uses a `_VertexProjector` Protocol rather than a direct `Renderer` import, keeping the module decoupled from the rendering backend.
- `hud.py` — `Hud` class extracted from `main.py`. Top-left 5-line stat block (FPS, Polys, Pos, Cubes+Tick, Score+Mark) + bottom-left controls hint (`Move: WASD / Arrows   Mark: SPACE   Trigger: X / Enter`). The extraction was scheduled for Step 4 in `PLAN.md`.

**Changed files**
- `wave_manager.py` — added `cube_at(grid_x, grid_z) -> Cube | None` with one-cube-per-tile assertion (continues scanning past a match to detect future invariant breakage) and `remove_cube(cube)` identity-based scan (raises `ValueError` if not in set).
- `main.py` — KEYDOWN handling for `KEY_MARK` (SPACE) → `game.try_mark`, `KEY_TRIGGER`/`KEY_TRIGGER_ALT` (X/Enter) → `game.on_trigger`. Instantiates `FlashEffects`, `GameManager`, `Hud`. `effects.update(dt)` after `wave.update`; `effects.draw(screen, renderer)` after `renderer.render_frame`; `hud.draw` last. HUD inline draw function removed.

**Design decisions recorded**
- `on_trigger` clears the mark BEFORE dispatch (post-panel fix). Previous ordering relied on `clear_mark`'s internal "skip if no longer MARKED" guard — a load-bearing cross-module invariant flagged by Code Quality. New ordering: `clear_mark` always leaves a clean PLATFORM; CREATE_TRAP then writes ADVANTAGE_TRAP onto it directly. Much simpler invariant.
- Marking a trap tile is silently refused. Policy call: trap tiles are live gameplay state (Step 7 detonate). May revisit when DETONATE lands (Vision Lead + Code Quality both flagged as "track, don't fix now").
- FORBIDDEN capture stub: cube is removed, score unchanged, tile returns to PLATFORM. Full row-delete side effect is Step 8 per PLAN (not Step 6 — Step 6 is missed-normal penalty path, a different trigger). TODO(step-8) at the dispatch branch.

**Panel findings resolved inline**
- Code Quality — `_dispatch_capture` relied on cross-module clear_mark guard → reordered to call `clear_mark` first (`game_manager.py:110-117`).
- Code Quality — `TriggerOutcome` docstring cited fictional import cycle → rewritten.
- Code Quality + Platform — `FlashEffects.update` rebuilt list every frame → added empty-list fast-path (`effects.py:100-102`).

**Panel findings deferred (tracked for later steps)**
- Vision Lead — flash color type-tinting → Step 10 polish.
- Vision Lead — mark-ahead-of-cube timing feel; `TriggerOutcome` consumed at audio layer → Step 10.
- Vision Lead + Code Quality — trap-tile-refuses-mark policy → Step 7 when DETONATE wires.
- Code Quality — `try_mark` enum return / rejection semantics → Step 10 audio dispatch.
- UX — FORBIDDEN visually indistinguishable + MISS silent → documented in `STEP4_REVIEW.md` §4 (both reference-faithful; audio is Step 10, penalty is Step 6/8).
- UX — controls-hint contrast over front-row tiles → Step 10 polish.
- Platform — font-render caching in HUD → Step 10 polish.

**Self-test (desktop invariants, passed)**
- `WaveManager.cube_at`/`remove_cube`: empty wave → None; spawned cube found; adjacent tiles miss; removing unknown cube raises `ValueError`.
- `GameManager.try_mark`: places + replaces; rejects off-grid; rejects trap tile.
- `GameManager.on_trigger`: NO_MARK / MISS / CAPTURED_SCORE / CAPTURED_TRAP / CAPTURED_FORBIDDEN paths all set the expected score, tile state, and flash count. Registry parity test catches new `CubeBehavior`s added without a dispatch branch.
- `FlashEffects`: spawn → update → evict lifecycle; `MAX_ACTIVE_FLASHES` cap holds under overspawn; negative dt raises; draw on empty + populated set doesn't raise.
- `Hud.draw`: runs end-to-end on a 960×640 off-screen surface; score round-trip through the HUD after a real capture path.
- `mark_persists_across_tick_and_captures_on_arrival`: spawn cube at z=3, mark z=2, advance one tick, trigger → CAPTURED_SCORE.
- Post-panel re-run of SCORE/TRAP/FORBIDDEN/MISS + empty-flash-fast-path after dispatch reorder → all pass.
- Headless main-loop smoke: `SDL_VIDEODRIVER=dummy` + QUIT after 0.3s runs one frame clean.

**Tooling**
- `uv run ruff check .` → all pass.
- `uv run mypy --strict main.py constants.py renderer.py cube_data.py grid_manager.py player.py wave_manager.py game_manager.py effects.py hud.py` → Success, 10 files.

**Phase B — user observations + fixes (2026-04-17)**

Fix 1 — rest phase (two rounds):
- Initial: `TUMBLE_REST_FRACTION=0.75` (trailing rest, rotation completes at 75% of tick). User didn't see a difference — had not refreshed browser. Confirmed working after refresh.
- Fix 2 (inverted, then reverted): attempted leading rest (progress 0→0.25 = rest). User confirmed first version was correct; reverted.

Fix 2 — capture timing and rest extension:
- User reported capture was triggering on the wrong side: pressing trigger as the cube *leaves* the marked tile worked, but capture should only be valid during the rest phase (cube visually landed).
- Added `WaveManager.capturable_at(x, z)`: returns None during mid-tumble (tick_progress < TUMBLE_REST_FRACTION); during rest phase checks `cube.grid_z == z + 1` (visual tile = gz-1).
- `GameManager.on_trigger` switched from `cube_at` to `capturable_at` — triggers during tumble phase now always MISS.
- Extended rest: `TUMBLE_REST_FRACTION` 0.75 → 0.55 (+20 pct-points); rest window 0.3s → 0.54s (45% of 1.2s tick).
- All invariants re-verified: mid-tumble blocked, rest-phase capture at visual tile, MISS/SCORE/TRAP/FORBIDDEN paths all pass.

**Step 4 APPROVED** ("Excellent. Step approved") 2026-04-17.

**Phase A status:** CODE COMPLETE; awaiting user browser verification per `docs/STEP3_REVIEW.md`. Phase B begins when user runs it.

### Session 6 — 2026-04-17 — Step 5 Phase A (Development)

User: "Proceed to 5A." Resumed from compacted context; all prior step files verified via system-reminder cache.

**New features**
- **Pre-crush telegraph:** `GameManager.crush_imminent(player, wave)` returns True when a cube is at `player.grid_z + 1` (one tick away) in WAVE_ACTIVE phase. Player cube renders with `PlayerVisual.TELEGRAPH` (bright red tint) when true.
- **Crush detection:** `on_tick(player, wave)` checks `wave.cube_at(player.grid_x, player.grid_z)` after each tick commit in WAVE_ACTIVE. On match, triggers avalanche.
- **Avalanche transition:** `_trigger_avalanche` sets `GamePhase.AVALANCHE`, calls `player.crush()`, accelerates `wave.tick_interval` to `AVALANCHE_TICK_INTERVAL=0.15s`, clears the active mark, fires `effects.trigger_shake(10.0, 0.6)`.
- **Player squash:** `player.is_crushed` drives `PlayerVisual.CRUSHED` (dark red, `scale_y=0.15` — 85% squash). `player.update()` early-returns when crushed (movement blocked).
- **Marks/triggers blocked:** `try_mark` and `on_trigger` both gate on `phase == WAVE_ACTIVE`; return early with `False` / `TriggerOutcome.BLOCKED` during avalanche.
- **Missed-normal counting:** `_count_avalanche_misses` iterates `wave.last_dropped` each avalanche tick; increments `_avalanche_penalty` for cubes with `on_missed == CubeBehavior.PENALTY` (NORMAL + ADVANTAGE; not FORBIDDEN).
- **WAVE_CLEARING transition:** `on_tick` transitions phase to `WAVE_CLEARING` when `wave.cube_count == 0` during avalanche.
- **Screen shake:** `FlashEffects.trigger_shake(amplitude, duration)` + `shake_offset() → tuple[int,int]` (decaying Lissajous oscillation at 60/47 rad/s). `update(dt)` advances shake state before the flash fast-path. `main.py` renders game scene to `scene_surf`, blits with `effects.shake_offset()` to screen; HUD draws directly to screen (stays fixed).

**Changed files**
- `constants.py` — `AVALANCHE_TICK_INTERVAL=0.15`; `PLAYER_TELEGRAPH_COLORS`/EDGE; `PLAYER_CRUSH_COLORS`/EDGE.
- `cube_data.py` — `PlayerVisual` string-constants class; `scale_y` param in `get_player_vertices`; visual dispatch in `get_player_faces`.
- `player.py` — `_crushed` bool; `is_crushed` property; `crush()` method; `update()` early-return guard.
- `wave_manager.py` — `tick_interval` setter; `_last_dropped` populated in `_advance_tick`; `last_dropped` property.
- `game_manager.py` — `_phase`/`_avalanche_penalty` state; `crush_imminent`/`on_tick`/`_trigger_avalanche`/`_count_avalanche_misses`; `TriggerOutcome.BLOCKED`; phase guards on `try_mark`/`on_trigger`.
- `effects.py` — `trigger_shake`; `shake_offset`; shake state advanced in `update`.
- `main.py` — `scene_surf`; `tick_fired → game.on_tick`; player visual selection; `_build_player_faces` gains `visual`+`scale_y`; blit with shake offset.

**Expert panel (all 4 APPROVED)**
- Vision Lead: faithful to I.Q. design; phase machine ready for Steps 6–9.
- Code Quality: all Power-of-Ten rules satisfied; docstring clarification applied to `on_tick`.
- UX Tester: telegraph/squash/shake visuals clear; polish gaps (HUD label, movement-lock indicator) deferred to Step 10.
- Platform Engineer: `scene_surf` double-blit Pygbag-compatible; sin/cos overhead negligible; DT_CLAMP/AVALANCHE_TICK_INTERVAL margin correct.

**Tooling**
- `uv run ruff check .` → all pass.
- `uv run mypy --strict .` → Success, 10 files.
- Desktop self-test: 20/20 checks pass (crush detection, telegraph, phase transitions, penalty counting, shake bounds, movement/mark blocking).

### Session 6 — 2026-04-17 — Step 5 Phase B (user feedback + fixes)

**Fix 1 — Telegraph removed:**
- User: "Remove the telegraph feature altogether. There should be no visual signal to the player that a cube is about to crush."
- Removed `PLAYER_TELEGRAPH_COLORS`/`PLAYER_TELEGRAPH_EDGE_COLOR` from `constants.py`, `PlayerVisual.TELEGRAPH` from `cube_data.py`, `crush_imminent()` from `game_manager.py`.
- Player now always renders NORMAL (blue) or CRUSHED (dark red); no intermediate color state.

**Fix 2 — Mid-tumble crush (capture-escape closed):**
- User: "In practice it is possible to capture cube in telegraphed state. This should not be possible. As soon as the tumbling cube intersects the player, say by tumbling past its fulcrum, the player is crushed."
- Replaced post-tick crush detection with per-frame `check_mid_tumble_crush()`. Fires at `CRUSH_TUMBLE_THRESHOLD = TUMBLE_REST_FRACTION / 2 = 0.275` — the cube's balance point, before capture window opens at 0.55.
- Added `CRUSH_TUMBLE_THRESHOLD` to `constants.py`. Added `check_mid_tumble_crush(player, wave)` to `GameManager`; called every frame from `main.py`.
- Fixed `wave_manager.py` tick_interval setter: resets `tick_elapsed = 0` when new interval < current elapsed, preventing the overshoot assertion from firing when mid-tumble crush switches interval from 1.2s to 0.15s.

**Fix 3 — Spawn position:**
- User: "Adjust PLAYER_SPAWN_Z so player spawns 3 rows from the tumbling cubes."
- `PLAYER_SPAWN_Z = max(0, GRID_DEPTH - 1 - 3) = 21` (3 rows in front of the back row where the wave starts; clamp to 0 for shallow grids).

**Carry-forward noted:**
- Cube-player collision blocking (player can walk through wave cubes) documented as TODO in `PLAN.md` Step 6.

**Step 5 APPROVED by user 2026-04-17.**

### Session 7 — 2026-04-17 — Step 6 Phase A (Development)

User: "Continue to Step 6." Resumed from compacted context.

**New capability:** Missed-normal penalty system, row deletion, GAME_OVER detection, cube-player collision blocking, focus-loss pause.

**Changed files**
- `grid_manager.py` — `delete_back_row()`: scans from depth-1 forward, voids first non-void row, clears mark if it was in that row. Returns True if deleted. Assertion verifies row fully voided.
- `game_manager.py` — `_wave_penalty` counter (WAVE_ACTIVE missed cubes); `wave_penalty` property; `_count_wave_misses(player, wave)` iterates `last_dropped` per tick; `_apply_avalanche_penalties(player)` applies `_avalanche_penalty // PENALTY_THRESHOLD` deletions at WAVE_CLEARING; `_check_game_over(player)` tests `is_valid_position` immediately after each deletion. `on_tick` updated for both branches. `PENALTY_THRESHOLD` imported. One `type: ignore[comparison-overlap]` at line 149 (mypy can't see `_apply_avalanche_penalties` mutates `_phase`; justified and documented inline).
- `wave_manager.py` — `blocked_tiles() -> frozenset[tuple[int, int]]`: committed cube positions; used by player collision.
- `player.py` — `wave_blocked: frozenset[tuple[int, int]] | None` added to `update()` and `try_move()`; blocks entry into cube-occupied tiles.
- `hud.py` — 6th stat line: `Penalty: N/3`; PENALTY_THRESHOLD imported; line-count assert updated to 6.
- `main.py` — `_drain_events` signature changed to `(player, game, paused) -> tuple[bool, bool]`; `pygame.ACTIVEEVENT` sets pause state; KEYDOWN blocked when paused. `_draw_pause_overlay` + `_draw_game_over_overlay` added. Main loop: `wave.blocked_tiles()` passed to `player.update()`; updates gated on `not paused and game.phase != GamePhase.GAME_OVER`; `effects.update(dt)` always runs (shake settles). `GamePhase` imported.

**Design decisions**
- Wave penalty subtracts PENALTY_THRESHOLD (not reset to 0) so misses carry over across row deletions. Correct I.Q. behavior.
- Collision blocking uses committed `grid_z` (not visual tile) — player can walk into the visually-landing tile during rest phase, consistent with capture mechanics.
- `_apply_avalanche_penalties` uses `// PENALTY_THRESHOLD` to compute deletions; remainder stays in `_avalanche_penalty` for next wave.

**Expert panel (all 4 APPROVED)**
- Vision Lead: mechanics match I.Q. original; penalty counting, avalanche application, GAME_OVER timing all correct.
- Code Quality: Power-of-Ten compliant; `type: ignore` justified; structural refactor (return bool from `_apply_avalanche_penalties`) noted as optional future improvement.
- UX Tester: mechanically sound; Step 10 polish items: penalty counter UX clarity, row deletion feedback, GAME_OVER intensity.
- Platform Engineer: frozenset creation O(175) per frame is WASM-safe; ACTIVEEVENT works in Pygbag; no compatibility issues.

**Tooling**
- `uv run ruff check .` → all pass (2 auto-fixed import sorts).
- `uv run mypy --strict .` → Success, 10 files.

**Phase A status:** CODE COMPLETE; panel clean; `docs/STEP6_REVIEW.md` written. Awaiting user browser verification.

### Session — 2026-04-25 — Step 9 Phase A (Development)

**New files**
- `wave_data.py` — `WaveData` class + `STAGE_1_WAVES` (4 Stage-1 waves). `spawn_positions(mirror)` emits `(grid_x, grid_z, cube_type)` with 50% X-axis mirror. `ideal_steps` drives Perfect bonus tiers.

**Changed files**
- `wave_manager.py` — `reset_for_new_wave()`: clears cubes, resets tick timer and interval.
- `grid_manager.py` — `restore_front_row()`: restores the row immediately adjacent to the current platform front edge (see Phase B fix below).
- `game_manager.py` — full wave-progression state machine: `start_first_wave`, `_spawn_wave` (50% mirror, per-wave state reset), `_on_wave_cleared` (Perfect detection, bonus award, row restore, next wave or VICTORY), `_calc_perfect_bonus` (4-tier table), `_calculate_final_iq`. Step counting in `try_mark`, `on_trigger`, `on_detonate`. Properties: `wave_index`, `wave_count`, `iq_score`.
- `hud.py` — 7th stat line: `Wave: N/4`.
- `main.py` — `start_first_wave(player, STAGE_1_WAVES)` replaces debug spawn; `frozen` includes VICTORY; `_draw_victory_overlay` added.

**Expert panel (all 4 APPROVED, two required fixes applied)**
- Code Quality: `assert ideal > 0` added to `_calc_perfect_bonus`; `type: ignore` comment extended with reason.
- Vision Lead: W2/W3/W4 ideal-step derivation comments in `wave_data.py` corrected (13, 14, 16).
- UX Tester: all concerns Step 10 deferred.
- Platform Engineer: no issues.

**Self-test:** 59/59 checks (T1–T16). Tooling: ruff + mypy --strict clean (11 files).

### Session — 2026-04-25 — Step 9 Phase B (user testing + fix)

**Bug: `restore_front_row()` produced a disconnected tile with a gap after multiple row deletions.**

Root cause: the old implementation scanned from z=0 and restored the first all-void row found. After two penalties (z=0 and z=1 voided, platform at z=2+), it restored z=0 while z=1 remained void — a disconnected tile the player could not reach, with a visible gap.

Fix: changed `restore_front_row()` to compute `front_edge_z` (first non-void row from z=0), then restore `front_edge_z - 1` — always the row immediately adjacent to the existing platform, never with a gap.

Smoke-test: 15/15 checks (intact grid no-op, single deletion round-trip, two-deletion adjacent restore + sequential second restore). Tooling: ruff + mypy --strict clean.

**Step 9 APPROVED by user 2026-04-25.**

### Session — 2026-04-26 — Step 10 Phase A (Development)

**Changes applied**

- `constants.py` — `MOVE_COOLDOWN` 0.08 → 0.12 s (Step 2 carry-forward tuning).
  `WAVE_RISING_DURATION = 2.0` s (new). 4-phase tumble constants: `TUMBLE_HEAVE_END = 0.40`,
  `TUMBLE_BALANCE_END = 0.48`, `TUMBLE_REST_FRACTION` 0.55 → 0.65, `CRUSH_TUMBLE_THRESHOLD`
  changed from `REST/2 = 0.275` to `TUMBLE_HEAVE_END = 0.40`.
- `cube_data.py` — `_lut_sin_cos()` rewritten with 4-phase easing: smoothstep heave
  (0→40%, 0°→45°), balance hold (40→48%, 45°), quadratic ease-in thud (48→65%, 45°→90°),
  rest (65→100%, 90°). `TUMBLE_HEAVE_END`/`TUMBLE_BALANCE_END` imported from constants.
  TODO(feel) comment removed.
- `game_manager.py` — `start_first_wave` now enters `GamePhase.TITLE` instead of spawning
  immediately. New public methods: `on_title_advance()` (TITLE → WAVE_RISING + sets 2 s timer),
  `update(dt, player)` (per-frame WAVE_RISING countdown → triggers `_spawn_wave` on expiry).
  New property: `perfect_display`. `_on_wave_cleared`: calls `player.uncrush()` +
  `grid.clear_mark()` before the pause; stores `_perfect_display`; enters WAVE_RISING
  instead of spawning directly. `_spawn_wave`: resets `_perfect_display = False`.
  `WAVE_RISING_DURATION` imported.
- `main.py` — `overlay_font = pygame.font.Font(None, 64)`. New functions:
  `_draw_title_overlay` (dark veil + "AVALANCHE" + prompt), `_draw_wave_rising_overlay`
  (PERFECT! banner + wave counter). `_drain_events`: TITLE any-key → `game.on_title_advance()`.
  Main loop: `game.update(dt, player)` before frozen check; `frozen` expanded to include TITLE
  and WAVE_RISING; overlay dispatch extended for both new phases.
- `docs/STEP10_REVIEW.md` written.

**Self-tests:** 9/9 smoke checks pass (constants, easing boundaries, TITLE→WAVE_RISING→
WAVE_ACTIVE state machine, WAVE_RISING timer, try_mark blocked during TITLE, perfect_display
default, on_title_advance no-op outside TITLE, negative-dt rejection, easing monotonicity).
Tooling: `ruff check .` → clean, `mypy --strict .` → clean (11 files).

**Step 10A APPROVED by user 2026-04-26.**

### Session — 2026-04-26 — Step 10 Phase B (Development)

**Changes applied**

- `grid_manager.py` — `reset()`: restore all tiles to PLATFORM, clear mark. Called on game restart.
- `player.py` — `reset()`: teleport to spawn, uncrush, zero cooldown. Raises if spawn not walkable (caller must reset grid first).
- `effects.py` — `reset()`: clear flashes and shake state.
- `game_manager.py` — `on_restart_key(player)`: resets grid/wave/effects/player/self in dependency order, then calls `start_first_wave` → TITLE. `_reset_state()`: private helper that zeroes score, iq, phase, penalties, wave counters. Explicit `wave.reset_for_new_wave()` in `on_restart_key` retained (panel initially suggested removing it as redundant, but it is needed to clear stale cubes before TITLE renders; `_spawn_wave` resets the wave a second time 2 s later, which is harmless).
- `main.py` — `_drain_events`: GAME_OVER/VICTORY any-key → `on_restart_key(player)`. `_draw_game_over_overlay`: takes `game: GameManager`; shows score + restart prompt; 3-line centered layout. `_draw_victory_overlay`: added "Press any key to restart" as 4th line; assert updated 3→4.
- `docs/STEP10B_REVIEW.md` written.

**Self-tests:** 7/7 smoke checks (restart from GAME_OVER with cubes, full round-trip, restart from VICTORY, grid fully PLATFORM after restart, player at spawn uncrushed, effects.reset(), on_restart_key no-op outside end-screen phases). Tooling: ruff + mypy --strict clean (11 files).

**Expert panel:** Vision Lead, Code Quality, UX Tester, Platform Engineer all APPROVED. Code Quality's "remove redundant reset_for_new_wave" suggestion triaged as incorrect and rejected — the call is necessary for visual correctness.

**Step 10B APPROVED by user 2026-04-26. Step 10 fully complete.**

### Session — 2026-04-27 — Post-v1 plan created + Step 12 Phase A (Development)

User requested a plan for post-v1 enhancements: deferred carry-forward items from
Steps 1–11, plus five new features (turbo key, Esc menu, graphics polish, capture
animations, additional stages), and public deployment.

Post-v1 plan written to `docs/PLAN.md` (Steps 12–25) and `docs/PROGRESS.md` step
tracker extended to cover all new steps.

**Step 12 — GitHub Pages deployment + CI/CD**

New files:
- `.github/workflows/deploy.yml` — triggered on push to `master`. Installs uv with
  tool cache, runs `pygbag --build` to build `build/web/`, verifies 5 expected
  output files are present, deploys via `actions/configure-pages` +
  `upload-pages-artifact@v3` + `deploy-pages@v4`.

Changed files:
- `static/sw.js` — `CACHE_NAME` bumped to `'avalanche-v2'`; `SHELL_URLS` changed to
  `BASE + 'filename'` where `BASE = new URL('./', self.location.href).pathname` —
  fixes SW pre-cache on GitHub Pages sub-path (`/<repo>/`) vs. localhost root (`/`).
- `pygbag.ini` — added `.python-version` and `run_dev.sh` to `ignorefiles` (excluded
  from browser APK to reduce bundle size).

Expert panel findings (all CONCERNS → APPROVED after fixes):
- Vision Lead: SW absolute paths (`/index.html`) wrong on GitHub Pages sub-path → fixed with BASE computation.
- Code Quality: `timeout 60 ... || true` masked errors; 60 s too short on cold runner → replaced with `pygbag --build`; `set -euo pipefail` added; `cache: true` on setup-uv.
- UX Tester: loading bar undocumented; URL format ambiguous; offline expectation missing; mobile scope unclear → review doc updated.
- Platform Engineer: suggested `--no_server` (incorrect — flag doesn't exist); actual working flag is `--build` (confirmed from pygbag help output in CI); same SW sub-path bug; `.python-version`/`run_dev.sh` inflating APK → all fixed.

`docs/STEP12_REVIEW.md` written (GitHub repo creation instructions + verification checklist).
Awaiting user to create GitHub repo and confirm live deployment.

---

### Session — 2026-04-27 — Step 11 Phase A (Development)

**New files**
- `scripts/make_icons.py` — pure-Python-stdlib PNG generator (struct + zlib).
  Draws an isometric cube on a black background (gold top face, dark goldenrod
  right, deep brown-gold left, warm-yellow edges) at 192 px and 512 px.
  Rule 2/5/9 compliant after panel fixes.
- `static/manifest.json` — PWA manifest: `display: standalone`, `orientation: landscape`,
  `background_color / theme_color: #000000`, `lang: en`, `categories: ["games"]`,
  4 icon entries (192 + 512, each with separate `any` and `maskable` purpose).
- `static/sw.js` — Service worker. Install pre-caches shell (index.html, icons,
  manifest). Activate cleans old caches + claims clients. Fetch: same-origin-only
  interception (CDN requests pass through — avoids opaque-response quota issue);
  stale-while-revalidate for `.wasm/.data/.tar.gz/.apk`; cache-first for rest.
  `favicon.png` excluded from SHELL_URLS (generated by pygbag at build time, cached
  lazily instead).
- `static/icon-192.png`, `static/icon-512.png` — generated by make_icons.py.
- `custom.tmpl` — modified default.tmpl (0.9.3): body background `#000000` (was
  `#7f7f7f` / `powderblue`); `<link rel="manifest">` + `<meta name="theme-color">`
  in head; canvas `tabindex="0"`; `custom_postrun()` calls `cv.focus()` + registers
  click listener; SW registered via `navigator.serviceWorker.register('sw.js')`.
- `docs/STEP11_REVIEW.md` — user review guide.

**Changed files**
- `run_dev.sh` — copies `static/`, `custom.tmpl`, `pygbag.ini` to BUILD_DIR;
  passes `--template custom.tmpl` to pygbag.
- `pygbag.ini` — added `static`, `scripts`, `custom.tmpl` to ignore lists.

**Expert panel findings applied**
- Vision Lead: APPROVED. Added `lang` + `categories` to manifest (minor suggestion).
- Code Quality: CONCERNS → 3 violations in make_icons.py fixed: Rule 2 (assert in
  while-loop), Rule 5 (thickness precondition in `_thick_edge`), Rule 9 (path chain
  broken up). APPROVED after fixes.
- UX Tester: CONCERNS → APPROVED. `display: fullscreen` → `standalone` (blocking:
  fullscreen traps mobile users). Icon purposes split into separate any/maskable entries.
- Platform Engineer: CONCERNS → APPROVED. (1) `favicon.png` removed from SHELL_URLS
  (blocking: not in static/, breaks SW install on fresh build). (2) Same-origin guard
  added to SW fetch handler (blocking: CDN opaque WASM would inflate Cache quota).
  `'/'` removed from SHELL_URLS (redundant with `/index.html`).

**Self-tests:** 6/6 checks (manifest fields, icon PNG dimensions, SW structure,
custom.tmpl additions, pygbag.ini ignoredirs, run_dev.sh commands) + 5/5 post-fix
checks (all panel fixes verified). Tooling: ruff + mypy --strict clean (12 files).

**Step 11 APPROVED by user 2026-04-27. Project complete.**

Post-approval fix: manifest description changed to "Retro puzzle game"
(removed third-party IP reference).
