# Avalanche: I.Q. Intelligent Qube Reproduction

## Context

Reproduce a single complete stage of **I.Q.: Intelligent Qube** (1997 PlayStation puzzle game) as a **browser-based Progressive Web Application**, developed entirely in Python. The research document at `Research/Intelligent Qube Technical Reproduction Research.md` provides exhaustive technical analysis of the original game's architecture, mechanics, and scoring systems.

The game is a real-time spatial puzzle: waves of cubes tumble across a suspended grid platform toward the player, who must mark tiles and trigger captures. Three cube types (Normal, Advantage, Forbidden) create strategic depth. Missing cubes shrinks the platform; getting crushed triggers an "Avalanche" failure state.

**Future expansion is planned.** The codebase must be modular with clear interfaces between systems so new cube types, stage formats, game modes, and modern features can be integrated without refactoring core architecture. The retro feel — especially the difficulty — must be preserved throughout all changes.

---

## Stack

| Layer | Technology | Why |
|---|---|---|
| Game engine | **Pygame CE** | Well-maintained, 2D drawing primitives, proven Pygbag support |
| 3D rendering | **Software 3D** (manual projection + `pygame.draw.polygon`) | No WebGL dependency; faithful perspective view; ~300 polygons/frame is trivial |
| Browser runtime | **Pygbag** | Compiles CPython + Pygame to WebAssembly; generates HTML/JS wrapper |
| Offline/install | **PWA** (manifest.json + service worker) | Self-contained, installable, works offline |

---

## File Structure

```
F:/Python/Avalanche/
    main.py              # Pygbag async entry point + game loop
    constants.py         # Enums, dimensions, timing, colors, key bindings
    renderer.py          # 3D projection engine (view/perspective matrices, face sorting, polygon drawing)
    cube_data.py         # Cube vertex/face definitions, tumble rotation math, tile geometry
    grid_manager.py      # 2D integer array for platform tile states (VOID/PLATFORM/MARKED/TRAP)
    wave_manager.py      # 2D cube array, tick-based advancement, capture logic
    wave_data.py         # Hardcoded puzzle patterns for 4 waves (includes ideal_steps per wave)
    player.py            # Grid-snapped avatar, movement, input actions
    game_manager.py      # State machine, scoring, wave flow, game-over logic
    hud.py               # Score/wave/penalty overlay using bundled .ttf font
    effects.py           # 2D particle effects (capture flash, row collapse)
    custom.tmpl          # Pygbag HTML template override (PWA hooks, canvas focus, tabindex)
    assets/
        font.ttf         # Bundled font (SysFont unavailable under WASM)
    static/
        manifest.json    # PWA manifest
        sw.js            # Service worker (stale-while-revalidate for .wasm/.data)
        icon-192.png     # PWA icon
        icon-512.png     # PWA icon
```

**Modularity principles:**
- Each manager (grid, wave, game, player) exposes a clean interface; no manager reaches into another's internals
- All tunable values (timing, scoring, thresholds, grid dimensions) live in `constants.py`
- Game logic is fully separated from rendering — swapping the renderer or adding new visual effects never touches game state code
- Cube types are data-driven via a config registry with `on_capture` and `on_missed` behavior hooks — adding a new cube type means adding an entry, not rewriting logic
- Wave patterns are data files, not code — future stages/modes load from the same format

---

## Core Architecture

### Principle: Logic and visuals are fully decoupled

The game state lives in integer arrays (`GridManager.grid`, `WaveManager.cubes`). Visual rendering reads this data each frame and projects it to screen. Animations (cube tumbling) are cosmetic interpolation — they never drive logic.

### Cube type registry (constants.py)

Each cube type is defined as a config entry with behavior hooks, not hardcoded branches:

```python
CUBE_TYPES = {
    CubeType.NORMAL: {
        "colors": {"top": (180,180,180), "front": (140,140,140), "side": (100,100,100)},
        "edge_color": (60, 60, 60),
        "edge_width": 1,
        "on_capture": "score",          # awards points
        "on_missed": "penalty",         # increments penalty counter
        "capture_score": 100,
        "chain_score": 200,
    },
    CubeType.ADVANTAGE: {
        "colors": {"top": (100,255,100), "front": (60,200,60), "side": (30,150,30)},
        "edge_color": (0, 255, 0),
        "edge_width": 1,
        "on_capture": "create_trap",    # places 3x3 trap on tile
        "on_missed": "penalty",
        "capture_score": 100,
        "chain_score": 200,
    },
    CubeType.FORBIDDEN: {
        "colors": {"top": (50,30,50), "front": (30,15,30), "side": (20,10,20)},
        "edge_color": (180, 0, 0),      # Red outline for visibility (UX panel fix)
        "edge_width": 2,                # Thicker edge (UX panel fix)
        "on_capture": "row_delete",     # immediate penalty
        "on_missed": "none",            # letting it fall off is correct
        "capture_score": 0,
        "chain_score": 0,
    },
}
```

### Rendering pipeline (renderer.py)

1. Pre-compute a 4x4 **view-projection matrix** once at startup from fixed camera position
2. Each frame: collect all faces (grid tiles + cubes + player) as `(4 world vertices, color)`
3. Project each face's vertices to 2D screen coords via the matrix
4. **Back-face cull**: discard faces whose screen-space winding is clockwise (normal points away)
5. **Painter's algorithm**: sort remaining faces by average depth (farthest first)
6. Draw with `pygame.draw.polygon()` — filled faces + edge lines (width/color per cube type)

Performance: ~300 polygons/frame, ~1200 vertex projections. Even at 3-5x WASM slowdown, well within budget. Tile projections cached (static until row deletion).

### Cube tumbling (cube_data.py)

The signature animation: each cube rotates **90 degrees around its leading bottom edge** per tick.

- Pivot point: bottom-front edge at `(gx, 0, gz - 0.5)` for -Z movement
- Each vertex: translate to put pivot at origin, apply X-axis rotation by `theta = progress * pi/2`, translate back
- `tumble_progress` interpolates 0→1 over the tick interval
- On tick completion: snap to exact integer grid position, reset rotation
- **Optimization**: Pre-compute sin/cos lookup table for 0-90 degree range (16 steps) to avoid per-vertex trig calls under WASM

### Tick-based game loop (main.py)

```python
async def main():
    while running:
        dt = clock.tick(0) / 1000.0     # Uncapped — browser rAF governs pacing
        handle_events()                  # discrete: mark, trigger, detonate
        handle_held_keys(dt)             # continuous: movement with cooldown
        wave_manager.update(dt)          # decrement tick timer, fire tick when ready
        # On tick: advance cubes, check crush, check off-edge, check wave complete
        screen.fill(BLACK)
        render_3d_scene(screen)
        hud.draw(screen)
        effects.draw(screen)
        pygame.display.flip()
        await asyncio.sleep(0)           # CRITICAL: yield to browser event loop
```

Note: `clock.tick(0)` instead of `clock.tick(FPS)` — under WASM, the browser's `requestAnimationFrame` handles frame pacing. Explicit capping adds unnecessary delays.

---

## Game State Machine (game_manager.py)

Explicit phases with defined transitions:

```
TITLE → WAVE_RISING → WAVE_ACTIVE → WAVE_CLEARING → PERFECT_CHECK → WAVE_RISING (next wave)
                                                                    → STAGE_CLEAR (all waves done)
                         ↓ (crush)
                      AVALANCHE → PENALTY_APPLIED → WAVE_RISING (next wave)
                                                   → GAME_OVER (no ground)
                         ↓ (row delete)
                      ROW_COLLAPSING → WAVE_ACTIVE (continue)
                                     → GAME_OVER (player on void)
```

### Avalanche lifecycle (detailed):
1. Crush detected on tick (cube at player position)
2. Player death visual (flatten/flash), camera shake
3. State enters `AVALANCHE`: tick interval drops to ~0.05s
4. All remaining cubes rush off the front edge
5. Every missed Normal during avalanche counts toward penalty counter
6. When wave is empty: apply accumulated penalties (row deletions)
7. If player has valid ground → `WAVE_RISING` (next wave)
8. If player tile is void → `GAME_OVER`

---

## Game Mechanics Summary

### Three cube types
- **Normal (gray)**: Must capture. Missing one increments penalty counter. Threshold exceeded → back row deleted.
- **Advantage (green)**: Capturing creates a trap tile. Detonating triggers 3x3 blast (200 pts/cube). Blast is indiscriminate.
- **Forbidden (black/dark with red outline)**: Must NOT capture. Capturing (directly or via blast) → immediate row deletion. Letting it fall off = correct.

### Interaction: Mark → Trigger → Detonate
1. **SPACE**: Mark the tile under the player (one mark at a time; re-marking clears the previous mark)
2. **X/ENTER**: Trigger — if a cube is on the marked tile, capture it. Clears the mark regardless.
3. **Z**: Detonate — all advantage traps explode in 3x3 radius

### Mark lifecycle (explicit):
- Pressing MARK places a mark at player position; any previous mark is cleared first
- TRIGGER always clears the active mark (whether a capture occurs or not)
- Marks persist across ticks — a cube may arrive later
- Only one mark active at any time

### Failure states
- **Crush → Avalanche**: Cube occupies player's tile on tick. Remaining cubes rush off. Massive penalty.
- **Row deletion**: Penalty threshold exceeded OR forbidden captured. Back row becomes void.
- **Game Over**: Player's tile becomes void, or player pushed off front edge.

### Perfect bonus
All Normal + Advantage captured, zero Forbidden captured → restore one row + score bonus based on Ideal Step comparison.

### Scoring & I.Q. Algorithm
- Standard capture: 100 pts
- Chain capture (3x3 blast): 200 pts/cube
- Row survival bonus: remaining rows x 1,000
- Perfect bonus: up to 10,000 pts (based on step efficiency vs. Ideal Step)
- **I.Q. calculation** (from research): `raw_score * difficulty_multiplier * iq_percentage`
  - Difficulty multipliers: 1.00x (stage 0) through 1.50x (stage 4)
  - I.Q. percentages: 0.060% (stage 1) down to 0.020% (final stage)
  - Tables stored in `constants.py` for future multi-stage expansion

---

## Player Experience (from UX panel review)

- **Movement cooldown**: 0.08s (tunable in `constants.py`), not 0.12s — faster traversal is critical
- **Forbidden cube visibility**: Red outline + thicker edges, distinct from gray Normal cubes
- **Miss feedback**: Screen-edge flash + penalty counter pulse when a Normal cube escapes
- **Crush telegraph**: Player tile highlights red when a cube is one tick away
- **Browser focus loss**: Detect via `pygame.ACTIVEEVENT`, pause game with "CLICK TO RESUME" overlay
- **Controls overlay**: Mini-legend shown during wave 1, fades for subsequent waves
- **Audio**: Defer `pygame.mixer.init()` until first user gesture (browser autoplay restriction)
- **Tick metronome**: Rhythmic impact sound on each cube tick — functions as gameplay aid, not just atmosphere

---

## Platform Considerations (from Platform Engineer review)

- **Frame pacing**: `clock.tick(0)` — let browser rAF handle it, not Python sleep
- **Font**: Bundle `.ttf` file, never use `pygame.font.SysFont()` (unavailable under WASM)
- **Service worker**: Stale-while-revalidate for `.wasm`/`.data` files; cache-first for everything else
- **Canvas focus**: Custom template must include `tabindex="0"` on canvas + `canvas.focus()` on click
- **Sin/cos LUT**: Pre-compute 16-step lookup table for tumble rotation angles
- **Wave mirror**: 50% X-axis flip stored as flag in `wave_data.py` to double pattern variety cheaply

---

## Implementation Steps

Each step produces a **testable result in the browser** via `uv run python -m pygbag main.py`.

**Phase convention (Steps 3+):** every step is split into two phases so work can be paused between them (useful when waiting for Claude usage limits to refresh). A step is only "complete" after **both** phases pass.

- **Phase A — Development.** All work that doesn't need the user: implement the code, run `ruff check .` + `mypy --strict`, run desktop self-tests, run the 4-agent expert panel, resolve CONCERNS, write `docs/STEP<N>_REVIEW.md`, and update `PROGRESS.md`. Ends with **"awaiting user verification"**. This is a natural pause point — a fresh session can resume at Phase B by reading STEP<N>_REVIEW.md and PROGRESS.md.
- **Phase B — Testing.** User runs the browser per STEP<N>_REVIEW.md, reports findings. I apply any fixes (re-running ruff/mypy/self-test/panel as needed), update PROGRESS.md, and flip the step tracker to `APPROVED <date>` once the user says "approved". This is also a natural pause point — waiting on the user is a wall-clock gap regardless.

Steps 1 and 2 predate the convention but followed the same shape informally.

### Step 1: Scaffold + 3D renderer proof-of-concept — **COMPLETE (user-approved 2026-04-16)**
- `main.py`: async loop, black screen, FPS display
- `constants.py`: initial values, enums, cube type registry
- `renderer.py`: matrix math (look-at, perspective), vertex projection, face rendering with edge lines
- `cube_data.py`: canonical cube vertices, static cube generation, tile quad generation, sin/cos LUT
- ~~Bundle a `.ttf` font in `assets/`~~ — deferred to Step 10 (polish); pygame's built-in freesansbold.ttf works under WASM
- **Test**: One colored cube + small grid visible in 3D perspective in the browser → implemented as 5 demo cubes of 3 distinct types with desynchronized tumble phases
- See `STEP1_REVIEW.md` for the review doc and `PROGRESS.md` Session 2 for the full change log

### Step 2: Grid platform + player movement
- `grid_manager.py`: 2D state array, `is_valid_position()`, tile accessors, mark lifecycle
- `player.py`: arrow key movement, grid snapping, 0.08s cooldown
- Render full grid tiles + player cube through projection pipeline
- Tune camera to frame the grid
- **Test**: Player cube moves around on the full grid

### Step 3: Cube tumbling animation

**3A — Development**
- `cube_data.py`: tumble math (pivot rotation with LUT) — uses existing `TUMBLE_SIN_LUT`/`TUMBLE_COS_LUT` from `constants.py`
- `wave_manager.py`: tick timer, `tumble_progress` interpolation, cube advancement (cube array + per-tick advance)
- Spawn a debug row of cubes, integrate into `main.py` render loop
- Self-test: tumble math invariants (bbox, pivot fixed, y ≥ 0); tick advances cubes exactly one tile per `TICK_INTERVAL`; cubes falling off front edge are removed
- Panel review, resolve concerns, write `docs/STEP3_REVIEW.md`, update `PROGRESS.md`
- (Audio/metronome deferred to Step 10 polish — see current `PLAN.md` audio note)

**3B — Testing (user)**
- User runs in browser, verifies tumble visual against reference footage, confirms cadence + fall-off behavior, reports any issues
- I apply fixes and re-verify; step flips to APPROVED

### Step 4: Marking + capture

**4A — Development**
- `game_manager.py`: `on_trigger()`, capture logic dispatching via `CubeBehavior` registry, score tracking
- `hud.py`: score display, controls overlay (wave 1)
- `effects.py`: capture flash effect
- Wire MARK/TRIGGER keys; tile highlight when marked; cube removed on successful trigger
- Self-test: mark lifecycle end-to-end; `on_trigger` scoring paths for each cube type; flash effect lifecycle; HUD draw invariants
- Panel review, resolve concerns, write `docs/STEP4_REVIEW.md`, update `PROGRESS.md`

**4B — Testing (user)**
- User marks a tile, waits for cube arrival, triggers, sees capture + score + flash
- User reports; fixes; approval

### Step 5: Crush detection + avalanche

**5A — Development**
- Crush check mid-tumble (cube passes balance point in player's column → instant crush; fires before capture window so escape-by-capture is impossible)
- Avalanche sub-state: tick interval drops, cubes rush off, penalty accumulation
- Player death visual + camera shake
- No telegraph: the original I.Q. gives no advance visual warning; the player must read the wave themselves
- Self-test: crush detection; avalanche state transitions; penalty accumulator; mid-tumble threshold
- Panel review, resolve concerns, write `docs/STEP5_REVIEW.md`, update `PROGRESS.md`

> **TODO (carry-forward to Step 6):** Player can currently walk freely through tumbling wave cubes. In I.Q. the cubes are solid — the player cannot move into a tile that contains a cube (committed grid position). Implement collision blocking in `Player.try_move()` or via a blocking-tile set passed from `GameManager`/`WaveManager`. This is a gameplay-correctness issue: without it the player can trivially dodge any cube by stepping into its column.

**5B — Testing (user)**
- User deliberately stands in a cube's path; verifies crush → avalanche rush → penalty lifecycle
- User reports; fixes; approval

### Step 6: Penalty system + row deletion

**6A — Development**
- Track missed normals, penalty threshold, miss feedback (screen-edge flash + counter pulse)
- `grid_manager.py`: `delete_back_row()`, row collapse visual
- `hud.py`: penalty counter display
- Game over when player's tile is void
- Browser focus-loss pause overlay (`pygame.ACTIVEEVENT`)
- Self-test: miss-to-row-delete pipeline; row deletion leaves grid consistent; game-over trigger when player on voided tile
- Panel review, resolve concerns, write `docs/STEP6_REVIEW.md`, update `PROGRESS.md`

**6B — Testing (user)**
- User lets cubes escape, watches platform shrink; pushes into game-over; verifies focus-pause
- User reports; fixes; approval

### Step 7: Advantage cubes + 3x3 blast

**7A — Development**
- Green cube type wiring (already in registry), `ADVANTAGE_TRAP` tile state lifecycle, detonate key binding
- `wave_manager.py`: `try_blast_capture()` — 3x3 area check
- Chain capture scoring (200 pts/cube)
- Self-test: trap creation/clear on detonate; 3x3 blast covers correct tiles incl. grid edges; chain scoring math
- Panel review, resolve concerns, write `docs/STEP7_REVIEW.md`, update `PROGRESS.md`

**7B — Testing (user)**
- User captures a green cube, places trap, detonates, verifies area capture + chain score
- User reports; fixes; approval

### Step 8: Forbidden cubes

**8A — Development**
- Black/red-outline cube type wiring (already in registry), immediate row deletion on direct or blast capture
- Correct behavior: forbidden falling off front edge = no penalty
- Self-test: forbidden direct capture triggers row deletion; forbidden caught in 3x3 blast also triggers it; forbidden escape is harmless
- Panel review, resolve concerns, write `docs/STEP8_REVIEW.md`, update `PROGRESS.md`

**8B — Testing (user)**
- User plays mixed-type wave; verifies visual distinction + forbidden penalty semantics
- User reports; fixes; approval

### Step 9: Wave progression + Perfect bonus

**9A — Development**
- `wave_data.py`: 4 hand-designed wave patterns with `ideal_steps` per wave + mirror flag
- Wave sequencing, rising animation, Perfect detection, row restoration
- I.Q. scoring calculation (uses `IQ_DIFFICULTY_MULTIPLIERS` + `IQ_PERCENTAGE_MULTIPLIERS` already in `constants.py`)
- Self-test: wave load/mirror/sequence; Perfect detection criteria; I.Q. formula against hand-computed values from research doc
- Panel review, resolve concerns, write `docs/STEP9_REVIEW.md`, update `PROGRESS.md`

**9B — Testing (user)**
- User completes full 4-wave stage; verifies Perfect flow, row restoration, I.Q. readout
- User reports; fixes; approval

### Step 10: Polish

**10A — Development**
- Full HUD (score, wave counter, penalty meter, I.Q. display)
- Capture particle effects, Perfect celebration, camera shake on avalanche
- Title screen, game over screen, victory screen with I.Q.
- Bundled `.ttf` font in `assets/` (replacing `freesansbold.ttf` fallback)
- Tick-metronome audio + capture SFX (defer `pygame.mixer.init()` to first user gesture)
- `MOVE_COOLDOWN` tuning pass (carry-forward from Step 2 — user flagged 0.08s as too fast)
- **Camera rework (carry-forward from Step 6B):** the provisional camera values in
  `constants.py` (`CAMERA_POS`, `CAMERA_TARGET`, `CAMERA_FOV`) need a full revisit.
  The original I.Q. has a camera that tracks the player position along the grid and
  changes elevation/zoom per stage. Key items: (a) smooth camera tracking / per-stage
  offsets; (b) framing that keeps the active wave and the player both in-frame as the
  platform shrinks via row deletion; (c) validate all grid corners stay on-screen after
  row deletions narrow the visible platform. A `_GRID_CENTER_Z`-derived derivation is
  already in place but is provisional. Revisit in tandem with Step 9 wave progression.
- Self-test: HUD layout invariants; effects lifecycle; audio init gating; screen transitions
- Panel review, resolve concerns, write `docs/STEP10_REVIEW.md`, update `PROGRESS.md`

**10B — Testing (user)**
- User plays full game; verifies polish quality, audio, screen flow, tuned movement feel
- User reports; fixes; approval

### Step 11: PWA packaging

**11A — Development**
- `static/manifest.json`, `static/sw.js` (stale-while-revalidate), icons
- `custom.tmpl`: Pygbag template with PWA hooks, canvas focus management, `tabindex="0"` + autofocus (closes Step 2 canvas-focus gotcha)
- Self-test: manifest parses; SW caches correct assets; template renders canvas with focus attributes
- Panel review, resolve concerns, write `docs/STEP11_REVIEW.md`, update `PROGRESS.md`

**11B — Testing (user)**
- User verifies installability (Chrome Lighthouse), offline functionality, canvas focus on load
- User reports; fixes; approval → original plan complete

---

## Post-v1 Enhancements (Steps 12–26)

Steps 12 onward are new work added after the original 11-step plan was completed.
The same Phase A / Phase B convention applies throughout.

---

### Step 12: GitHub Pages deployment + CI/CD

**Goal:** Anyone can navigate to a URL in a browser and play immediately — no
installer, no setup.

**12A — Development**
- `.github/workflows/deploy.yml` — GitHub Actions workflow triggered on push to `master`:
  1. `actions/checkout@v4`
  2. `astral-sh/setup-uv@v3` with `cache: true`
  3. `uv tool run --from 'pygbag==0.9.3' pygbag --no_server --ume_block 0 --disable-sound-format-error --template custom.tmpl main.py`
  4. Belt-and-suspenders checks: `index.html`, `manifest.json`, `sw.js`, `icon-192.png`, `icon-512.png` present in `build/web/`
  5. `actions/configure-pages@v4` → `upload-pages-artifact@v3` → `deploy-pages@v4`
- `static/sw.js` — bump `CACHE_NAME` to `'avalanche-v2'`; `SHELL_URLS` changed to
  `BASE + 'filename'` where `BASE = new URL('./', self.location.href).pathname`
  (fixes pre-cache on GitHub Pages sub-paths like `/<repo>/`)
- `pygbag.ini` — add `.python-version` and `run_dev.sh` to `ignorefiles`
- Panel review, write `docs/STEP12_REVIEW.md`, update `PROGRESS.md`

**12B — Testing (user)**
- Create public GitHub repo; `git remote add origin`; enable GitHub Pages → Source: GitHub Actions
- Initial commit + push; verify Actions run passes (~60–90 s)
- Open public URL; verify game loads and is playable; verify PWA manifest + SW in DevTools
- Verify auto-redeploy on a follow-up push

---

### Step 13: Turbo / accelerate key

**Goal:** Hold a key (`F`) to speed up the wave tick when the player has already
planned their moves.

**13A — Development**
- `constants.py` — new `TURBO_TICK_INTERVAL: float = 0.25` (between normal 1.2 s and
  avalanche 0.15 s)
- `game_manager.py` — `set_turbo(enabled: bool)`: sets
  `wave.tick_interval = TURBO_TICK_INTERVAL if enabled else TICK_INTERVAL`;
  only active during `WAVE_ACTIVE` phase; `tick_interval` setter safety guards
  (wave_manager.py lines 81–90) handle the interval change cleanly
- `main.py` `_drain_events()` — `KEYDOWN F` → `game.set_turbo(True)`;
  `KEYUP F` → `game.set_turbo(False)` (hold-to-turbo, not toggle)
- `hud.py` — add `"Turbo: F"` to controls hint
- Self-test: hold turbo → faster ticks; release → normal; no overshoot assertion;
  turbo key has no effect during avalanche phase

**13B — Testing (user)**
- Hold turbo mid-wave: cubes visibly tick faster
- Release: normal speed resumes immediately
- Turbo during avalanche: no effect (avalanche already at max speed)

---

### Step 14: Esc pause menu

**Goal:** Pressing Esc opens an overlay with Resume and Restart options.

**14A — Development**
- `constants.py` — add `GamePhase.MENU` to the enum (lines 130–140)
- `game_manager.py` — `on_menu_open()`, `on_menu_close()`, `on_menu_select(item: int)`,
  `_restart()`, `_pre_menu_phase: GamePhase` field; add MENU to frozen phases
- `renderer.py` — `_draw_menu_overlay(screen, selected_item)`: semi-transparent black
  rect, item list, highlight on selected row
- `main.py` — Esc routing: if MENU → close; else → open; UP/DOWN/ENTER route to menu
  navigation when phase is MENU
- Self-test: Esc opens overlay; wave frozen; Resume restores exact phase; Restart resets
  from Wave 1; Esc-while-open = Resume

**14B — Testing (user)**
- Esc mid-wave: overlay appears, cubes frozen
- Navigate items; Resume: game continues from exact state
- Restart: fresh game from Wave 1

---

### Step 15: Capture animation + flash colour tinting

**Goal:** Replace single-frame flash with multi-frame particle burst; tint by cube type.
(Covers deferred A5 flash-tinting; A5 is absorbed into this step.)

**15A — Development**
- `effects.py` — expand `_Flash` with `cube_type: CubeType` and
  `particles: list[_Particle]`; add `_Particle` dataclass
  (`x, y, vx, vy, life, color`); `spawn_flash(grid_x, grid_z, cube_type)` projects
  grid → screen coords at spawn, emits 8–12 particles coloured by type
  (Normal: white, Advantage: green, Forbidden: red); `update`/`draw` animate particles
- `game_manager.py` — update `_dispatch_capture` (lines 491–529) and
  `_execute_blast` (lines 429–470) to pass `cube_type` to `spawn_flash`; blast spawns
  16+ particles with wider spread
- Bounds: `assert len(self._flashes) < 64` (Rule 3)
- Self-test: particle spawn/update/evict lifecycle; type-colour mapping; blast burst
  larger than single-capture burst; cap holds under overspawn

**15B — Testing (user)**
- Capture Normal cube: white burst
- Capture Advantage cube: green burst
- Capture Forbidden cube: red burst
- Detonate blast: larger green burst over affected tiles

---

### Step 16: Enhanced graphics — face shading + camera

**Goal:** Richer depth on cubes; better camera angle. (Covers B3a and A7/B3b.)

**16A — Development**
- `constants.py` — add `FACE_TOP_MULT = 1.0`, `FACE_RIGHT_MULT = 0.75`,
  `FACE_LEFT_MULT = 0.55`; adjust `CAMERA_*` constants for better depth perception
  (reduce tilt slightly to show more of the top faces)
- `cube_data.py` — `get_cube_faces()` (lines 192–200) applies multiplier to each
  face colour based on face index in `_CUBE_FACES` (lines 49–56); no pipeline change
- Self-test: top/right/left face colours are in descending brightness order for every
  cube type; multiplier table is the same length as `_CUBE_FACES`

**16B — Testing (user)**
- All three cube faces visibly distinct in brightness
- Camera angle shows top face clearly without distorting perspective

---

### Step 17: HUD render caching

**Goal:** Stop re-rendering 7 font surfaces every frame when values haven't changed.

**17A — Development**
- `hud.py` — add `_cache: dict[str, tuple[str, pygame.Surface]]` keyed by label;
  call `font.render()` only when the cached text string differs from the new value
- Self-test: render called once on first draw; not called on second draw with same
  value; called again after value changes

**17B — Testing (user)**
- No visual regression on HUD display
- FPS counter in browser should be marginally higher (or at least no lower)

---

### Step 18: Transition hold animations

**Goal:** Add a timed hold on GAME OVER / VICTORY overlays before accepting restart input.

**18A — Development**
- `game_manager.py` — add `_overlay_elapsed: float = 0.0`; `update()` increments it
  during GAME_OVER and VICTORY; `on_restart_key` / `on_title_advance` gate on
  `_overlay_elapsed >= OVERLAY_HOLD_DURATION` (e.g. 2.0 s)
- `constants.py` — `OVERLAY_HOLD_DURATION: float = 2.0`
- `renderer.py` (or `main.py`) — optional fade-to-black overlay during the hold
- Self-test: restart key ignored during hold; accepted after hold expires; timer resets
  on new game

**18B — Testing (user)**
- GAME OVER: overlay holds for ~2 s before any key advances to title
- VICTORY: same hold
- No premature restart from accidental key press at end of wave

---

### Step 19: Grid texture + player shadow + danger telegraph

**Goal:** Visual polish sub-tasks: checkerboard floor, player ground shadow,
front-edge cube warning. (Covers B3c, B3d, B3e.)

**19A — Development**
- `renderer.py` `_render_grid_tile()` — `(grid_x + grid_z) % 2` alternates tile
  lightness by 5–8% for subtle checkerboard
- `renderer.py` — render a filled ellipse under the player before the player cube
  at the player's projected ground position (player shadow)
- `wave_manager.py` — `_danger_cubes: set[int]` (cube IDs at front-edge Z, one tick
  from falling off); exposed as `danger_cube_ids` property
- `renderer.py` / `cube_data.py` — override top-face colour to white for cubes in
  `danger_cube_ids` (countdown telegraph)
- Self-test: danger set populated for cubes at front edge; empty when no cubes there;
  checkerboard pattern consistent

**19B — Testing (user)**
- Floor shows subtle checkerboard
- Shadow visible under player
- Cubes at front edge show white-flashed top face

---

### Step 20: Additional stages (Stage 2+)

**Goal:** Add Stage 2 so the game continues after Stage 1.

**20A — Development**
- `wave_data.py` — `STAGE_2_WAVES: tuple[WaveData, ...]` (harder patterns: more
  Forbidden cubes, tighter ideal-step counts); document `ideal_steps` derivation
- `constants.py` — `STAGES: tuple[tuple[WaveData, ...], ...] = (STAGE_1_WAVES, STAGE_2_WAVES)`
- `game_manager.py` — `_stage_index: int = 0`; `_on_stage_complete()` increments and
  calls `start_first_wave(player, STAGES[_stage_index])`, or VICTORY if last stage;
  `_calculate_final_iq()` uses `IQ_DIFFICULTY_MULTIPLIERS[_stage_index]`
  (replaces hardcoded `[0]`; table already in `constants.py` lines 264–268)
- `hud.py` — add `Stage: N` line alongside `Wave: N/M`
- `renderer.py` — `_draw_stage_clear_overlay()` between stages (distinct from VICTORY)
- Self-test: Stage 1 completion triggers Stage 2 start; IQ multiplier for Stage 2 is
  1.25×; Stage 2 completion triggers VICTORY; stage index guard prevents out-of-bounds

**20B — Testing (user)**
- Clear all 4 Stage-1 waves → Stage Clear overlay → Stage 2 starts
- IQ multiplier for Stage 2 is 1.25×
- Clear Stage 2 → VICTORY
- HUD shows correct stage and wave numbers throughout

---

### Step 21: Per-stage tick interval table

**Goal:** Replace provisional `TICK_INTERVAL = 1.2` with a proper per-stage table.

**21A — Development**
- `constants.py` — `STAGE_TICK_INTERVALS: list[float]` and
  `STAGE_AVALANCHE_TICK_INTERVALS: list[float]`, both indexed by stage (0-based)
- `game_manager.py` — read from the table using `_stage_index` when starting a wave;
  replace hardcoded `TICK_INTERVAL` and `AVALANCHE_TICK_INTERVAL` references
- Self-test: Stage 0 uses `STAGE_TICK_INTERVALS[0]`; Stage 1 uses `[1]`; avalanche
  interval also stage-indexed

**21B — Testing (user)**
- Stage 1 feels measurably faster than Stage 0 (if different values chosen)
- Avalanche speed per stage is correct

---

### Step 22: Bundled `.ttf` font

**Goal:** Replace `pygame.font.Font(None, …)` (freesansbold fallback) with a
permissively-licensed retro pixel font bundled in `assets/`.

**22A — Development**
- Add OFL-licensed font (e.g. Press Start 2P, Silkscreen) to `assets/<font>.ttf`
- New `fonts.py` — `_load_font(size: int) -> pygame.font.Font` with size-keyed cache
  (Rule 3 cap on cache size); falls back to `Font(None, size)` if file missing
- `hud.py`, `renderer.py` — replace all `Font(None, …)` calls with `_load_font(…)`
- Self-test: cache hit / miss behavior; fallback path when file absent; HUD renders
  same number of lines as before

**22B — Testing (user)**
- HUD and overlays show the new font
- Font is legible at all sizes used

---

### Step 23: Movement perpendicular priority

**Goal:** Enforce Z-priority (perpendicular to wave = forward/backward) when both
axes pressed simultaneously, matching original I.Q. behaviour.

**23A — Development**
- `player.py` — in `_first_held_direction`: if both X and Z axis keys are held,
  return the Z-axis direction (FORWARD or BACKWARD); document the priority rule
- Self-test: LEFT+FORWARD → FORWARD; RIGHT+BACKWARD → BACKWARD; LEFT+RIGHT → None
  (cancellation still applies before priority); single-axis unchanged

**23B — Testing (user)**
- Diagonal key presses consistently produce perpendicular (Z-axis) movement

---

### Step 24: Camera rework

**Goal:** Tune camera constants for improved depth perception and grid framing.
(Carry-forward from TODO comment in `constants.py` lines 68–71.)

**24A — Development**
- `constants.py` — adjust `CAMERA_POS`, `CAMERA_TARGET`, `CAMERA_FOV` for better
  depth perception; validate all grid corners remain on-screen after any row
  deletions (reuse the framing-test from Step 2 self-test)
- No code changes — purely constant tuning

**24B — Testing (user)**
- Cubes and grid feel more three-dimensional
- Front edge, back row, and player all comfortably in frame at all times

---

### Step 25: Audio system

**Goal:** Add the full audio suite — tick metronome, capture SFX, row-crack, wave
fanfare, penalty buzz, game-over sting.

**25A — Development**
- `audio.py` — `AudioManager`: defers `pygame.mixer.init()` to first user gesture
  (browser autoplay restriction); generates sounds procedurally (no external files);
  exposes `on_tick()`, `on_capture(cube_type)`, `on_penalty()`, `on_row_delete()`,
  `on_wave_clear()`, `on_game_over()`
- `constants.py` — `SOUND_ENABLED: bool` flag
- `main.py` — instantiate `AudioManager`; wire gesture detection; call audio hooks at
  each game event
- `game_manager.py` — pass audio hooks into dispatch / state transitions
- Metronome: pitch and tempo increase as avalanche approaches (tick interval shrinks);
  functions as gameplay aid (rhythmic cue) as much as atmosphere
- Self-test: init deferred until first key press; each hook fires at the correct game
  event; graceful no-op if `mixer.get_init()` returns falsy

**25B — Testing (user)**
- All sound events fire at the right moments
- Metronome tempo audibly increases during avalanche
- Game is playable with sound on and off (toggle via SOUND_ENABLED or Esc menu option)

---

## Implementation order (post-v1)

| Step | ID | Description | Effort | Value |
|------|----|-------------|--------|-------|
| 12 | C1 | GitHub Pages deployment | Low | Critical |
| 13 | B1 | Turbo key | Low | High |
| 14 | B2 | Esc menu | Medium | High |
| 15 | A5+B4 | Capture animation + flash tinting | Medium | High |
| 16 | B3a+A7 | Face shading + camera | Low | High |
| 17 | A4 | HUD render cache | Low | Medium |
| 18 | A6 | Transition hold | Low | Medium |
| 19 | B3c+d+e | Grid texture + player shadow + telegraph | Medium | Medium |
| 20 | B5 | Stage 2 | High | High |
| 21 | A2 | Per-stage tick table | Low | Medium |
| 22 | A3 | Bundled font | Low | Medium |
| 23 | A8 | Movement priority | Very low | Low |
| 24 | A7 | Camera rework | Very low | Low |
| 25 | A1 | Audio | Very high | Very high |

---

## Out of scope (post-v1, deferred indefinitely)

- **Lighthouse 100 PWA score** — needs a `screenshots` manifest entry; add when
  a good screenshot is available after deployment.
- **Stage 3+ wave data** — stub `STAGES` tuple; lay out after Stage 2 is approved.
- **Mobile touchscreen** — game is `orientation: landscape`, keyboard-only by design.
- **Custom domain** — add `CNAME` to `static/` and configure GitHub Pages when desired.

---

## Expert Review Panel

After each step, 4 specialist agents review the changes in parallel:

| Expert | Focus |
|---|---|
| **Vision Lead** (Game Designer) | Gameplay feel, faithfulness to original, difficulty pacing, retro identity, future expansion compatibility |
| **Code Quality** (Senior Programmer) | Modularity, separation of concerns, naming, bugs, edge cases, extensibility |
| **Player Experience** (UX Tester) | Input responsiveness, visual clarity, control intuitiveness, feedback quality, player confusion points |
| **Platform Engineer** | WASM performance, Pygbag compatibility, browser gotchas, PWA correctness, frame budget |

Each returns: **Approved / Concerns** with specific findings. Issues are resolved before user review.

---

## Verification Plan

1. **Each step**: Run `uv run python -m pygbag main.py`, open browser at localhost:8000, verify the milestone
2. **Step 3**: Compare tumble animation visually against original game footage
3. **Step 8**: Play through a full wave mixing all 3 cube types — verify scoring, penalties, blast interactions
4. **Step 9**: Complete all 4 waves — verify Perfect bonus, I.Q. calculation, stage clear
5. **Step 10**: Test edge cases: get crushed intentionally, capture a forbidden in a blast, let platform shrink to near-nothing
6. **Step 11**: Chrome DevTools → Application → Manifest check; toggle offline in DevTools → reload → game still runs
