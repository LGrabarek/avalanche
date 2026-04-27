# Step 3 — User Review (Phase B)

**What Step 3 covers:** cubes spawn at the back row and tumble forward one tile per tick. That's it. No capture, no scoring, no crush — the row just rolls across the grid and falls off the front edge. This is the first step with moving game content, so the bar for Phase B is "does the animation read correctly and feel about right."

**What's new vs. Step 2:** cubes tumble. Everything else (grid, player movement, camera, HUD layout) is identical to Step 2.

---

## 1. Run the dev server

Same as prior steps. Serves on **http://localhost:8000**.

### Option A — Git Bash on Windows

```bash
cd /f/Python/Avalanche
bash run_dev.sh
```

### Option B — WSL

```bash
cd /mnt/f/Python/Avalanche
bash run_dev.sh
```

First fresh-browser load is still ~30s. `Ctrl+C` to stop.

> **Canvas-focus carry-over:** cubes start tumbling immediately on page load — you do NOT need to click the canvas to see them move (the wave is driven by `dt`, not keyboard). But to move the player, you still need to click the canvas first to give it keyboard focus. Same rule as Step 2.

> **Port-8000 squatter:** if `run_dev.sh` fails to start or the browser shows `ERR_EMPTY_RESPONSE`, a prior Python process is holding the port. On Windows: `netstat -ano | findstr :8000` then `taskkill /F /PID <PID>`. Re-run `run_dev.sh`.

---

## 2. What you should see

On page load, once WASM finishes loading, on a black background:

- The same **perspective grid** as Step 2 (7 × 25 = 175 tiles, front row near the bottom of the screen).
- The same **blue player cube** at `(3, 1)`.
- **Seven new cubes** at the back row (z=24), one per column, in this left-to-right order:
  1. `NORMAL` (gray)
  2. `NORMAL` (gray)
  3. `ADVANTAGE` (bright green with green edges)
  4. `FORBIDDEN` (dark purple with red edges, visibly thicker outline)
  5. `ADVANTAGE` (bright green)
  6. `NORMAL` (gray)
  7. `NORMAL` (gray)

Every **~1.2 seconds**, all 7 cubes **tumble one tile forward** in lockstep — they rotate 90° around their leading bottom edge. Between ticks you can see each cube mid-rotation (peak height ~1.4× a tile during the tumble).

After **~30 seconds** (25 ticks) every cube has rolled off the front edge and the grid is empty.

### HUD (top-left, four lines)

- `FPS: <N>` — expect 60+ on a modern desktop; 120+ on an uncapped display.
- `Polys: <N>` — rises to ~220 when all 7 cubes are live (175 tiles + ~42 cube faces + 6 player faces, minus back-face culling). Falls as cubes fall off.
- `Pos: (x, z)` — the player's grid coords (same as Step 2).
- `Cubes: <N>  Tick: 0.NN` — **new this step.**
  - `Cubes` is the live cube count. Starts at 7, decrements each time a cube rolls off.
  - `Tick` is the **fraction of the current tick interval** — climbs from 0.00 to ~1.00 over 1.2s, then resets. A useful way to eyeball the cadence.

---

## 3. Success criteria (check each)

- [ ] On page load, 7 cubes appear at the back row in the pattern above. All 7 are visually distinguishable from each other and from the platform.
- [ ] Every 1.2 seconds, all 7 cubes advance one tile forward **in unison**. None drifts out of phase.
- [ ] Between ticks, each cube visibly **tumbles** (rotates forward around its leading edge) — it does not teleport or slide.
- [ ] The FORBIDDEN cube (column 3) is distinguishable from the NORMAL cubes at every point during the tumble — the red edge + thicker outline should stay visible even mid-rotation. If it looks like "just a red wireframe" and you can't tell it's solid, flag that (it's a polish-candidate for Step 10).
- [ ] The ADVANTAGE cubes (columns 2 and 4) are obviously green — bright fill + green edges.
- [ ] `Cubes:` counter starts at 7, decrements by 1 each time a cube rolls off the front edge.
- [ ] `Tick:` climbs from 0.00 toward 1.00 over ~1.2s, then resets. The cadence feels steady — no stutter.
- [ ] After ~30 seconds, the grid is empty (`Cubes: 0`). Refresh the page to respawn the row.
- [ ] Player still moves (arrow keys / WASD) with the same feel as Step 2. `Pos:` still updates live.
- [ ] FPS stays stable during tumbling (no drops when all 7 cubes are mid-rotation).
- [ ] No Python tracebacks in the browser console (F12 → Console).

---

## 4. Intentionally inert for this step (please do NOT report as bugs)

These will be wired up in later steps. If you hit them, it's expected:

- **Standing in a cube's path does nothing.** If you park the player on a tile a cube is about to roll onto, the cube will visually pass through/over the player with no effect. **Crush detection lands in Step 5.**
- **Pressing SPACE / X / Z does nothing.** Mark / trigger / detonate are all Step 4.
- **No audio.** No tick metronome, no capture SFX. Audio is Step 10 polish.
- **Cubes disappear abruptly at the front edge.** When a cube reaches `z=0` and the next tick fires, it vanishes instead of tumbling off the edge. A smoother fall-off animation is Step 10 polish.
- **No capture, no scoring, no wave progression.** One debug row spawns on page load; when it's gone, the grid stays empty until refresh. Real wave patterns + progression are Step 9.

---

## 5. Expert Panel findings (Phase A → Phase B)

All 4 experts returned **APPROVED WITH CONCERNS** on the Phase A code. Summary of what changed in response:

| Reviewer | Finding | Resolution |
|---|---|---|
| Vision Lead | `TICK_INTERVAL=1.2s` is a provisional Stage-1 value; the real I.Q. uses a dual-variable Wait/Speed metronome that accelerates per stage | Added a TUNING comment at `constants.py:34` marking it as provisional; full per-stage tick table **deferred to Step 7** (difficulty curve) |
| Code Quality | `WaveManager.update()`'s overshoot clamp had dead code + silent truncation that broke the "cadence stays even" promise under bad dt | Replaced with an explicit assertion that the caller's DT_CLAMP contract holds; violating dt now fails loudly rather than silently desyncing cadence |
| Code Quality | `Cube` mutability vs `frozen=True` for Step 4 capture semantics | **Deferred to Step 4** (capture logic will decide identity-vs-value semantics) |
| Code Quality | No `cube_at(x, z)` spatial lookup — Steps 4-5 will need it | **Deferred to Step 4** (add it when capture semantics are defined, not speculatively) |
| UX Tester | User will try standing under a cube and be confused when nothing happens (non-bug) | Explicit "intentionally inert" callout above (§4) |
| UX Tester | HUD label `Tick:` is ambiguous ("tick number" vs "fraction") | Documented meaning in §2 above; not relabeling in code until the real HUD lands in Step 4 |
| UX Tester | Fall-off at front edge is abrupt (no tumble-off animation) | Documented in §4 above; polish in Step 10 |
| UX Tester | FORBIDDEN cube may read as "red wireframe" on dim screens | Documented as polish candidate for Step 10; please flag in Phase B if it's a real readability issue |
| Platform Engineer | Allocation churn in `get_cube_vertices` / `get_cube_faces` at scale | **Deferred to Step 5** (matters at 20+ simultaneous cubes; Step 3A is 7) |
| Platform Engineer | Frame budget at 7 cubes: ~11ms of 16.67ms WASM budget; tile projection dominates, not cubes | No action — comfortable headroom |
| Platform Engineer | Sort-key lambda vs `operator.itemgetter` micro-optimization | **Deferred to Step 8** |

Carry-forward from Step 2 (still open, not Step-3 business):
- `MOVE_COOLDOWN = 0.08s` retune (revisit Step 3+ with real crush pressure — that's Step 5, not now)
- Static perpendicular-priority in `_first_held_direction` (revisit after real gameplay pressure exists)
- Camera pitch judgment call (STEP2_REVIEW §5 item 2)

Carry-forward from Step 3 Phase B (user observation, deferred by user request):
- **Tumble animation feel** — current uniform 90°/tick tumble is mechanically correct but lacks the authentic I.Q. "heavy cube" character (slow heave → balance-point pause → accelerating thud → rest). User asked to defer to a future step. Full four-stage profile, timing budget, and implementation notes captured in `.claude/memory/feedback_tumble_feel.md`; TODO(feel) comment at `cube_data.py:52` (`_lut_sin_cos`) points at the memory file. **Natural landing:** Step 10 polish (animation feel + audio "thud" co-located). Orthogonal to TICK_INTERVAL tuning — keep in separate commits.

---

## 6. Known dev-tooling quirks (carry-over)

- Use **`http://localhost:8000`**, not `http://0.0.0.0:8000`.
- If port 8000 is stuck: Windows `netstat -ano | findstr :8000` → `taskkill /F /PID <PID>`.
- WSL2 localhost forwarding via `wslrelay.exe` works; launch in WSL, open in Windows browser.
- Hidden-tab `rAF` pause is still in effect — the wave correctly "pauses" while the tab is hidden (missed ticks, not banked ticks).

---

## 7. What to tell me after you review

Any one of:

- **"Step 3 approved, proceed to Step 4"** — I'll start Step 4 Phase A (marking + capture).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify before Step 4.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel on the fixes.
- **"I can't run it because [error]"** — paste the terminal/console output.

---

## Files changed/added in Step 3 Phase A

```
wave_manager.py    (new)     — WaveManager class; Cube dataclass; tick-driven advance; spawn_debug_row; iter_cubes.
main.py            (updated) — wired WaveManager: update each frame, _build_cube_faces renders cubes with shared tumble_progress, HUD shows cube count + tick fraction.
constants.py       (updated) — TICK_INTERVAL annotated as provisional Stage-1 value (Vision Lead finding).
docs/PROGRESS.md   (updated) — Step 3A session log; step-tracker Phase A flipped to AWAITING USER.
```

No changes to `renderer.py`, `cube_data.py`, `grid_manager.py`, or `player.py` — their existing APIs were sufficient.
