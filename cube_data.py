"""Cube and tile geometry definitions, tumble rotation math.

All geometry is defined in world-space coordinates.
Grid convention: X = columns (0..GRID_WIDTH-1), Z = rows (0 = front/camera-side,
GRID_DEPTH-1 = back). Cubes advance from high Z toward low Z.
Y = up. Tile surface is at Y=0. Cube centers rest at Y=0.5.
"""

import math

from constants import (
    CUBE_TYPES,
    PLAYER_CENTER_Y,
    PLAYER_COLORS,
    PLAYER_CRUSH_COLORS,
    PLAYER_CRUSH_EDGE_COLOR,
    PLAYER_EDGE_COLOR,
    PLAYER_HALF_EXTENT,
    TILE_COLORS,
    TUMBLE_BALANCE_END,
    TUMBLE_COS_LUT,
    TUMBLE_HEAVE_END,
    TUMBLE_LUT_STEPS,
    TUMBLE_REST_FRACTION,
    TUMBLE_SIN_LUT,
    ColorRGB,
    CubeType,
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

# Face definitions: (vertex indices, face_direction). face_direction maps to
# color keys in the cube-type registry (enforced at runtime by _build_faces).
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

    Shared by both game cubes and the player cube. The `colors` dict must have
    a key for every face direction in `_CUBE_FACES` ("top", "bottom", "front",
    "back", "side") — missing keys raise `KeyError` rather than silently
    falling back, so palette coverage is enforced at the registry.
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
    """Get renderable faces for a cube given its 8 world-space vertices."""
    type_info = CUBE_TYPES[cube_type]
    return _build_faces(
        world_verts,
        type_info["colors"],
        type_info["edge_color"],
        type_info["edge_width"],
    )


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
    return (verts, colors["top"], colors["edge"], 1)
