# Step 1 — User Review

**What Step 1 covers:** project scaffolding, software-3D renderer, a grid of tiles rendered in perspective, and five demo cubes (of three distinct types) tumbling forward across the grid to prove the rendering pipeline works end-to-end in the browser. **No gameplay yet** — that starts in Step 2.

Everything below is what you (the user) need to do to verify Step 1 before I move on.

---

## 1. Run the dev server

You have two equivalent paths; pick whichever you prefer. Both serve the game on **http://localhost:8000**.

### Option A — Git Bash on Windows (recommended)

```bash
cd /f/Python/Avalanche
bash run_dev.sh
```

### Option B — WSL

```bash
cd /mnt/f/Python/Avalanche
bash run_dev.sh
```

`run_dev.sh` copies the game files into `/tmp/avalanche_build/` and launches `pygbag` (pinned to `0.9.3`) via `uv tool run`. It never touches the project's `.venv`, so you can switch between Windows and WSL without conflicts.

### First-time expectations

- You'll see a progress log in the terminal ending with something like:
  `Serving HTTP on 127.0.0.1 port 8000 ...`
- **The first load in a fresh browser takes ~30 seconds** while pygbag downloads CPython + Pygame CE from its CDN. Subsequent reloads (same browser profile) are near-instant because the browser caches the WASM.
- Open **http://localhost:8000** in Chrome/Edge/Firefox.

### Stopping

`Ctrl+C` in the terminal.

---

## 2. What you should see in the browser

Once the WASM finishes loading you should see, on a black background:

- A **perspective grid** of tiles receding into the distance (2 rows × many columns of gray quads). Tiles nearer the camera appear larger; tiles farther away appear smaller.
- **Five cubes** positioned on the grid at different depths:
  - 3 × **Normal** — light-gray tops, fading to darker gray sides, thin dark edges.
  - 1 × **Advantage** — muted green (not eye-searing neon), thin bright-green edges.
  - 1 × **Forbidden** — near-black with a distinct **red outline**.
- Each cube tumbles forward (rolls over its leading edge toward the camera) continuously. **The cubes should be desynchronized** — they should not all tip at the same moment; each has its own phase offset. If they tumble in lockstep, that's a bug.
- Top-left HUD:
  - `FPS: <number>` — should be ≥ 60 on a modern desktop; expect 120+ if your display refresh is uncapped.
  - `Polys: 186` — should be stable (approximately 60 tiles + 5 cubes × ~6 visible faces, after back-face culling).

### Success criteria (everything should be true)

- [ ] Grid draws correctly in perspective — rows near you are larger than rows far away.
- [ ] All 5 demo cubes visible; 3 distinct types are clearly distinguishable by color.
- [ ] The **Forbidden** cube has a visible red outline.
- [ ] Cubes tumble **independently** (desynced phases), not in unison.
- [ ] No cube ever dips below the grid during the tumble animation (no geometry through the floor).
- [ ] FPS is stable (varies by ≤ ~10% once warm). No stuttering or freezing.
- [ ] No Python tracebacks in the browser console (press F12 → Console).

### Known harmless console messages

- `BrowserFS not found` — pygbag prints this when running without its optional filesystem polyfill. We don't use it. Safe to ignore.
- Pygame CE banner / version string on startup.

---

## 3. Expert Panel findings (how they were addressed)

After my self-test I ran the 4-expert panel review. Summary of what changed:

| Reviewer | Finding | Resolution |
|---|---|---|
| Game Designer | Advantage-cube green was too neon-bright — breaks retro-PS1 palette | Muted `(100,255,100)` → `(100,220,100)`; edge kept bright for readability |
| Game Designer | Demo cubes all tumbled in lockstep — reads as a looping GIF, not individual cubes | Added per-cube `phase_offset`; 5 cubes now at phases 0.00, 0.22, 0.47, 0.68, 0.85 |
| Code Quality | `CUBE_TYPES` behavior hooks were free-form strings — easy to typo, no IDE completion | Introduced `CubeBehavior` enum (`SCORE`, `PENALTY`, `CREATE_TRAP`, `DETONATE_3X3`, `ROW_DELETE`, `NONE`). All hooks now reference the enum |
| Code Quality | Camera position was hardcoded magic numbers — would drift from `GRID_WIDTH`/`GRID_DEPTH` if dimensions changed | Derived from grid: `CAMERA_POS = (grid_center_x, 14.0, -6.0)`, `CAMERA_TARGET = (grid_center_x, 0.0, grid_depth * 0.5)` |
| Code Quality | `get_cube_faces` silently fell back to default colors if a palette key was missing | Added explicit `"back"` keys to all 3 cube types + player; `_build_faces` helper now requires full palette coverage (KeyError on missing) |
| Code Quality | `get_player_vertices` used magic `(scale / 0.5)` | Replaced with `PLAYER_HALF_EXTENT = 0.4` constant; `s = 2.0 * PLAYER_HALF_EXTENT` |
| Code Quality | `_transform_point` returned `rw` with no docstring — unclear what that value means | Renamed `clip_w`, added docstring: *"With our perspective matrix, `clip_w == -z_view`"* |
| UX Tester | Forbidden cube must be instantly recognizable (user's #1 death cause) | Red edge at width 2 (vs. 1 for other types). Verified visible against black background |
| UX Tester | FPS readout showed "1" under WASM even when rendering smoothly | `pygame.Clock.get_fps()` is unreliable with `tick(0)` in WASM. Replaced with a rolling-60-sample dt average |
| Platform Engineer | `clock.tick(0)` + `await asyncio.sleep(0)` — confirmed these are the correct pygbag idioms for letting the browser's rAF govern pacing |
| Platform Engineer | Initial tumble math rolled the cube **through the grid floor** (desktop invariant test caught this before browser test) | Inverted rotation sign. Analytical check: rest bbox y=(0,1); half-tumble y_peak=1.414, all y ≥ 0; full-tumble bbox y=(0,1) and pivot edge stays fixed |

### Deferred to later steps (intentional)

- Mouse/keyboard input handling — Step 2 (player movement).
- Font loading from a bundled `.ttf` — Step 10 (polish). Currently uses pygame's built-in `freesansbold.ttf`, which works under WASM.
- Service worker / PWA manifest — Step 11.
- Audio — Step 10.

---

## 4. Known dev-tooling quirks (for your awareness)

These are environment things, not game bugs:

- **`http://0.0.0.0:8000` will NOT work.** pygbag templates the bind address directly into its asset URLs, and browsers reject `0.0.0.0` as a navigation target. Always use `http://localhost:8000`. `run_dev.sh` intentionally uses the default `--bind localhost`.
- **If port 8000 is already in use**, the server will refuse to start. On Windows, check with `netstat -ano | findstr :8000` and kill the offending PID. On Linux: `ss -ltnp | grep :8000`.
- **WSL2 networking**: `wslrelay.exe` automatically forwards Windows `localhost:8000` to WSL's `127.0.0.1:8000`, so you can launch the server in WSL and still open it from a Windows browser.
- **Hidden-tab pause**: modern browsers pause `requestAnimationFrame` in hidden tabs, which stalls pygbag's async loop. This is expected — the game will resume when the tab is foregrounded. (Relevant if you try to screenshot via a headless browser tool; for normal use this is fine.)

---

## 5. What to tell me after you review

Any one of:

- **"Step 1 approved, proceed to Step 2"** — I'll start the Step 2 plan (grid-platform state + player movement).
- **"Changes needed: [X, Y, Z]"** — I'll address them and re-run the panel.
- **"I can't run it because [error]"** — paste the terminal output and I'll debug.

---

## Files changed/added in Step 1

```
main.py            (new)     — async entry point, demo loop, per-cube tumble phases, rolling-dt FPS
constants.py       (new)     — screen/grid dims, camera derived from grid, CubeType/TileState/CubeBehavior enums, CUBE_TYPES registry with back-face colors
renderer.py        (new)     — view-projection matrices, back-face culling, painter's algorithm, clip_w-based near-plane rejection
cube_data.py       (new)     — cube/tile vertex generation, tumble rotation (fixed sign), _build_faces palette-coverage helper
run_dev.sh         (new)     — dev server launcher (uv tool run --from pygbag==0.9.3)
pygbag.ini         (new)     — pygbag config
pyproject.toml     (new)     — pygame-ce dependency
docs/PROGRESS.md   (updated) — Step 1 marked complete, session log appended
```

> Note: As of the post-Step-1 repo reorganization, planning/progress docs live in `docs/` and Claude memory lives in `.claude/memory/`. See `CLAUDE.md` at the project root for the full layout.
