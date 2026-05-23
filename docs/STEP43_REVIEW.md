# Step 43 Review — Row Cap Removed; Kneel on Mark; Arm Raise on Detonate

**Status:** APPROVED 2026-05-21
**Date:** 2026-05-21

---

## What changed

### `grid_manager.py`

| Change | Detail |
|--------|--------|
| `_initial_depth: int` field | Stored in `__init__`; used by `reset()` and `resize()` to discard Perfect-wave growth |
| `restore_front_row()` — full grid branch | When `front_edge_z == 0` (grid intact), appends `_width` new PLATFORM tiles and increments `_depth`. Previously returned `False`. |
| `reset()` | Now resets `self._depth = self._initial_depth` before rebuilding tiles |
| `resize()` | Now resets `self._depth = self._initial_depth` before rebuilding tiles |

Waves are unaffected: `_compute_wave_z_starts` uses the hardcoded `GRID_DEPTH − 1 = 59` as the back wall. Extra rows live at z ≥ 60, behind the wave stack.

### `cube_data.py`

| Addition | Detail |
|----------|--------|
| `_CHAR_KNEEL_DROP = 0.20` | Pelvis + body drop when kneeling (head, torso, hip joints all shift down by this amount) |
| `_CHAR_KNEEL_HIP_Y = 0.20` | Kneeling right-leg top y — represents the compressed shin with knee near floor |
| `_append_arm_faces` signature | `arm_cy: float` → `l_arm_cy: float, r_arm_cy: float` (separate per-arm centre y) |
| `get_player_character_faces` | Two new optional parameters: `is_marking: bool = False`, `is_detonating: bool = False` |

**Kneel pose** (`is_marking=True`, not crushed):
- Walk animation zeroed: no swing, lift, bob, or arm swing
- `head_cy = 0.77 − 0.20 = 0.57` (head spans y = 0.46…0.68)
- `torso_cy = 0.51 − 0.20 = 0.31` (torso spans y = 0.16…0.46)
- Left leg: hip_y = 0.36 − 0.20 = 0.16 (standing leg, pelvis-down)
- Right leg: hip_y = 0.20 (kneeling shin stub, knee near floor)
- Body drop: ~8.4 screen pixels — clearly above the ~3–5 px perceptibility threshold

**Raised arm** (`is_detonating=True`, not crushed):
- Right arm centre y: normal hang = 0.61 − 0.09 = 0.52 → raised = 0.61 + 0.09 = 0.70
- Arm spans y = 0.61…0.79 (raised above shoulder, slight overlap with lower head)
- Left arm unchanged

### `main.py`

| Change | Detail |
|--------|--------|
| `DETONATE_FLASH_DUR = 0.4` | Seconds the right arm stays raised after detonating |
| `_drain_events` return type | `tuple[bool, bool, int]` → `tuple[bool, bool, int, bool]` (adds `det_fired`) |
| `det_fired: bool` | Set True on KEY_DETONATE press within `_drain_events` |
| `detonate_flash: float` | Timer in main loop; reset to `DETONATE_FLASH_DUR` on `det_fired`, decays by dt |
| `is_marking: bool` | `bool(held_keys[KEY_MARK])` — set each frame inside `not frozen` block |
| `_build_player_faces` | Gains `is_marking: bool` and `is_detonating: bool` params; forwards both to `get_player_character_faces` |

---

## Expert panel findings

| Reviewer | Verdict | Finding |
|----------|---------|---------|
| Vision Lead | APPROVED (post-fix) | Original `_CHAR_KNEEL_DROP=0.12` was sub-perceptible (~5 px). Increased to 0.20 (~8.4 px). `_CHAR_KNEEL_HIP_Y=0.12` read as leg vanishing; increased to 0.20. Raised arm overlap (0.13 wu head overlap) acceptable at PS1 fidelity. |
| Code Quality | APPROVED | All 10 rules satisfied. `extend()` not inside a loop — Rule 3 not triggered. `lift_y < hy` asserts hold for all kneel values. `_drain_events` 48 exec lines; `get_player_character_faces` 49 exec lines (both ≤ 50). |
| UX Tester | APPROVED | Kneel on held SPACE correctly signals "marking mode" (hold-to-aim idiom). Walk zeroed during kneel eliminates walk+kneel conflict. Arm raise 0.4 s well-calibrated — noticeable but snappy. Row counter above 60 is expected, rewarding, incentivises skill. |
| Platform Engineer | APPROVED | Dynamic `_depth` growth safe — all indexing uses `self._depth` at call time, no cached values. `_compute_wave_z_starts` confirmed hardcoded to `GRID_DEPTH-1=59`. Max list growth: 40 waves × 11 = 440 extra tiles (trivial). WASM-safe. |

---

## How to test

### Row cap removal (Perfect wave)
1. Play normally and achieve a Perfect wave (capture all Normal + Advantage, let all Forbidden pass, zero misses).
2. After the first clean-grid Perfect, the "Rows" counter in the HUD and the Stage Clear stats should show 61 (or higher after multiple Perfect waves on a full grid).
3. The `+1` floating label should still appear.

### Character kneels when marking (SPACE held)
1. Hold SPACE for 1–2 seconds. The character should visibly lower and adopt a crouching right-knee-down pose — body drops ~8 screen pixels, right leg appears compressed to about half height.
2. Release SPACE. The character immediately returns to standing/idle height.
3. While holding SPACE and moving (arrow keys), the character should remain in the kneel pose (walk animation suppressed).

### Raised arm when detonating (Z key)
1. Place a marker on an Advantage tile to create a trap, then press Z (detonate).
2. The character's right arm should visibly raise above the shoulder for about 0.4 seconds, then return to normal hanging position.
3. The left arm should not change.
4. Press Z without an active Advantage trap (no-op detonation). The arm raise should still appear.

### Facing direction (carry-over from Step 42)
1. Press the DOWN arrow (move toward camera). The lighter face on the character's head should now face the camera (light face visible).
2. Press UP (move away). The lighter face should face the wave direction (not camera-visible — character shows its back).

### Row counter consistency
1. At Stage Clear screen: "Rows gained" should increment by 1 for each Perfect wave.
2. "Rows surviving" can exceed 60 after multiple Perfect waves.

---

## Files changed

- `grid_manager.py` (`_initial_depth`, `restore_front_row`, `reset`, `resize`)
- `cube_data.py` (`_CHAR_KNEEL_DROP`, `_CHAR_KNEEL_HIP_Y`, `_append_arm_faces`, `get_player_character_faces`)
- `main.py` (`DETONATE_FLASH_DUR`, `_drain_events`, `_build_player_faces`, main loop state)
