"""Cube and tile geometry definitions, tumble rotation math.

All geometry is defined in world-space coordinates.
Grid convention: X = columns (0..GRID_WIDTH-1), Z = rows (0 = front/camera-side,
GRID_DEPTH-1 = back). Cubes advance from high Z toward low Z.
Y = up. Tile surface is at Y=0. Cube centers rest at Y=0.5.
"""

import math

from constants import (
    CUBE_TYPES,
    FACE_MULTS,
    PLAYER_CENTER_Y,
    PLAYER_COLORS,
    PLAYER_CRUSH_COLORS,
    PLAYER_CRUSH_EDGE_COLOR,
    PLAYER_EDGE_COLOR,
    PLAYER_HALF_EXTENT,
    TABLE_DEPTH,
    TABLE_SIDE_COLOR,
    TILE_CHECKER_DELTA,
    TILE_COLORS,
    TUMBLE_BALANCE_END,
    TUMBLE_COS_LUT,
    TUMBLE_HEAVE_END,
    TUMBLE_LUT_STEPS,
    TUMBLE_REST_FRACTION,
    TUMBLE_SIN_LUT,
    ColorRGB,
    CubeType,
    Direction,
    TileState,
)
from renderer import FaceDescriptor, TriFaceDescriptor, Vec3

# --- Canonical unit cube ------------------------------------------------------
# 8 vertices of a unit cube centered at origin, half-extent 0.5.

_CUBE_VERTS: tuple[Vec3, ...] = (
    (-0.5, -0.5, -0.5),  # 0: bottom-left-back
    ( 0.5, -0.5, -0.5),  # 1: bottom-right-back
    ( 0.5,  0.5, -0.5),  # 2: top-right-back
    (-0.5,  0.5, -0.5),  # 3: top-left-back
    (-0.5, -0.5,  0.5),  # 4: bottom-left-front
    ( 0.5, -0.5,  0.5),  # 5: bottom-right-front
    ( 0.5,  0.5,  0.5),  # 6: top-right-front
    (-0.5,  0.5,  0.5),  # 7: top-left-front
)

# Face definitions: (vertex indices, face_direction). face_direction is the
# direction label used by _build_faces (player path); get_cube_faces (game cube
# path) uses the face INDEX directly with FACE_MULTS and ignores the label.
_CubeFaceDef = tuple[tuple[int, int, int, int], str]
_CUBE_FACES: tuple[_CubeFaceDef, ...] = (
    ((3, 2, 6, 7), "top"),     # +Y
    ((0, 1, 5, 4), "bottom"),  # -Y
    ((4, 5, 6, 7), "front"),   # +Z  (toward camera)
    ((1, 0, 3, 2), "back"),    # -Z
    ((0, 4, 7, 3), "side"),    # -X  (left)
    ((5, 1, 2, 6), "side"),    # +X  (right)
)


def _lut_sin_cos(progress: float) -> tuple[float, float]:
    """Look up sin/cos from the pre-computed quarter-circle LUT, interpolating.

    `progress` is the raw tick fraction [0, 1]. Four-phase easing maps it to
    a rotation fraction `rot` in [0, 1] before LUT sampling (Step 10A):

      heave    [0, TUMBLE_HEAVE_END)          smoothstep 0°→45° (builds momentum)
      balance  [TUMBLE_HEAVE_END, TUMBLE_BALANCE_END)  holds at 45° (tipping point)
      thud     [TUMBLE_BALANCE_END, TUMBLE_REST_FRACTION)  ease-in 45°→90° (fast fall)
      rest     [TUMBLE_REST_FRACTION, 1]      rot = 1.0 (capture window)

    Returns (sin θ, cos θ) for θ in [0°, 90°]; both values live in [0, 1].
    """
    t = max(0.0, min(1.0, progress))
    if t >= TUMBLE_REST_FRACTION:
        # Rest phase: cube has landed; return full 90° position.
        return TUMBLE_SIN_LUT[TUMBLE_LUT_STEPS], TUMBLE_COS_LUT[TUMBLE_LUT_STEPS]
    if t < TUMBLE_HEAVE_END:
        # Heave: smoothstep S(x)=3x²-2x³ from 0 to 0.5 (0°→45°).
        tn = t / TUMBLE_HEAVE_END
        rot = 0.5 * tn * tn * (3.0 - 2.0 * tn)
    elif t < TUMBLE_BALANCE_END:
        # Balance hold: cube pauses at exactly 45°.
        rot = 0.5
    else:
        # Thud: quadratic ease-in from 45° to 90°.
        span = TUMBLE_REST_FRACTION - TUMBLE_BALANCE_END
        tn = (t - TUMBLE_BALANCE_END) / span
        rot = 0.5 + 0.5 * tn * tn
    idx_f = rot * TUMBLE_LUT_STEPS
    idx = int(idx_f)
    if idx >= TUMBLE_LUT_STEPS:
        return TUMBLE_SIN_LUT[TUMBLE_LUT_STEPS], TUMBLE_COS_LUT[TUMBLE_LUT_STEPS]
    frac = idx_f - idx
    sin_val = TUMBLE_SIN_LUT[idx] + frac * (TUMBLE_SIN_LUT[idx + 1] - TUMBLE_SIN_LUT[idx])
    cos_val = TUMBLE_COS_LUT[idx] + frac * (TUMBLE_COS_LUT[idx + 1] - TUMBLE_COS_LUT[idx])
    # Quarter-circle invariant: sin and cos both live in [0, 1] for t in [0, 1].
    assert 0.0 <= sin_val <= 1.0 and 0.0 <= cos_val <= 1.0, (
        f"LUT returned out-of-range sin/cos: {sin_val=}, {cos_val=}"
    )
    return sin_val, cos_val


def get_cube_vertices(grid_x: int, grid_z: int, tumble_progress: float = 0.0) -> tuple[Vec3, ...]:
    """Get 8 world-space vertices for a cube at grid position (grid_x, grid_z).

    `tumble_progress`: 0.0 = at rest at current position,
                       1.0 = completed tumble to next position (grid_z - 1).
    Cubes advance in the -Z direction (toward camera/front edge).

    The leading (low-Z) bottom edge is the pivot. At progress=1.0 the cube has
    rotated -90 degrees around +X (right-hand rule: +Y rotates toward -Z),
    landing exactly on the next tile forward with y in [0, 1].
    """
    cx = float(grid_x)
    cz = float(grid_z)

    if tumble_progress <= 0.0:
        rest_verts: tuple[Vec3, ...] = tuple(
            (cx + vx, 0.5 + vy, cz + vz) for vx, vy, vz in _CUBE_VERTS
        )
        _assert_cube_invariants(rest_verts)
        return rest_verts

    # Tumbling: rotate around the leading (low-Z) bottom edge.
    # Pivot is at world (cx, 0, cz-0.5). The rotation is negative around +X so
    # the trailing bottom (y=0, z_rel=+1) sweeps UP AND FORWARD to land at the
    # new back-top position, rolling the cube one tile in -Z.
    sin_t, cos_t = _lut_sin_cos(tumble_progress)
    tumbled_verts: tuple[Vec3, ...] = tuple(
        _tumble_vertex(vx, vy, vz, cx, cz, sin_t, cos_t) for vx, vy, vz in _CUBE_VERTS
    )
    _assert_cube_invariants(tumbled_verts)
    return tumbled_verts


def _tumble_vertex(
    vx: float, vy: float, vz: float,
    cx: float, cz: float,
    sin_t: float, cos_t: float,
) -> Vec3:
    """Apply the pivot rotation for one cube vertex.

    Extracted from `get_cube_vertices` so both branches share a single
    transform and the outer function stays short and readable.
    """
    # Pivot-relative coords: y = 0.5 + vy (range 0..1), z = 0.5 + vz (range 0..1).
    ry = 0.5 + vy
    rz = 0.5 + vz
    # Rotate -theta around +X:  [y']   [ cos   sin] [y]
    #                           [z'] = [-sin   cos] [z]
    new_ry = ry * cos_t + rz * sin_t
    new_rz = -ry * sin_t + rz * cos_t
    # Translate back to world (pivot is at (cx, 0, cz-0.5)).
    return (cx + vx, new_ry, (cz - 0.5) + new_rz)


def _assert_cube_invariants(verts: tuple[Vec3, ...]) -> None:
    """Tumble-geometry invariant: cube has 8 vertices and never passes through
    the floor. This is the bug we caught during Step 1; encoding it as a
    runtime assertion keeps any future tumble-math change honest.
    """
    assert len(verts) == 8, f"cube geometry must have 8 vertices, got {len(verts)}"
    assert all(y >= -1e-6 for _, y, _ in verts), (
        "cube vertex dipped below the floor — tumble rotation sign is wrong"
    )


def _build_faces(
    world_verts: tuple[Vec3, ...],
    colors: dict[str, ColorRGB],
    edge_color: ColorRGB,
    edge_width: int,
) -> list[FaceDescriptor]:
    """Turn 8 cube vertices + a color dict into a list of renderable faces.

    Used by the player cube path only (via `get_player_faces`). Game cubes use
    `get_cube_faces` directly, deriving face colours from FACE_MULTS. The
    `colors` dict must have a key for every face direction in `_CUBE_FACES`
    ("top", "bottom", "front", "back", "side") — missing keys raise `KeyError`.
    """
    assert len(world_verts) == 8, f"_build_faces expects 8 cube verts, got {len(world_verts)}"
    return [
        (
            (world_verts[idx[0]], world_verts[idx[1]], world_verts[idx[2]], world_verts[idx[3]]),
            colors[direction],
            edge_color,
            edge_width,
        )
        for idx, direction in _CUBE_FACES
    ]


def get_cube_faces(world_verts: tuple[Vec3, ...], cube_type: CubeType) -> list[FaceDescriptor]:
    """Get renderable faces for a cube given its 8 world-space vertices.

    Each face colour is derived by multiplying the cube type's `base_color`
    by the corresponding entry in `FACE_MULTS` (indexed by face position in
    `_CUBE_FACES`). This gives two distinct visible side shades — the +X face
    (screen-left) is the lit side; the -X face (screen-right) is the shadow
    side — producing proper depth without hand-tuning per-face values.
    """
    assert len(world_verts) == 8, f"get_cube_faces expects 8 vertices, got {len(world_verts)}"
    info = CUBE_TYPES[cube_type]
    base = info["base_color"]
    edge = info["edge_color"]
    width = info["edge_width"]
    faces: list[FaceDescriptor] = []
    for face_idx, (vert_indices, _dir) in enumerate(_CUBE_FACES):
        mult = FACE_MULTS[face_idx]
        # int() truncates toward zero (not round). Channels are always positive
        # and the difference vs round() is at most 1 unit — imperceptible.
        shaded: ColorRGB = (int(base[0] * mult), int(base[1] * mult), int(base[2] * mult))
        v0, v1, v2, v3 = vert_indices
        quad = (world_verts[v0], world_verts[v1], world_verts[v2], world_verts[v3])
        assert len(faces) < 6, "cube face overflow — _CUBE_FACES has more than 6 entries"
        faces.append((quad, shaded, edge, width))
    assert len(faces) == 6, f"expected 6 cube faces, got {len(faces)}"
    return faces


class PlayerVisual:
    """Render-mode tags for `get_player_faces`."""
    NORMAL: str = "normal"
    CRUSHED: str = "crushed"   # Avalanche active — player squashes flat.


def get_player_vertices(
    grid_x: int, grid_z: int, scale_y: float = 1.0,
) -> tuple[Vec3, ...]:
    """Get 8 world-space vertices for the player at grid position.

    `scale_y`: 1.0 = normal height; values < 1 squash the cube toward
    the floor (crush visual). The y coordinate scales relative to y=0
    so the bottom stays on the platform surface.
    """
    if scale_y <= 0.0:
        raise ValueError(f"scale_y must be positive, got {scale_y}")
    cx = float(grid_x)
    cz = float(grid_z)
    s = 2.0 * PLAYER_HALF_EXTENT
    return tuple(
        (cx + vx * s, (PLAYER_CENTER_Y + vy * s) * scale_y, cz + vz * s)
        for vx, vy, vz in _CUBE_VERTS
    )


def get_player_faces(
    world_verts: tuple[Vec3, ...],
    visual: str = PlayerVisual.NORMAL,
) -> list[FaceDescriptor]:
    """Get renderable faces for the player cube.

    `visual` selects the color palette: NORMAL (blue) or CRUSHED (dark red,
    squashed flat when avalanche active).
    """
    if visual == PlayerVisual.CRUSHED:
        return _build_faces(
            world_verts, PLAYER_CRUSH_COLORS, PLAYER_CRUSH_EDGE_COLOR, 1,
        )
    return _build_faces(world_verts, PLAYER_COLORS, PLAYER_EDGE_COLOR, 1)


# --- Marker cone geometry -----------------------------------------------------
# Floating inverted cone (apex pointing down) rendered above MARKED and
# ADVANTAGE_TRAP tiles. Apex at CONE_APEX_Y, hexagonal base at CONE_BASE_Y.
# "Inverted" = base on top, tip pointing down, giving the impression the cone
# is hovering just above the cube surface with its tip indicating the tile.
# Positioned 25% above cube height: cube top = 1.0, 25% above = 1.25 (apex).

CONE_SIDES: int = 6           # Hexagonal cross-section
CONE_APEX_Y: float = 1.25     # Tip y — 25% above cube top (which is y=1.0)
CONE_BASE_Y: float = 1.50     # Open base y — 0.25 world units above the tip
CONE_RADIUS: float = 0.20     # Hexagon circumradius at the base

# Fill and edge colors per tile state.  Only MARKED and ADVANTAGE_TRAP have
# cone representations; other states are handled by an early return.
_CONE_COLORS: dict[TileState, tuple[ColorRGB, ColorRGB]] = {
    TileState.MARKED:         ((200, 220, 255), (120, 140, 180)),
    TileState.ADVANTAGE_TRAP: ((80, 200, 80),   (40, 120, 40)),
}


def get_marker_cone_faces(
    grid_x: int, grid_z: int, tile_state: TileState,
) -> list[TriFaceDescriptor]:
    """Return triangular face descriptors for a floating cone marker.

    Produces `CONE_SIDES` triangular side faces for an inverted cone centred
    at world (grid_x, CONE_BASE_Y, grid_z), with the apex at CONE_APEX_Y.
    Returns an empty list for tile states that have no cone (e.g. PLATFORM).
    """
    if tile_state not in _CONE_COLORS:
        return []
    fill_color, edge_color = _CONE_COLORS[tile_state]
    cx = float(grid_x)
    cz = float(grid_z)
    apex: Vec3 = (cx, CONE_APEX_Y, cz)
    base_verts: list[Vec3] = []
    for i in range(CONE_SIDES):
        angle = (2.0 * math.pi * i) / CONE_SIDES
        bx = cx + CONE_RADIUS * math.cos(angle)
        bz = cz + CONE_RADIUS * math.sin(angle)
        assert len(base_verts) < CONE_SIDES, "cone base vertex overflow"
        base_verts.append((bx, CONE_BASE_Y, bz))
    assert len(base_verts) == CONE_SIDES, "cone base vertex count mismatch"
    faces: list[TriFaceDescriptor] = []
    for i in range(CONE_SIDES):
        v0 = base_verts[i]
        v1 = base_verts[(i + 1) % CONE_SIDES]
        tri: tuple[Vec3, Vec3, Vec3] = (v0, v1, apex)
        assert len(faces) < CONE_SIDES, "cone face overflow"
        faces.append((tri, fill_color, edge_color, 1))
    assert len(faces) == CONE_SIDES, "cone face count mismatch"
    return faces


def get_tile_face(
    grid_x: int, grid_z: int, tile_state: TileState = TileState.PLATFORM,
) -> tuple[tuple[Vec3, Vec3, Vec3, Vec3], ColorRGB, ColorRGB, int]:
    """Get a single renderable face for a grid tile at (grid_x, grid_z).

    Tiles are thin quads at y=-0.01 (slightly below cube bottom to avoid
    z-fighting). An inset of 0.02 per side creates visible gaps between tiles.
    Callers must pass a tile_state that has a palette entry in `TILE_COLORS`;
    `TileState.VOID` is not renderable and must not reach this function.

    B3c: PLATFORM tiles alternate between two shades based on
    `(grid_x + grid_z) % 2` (checkerboard). MARKED and ADVANTAGE_TRAP tiles
    keep their palette colour unchanged — they are already visually distinctive.
    """
    # Rule-5 precondition: only palette-backed tile states are renderable.
    if tile_state not in TILE_COLORS:
        raise ValueError(f"tile_state {tile_state!r} has no palette entry in TILE_COLORS")

    inset = 0.02
    y = -0.01
    x0 = grid_x - 0.5 + inset
    x1 = grid_x + 0.5 - inset
    z0 = grid_z - 0.5 + inset
    z1 = grid_z + 0.5 - inset

    verts: tuple[Vec3, Vec3, Vec3, Vec3] = (
        (x0, y, z0),   # back-left
        (x1, y, z0),   # back-right
        (x1, y, z1),   # front-right
        (x0, y, z1),   # front-left
    )
    colors = TILE_COLORS[tile_state]
    # B3c: lighten alternate PLATFORM tiles by TILE_CHECKER_DELTA per channel.
    if tile_state == TileState.PLATFORM and (grid_x + grid_z) % 2 == 1:
        base = colors["top"]
        fill: ColorRGB = (
            min(255, base[0] + TILE_CHECKER_DELTA),
            min(255, base[1] + TILE_CHECKER_DELTA),
            min(255, base[2] + TILE_CHECKER_DELTA),
        )
    else:
        fill = colors["top"]
    return (verts, fill, colors["edge"], 1)


# --- Table edge wall geometry (Step 40) ----------------------------------------
# Three light-multipliers for the three visible wall directions.
# Front wall faces the camera (-Z direction); left faces +X; right faces -X.
# Using FACE_MULTS convention: front and +X are "lit" (0.75), -X is "shadow" (0.55).
_WALL_MULT_FRONT: float = 0.75    # front wall — obliquely lit, faces camera
_WALL_MULT_LEFT: float = 0.65     # left wall (+X facing) — partially lit
_WALL_MULT_RIGHT: float = 0.50    # right wall (-X facing) — shadow side


def _shade(color: ColorRGB, mult: float) -> ColorRGB:
    return (int(color[0] * mult), int(color[1] * mult), int(color[2] * mult))


def get_table_edge_faces(
    grid_width: int,
    grid_depth: int,
    front_edge_z: int,
    table_depth: float = TABLE_DEPTH,
) -> list[FaceDescriptor]:
    """Return wall quads hanging below the visible grid edges.

    Generates one quad per tile segment for front, left, and right walls so
    painter's-algorithm depth sorting stays accurate even when cubes overlap
    the wall z-range.  Face count: grid_width (front) + 2*(grid_depth −
    front_edge_z) (left + right) = O(grid_width + grid_depth), always bounded.

    Vertex winding matches the cube face conventions in _CUBE_FACES so the
    same back-face culling applies: front wall uses back-face winding (visible
    from lower z), side walls use +X/-X face winding respectively.
    """
    if table_depth <= 0.0:
        raise ValueError(f"table_depth must be positive, got {table_depth}")
    if grid_width <= 0 or grid_depth <= 0:
        raise ValueError(
            f"grid dimensions must be positive, got {grid_width}×{grid_depth}"
        )

    faces: list[FaceDescriptor] = []
    d = table_depth      # depth below y=0
    lx = -0.5            # left boundary x (left edge of column 0)
    rx = grid_width - 0.5  # right boundary x (right edge of last column)

    front_color = _shade(TABLE_SIDE_COLOR, _WALL_MULT_FRONT)
    left_color  = _shade(TABLE_SIDE_COLOR, _WALL_MULT_LEFT)
    right_color = _shade(TABLE_SIDE_COLOR, _WALL_MULT_RIGHT)

    # Front wall: one quad per column at z = front_edge_z - 0.5.
    # Winding: top-right → top-left → bottom-left → bottom-right.
    # Camera looks in +Z; the front wall faces -Z (toward camera).  A 2D
    # cross-product analysis for the follow camera confirms this order gives
    # cross > 0 (front-facing) for all valid front_edge_z values visible to
    # the camera.  The wall is behind the camera when front_edge_z is small
    # (camera at z≈27 vs wall at z=-0.5); project_vertex rejects those verts
    # via clip_w < NEAR_PLANE, so the face safely returns None until the wall
    # enters the frustum as penalty rows are deleted.
    fz = front_edge_z - 0.5
    for gx in range(grid_width):
        x0 = gx - 0.5
        x1 = gx + 0.5
        quad: tuple[Vec3, Vec3, Vec3, Vec3] = (
            (x1,  0, fz),
            (x0,  0, fz),
            (x0, -d, fz),
            (x1, -d, fz),
        )
        faces.append((quad, front_color, None, 0))

    # Left and right walls: one quad per row from front_edge_z to grid_depth-1.
    for gz in range(front_edge_z, grid_depth):
        z0 = gz - 0.5
        z1 = gz + 0.5

        # Left wall at x=lx, facing +X.
        # Winding: top-far → top-near → bottom-near → bottom-far.
        left_quad: tuple[Vec3, Vec3, Vec3, Vec3] = (
            (lx,  0, z1),
            (lx,  0, z0),
            (lx, -d, z0),
            (lx, -d, z1),
        )
        faces.append((left_quad, left_color, None, 0))

        # Right wall at x=rx, facing -X.
        # Winding: top-near → top-far → bottom-far → bottom-near.
        right_quad: tuple[Vec3, Vec3, Vec3, Vec3] = (
            (rx,  0, z0),
            (rx,  0, z1),
            (rx, -d, z1),
            (rx, -d, z0),
        )
        faces.append((right_quad, right_color, None, 0))

    max_faces = grid_width + 2 * (grid_depth - front_edge_z)
    assert len(faces) == max_faces, (
        f"table edge face count mismatch: expected {max_faces}, got {len(faces)}"
    )
    return faces


# --- Player character geometry (Step 41) ----------------------------------------
# Low-poly humanoid: head cube + torso box + two swinging legs.
# All y-positions are multiplied by scale_y (0.15 when crushed, 1.0 normally)
# so the character flattens toward the floor in the avalanche crush state.
# Vertex ordering matches _CUBE_VERTS throughout, so _build_faces works directly.

_CHAR_HEAD_HW: float = 0.11    # head half-width and half-depth (square cross-section)
_CHAR_HEAD_HH: float = 0.11    # head half-height
_CHAR_HEAD_CY: float = 0.77    # head centre y  (spans y = 0.66 … 0.88)

_CHAR_TORSO_HW: float = 0.14   # torso half-width (x)
_CHAR_TORSO_HH: float = 0.15   # torso half-height (y)  → height = 0.30
_CHAR_TORSO_HD: float = 0.10   # torso half-depth (z)
_CHAR_TORSO_CY: float = 0.51   # torso centre y  (spans y = 0.36 … 0.66)

_CHAR_LEG_HW: float = 0.05     # half-width per leg (x)
_CHAR_LEG_HD: float = 0.07     # half-depth per leg (z)
_CHAR_LEG_HIP_Y: float = 0.36  # hip-joint y = top of leg (leg spans y = 0 … 0.36)
_CHAR_LEG_X_OFF: float = 0.09   # each leg's x-offset from the tile centre
_CHAR_LEG_SWING: float = 0.06   # max z-translation of foot at walk peak (depth cue only)
_CHAR_LEG_LIFT_Y: float = 0.18  # max foot Y-rise at walk peak (main visible axis)
_CHAR_BODY_BOB: float = 0.08    # max whole-body Y-rise at walk peak

# Kneel pose (right knee on ground while marking): body drops _CHAR_KNEEL_DROP
# world-units so the pelvis descends; right leg is compressed to _CHAR_KNEEL_HIP_Y
# height, representing the shin with the knee touching the floor.
_CHAR_KNEEL_DROP: float = 0.20  # pelvis + body drop (head/torso/hips all shift down)
_CHAR_KNEEL_HIP_Y: float = 0.20  # kneeling right-leg top y (compressed shin height)

# Arms: small boxes hanging from the torso shoulders.
# Shoulder joint at y = _CHAR_ARM_SH_Y (near the top of the torso = 0.66).
# Arms swing in Z cross-body: right arm forward with left leg, left with right.
_CHAR_ARM_HW: float = 0.04     # arm half-width (x)
_CHAR_ARM_HH: float = 0.09     # arm half-height (y) — arm length 0.18 wu
_CHAR_ARM_HD: float = 0.04     # arm half-depth (z)
_CHAR_ARM_SH_Y: float = 0.61   # shoulder joint y (near top of torso = 0.66)
_CHAR_ARM_X_OFF: float = 0.18  # arm x-offset from tile centre (torso 0.14 + arm 0.04)
_CHAR_ARM_SWING: float = 0.06  # max arm Z-swing (matches leg Z-swing amplitude)

# Facing-direction face highlight: a distinctly lighter blue applied to the
# face-direction face of the head so the front reads clearly at small character size.
_CHAR_FACE_COLOR: ColorRGB = (210, 235, 255)

# Map from player facing Direction to the _CUBE_FACES key for the face highlight.
# "front"=+Z face, "back"=−Z face, "side"=±X (both X faces share the one key).
_FACING_FACE_KEY: dict[Direction, str] = {
    Direction.FORWARD:  "front",   # faces +Z (toward wave, away from camera)
    Direction.BACKWARD: "back",    # faces −Z (toward camera)
    Direction.LEFT:     "side",    # faces +X
    Direction.RIGHT:    "side",    # faces −X
}

# Per-part colour multipliers (applied to PLAYER_COLORS face values).
# Head 100%; torso 85%; legs 70%; arms 75%.
_CHAR_PART_MULTS: tuple[float, float, float, float] = (1.0, 0.85, 0.70, 0.75)

_CHAR_TOTAL_FACES: int = 36    # 6 parts × 6 cube-faces each


def _tinted(colors: dict[str, ColorRGB], m: float) -> dict[str, ColorRGB]:
    """Return a copy of a face-direction color dict with each channel scaled by m."""
    assert 0.0 < m <= 1.0, f"tint multiplier {m} not in (0, 1]"
    return {k: (int(v[0] * m), int(v[1] * m), int(v[2] * m)) for k, v in colors.items()}


def _head_face_colors(
    colors: dict[str, ColorRGB], mult: float, facing: Direction, crushed: bool,
) -> dict[str, ColorRGB]:
    """Return head color dict with the facing-direction face highlighted.

    The face-side face gets `_CHAR_FACE_COLOR` (distinctly lighter than the
    back) so the character's front is readable at small screen size.  Suppressed
    when crushed — the character is flat and the highlight serves no purpose.
    """
    tinted = _tinted(colors, mult)
    if crushed:
        return tinted
    face_key = _FACING_FACE_KEY[facing]
    assert face_key in tinted, f"face key {face_key!r} missing from color dict"
    return {**tinted, face_key: _CHAR_FACE_COLOR}


def _append_arm_faces(
    faces: list[FaceDescriptor],
    cx: float, cz: float,
    l_arm_cy: float, r_arm_cy: float,
    scale_y: float,
    left_arm_z: float, right_arm_z: float,
    colors: dict[str, ColorRGB], mult: float, edge: ColorRGB,
) -> None:
    """Build and append left + right arm faces (12 faces total).

    `l_arm_cy` / `r_arm_cy`: centre-y of each arm box.  Normally equal (both
    hanging from the shoulder), but `r_arm_cy` is raised above the shoulder
    when the player is detonating.
    """
    pre = len(faces)
    assert pre <= _CHAR_TOTAL_FACES - 12, f"no room for 12 arm faces: {pre}"
    lv = _char_box_verts(
        cx - _CHAR_ARM_X_OFF, l_arm_cy, cz + left_arm_z,
        _CHAR_ARM_HW, _CHAR_ARM_HH, _CHAR_ARM_HD, scale_y,
    )
    _append_part_faces(faces, lv, _tinted(colors, mult), edge)
    rv = _char_box_verts(
        cx + _CHAR_ARM_X_OFF, r_arm_cy, cz + right_arm_z,
        _CHAR_ARM_HW, _CHAR_ARM_HH, _CHAR_ARM_HD, scale_y,
    )
    _append_part_faces(faces, rv, _tinted(colors, mult), edge)
    assert len(faces) == pre + 12, f"arm faces added {len(faces) - pre}, expected 12"


def _char_box_verts(
    cx: float, cy: float, cz: float,
    hw: float, hh: float, hd: float,
    scale_y: float,
) -> tuple[Vec3, ...]:
    """Eight vertices for a y-scaled axis-aligned box, in _CUBE_VERTS order.

    All y-coordinates are multiplied by scale_y so the crush squash (scale_y=0.15)
    collapses every body part toward the floor uniformly.
    """
    if scale_y <= 0.0:
        raise ValueError(f"scale_y must be positive, got {scale_y}")
    sy = cy * scale_y
    sh = hh * scale_y
    return (
        (cx - hw, sy - sh, cz - hd),  # 0 bottom-left-back
        (cx + hw, sy - sh, cz - hd),  # 1 bottom-right-back
        (cx + hw, sy + sh, cz - hd),  # 2 top-right-back
        (cx - hw, sy + sh, cz - hd),  # 3 top-left-back
        (cx - hw, sy - sh, cz + hd),  # 4 bottom-left-front
        (cx + hw, sy - sh, cz + hd),  # 5 bottom-right-front
        (cx + hw, sy + sh, cz + hd),  # 6 top-right-front
        (cx - hw, sy + sh, cz + hd),  # 7 top-left-front
    )


def _char_leg_verts(
    leg_x: float, cz: float, swing_z: float,
    lift_y: float, hip_y: float, scale_y: float,
) -> tuple[Vec3, ...]:
    """Eight vertices for one leg with foot-lift and hip-anchor walking motion.

    `swing_z`: z-translation of the foot (minor depth cue, ~invisible from camera).
    `lift_y`:  world-space y-height of the foot above the floor — this is the
               primary visible animation axis (~42 px/world-unit at game distance).
    `hip_y`:   unscaled hip-joint y; multiplied by scale_y so the crush-flat
               effect collapses both ends of the leg toward the floor.
    """
    if scale_y <= 0.0:
        raise ValueError(f"scale_y must be positive, got {scale_y}")
    hy = hip_y * scale_y
    hw = _CHAR_LEG_HW
    hd = _CHAR_LEG_HD
    assert 0.0 <= lift_y < hy, (
        f"lift_y {lift_y:.4f} must be in [0, hip_y×scale_y={hy:.4f})"
    )
    return (
        (leg_x - hw, lift_y, cz - hd + swing_z),  # 0 bottom-left-back
        (leg_x + hw, lift_y, cz - hd + swing_z),  # 1 bottom-right-back
        (leg_x + hw, hy,     cz - hd),             # 2 top-right-back (hip)
        (leg_x - hw, hy,     cz - hd),             # 3 top-left-back  (hip)
        (leg_x - hw, lift_y, cz + hd + swing_z),  # 4 bottom-left-front
        (leg_x + hw, lift_y, cz + hd + swing_z),  # 5 bottom-right-front
        (leg_x + hw, hy,     cz + hd),             # 6 top-right-front (hip)
        (leg_x - hw, hy,     cz + hd),             # 7 top-left-front  (hip)
    )


def _append_part_faces(
    faces: list[FaceDescriptor],
    part_verts: tuple[Vec3, ...],
    colors: dict[str, ColorRGB],
    edge: ColorRGB,
) -> None:
    """Append the 6 rendered faces of one character body part into `faces`."""
    for fd in _build_faces(part_verts, colors, edge, 1):
        assert len(faces) < _CHAR_TOTAL_FACES, "character face overflow"
        faces.append(fd)


def get_player_character_faces(
    grid_x: float,
    grid_z: float,
    walk_progress: float,
    step_parity: bool,
    is_crushed: bool,
    facing: Direction,
    is_marking: bool = False,
    is_detonating: bool = False,
    is_triggering: bool = False,
) -> list[FaceDescriptor]:
    """Return face descriptors for the animated low-poly player character.

    6 parts × 6 faces = 36 FaceDescriptors total (head, torso, 2 legs, 2 arms).
    `facing` drives which face of the head carries the lighter face highlight.
    `walk_progress` [0,1]: 1 just stepped, decays to 0 idle.  Y-axis foot-lift
    and body-bob are the primary visible animation; Z-swing is a minor depth cue.
    `step_parity` alternates the leading leg; arms swing cross-body.
    `is_crushed` flattens to scale_y=0.15 and switches to dark red.
    `is_marking` kneels on the right knee (body drops, right leg compressed).
    `is_detonating` raises the right arm above the shoulder (Z key gesture).
    `is_triggering` raises the left arm (X key capture gesture).
    """
    if not (0.0 <= walk_progress <= 1.0):
        raise ValueError(f"walk_progress {walk_progress!r} not in [0, 1]")
    scale_y = 0.15 if is_crushed else 1.0
    colors = PLAYER_CRUSH_COLORS if is_crushed else PLAYER_COLORS
    edge = PLAYER_CRUSH_EDGE_COLOR if is_crushed else PLAYER_EDGE_COLOR
    cx = float(grid_x)
    cz = float(grid_z)
    # Half-sine clamped to [0,1] guards the float sign-flip at sin(π).
    t = max(0.0, math.sin(math.pi * walk_progress))
    raw_swing = _CHAR_LEG_SWING * t
    raw_lift = 0.0 if is_crushed else _CHAR_LEG_LIFT_Y * t
    y_bob = 0.0 if is_crushed else _CHAR_BODY_BOB * t
    # Kneeling pose: right knee on ground while marking (suppresses walk swing).
    if is_marking and not is_crushed:
        left_swing = right_swing = left_lift = right_lift = left_arm_z = right_arm_z = 0.0
        head_cy = _CHAR_HEAD_CY - _CHAR_KNEEL_DROP
        torso_cy = _CHAR_TORSO_CY - _CHAR_KNEEL_DROP
        l_hip = _CHAR_LEG_HIP_Y - _CHAR_KNEEL_DROP  # standing leg (pelvis-down)
        r_hip = _CHAR_KNEEL_HIP_Y                    # kneeling leg (compressed shin)
    else:
        # Walking: leading leg lifts + swings; trailing planted. Arms cross-body.
        if not step_parity:
            left_swing, left_lift = raw_swing, raw_lift
            right_swing, right_lift = -raw_swing, 0.0
            left_arm_z, right_arm_z = -raw_swing, raw_swing
        else:
            left_swing, left_lift = -raw_swing, 0.0
            right_swing, right_lift = raw_swing, raw_lift
            left_arm_z, right_arm_z = raw_swing, -raw_swing
        head_cy = _CHAR_HEAD_CY + y_bob
        torso_cy = _CHAR_TORSO_CY + y_bob
        l_hip = r_hip = _CHAR_LEG_HIP_Y + y_bob
    # Arms: trigger raises left (X key), detonate raises right (Z key); crushed suppresses all.
    base_arm_cy = _CHAR_ARM_SH_Y + y_bob - _CHAR_ARM_HH
    up_arm_cy = _CHAR_ARM_SH_Y + y_bob + _CHAR_ARM_HH
    l_arm_cy = up_arm_cy if is_triggering and not is_crushed else base_arm_cy
    r_arm_cy = up_arm_cy if is_detonating and not is_crushed else base_arm_cy
    faces: list[FaceDescriptor] = []
    head_mult, torso_mult, leg_mult, arm_mult = _CHAR_PART_MULTS
    hv = _char_box_verts(cx, head_cy, cz, _CHAR_HEAD_HW, _CHAR_HEAD_HH, _CHAR_HEAD_HW, scale_y)
    _append_part_faces(faces, hv, _head_face_colors(colors, head_mult, facing, is_crushed), edge)
    tv = _char_box_verts(cx, torso_cy, cz, _CHAR_TORSO_HW, _CHAR_TORSO_HH, _CHAR_TORSO_HD, scale_y)
    _append_part_faces(faces, tv, _tinted(colors, torso_mult), edge)
    lv = _char_leg_verts(cx - _CHAR_LEG_X_OFF, cz, left_swing, left_lift, l_hip, scale_y)
    _append_part_faces(faces, lv, _tinted(colors, leg_mult), edge)
    rv = _char_leg_verts(cx + _CHAR_LEG_X_OFF, cz, right_swing, right_lift, r_hip, scale_y)
    _append_part_faces(faces, rv, _tinted(colors, leg_mult), edge)
    _append_arm_faces(
        faces, cx, cz, l_arm_cy, r_arm_cy, scale_y,
        left_arm_z, right_arm_z, colors, arm_mult, edge,
    )
    assert len(faces) == _CHAR_TOTAL_FACES, f"got {len(faces)} character faces"
    return faces
