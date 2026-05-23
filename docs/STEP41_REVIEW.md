# Step 41 Review — V2: Animated Player Character

**Status:** APPROVED 2026-05-21
**Date:** 2026-05-20

---

## What changed

### `player.py`

| Addition | Detail |
|----------|--------|
| `_step_parity: bool = False` | New field; flips on every successful move. |
| `walk_progress` property | `self._cooldown / MOVE_COOLDOWN` — 1.0 just after a step, decays to 0.0 at idle. Drives leg-swing amplitude. |
| `step_parity` property | Returns `self._step_parity`. Drives which leg leads each step. |
| `try_move` update | `self._step_parity = not self._step_parity` on successful move (before the invariant assert). |
| `reset()` update | `self._step_parity = False` alongside the existing cooldown zero. |

No changes to the movement or cooldown logic itself.

### `cube_data.py`

New section at end of file: character geometry constants, three helpers, and one public function.

**Body dimensions (world units, floor at y = 0):**

| Part | Dimensions | Centre y | y range |
|------|-----------|----------|---------|
| Head | 0.22 × 0.22 × 0.22 | 0.77 | 0.66 … 0.88 |
| Torso | 0.28w × 0.30h × 0.20d | 0.51 | 0.36 … 0.66 |
| Legs (×2) | 0.10w × 0.36h × 0.14d, ±0.09 from tile centre | hip 0.36 | 0.00 … 0.36 |

Total character height: **0.88 units** (game cubes are 1.0). Parts share colours from `PLAYER_COLORS` with per-part brightness multipliers (head 100%, torso 85%, legs 70%).

**Helpers:**

| Function | Purpose |
|----------|---------|
| `_tinted(colors, m)` | Scales a face-direction color dict by multiplier m. Called 4× per frame. |
| `_char_box_verts(cx, cy, cz, hw, hh, hd, scale_y)` | 8 vertices for a y-scaled axis-aligned box in `_CUBE_VERTS` order. `scale_y` uniformly applies the crush-squash. |
| `_char_leg_verts(leg_x, cz, swing_z, scale_y)` | 8 vertices for one sheared leg: hip top anchored at cz ± hd; foot shifts by swing_z in z. |

**`get_player_character_faces(grid_x, grid_z, walk_progress, step_parity, is_crushed)`:**

- `scale_y = 0.15` (crushed) or `1.0` (normal) — applied to all y-coordinates
- `t = max(0.0, sin(π × walk_progress))` — half-sine clamped to ≥ 0 (guards float sign-flip at sin(π))
- **Y-axis animation (primary visible axis):**
  - `raw_lift = 0.18 × t` — foot Y-rise for the leading leg (0 when crushed)
  - `y_bob   = 0.08 × t` — whole-body Y-rise applied to head_cy, torso_cy, leg_hip_y (0 when crushed)
- **Z-axis swing (minor depth cue only):** `raw_swing = 0.06 × t`
- Leading leg (per `step_parity`) gets `lift = raw_lift`; trailing leg stays planted (`lift = 0`)
- Returns exactly **24 FaceDescriptors** (4 parts × 6 faces); asserted at return

**Animation fix note:** The original implementation used Z-axis swing (0.12 wu). At the follow-camera angle (looking in +Z at 21.8° elevation) this projected to only ~1.7 screen pixels — imperceptible. Switching to Y-axis gives ~42 px/wu: foot lift = ~7.6 px, body bob = ~3.4 px, total ~11 px of visible motion per step.

### `main.py`

- `_build_player_faces` signature simplified to `(renderer, Player)` — no `visual` parameter
- Calls `get_player_character_faces(px, pz, player.walk_progress, player.step_parity, player.is_crushed)` directly
- `player_visual = PlayerVisual.CRUSHED if ...` variable removed from render loop
- Imports: removed `PlayerVisual`, `get_player_faces`, `get_player_vertices`; added `get_player_character_faces`
- Shadow (`_draw_player_shadow`) unchanged — still based on `PLAYER_HALF_EXTENT` at y=0

---

## Animation design

**walk_progress = `_cooldown / MOVE_COOLDOWN`**

- Immediately after a step: `_cooldown = MOVE_COOLDOWN` → `walk_progress = 1.0`
- Mid-cooldown: `walk_progress = 0.5` → `t = sin(π × 0.5) = 1.0` → max animation
- At rest: `_cooldown = 0` → `walk_progress = 0.0` → `t = 0` → character fully still

`t = max(0.0, sin(π × walk_progress))` — the clamp guards against IEEE 754's non-zero result for `sin(π)` flipping the sign of lift_y.

**Y-axis animation (primary visible axis ~42 px/wu at game distance):**
- Leading leg foot rises `0.18 × t` world-units above the floor
- Whole body (head, torso, hip joints) rises `0.08 × t` world-units — the body bob
- Combined peak screen displacement: ~7.6 + ~3.4 = ~11 screen pixels
- Trailing leg stays planted (lift = 0); next step they swap via `step_parity`

**Z-axis swing (minor depth cue ~0.85 px at game distance):**
- Foot translates `0.06 × t` world-units in Z — retained for physical gesture but imperceptible

Legs and body always return to neutral when the player is stationary.

**Crushed state:** All body parts flatten to 13% of normal height (0.88 → 0.12 world units) and switch to `PLAYER_CRUSH_COLORS` (dark red). Foot-lift and body-bob are both zeroed (`raw_lift = y_bob = 0.0`).

---

## Performance

| Item | Count/frame |
|------|------------|
| New `project_face` calls (player) | 24 (was 6, +18) |
| `_tinted()` calls | 4 × 5-item dict comprehension |
| `math.sin` calls | 1 |
| Face-list sort delta | +18 faces over ~300 baseline (~6%) |

No new allocations beyond FaceDescriptor tuples. All operations are pure Python arithmetic — WASM-compatible.

---

## Panel findings

| Reviewer | Verdict | Finding |
|----------|---------|---------|
| Vision Lead | APPROVED | Proportions faithful to I.Q. PS1 aesthetic; 0.88-unit height preserves cube-threat dynamic; half-sine waveform is correct for a foot-plants-and-pushes-off stride; step_parity handles all directions correctly. Advisory: verify 70% leg brightness doesn't blend against MARKED tiles (200, 220, 255) in-game. |
| Code Quality | APPROVED | All 10 Power-of-Ten rules satisfied; `_char_leg_verts` shear produces planar quads — back-face culling cross-product works correctly; walk_progress is always in [0,1] by construction; step_parity is reset in all the right places; face count invariant (24) properly enforced. Post-loop assert in `_build_player_faces` correctly uses `<= 24` (back-face culling can legitimately reduce the count below 24). |
| UX Tester | APPROVED* | *Reviewed via design spec (changes not yet committed). In-game verification items: (1) head reads clearly at camera distance (~21 world units); (2) 70% legs don't merge with tile surface at y=0; (3) crush-flat clearly reads as danger, not as character disappearing. |
| Platform Engineer | APPROVED | +6% face count and sort work — well within budget under WASM. WASM-compatible. One advisory: character vertices lack the floor-invariant assert used by game cubes — harmless by construction (foot is hard-coded at y=0, shear is z-only). |

### Animation fix panel (2026-05-20 — after user reported invisible animation)

| Reviewer | Verdict | Finding |
|----------|---------|---------|
| Vision Lead | APPROVED | 0.18 wu foot lift = ~20% of leg length — within natural stride range (15–25%). 0.08 wu body bob is correct: ~half the foot lift, matching weight-transfer propagation without reading as floating. Leading-leg-only lift is accurate bipedal gait. 0.04 wu clearance below cube tops (0.96 vs 1.0) is safe. No advisory concerns. |
| Code Quality | APPROVED | Both checks in `_char_leg_verts` are meaningful (scale_y guards inversion, lift_y < hy guards foot-above-hip invariant). `_append_part_faces` qualifies for the 5-line Rule 5 exemption and also earns its assert via Rule 3. `get_player_character_faces` body is 49 executable lines (≤ 50 ✓). `t = max(0.0, ...)` is necessary and correctly prevents the IEEE 754 sign-flip at sin(π) from triggering the lift_y assert. mypy --strict passes on all 15 files. |
| UX Tester | APPROVED | 7.6 px foot lift clearly clears the perceptual threshold (~3–5 px). 3.4 px body bob ties the silhouette into the rhythm without being distracting. "One leg lifts, one stays planted" reads as a walk, not a limp. 3.4 px bob is below the distraction threshold (~5+ px) for tense gameplay. Verify: leg swap alternates on consecutive steps; stationary character has zero residual bob. |
| Platform Engineer | APPROVED | `max()` and 3 additions: negligible. `_append_part_faces` (4×, 6-item loop) = ~3µs total. Two asserts per frame in `_char_leg_verts`: unmeasurable. No new imports, no WASM-incompatible calls, no unbounded growth. |

---

## How to test

### Basic character appearance

1. `python main.py` — start a game. The player should appear as a small blue humanoid: a square head, boxy torso, and two short legs. It should be clearly shorter than the approaching game cubes.

### Walking animation

1. Hold an arrow key. The legs should visibly swing forward and back as the player moves.
2. Release the key. The legs should return to a neutral stance (feet together below the torso) within one step.
3. Hold TURBO (Shift) and move. The legs should swing at the same per-step amplitude but at a faster pace (cooldown halved).

### Leg alternation

1. Tap the forward key repeatedly. The left and right legs should take turns leading on consecutive steps.

### Crushed / Avalanche state

1. Let a cube land on the player. The character should squash flat into the floor and turn dark red, matching the previous cube crush visual.
2. When the next wave starts (uncrush), the character should return to full height and blue colour.

### Shadow

1. The dark ellipse shadow beneath the player should remain correctly positioned under the character's tile centre throughout all movement.

### Overview camera (TITLE, GAME_OVER, VICTORY)

1. Reach a non-gameplay screen. No crash expected; character may be off-screen or partially visible — no artefacts.

---

## Files changed

- `player.py` (`_step_parity`, `walk_progress`, `step_parity`, `reset`, `try_move`)
- `cube_data.py` (`_tinted`, `_char_box_verts`, `_char_leg_verts`, `_append_part_faces`, `get_player_character_faces`)
  - Animation fix: switched leg animation from Z-axis swing → Y-axis foot-lift + body bob
  - `_CHAR_LEG_SWING` reduced 0.12 → 0.06; added `_CHAR_LEG_LIFT_Y = 0.18`, `_CHAR_BODY_BOB = 0.08`
  - `_char_leg_verts` gains `lift_y` and `hip_y` parameters; added `_append_part_faces` helper
- `main.py` (`_build_player_faces`, imports, render loop)
