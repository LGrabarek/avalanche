"""Constants, enums, and configuration for Avalanche.

Types and values that are shared across modules live here. Everything is
compile-time constant or derived from the grid dimensions — no runtime
configuration. See `CLAUDE.md` for the coding standards this file obeys.
"""

import math
from enum import Enum, IntEnum
from typing import TypedDict

import pygame

# --- Shared type aliases ------------------------------------------------------

ColorRGB = tuple[int, int, int]


# --- Display ------------------------------------------------------------------

SCREEN_WIDTH: int = 960
SCREEN_HEIGHT: int = 640


# --- Grid ---------------------------------------------------------------------

GRID_WIDTH: int = 7      # X-axis tile count
GRID_DEPTH: int = 25     # Z-axis tile count (rows)
TILE_SIZE: float = 1.0   # World-space unit per tile


# --- Timing -------------------------------------------------------------------

# Per-stage wave tick intervals (0-based stage index).
# Index 0: 1.2 s — the single base value used by all stages.
# GameManager._cur_tick_interval applies TICK_SPEED_DECAY from this base.
STAGE_TICK_INTERVALS: list[float] = [1.2]
assert len(STAGE_TICK_INTERVALS) > 0, "STAGE_TICK_INTERVALS must not be empty"
# Applied to STAGE_TICK_INTERVALS[0] once every two stages (3, 5, 7, …).
# 0.9 = 10 % faster. Stages 1+2 share the base. Even stages (4, 6, 8, …)
# share the interval of the preceding odd stage (i // 2 integer division).
TICK_SPEED_DECAY: float = 0.9

# Per-stage avalanche tick intervals (0-based stage index).
# Both values must be > DT_CLAMP (0.1 s) — see WaveManager.update() overshoot
# assertion. Stage 1 (index 0): 0.15 s. Stage 2 (index 1): 0.12 s.
STAGE_AVALANCHE_TICK_INTERVALS: list[float] = [0.15, 0.12]
assert len(STAGE_AVALANCHE_TICK_INTERVALS) > 0, (
    "STAGE_AVALANCHE_TICK_INTERVALS must not be empty"
)

# Backward-compatible aliases: Stage-1 (index-0) values.
# TICK_INTERVAL is used by WaveManager.__init__ as its default argument.
TICK_INTERVAL: float = STAGE_TICK_INTERVALS[0]
AVALANCHE_TICK_INTERVAL: float = STAGE_AVALANCHE_TICK_INTERVALS[0]
# Turbo mode: hold KEY_TURBO (F) to tick faster during WAVE_ACTIVE. Chosen
# faster than STAGE_TICK_INTERVALS[0] (1.2 s) but slower than
# STAGE_AVALANCHE_TICK_INTERVALS[0] (0.15 s): controlled acceleration, not panic.
# GameManager.set_turbo() restores to the per-stage normal interval on release.
TURBO_TICK_INTERVAL: float = 0.25   # Seconds between cube advances in turbo mode
# Step 10A: tuned from 0.08 s to 0.12 s after user confirmation that the
# original felt too fast. 120 ms is still snappy but aligns better with
# the crush pressure of the real I.Q. (range tested: 0.10–0.18 s).
MOVE_COOLDOWN: float = 0.12   # Seconds between player moves
# Pause between wave-cleared and the next wave spawning. During this window
# the WAVE_RISING overlay shows (and PERFECT! if the wave was Perfect).
WAVE_RISING_DURATION: float = 2.0   # Seconds
# Hold before the restart prompt becomes active on the GAME_OVER / VICTORY screen.
# Prevents accidental skips when the end condition fires mid-keypress.
# During the hold the prompt is shown dimmed; it brightens when input is accepted.
END_SCREEN_HOLD: float = 2.0        # Seconds


# --- Camera -------------------------------------------------------------------
# Derived from grid dimensions so changing GRID_WIDTH/GRID_DEPTH for a future
# stage automatically reframes the view.
#
# Step 24 (A7 camera rework): raised elevation from 25° → 28° by lifting the
# camera Y from 13.0 to 15.0.  Higher elevation gives clearer row-depth cues
# (the checkerboard pattern reads more strongly) and makes the advancing wave
# look more dramatic.  Per-stage camera travel (the platform scrolls in the
# original I.Q.) is explicitly out of scope for this step.
#
# Elevation geometry (verified numerically):
#   direction = target – pos = (0, –15, 28)
#   elevation = atan2(15, 28) ≈ 28°
#   front-row vertex z=–0.5, y=0 → y_ndc ≈ –0.61  (safely above –1.0 clip)
#   back-row  vertex z=24.5, y=0 → y_ndc ≈ +0.30  (safely below +1.0 clip)
#   front-left corner x=–0.5    → x_ndc ≈ +0.24  (within ±1.0)
#   back-right corner x=6.5     → x_ndc ≈ –0.12  (within ±1.0)

_GRID_CENTER_X: float = (GRID_WIDTH - 1) * 0.5
_GRID_CENTER_Z: float = (GRID_DEPTH - 1) * 0.5   # = 12.0 for GRID_DEPTH=25
CAMERA_POS: tuple[float, float, float] = (_GRID_CENTER_X, 15.0, _GRID_CENTER_Z - 28.0)
CAMERA_TARGET: tuple[float, float, float] = (_GRID_CENTER_X, 0.0, _GRID_CENTER_Z)
CAMERA_FOV: float = 50.0     # Widened from 45° in Step 6B to keep full grid in frame
NEAR_PLANE: float = 0.1
FAR_PLANE: float = 100.0

# Step 27 — fixed-vantage follow camera used during all gameplay phases.
#
# The camera eye is FIXED in world space.  Each frame, a smoothly-lerped
# look-at target tracks the player's floor tile via exponential decay
# (CAMERA_FOLLOW_SMOOTH).  Because the eye never translates, the world
# stays spatially anchored; only the viewing direction swivels gently.
#
# Eye position:  (3.0, 7.8, 2.0)
#
#   eye.z = +2: placed two units inside the front edge, giving a 20%
#   shorter look-distance to spawn vs eye.z=−2 (dz 19.5 vs 23.5 u).
#   Shorter dz → larger horizontal swivel angle per tile of lateral
#   player movement → 20% wider perceived swivel range.
#
#   Orientation safety: eye.z = +2 would let the camera look BACKWARD
#   once the smooth target.z fell below 2.0.  CAMERA_FOLLOW_TARGET_Z_MIN
#   clamps the smooth target to ≥ 2.5, guaranteeing target.z > eye.z
#   always.  With k=2 the smooth target only reaches 2.5 after ~1.6 s
#   of the player sitting at z=0 (effectively unreachable — they're dead
#   long before then).
#
#   eye.y = 7.8 (20% shallower elevation than the previous 27°):
#     At player spawn (3.5, 0, 21.5):
#       horiz dist ≈ sqrt(0.5² + 19.5²) ≈ 19.5 u
#       elevation  = atan2(7.8, 19.5) ≈ 21.8°  (80% of previous 27.1°)
#       total dist ≈ 21.0 u
#
#   Horizontal swivel range at spawn (tile-centred, 20% wider than before):
#     left  x=0 → dx=−2.5, dz=19.5 → atan2(2.5,19.5) ≈ 7.3°
#     right x=6 → dx=+3.5, dz=19.5 → atan2(3.5,19.5) ≈ 10.2°
#     Total ≈ 17.5° vs previous 14.6° (+20%).
#
# CAMERA_FOLLOW_SMOOTH: exponential-decay coefficient (s⁻¹).
#   alpha = 1 − exp(−k·dt).  k=2 → ~21% per MOVE_COOLDOWN (0.12 s);
#   ~63% catch-up in 0.5 s; ~86% in 1 s.  Heavier weighted glide.
#
# CAMERA_FOLLOW_TARGET_Z_MIN: floor on the smooth z-target so it never
#   falls below eye.z, preserving +z look-direction at all times.
#
# CAMERA_FOLLOW_FOV: narrower than 50° overview to reduce peripheral
# distortion at close range.
CAMERA_FOLLOW_EYE: tuple[float, float, float] = (3.0, 7.8, 2.0)
CAMERA_FOLLOW_FOV: float = 42.0
CAMERA_FOLLOW_SMOOTH: float = 2.0
CAMERA_FOLLOW_TARGET_Z_MIN: float = 2.5   # eye.z (2.0) + 0.5 clearance


# --- Face shading -------------------------------------------------------------
# Per-face brightness multipliers applied in cube_data.get_cube_faces().
# Ordered to match the _CUBE_FACES tuple in cube_data.py (indices 0–5):
#   0 top (+Y)   1 bottom (-Y)   2 front (+Z, toward camera)
#   3 back (-Z)  4 side -X       5 side +X
#
# Light implied from upper-left (screen space).  Screen-left = world +X, so
# the +X face (index 5) is the lit side; -X (index 4) and back (index 3) are
# shadow.  Front (+Z, index 2) catches oblique light — same tier as lit side.
FACE_TOP_MULT: float = 1.00
FACE_RIGHT_MULT: float = 0.75   # lit side: front and screen-left (+X) face
FACE_LEFT_MULT: float = 0.55    # shadow side: back and screen-right (-X) face
FACE_BOTTOM_MULT: float = 0.40  # floor face — never visible in play
# Ordered tuple for indexed lookup by face index in cube_data.get_cube_faces().
FACE_MULTS: tuple[float, ...] = (
    FACE_TOP_MULT,     # 0: top
    FACE_BOTTOM_MULT,  # 1: bottom
    FACE_RIGHT_MULT,   # 2: front (+Z toward camera) — obliquely lit
    FACE_LEFT_MULT,    # 3: back  (-Z) — shadow
    FACE_LEFT_MULT,    # 4: side -X   — screen-right shadow face
    FACE_RIGHT_MULT,   # 5: side +X   — screen-left lit face
)
assert len(FACE_MULTS) == 6, "FACE_MULTS must have one entry per face in _CUBE_FACES"


# --- Enums --------------------------------------------------------------------

class TileState(IntEnum):
    VOID = 0
    PLATFORM = 1
    MARKED = 2
    ADVANTAGE_TRAP = 3


class CubeType(IntEnum):
    NORMAL = 0
    ADVANTAGE = 1
    FORBIDDEN = 2


class CubeBehavior(Enum):
    """Named behavior hooks referenced by CUBE_TYPES entries.

    Using an enum (instead of bare strings) makes typos fail at import time
    and gives the dispatcher in game_manager.py a closed set to switch on.
    """

    NONE = "none"
    SCORE = "score"              # Normal on_capture: award points
    PENALTY = "penalty"          # Normal on_missed: increment penalty counter
    CREATE_TRAP = "create_trap"  # Advantage on_capture: turn tile into trap
    DETONATE_3X3 = "detonate"    # Advantage trap on_detonate: 3x3 blast
    ROW_DELETE = "row_delete"    # Forbidden on_capture: delete back row


class Direction(Enum):
    """Cardinal movement directions, named from the **player's on-screen view**.

    Value tuple is `(dx, dz)` in grid coordinates. The current camera
    (`CAMERA_POS`, `CAMERA_TARGET`) renders with world +X projecting to
    screen-LEFT and world +Z projecting to screen-UP (away from the camera).
    These enum values account for that flip so that pressing LEFT on the
    keyboard visibly moves the player screen-LEFT, UP moves screen-UP
    (toward the back of the grid), etc. If the camera orientation changes,
    revisit these deltas rather than rebinding keys in `MOVEMENT_KEYS`.
    """

    LEFT = (1, 0)        # arrow LEFT / A key → world +X (screen-left)
    RIGHT = (-1, 0)      # arrow RIGHT / D key → world -X (screen-right)
    FORWARD = (0, 1)     # arrow UP / W key → world +Z (away from camera / back row)
    BACKWARD = (0, -1)   # arrow DOWN / S key → world -Z (toward camera / front row)


class GamePhase(Enum):
    TITLE = "title"
    WAVE_RISING = "wave_rising"
    WAVE_ACTIVE = "wave_active"
    WAVE_CLEARING = "wave_clearing"
    PERFECT_CHECK = "perfect_check"
    AVALANCHE = "avalanche"
    ROW_COLLAPSING = "row_collapsing"
    GAME_OVER = "game_over"
    VICTORY = "victory"
    STAGE_CLEAR = "stage_clear"  # Between-stage screen; all gameplay frozen
    MENU = "menu"           # Esc pause menu open; all gameplay frozen


# --- Registry TypedDicts ------------------------------------------------------
# Runtime palette coverage is enforced by `cube_data._build_faces` (missing keys
# raise KeyError). The TypedDicts here give us mypy-level coverage so new cube
# types can't ship with a typo'd color key.

class CubeTypeInfo(TypedDict):
    # Single base colour; face shading is derived by multiplying with FACE_MULTS
    # in cube_data.get_cube_faces() — no per-face hand-coding needed.
    base_color: ColorRGB
    edge_color: ColorRGB
    edge_width: int
    on_capture: CubeBehavior
    on_missed: CubeBehavior
    on_detonate: CubeBehavior
    capture_score: int
    chain_score: int


class TileColorSet(TypedDict):
    top: ColorRGB
    edge: ColorRGB


# --- Cube Type Registry -------------------------------------------------------
# Data-driven: each type defines colors, edge style, and behavior hooks.
# Adding a new cube type = adding an entry here.

CUBE_TYPES: dict[CubeType, CubeTypeInfo] = {
    CubeType.NORMAL: {
        "base_color": (180, 180, 180),  # mid-grey; FACE_MULTS derive all six faces
        "edge_color": (60, 60, 60),
        "edge_width": 1,
        "on_capture": CubeBehavior.SCORE,
        "on_missed": CubeBehavior.PENALTY,
        "on_detonate": CubeBehavior.SCORE,
        "capture_score": 100,
        "chain_score": 200,
    },
    CubeType.ADVANTAGE: {
        "base_color": (100, 220, 100),  # bright green; lit side ≈ (75,165,75)
        "edge_color": (0, 200, 0),      # toned down from pure (0,255,0)
        "edge_width": 1,
        "on_capture": CubeBehavior.CREATE_TRAP,
        "on_missed": CubeBehavior.PENALTY,
        "on_detonate": CubeBehavior.DETONATE_3X3,
        "capture_score": 100,
        "chain_score": 200,
    },
    CubeType.FORBIDDEN: {
        "base_color": (60, 30, 60),     # dark purple; lit side ≈ (45,22,45)
        "edge_color": (180, 0, 0),
        "edge_width": 2,
        "on_capture": CubeBehavior.ROW_DELETE,
        "on_missed": CubeBehavior.NONE,
        "on_detonate": CubeBehavior.ROW_DELETE,
        "capture_score": 0,
        "chain_score": 0,
    },
}


# --- Platform tile colors -----------------------------------------------------

TILE_COLORS: dict[TileState, TileColorSet] = {
    TileState.PLATFORM: {"top": (90, 90, 110),   "edge": (50, 50, 65)},
    TileState.MARKED:   {"top": (200, 220, 255), "edge": (120, 140, 180)},
    TileState.ADVANTAGE_TRAP: {"top": (80, 200, 80), "edge": (40, 120, 40)},
}

# B3c: Amount to add to each RGB channel on alternate PLATFORM tiles (checkerboard).
# Applied when (grid_x + grid_z) % 2 == 1. Only affects PLATFORM tiles;
# MARKED and ADVANTAGE_TRAP are already visually distinctive.
TILE_CHECKER_DELTA: int = 8

# B3e: Top-face override colour for cubes one tick from the platform's front edge.
# Saturated yellow: orthogonal to Normal (grey), Advantage (green), Forbidden
# (purple), and the player cube (blue), while matching the PERFECT! warning
# vocabulary already present in the HUD/overlay palette (255, 220, 50).
DANGER_TOP_COLOR: ColorRGB = (255, 220, 0)


# --- Player -------------------------------------------------------------------

PLAYER_HALF_EXTENT: float = 0.4    # Total edge = 0.8, slightly smaller than a tile
PLAYER_CENTER_Y: float = 0.4       # Center-Y so player sits on the platform
PLAYER_SPAWN_X: int = GRID_WIDTH // 2
# Spawn 3 rows in front of the first wave row. Clamped to 0 so a shallow
# grid degrades to front-row spawn rather than going off-map.
PLAYER_SPAWN_Z: int = max(0, GRID_DEPTH - 1 - 3)
PLAYER_COLORS: dict[str, ColorRGB] = {
    "top": (130, 200, 255),     # Brighter luminance so the player reads clearly
    "front": (80, 160, 230),    # against the bluish-gray tile top (90, 90, 110).
    "back": (50, 120, 190),     # UX panel (Step 2) flagged marginal contrast;
    "side": (50, 120, 190),     # this widens the player/platform luminance gap.
    "bottom": (30, 80, 140),
}
PLAYER_EDGE_COLOR: ColorRGB = (20, 50, 100)
# Crush: player squashes flat and turns dark red.
PLAYER_CRUSH_COLORS: dict[str, ColorRGB] = {
    "top": (200, 60, 60), "front": (160, 40, 40),
    "back": (120, 20, 20), "side": (120, 20, 20), "bottom": (80, 10, 10),
}
PLAYER_CRUSH_EDGE_COLOR: ColorRGB = (100, 0, 0)


# --- Scoring ------------------------------------------------------------------

PENALTY_THRESHOLD: int = 3       # Missed normals before row deletion
SCORE_ROW_SURVIVAL: int = 1000   # Per surviving row at stage end
PERFECT_BONUS_MAX: int = 10000


# --- I.Q. Algorithm tables (from research doc) --------------------------------

IQ_DIFFICULTY_MULTIPLIERS: list[float] = [1.00, 1.25, 1.33, 1.45, 1.50]
IQ_PERCENTAGE_MULTIPLIERS: list[float] = [
    0.00060, 0.00055, 0.00050, 0.00045, 0.00040,
    0.00035, 0.00030, 0.00025, 0.00020,
]


# --- Key bindings -------------------------------------------------------------
# Movement keys: both arrows and WASD so left-hand and right-hand users have
# equal access. All four directions accept either binding. Action keys stay
# on the right hand (space/x/z) so movement and actions don't conflict.

KEY_MARK: int = pygame.K_SPACE
KEY_TRIGGER: int = pygame.K_x
KEY_TRIGGER_ALT: int = pygame.K_RETURN
KEY_DETONATE: int = pygame.K_z
# Hold to speed up wave ticks during WAVE_ACTIVE only. Right-hand key so
# movement (WASD) and turbo can be used simultaneously.
KEY_TURBO: int = pygame.K_f

# A direction is triggered when ANY key in its tuple is held. Using
# tuple[int, ...] lets Step 2 ship with two bindings per direction without
# ballooning into per-key constants. pygame.key.get_pressed() returns a dense
# sequence, so lookup is O(1) per key.
MOVEMENT_KEYS: dict[Direction, tuple[int, ...]] = {
    Direction.LEFT:     (pygame.K_LEFT,  pygame.K_a),
    Direction.RIGHT:    (pygame.K_RIGHT, pygame.K_d),
    Direction.FORWARD:  (pygame.K_UP,    pygame.K_w),
    Direction.BACKWARD: (pygame.K_DOWN,  pygame.K_s),
}


# --- Audio -------------------------------------------------------------------

# Set to False to silence all sound effects globally. AudioSystem also
# self-disables when pygame.mixer fails to initialise (no audio device,
# headless CI, WASM format errors). This flag is the user-facing override.
SOUND_ENABLED: bool = True


# --- Sin/cos lookup table for tumble animation --------------------------------
# Pre-computed for 0..90 degrees in 32 steps to avoid per-vertex trig under
# WASM. The builder lives in a function so the loop variables don't leak into
# the module namespace (Rule 6 — narrow scope).

TUMBLE_LUT_STEPS: int = 32
# Four-phase tumble easing profile (Step 10A):
#   heave    [0, TUMBLE_HEAVE_END)          smoothstep 0°→45°, builds momentum
#   balance  [TUMBLE_HEAVE_END, TUMBLE_BALANCE_END)  holds at 45° (tipping point)
#   thud     [TUMBLE_BALANCE_END, TUMBLE_REST_FRACTION)  ease-in 45°→90°, fast fall
#   rest     [TUMBLE_REST_FRACTION, 1]      cube at rest, capture window open
# At 1.2 s per tick: 0.65 × 1.2 = 0.78 s for animation, 0.42 s rest window.
# History: rest-fraction 0.75 (Step 1) → 0.55 (Step 4B) → 0.65 (Step 10).
TUMBLE_HEAVE_END: float = 0.40      # Tick fraction where heave ends (cube at 45°)
TUMBLE_BALANCE_END: float = 0.48    # Tick fraction where balance-hold ends
TUMBLE_REST_FRACTION: float = 0.65  # Tick fraction where rest/capture window opens
# Crush fires when a tumbling cube passes its balance point (45° — the point
# of no return). TUMBLE_HEAVE_END marks exactly that moment: the heave ends
# at 45° and the balance hold begins. This fires before the rest phase
# (TUMBLE_REST_FRACTION = 65%), so the cube is never capturable before crush.
CRUSH_TUMBLE_THRESHOLD: float = TUMBLE_HEAVE_END


def _build_tumble_luts(steps: int) -> tuple[list[float], list[float]]:
    if steps <= 0:
        raise ValueError(f"steps must be positive, got {steps}")
    sin_lut: list[float] = []
    cos_lut: list[float] = []
    for i in range(steps + 1):
        angle = (i / steps) * (math.pi / 2.0)
        sin_lut.append(math.sin(angle))
        cos_lut.append(math.cos(angle))
    assert len(sin_lut) == steps + 1 and len(cos_lut) == steps + 1, (
        "LUT length must equal steps + 1"
    )
    return sin_lut, cos_lut


TUMBLE_SIN_LUT, TUMBLE_COS_LUT = _build_tumble_luts(TUMBLE_LUT_STEPS)
