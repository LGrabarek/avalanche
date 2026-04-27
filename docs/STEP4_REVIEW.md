# Step 4 — User Review (Phase B)

**What Step 4 covers:** marking a tile with SPACE, triggering with X/Enter to capture the cube resting on it, and seeing score / tile-state / capture-flash feedback. This is the first step where you actually *interact* with the wave.

**What's new vs. Step 3:** mark+trigger input, capture dispatch for all three cube types, capture-flash ring effect, `Score` + `Mark` in the HUD, bottom-left controls hint. The tumble animation, cadence, and player movement are unchanged.

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

First fresh-browser load is still ~30s. `Ctrl+C` to stop. **Click the canvas** once loaded so keyboard events reach the game.

> **Port-8000 squatter:** if `run_dev.sh` fails to start or the browser shows `ERR_EMPTY_RESPONSE`, a prior Python process is holding the port. On Windows: `netstat -ano | findstr :8000` then `taskkill /F /PID <PID>`. Re-run `run_dev.sh`.

---

## 2. What you should see

On load, identical Step 3 scene: grid + player at `(3, 1)` + 7 debug cubes at the back row tumbling forward on a 1.2s tick.

**New HUD line (5th stat-block line):** `Score: 0  Mark: ---`
**New bottom-left hint (always visible in Step 4A):** `Move: WASD / Arrows   Mark: SPACE   Trigger: X / Enter`

### New controls

| Key | Effect |
|---|---|
| SPACE | Mark the tile under the player. Replaces any previous mark. Marking a void/trap/off-grid tile is silently ignored. |
| X or Enter | Trigger. If a cube is resting on the marked tile, capture it per type (see below). Always clears the mark, whether capture succeeded or not. |

### Per-type capture behavior

| Cube type | On capture | Score delta | Tile afterward |
|---|---|---|---|
| NORMAL (gray) | Removed; scored | +100 | PLATFORM |
| ADVANTAGE (bright green) | Removed; tile becomes trap (detonate is Step 7) | 0 (points come via detonate) | ADVANTAGE_TRAP (green tile) |
| FORBIDDEN (dark / red outline) | Removed; **no score change, no visible penalty** | 0 | PLATFORM |

**Every capture (all three types) plays the same expanding white ring** (radius 6→48 px, fades over 0.4s) centered on the captured tile.

---

## 3. Success criteria (check each)

- [ ] On page load: HUD 5th line shows `Score: 0  Mark: ---`. Controls hint visible at bottom-left.
- [ ] Press SPACE while standing on a platform tile → that tile turns bluish-white (MARKED). HUD shows `Mark: (x, z)`.
- [ ] Press SPACE again on a *different* tile → the first mark clears back to platform color; new tile is marked.
- [ ] Mark a tile ahead of an incoming cube, don't move, wait for the tick to commit the cube onto the marked tile, then press X → cube vanishes, ring flash plays on that tile, `Score` reads `100` (NORMAL) or the tile turns green (ADVANTAGE) or nothing visually distinguishes it from a NORMAL capture (FORBIDDEN — see §4).
- [ ] Press X with no mark active → nothing happens visually, `Score` unchanged.
- [ ] Mark a tile but trigger *before* the cube arrives (or when no cube will arrive) → mark vanishes, no flash, `Mark: ---`.
- [ ] Mark persists across ticks — it stays blue-white while cubes tumble until you trigger it or replace it.
- [ ] Capture an ADVANTAGE cube (column 3 or 5 in the debug row) → tile turns trap-green *and stays green*. This is the trap that Step 7 will detonate.
- [ ] Capture a FORBIDDEN cube (column 4 in the debug row) → cube vanishes and ring flashes, but Score does NOT change. This is intentional (see §4).
- [ ] Player still moves with WASD/arrows; capture flashes don't interfere with movement.
- [ ] FPS stays stable (no drops) during captures, including overlapping flashes.
- [ ] No Python tracebacks in the browser console (F12 → Console).

---

## 4. Intentionally inert for this step (please do NOT report as bugs)

These behaviors are deliberate Step 4A scope limits. Each has an explicit wiring point in a later step.

- **FORBIDDEN capture looks like a successful capture** (cube vanishes, ring flashes, tile restores to PLATFORM) but score doesn't change and there's no penalty indicator. *Real row-delete side effect lands in Step 8*; *screen-edge miss-flash + penalty counter land in Step 6*. For now the cube is consumed silently. If you think you "captured" a forbidden and wonder why you didn't score, this is correct.
- **MISS is silent.** Triggering with a mark but no cube on it just wipes the mark — no flash, no sound. This matches I.Q. reference. *Audio feedback (capture tick + miss blip) lands in Step 10 polish.*
- **Standing on a cube's path does nothing.** Crush detection is still Step 5.
- **Z (detonate) does nothing yet.** The Z key isn't bound in Step 4A; the green trap tile you create sits there indefinitely until Step 7 wires detonation. You *can* see the trap — that's the point.
- **No missed-normal penalty.** Letting a gray cube roll off the front edge is currently consequence-free. *Counter + threshold land in Step 6.*
- **Controls hint never fades.** Always visible in Step 4A. *Wave-1-only gating lands in Step 10 (waves are Step 9).*
- **Flash ring color is a generic white.** Not type-tinted. *Step 10 polish — tint by captured cube's `edge_color` from `CUBE_TYPES`.*
- **Trap tile refuses a new mark** (SPACE on a green trap tile is a no-op). This is a defensible policy now; whether it's the right call long-term gets revisited with Step 7 DETONATE semantics. Flag if it feels wrong during play.

### Carry-forward from prior steps (still open, not Step-4 business)

- **Tumble animation feel (partial fix applied in Phase B)** — Phase B feedback: no rest period made captures require frame-perfect timing. Fixed: `TUMBLE_REST_FRACTION=0.75` in `constants.py` — rotation now completes at 75% of the tick, cube holds at rest for the remaining 25% (~0.3s at 1.2s tick). Full heave/balance/thud easing still deferred to Step 10 polish. See `.claude/memory/feedback_tumble_feel.md`; TODO(feel) at `cube_data.py:52`.
- **`MOVE_COOLDOWN = 0.08s`** — user-flagged as faster than original. Retune in Step 10 polish.
- **Static perpendicular-priority in `_first_held_direction`** — revisit after real gameplay pressure.
- **Camera pitch judgment call** (STEP2_REVIEW §5 item 2).

---

## 5. Expert Panel findings (Phase A → Phase B)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED WITH CONCERNS | Mark-ahead-of-cube: player marks a tile a cube is animating toward, hits TRIGGER at tumble_progress=0.9 → MISS (cube not committed yet). Faithful but no feedback cue. | Flagged for Step 10 audio-tick polish; track in this review doc so Phase B can sanity-check if the timing is frustrating. |
| Vision Lead | | Trap tile refuses marks — may conflict with Step 7 DETONATE semantics. | **Deferred to Step 7** (re-evaluate when DETONATE wires). |
| Vision Lead | | Flash color is generic (not type-tinted). | **Deferred to Step 10** (polish). |
| Vision Lead | | `TriggerOutcome` is discarded at the call site (no audio cue). | **Deferred to Step 10** (audio dispatch). |
| Code Quality | APPROVED WITH CONCERNS | `_dispatch_capture` relied on `clear_mark`'s internal "skip if no longer MARKED" guard — a non-obvious cross-module invariant. | **Fixed:** `on_trigger` now calls `clear_mark` *before* dispatch; CREATE_TRAP writes ADVANTAGE_TRAP onto a clean PLATFORM tile. Comment at `game_manager.py:110-117` records the reasoning. |
| Code Quality | | `TriggerOutcome` docstring claimed an "import cycle with constants.py" that doesn't actually exist. | **Fixed:** docstring rewritten to cite the real rationale (scope + no current need for Enum). |
| Code Quality | | `FlashEffects.update` rebuilt the list every frame even with zero flashes. | **Fixed:** empty-list fast-path at `effects.py:100-102`. Platform Engineer also flagged this as a nit. |
| Code Quality | | `try_mark` silent no-op on `ADVANTAGE_TRAP` is under-specified (no audio rejection chirp). | **Deferred to Step 10** (audio dispatch will need to distinguish rejection from success). |
| Code Quality | | `cube_at` continues scanning past a match to check one-per-tile invariant. | No action — O(n) on ≤175 entries, fired per keypress, zero budget impact. Flagged for awareness if reused inside `_advance_tick`. |
| UX Tester | APPROVED WITH CONCERNS | FORBIDDEN capture is visually indistinguishable from a successful capture. | Called out in §4 above. User reviewer: please test a FORBIDDEN capture and confirm the no-feedback behavior is acceptable as a Step-4A stopgap. |
| UX Tester | | MISS is silent — no audio/visual signal that the mark was wiped without a capture. | Called out in §4 above. Reference-faithful to I.Q. Audio cue lands Step 10. |
| UX Tester | | Controls-hint text contrast drops where the text overlaps front-row tiles (`(140,140,160)` on `(90,90,110)`). | Flag in Phase B if readability is a problem; simple fix (brighter color / backdrop strip) lands Step 10. |
| UX Tester | | Mark visibility, Score-line discoverability, Mark-indicator state change all read well. | No action — confirmation of good design. |
| Platform | APPROVED | FlashEffects update/draw, HUD font renders, cube_at scan, project_vertex per flash all comfortably inside the WASM frame budget (≤32 flashes, 6 font.renders, bounded event drain). | No action — nits already addressed by the empty-list fast-path above. Font-render caching is a Step 10 polish candidate. |
| Platform | | `Hud._draw_stat_block` re-renders 5 font surfaces every frame (no cache). | **Deferred to Step 10** (font-cache polish). |

**Carry-forward panel deferrals tracked for their target step:**
- Step 7 — Trap-tile-refuses-mark policy revisit; DETONATE (Z) wiring.
- Step 8 — FORBIDDEN full row-delete side effect.
- Step 10 — Flash color type-tinting; audio cue dispatch consuming `TriggerOutcome`; font-render caching in HUD; controls-hint fade after wave 1; `MOVE_COOLDOWN` retune.

---

## 6. Known dev-tooling quirks (carry-over)

- Use **`http://localhost:8000`**, not `http://0.0.0.0:8000`.
- If port 8000 is stuck: Windows `netstat -ano | findstr :8000` → `taskkill /F /PID <PID>`.
- WSL2 localhost forwarding via `wslrelay.exe` works; launch in WSL, open in Windows browser.
- Hidden-tab `rAF` pause is still in effect — the wave correctly "pauses" while the tab is hidden.

---

## 7. What to tell me after you review

Any one of:

- **"Step 4 approved, proceed to Step 5"** — I'll start Step 5 Phase A (crush detection + avalanche).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify before Step 5.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel on the fixes.
- **"I can't run it because [error]"** — paste the terminal/console output.

---

## Files changed/added in Step 4 Phase A

```
game_manager.py    (new)     — GameManager, TriggerOutcome, try_mark, on_trigger, _dispatch_capture via CubeBehavior.
effects.py         (new)     — FlashEffects manager, _Flash dataclass, expanding ring overlay.
hud.py             (new)     — Hud class extracted from main.py; 5-line stat block + controls hint.
wave_manager.py    (updated) — cube_at(x, z); remove_cube(cube); one-cube-per-tile assertion.
main.py            (updated) — KEYDOWN dispatch for SPACE/X/ENTER; wires FlashEffects + GameManager + Hud; effects.update + effects.draw per frame.
docs/PROGRESS.md   (updated) — Step 3 APPROVED entry; Step 4A session log.
```

No changes to `constants.py`, `renderer.py`, `cube_data.py`, `grid_manager.py`, or `player.py`.
