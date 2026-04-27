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

AVALANCHE_TICK_INTERVAL: float = 0.15  # Seconds between cube advances during avalanche.
# Must be > DT_CLAMP (0.1) so the overshoot assertion in WaveManager.update()
# is never violated on a clamped tab-switch frame.

# TICK_INTERVAL: provisional Stage-1 value. I.Q.'s original uses a dual-
# variable Wait/Speed metronome that accelerates per stage; a full per-stage
# tick table lands in Step 7 when the difficulty curve is calibrated. Values
# in the 0.8–1.2s range are plausible for Stage 1; 1.2s errs toward slow
# so Step 3A's visual verification is easy to eyeball.
TICK_INTERVAL: float = 1.2    # Seconds between cube advances
# Step 10A: tuned from 0.08 s to 0.12 s after user confirmation that the
# original felt too fast. 120 ms is still snappy but aligns better with
# the crush pressure of the real I.Q. (range tested: 0.10–0.18 s).
MOVE_COOLDOWN: float = 0.12   # Seconds between player moves
# Pause between wave-cleared and the next wave spawning. During this window
# the WAVE_RISING overlay shows (and PERFECT! if the wave was Perfect).
WAVE_RISING_DURATION: float = 2.0   # Seconds


# --- Camera -------------------------------------------------------------------
# Derived from grid dimensions so changing GRID_WIDTH/GRID_DEPTH for a future
# stage automatically reframes the view.
#
# Step 6B values: elevation reduced from ~45° to ~23° (≈20° offset as requested)
# so the full grid — including the front row at z=0 — is visible in the 960×640
# viewport.  The camera sits above and in front of the grid, targeting the
# exact centre of the grid in both X and Z.
#
# Elevation geometry:
#   direction = target – pos = (0, –12, 28)
#   elevation = atan2(12, 28) ≈ 23° ≈ (original 45°) – 22°
#   front-row vertex at z=–0.5 projects to y_ndc ≈ –0.84 (clearly above –1.0 clip)
#   back-row vertex at z=24.5 projects to y_ndc ≈ +0.41 (well within top clip)
#
# TODO(camera): camera positioning, angles, and per-stage travel (the platform
# scrolls under the player in the original I.Q.) need a full rework in a future
# stage.  The values here are provisional for Steps 6–9 and should be revisited
# alongside wave-progression work (Step 9) and visual polish (Step 10).

_GRID_CENTER_X: float = (GRID_WIDTH - 1) * 0.5
_GRID_CENTER_Z: float = (GRID_DEPTH - 1) * 0.5   # = 12.0 for GRID_DEPTH=25
CAMERA_POS: tuple[float, float, float] = (_GRID_CENTER_X, 12.0, _GRID_CENTER_Z - 28.0)
CAMERA_TARGET: tuple[float, float, float] = (_GRID_CENTER_X, 0.0, _GRID_CENTER_Z)
CAMERA_FOV: float = 50.0     # Widened from 45° to keep full grid in frame at lower elevation
NEAR_PLANE: float = 0.1
FAR_PLANE: float = 100.0


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


# --- Registry TypedDicts ------------------------------------------------------
# Runtime palette coverage is enforced by `cube_data._build_faces` (missing keys
# raise KeyError). The TypedDicts here give us mypy-level coverage so new cube
# types can't ship with a typo'd color key.

class CubeTypeInfo(TypedDict):
    # `colors` is typed as plain dict[str, ColorRGB] rather than a nested
    # TypedDict because _build_faces indexes it with a runtime-computed key
    # from _CUBE_FACES, which TypedDict literal-key lookup does not support.
    colors: dict[str, ColorRGB]
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
        "colors": {
            "top": (180, 180, 180),
            "front": (140, 140, 140),
            "back": (100, 100, 100),
            "side": (100, 100, 100),
            "bottom": (80, 80, 80),
        },
        "edge_color": (60, 60, 60),
        "edge_width": 1,
        "on_capture": CubeBehavior.SCORE,
        "on_missed": CubeBehavior.PENALTY,
        "on_detonate": CubeBehavior.SCORE,
        "capture_score": 100,
        "chain_score": 200,
    },
    CubeType.ADVANTAGE: {
        "colors": {
            "top": (100, 220, 100),
            "front": (60, 180, 60),
            "back": (30, 140, 30),
            "side": (30, 140, 30),
            "bottom": (20, 90, 20),
        },
        "edge_color": (0, 255, 0),
        "edge_width": 1,
        "on_capture": CubeBehavior.CREATE_TRAP,
        "on_missed": CubeBehavior.PENALTY,
        "on_detonate": CubeBehavior.DETONATE_3X3,
        "capture_score": 100,
        "chain_score": 200,
    },
    CubeType.FORBIDDEN: {
        "colors": {
            "top": (60, 30, 60),
            "front": (40, 20, 40),
            "back": (25, 12, 25),
            "side": (25, 12, 25),
            "bottom": (15, 8, 15),
        },
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
