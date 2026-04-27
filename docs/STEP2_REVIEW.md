# Step 2 — User Review

**What Step 2 covers:** the platform-state model (`GridManager`), a grid-snapped player avatar with keyboard movement (`Player`), the full grid rendered through the existing 3D pipeline, and a retuned camera that anchors the front row near the bottom of the screen so the entire play area and the player spawn are always on-screen. **No cubes, no scoring, no avalanche yet** — the platform is quiet; the only thing moving is you.

Everything below is what you need to do to verify Step 2 before I move on to Step 3.

---

## 1. Run the dev server

Same as Step 1. Pick whichever shell you prefer; both serve on **http://localhost:8000**.

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

First-time fresh-browser load is still ~30s while pygbag fetches CPython. `Ctrl+C` in the terminal to stop.

> **Canvas focus gotcha (Platform panel flagged this):** pygbag's canvas must have keyboard focus for `pygame.key.get_pressed()` to see anything. **Click anywhere inside the game canvas after it loads** before you try moving. If keys feel dead on first load, that's almost certainly why — click and they'll start working.

---

## 2. What you should see in the browser

Once WASM finishes loading, on a black background:

- A **perspective grid** of 7 × 25 = 175 tiles, receding into the distance. The **front row is anchored near the bottom of the screen**, and the back row sits near the top — this framing mimics I.Q.'s original composition. Tiles are uniformly gray-blue with thin dark edges.
- A **blue player cube** sitting on tile `(3, 1)` — one row back from the front edge, centered horizontally. It's slightly smaller than a tile so you can see the tile under it.
- Top-left HUD:
  - `FPS: <number>` — expect 60+ on a modern desktop; 120+ if your display refresh is uncapped.
  - `Polys: 181` (roughly) — 175 tiles + 6 player-cube faces. Back-face culling drops a handful, so expect ~180.
  - `Pos: (x, z)` — the player's current grid coordinates. Updates live as you move. (This is debug overlay — it'll get gated behind a debug flag once the real HUD lands in Step 4.)

---

## 3. Movement controls to test

Both bindings work for every direction:

| Direction | Arrow key | WASD |
|---|---|---|
| Left (−X) | `←` | `A` |
| Right (+X) | `→` | `D` |
| Forward / toward camera (−Z) | `↑` | `W` |
| Back / away from camera (+Z) | `↓` | `S` |

**Cooldown:** `0.08s` between moves. First-press is instant (no cooldown on the first held frame), subsequent auto-repeat is ~12 Hz. Holding a direction should feel snappy but not spray-walk.

### Success criteria (every item should be true)

- [ ] Player cube is visible at `(3, 1)` on page load, sitting on top of a tile. Position HUD reads `Pos: (3, 1)`.
- [ ] Arrow keys move the player one tile per press. HUD `Pos` updates to match.
- [ ] WASD also moves the player, identically to arrows.
- [ ] **Holding** a direction key auto-repeats at a consistent cadence (roughly 12 moves/sec — the full 7-tile width should clear in under half a second).
- [ ] Pressing LEFT + RIGHT together (or UP + DOWN together) → player does **not** move. No silent bias. (Perpendicular combos like LEFT + UP → picks LEFT — see §5 below, this may become a fix after you try it.)
- [ ] Pressing into the grid edge (e.g., hold LEFT at column 0) → player stops at the edge, does not wrap, does not crash. Releasing and pressing the opposite direction immediately moves.
- [ ] Player can traverse to the back row (`Pos: (x, 24)`) and back to the front row (`Pos: (x, 0)`) without ever going off-screen.
- [ ] No Python tracebacks in the browser console (F12 → Console).
- [ ] FPS stable (±10% once warm). No stuttering when moving.

---

## 4. Expert Panel findings (how they were addressed)

After my self-test I ran the 4-expert panel review. All four APPROVED with concerns. Summary of what changed in response:

| Reviewer | Finding | Resolution |
|---|---|---|
| Code Quality | `_update_fps` appended before bounds-check — Rule 3 requires the guard to precede the mutation | Rewrote to trim-then-append-then-assert so the precondition is visible at the append site |
| Code Quality | `_drain_events` had no Rule-5 meaningful check | Added `MAX_EVENTS_PER_FRAME = 1024` assertion — catches flooded queues rather than silently hanging |
| Code Quality | `_first_pressed_direction` name was misleading (`"pressed"` is edge-triggered in pygame; the function reads held state) | Renamed to `_first_held_direction`; docstring explicitly calls out the distinction |
| Code Quality | `iter_tiles`'s mutation contract was implicit | Added an explicit "callers must not mutate during iteration" note to the docstring |
| UX Tester | Opposite-axis holds silently picked the higher-priority direction (classic "sticky axis" frustration) | `_first_held_direction` now cancels opposite-axis pairs — LEFT+RIGHT → None, FORWARD+BACKWARD → None. Perpendicular conflicts still collapse to insertion-order priority |
| UX Tester | Player's blue-on-bluish-gray contrast was marginal — could blur on dim screens under WASM's color gamut | Bumped `PLAYER_COLORS.top` from `(80,160,255)` → `(130,200,255)` and brightened the gradient chain for a wider luminance gap against the `(90,90,110)` tile top |
| Platform Engineer | Canvas-focus gotcha: `pygame.key.get_pressed()` reads `False` for everything until the user clicks the canvas | Flagged at the top of this document; cleanly-scoped PWA fix lands in Step 11 (`tabindex`/autofocus in the pygbag template) |
| Platform Engineer | Confirmed `pygame.key.get_pressed()` + `ScancodeWrapper` handles large K_* values (e.g. K_LEFT = 1073741904 > wrapper length 512) under WASM — pygame-CE's `__getitem__` translates them internally | No change needed; comment in `player.py` documents the assumption |
| Vision Lead | Camera pitch feels slightly more top-down than the original I.Q. (y=18 vs. original's shallower ~25-30°) | **Deferred to your visual judgment — please compare against reference footage in §5** |
| Vision Lead | Static priority (LEFT beats RIGHT beats FORWARD beats BACKWARD) isn't how the original handled multi-direction holds — original used most-recently-pressed | **Deferred** — needs KEYDOWN tracking; belongs to an input-polish pass, not Step 2 scaffolding. Opposite-axis cancellation above covers the worst of the frustration |
| Vision Lead | Player spawn at `(GRID_WIDTH//2, 1)` — suggested Z=0 for faithfulness | **Deferred** — research doc doesn't specify exact spawn row; Z=1 keeps one tile of retreat space, which is load-bearing once the back-edge-fall rule arrives in Step 6. See §5 to call the judgment |

### Deferred to later steps (intentional)

- **Initial-move-delay (UX polish):** an I.Q.-style "first tap + ramped auto-repeat" would feel more retro, but current 0.08s uniform cadence is the value the approved PLAN specifies.
- **Last-pressed direction priority:** requires KEYDOWN event tracking; input polish pass.
- **Front-row "danger zone" visual cue:** Step 5 (crush telegraph) or Step 6 (row-delete visual).
- **Player facing-direction indicator:** Step 3+ — once the player tumbles or acts, orientation becomes contextual.
- **HUD debug-gating (`Pos:` readout):** Step 4 when the real HUD arrives.
- **Pre-allocated face buffer (Platform perf):** defer until Step 5+ profiling shows it's needed.

---

## 5. Judgment calls I'd like you to make

These are design decisions the panel raised that I didn't change unilaterally. Tell me your preference when you review:

1. ~~**Spawn row.** Currently `PLAYER_SPAWN_Z = 1`.~~ **RESOLVED** — user confirmed `(3, 1)` is the correct spawn (row 1, center column, one-tile retreat buffer preserved).
2. **Camera pitch.** Currently `CAMERA_POS = (3.0, 18.0, -8.0)`, `CAMERA_TARGET = (3.0, 0.0, 10.0)`. Vision Lead flagged this as more top-down than I.Q.'s original ~25-30° pitch. Compare against your memory of the original: does it feel too overhead? If so, I'll lower the camera y and bring the target z closer to the camera for a shallower look-angle.
3. ~~**Static perpendicular priority.** Holding LEFT+UP currently picks LEFT.~~ **DEFERRED** — user asked to revisit at a later stage; this feature will need tuning later. Revisit candidate: after Step 3 (cubes land) when real gameplay pressure exposes whether static priority feels wrong. Implementation note: switch to last-pressed via a KEYDOWN-tracked deque in `_first_held_direction`.

---

## 6. Known dev-tooling quirks (carry-over from Step 1)

- Use **`http://localhost:8000`**, not `http://0.0.0.0:8000`. Pygbag templates the bind address into its asset URLs; browsers reject `0.0.0.0`.
- If port 8000 is in use: Windows `netstat -ano | findstr :8000` then kill the PID. Linux: `ss -ltnp | grep :8000`.
- WSL2 localhost forwarding via `wslrelay.exe` works; you can launch the server in WSL and open it from a Windows browser.
- Hidden-tab `rAF` pause is still in effect — the game correctly resumes when the tab is foregrounded (confirmed by the `DT_CLAMP = 0.1` tab-switch recovery).

---

## 7. What to tell me after you review

Any one of:

- **"Step 2 approved, proceed to Step 3"** — I'll start the Step 3 plan (cube tumbling animation + wave_manager scaffolding).
- **"Approved, plus these changes: [1=Z0, 2=shallower pitch, 3=last-pressed]"** — I'll apply the §5 decisions before moving on.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel.
- **"I can't run it because [error]"** — paste the terminal/browser-console output and I'll debug.

---

## Files changed/added in Step 2

```
grid_manager.py    (new)     — GridManager: 2D TileState array, accessors, mark lifecycle (mark/clear_mark), iter_tiles for rendering
player.py          (new)     — Player: grid-snapped avatar, cooldown-gated movement, opposite-axis cancellation, WASD + arrow bindings
main.py            (updated) — removed demo cubes; now wires GridManager + Player; renders full grid each frame; HUD adds Pos readout; _update_fps + _drain_events tightened per Code-Quality panel
constants.py       (updated) — camera retuned (y 14→18, z -6→-8, target.z 12.5→10); PLAYER_COLORS luminance bumped for contrast
docs/PROGRESS.md   (updated) — Step 2 status flipped to complete; session log appended
```

No changes to `renderer.py` or `cube_data.py` — their Step 1 APIs were sufficient.
