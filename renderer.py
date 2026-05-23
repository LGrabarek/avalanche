"""Software 3D projection engine.

Transforms world-space geometry into 2D screen-space polygons and draws
them using the painter's algorithm. No numpy, no GPU — the frame budget is
generous (few hundred polys) and keeping this in pure Python avoids any
WASM/Pygbag compatibility risk.
"""

import math

import pygame

from constants import (
    CAMERA_FOV,
    CAMERA_POS,
    CAMERA_TARGET,
    FAR_PLANE,
    NEAR_PLANE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    ColorRGB,
)

# --- Type aliases -------------------------------------------------------------

Vec3 = tuple[float, float, float]
Mat4 = list[float]               # Row-major 4x4 as a flat list of 16 floats
ScreenPoint = tuple[float, float]

# A face handed to the renderer: 4 world-space corners + colors/edge style.
# edge_color may be None to suppress outline drawing (used for table wall faces).
FaceDescriptor = tuple[tuple[Vec3, Vec3, Vec3, Vec3], ColorRGB, ColorRGB | None, int]

# A triangular face: 3 world-space corners + colors/edge style.
# Used for cone marker geometry where quads are unnecessarily complex.
TriFaceDescriptor = tuple[tuple[Vec3, Vec3, Vec3], ColorRGB, ColorRGB, int]

# A face after projection: screen-space points, depth for sorting, and style.
ProjectedFace = tuple[list[ScreenPoint], float, ColorRGB, ColorRGB | None, int]


# --- Vector math helpers (Rule 5 exempt: ≤5 lines, typed, pure, no branching) -

def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(v: Vec3) -> Vec3:
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length < 1e-10:
        return (0.0, 0.0, 0.0)
    inv = 1.0 / length
    return (v[0] * inv, v[1] * inv, v[2] * inv)


# --- Matrix construction ------------------------------------------------------

def _mat4_look_at(eye: Vec3, target: Vec3, world_up: Vec3 = (0.0, 1.0, 0.0)) -> Mat4:
    """Construct a view matrix looking from eye toward target."""
    if eye == target:
        raise ValueError("eye and target must differ (look-at is degenerate otherwise)")
    fwd = _normalize(_sub(eye, target))      # camera looks along -fwd
    right = _normalize(_cross(world_up, fwd))
    up = _cross(fwd, right)
    return [
        right[0], right[1], right[2], -_dot(right, eye),
        up[0],    up[1],    up[2],    -_dot(up, eye),
        fwd[0],   fwd[1],   fwd[2],  -_dot(fwd, eye),
        0.0,      0.0,      0.0,      1.0,
    ]


def _mat4_perspective(fov_deg: float, aspect: float, near: float, far: float) -> Mat4:
    """Construct a perspective projection matrix."""
    if not (0.0 < fov_deg < 180.0):
        raise ValueError(f"fov_deg must be in (0, 180), got {fov_deg}")
    if aspect <= 0.0:
        raise ValueError(f"aspect must be positive, got {aspect}")
    if not (0.0 < near < far):
        raise ValueError(f"require 0 < near < far, got near={near} far={far}")
    f = 1.0 / math.tan(math.radians(fov_deg) * 0.5)
    nf = 1.0 / (near - far)
    return [
        f / aspect, 0.0, 0.0,                   0.0,
        0.0,        f,   0.0,                   0.0,
        0.0,        0.0, (far + near) * nf,     2.0 * far * near * nf,
        0.0,        0.0, -1.0,                  0.0,
    ]


def _mat4_mul(a: Mat4, b: Mat4) -> Mat4:
    """Multiply two row-major 4x4 matrices."""
    assert len(a) == 16 and len(b) == 16, "Mat4 operands must each have 16 elements"
    result: Mat4 = [0.0] * 16
    for r in range(4):
        for c in range(4):
            s = 0.0
            for k in range(4):
                s += a[r * 4 + k] * b[k * 4 + c]
            result[r * 4 + c] = s
    return result


def _transform_point(mat: Mat4, x: float, y: float, z: float) -> tuple[float, float, float, float]:
    """Multiply a point (x,y,z,1) by a row-major 4x4 matrix.

    Returns (ndc_x, ndc_y, ndc_z, clip_w) where the first three components
    have already been divided by clip_w, and clip_w is the raw pre-divide w.
    With our perspective matrix, clip_w == -z_view, so clip_w > 0 means the
    point is in front of the camera and clip_w >= NEAR_PLANE means it's
    beyond the near plane.
    """
    assert len(mat) == 16, "mat must be a 16-element Mat4"
    rx = mat[0] * x + mat[1] * y + mat[2] * z + mat[3]
    ry = mat[4] * x + mat[5] * y + mat[6] * z + mat[7]
    rz = mat[8] * x + mat[9] * y + mat[10] * z + mat[11]
    clip_w = mat[12] * x + mat[13] * y + mat[14] * z + mat[15]
    if abs(clip_w) < 1e-10:
        clip_w = 1e-10
    inv_w = 1.0 / clip_w
    return (rx * inv_w, ry * inv_w, rz * inv_w, clip_w)


# --- Renderer -----------------------------------------------------------------

class Renderer:
    """Projects 3D faces to 2D and draws them with painter's algorithm."""

    def __init__(
        self,
        screen_width: int = SCREEN_WIDTH,
        screen_height: int = SCREEN_HEIGHT,
    ) -> None:
        if screen_width <= 0 or screen_height <= 0:
            raise ValueError(
                f"screen dimensions must be positive, got {screen_width}x{screen_height}"
            )
        self.screen_width: int = screen_width
        self.screen_height: int = screen_height
        self.half_w: float = screen_width * 0.5
        self.half_h: float = screen_height * 0.5
        # Stored so rebuild_vp() can re-use it without recomputing each call.
        self._aspect: float = screen_width / screen_height
        # Build the initial VP matrix (overview camera); gameplay calls
        # rebuild_vp() every frame to track the player.
        self.vp_matrix: Mat4 = [0.0] * 16   # populated immediately below
        self.rebuild_vp(CAMERA_POS, CAMERA_TARGET)

    def rebuild_vp(
        self,
        eye: Vec3,
        target: Vec3,
        fov: float = CAMERA_FOV,
    ) -> None:
        """Rebuild the combined view-projection matrix for a new camera pose.

        Called once at startup (via __init__) and every frame when the camera
        follows the player.  Pass CAMERA_FOLLOW_FOV for the follow pose;
        the default CAMERA_FOV is used for the title / end-screen overview.
        """
        if eye == target:
            raise ValueError(f"eye {eye} and target {target} must differ")
        view = _mat4_look_at(eye, target)
        proj = _mat4_perspective(fov, self._aspect, NEAR_PLANE, FAR_PLANE)
        self.vp_matrix = _mat4_mul(proj, view)

    def project_vertex(self, x: float, y: float, z: float) -> tuple[float, float, float] | None:
        """Project a world-space point to screen coords.

        Returns (sx, sy, depth) or None if the point is at/behind the near plane.
        """
        ndc_x, ndc_y, _ndc_z, clip_w = _transform_point(self.vp_matrix, x, y, z)
        # clip_w is raw clip-space w (== -z_view). Reject points closer than
        # the near plane. This is the meaningful precondition for this function.
        if clip_w < NEAR_PLANE:
            return None
        sx = (ndc_x + 1.0) * self.half_w
        sy = (1.0 - ndc_y) * self.half_h
        return (sx, sy, clip_w)

    def project_face(
        self,
        world_verts: tuple[Vec3, Vec3, Vec3, Vec3],
        fill_color: ColorRGB,
        edge_color: ColorRGB | None = None,
        edge_width: int = 1,
    ) -> ProjectedFace | None:
        """Project a quad (4 world-space vertices) to screen space.

        Returns a face tuple or None if the face is back-facing or has any
        vertex behind the near plane.
        """
        # Rule-5 precondition: project_face is specifically for quads.
        assert len(world_verts) == 4, f"project_face expects 4 verts, got {len(world_verts)}"

        projected: list[ScreenPoint] = []
        depth_sum = 0.0
        for vx, vy, vz in world_verts:
            p = self.project_vertex(vx, vy, vz)
            if p is None:
                return None
            projected.append((p[0], p[1]))
            depth_sum += p[2]

        # Back-face culling: 2D cross product of first two screen-space edges.
        ax = projected[1][0] - projected[0][0]
        ay = projected[1][1] - projected[0][1]
        bx = projected[2][0] - projected[0][0]
        by = projected[2][1] - projected[0][1]
        cross = ax * by - ay * bx
        if cross <= 0:
            return None  # Back-facing

        avg_depth = depth_sum / len(projected)
        return (projected, avg_depth, fill_color, edge_color, edge_width)

    def project_triangle(
        self,
        world_verts: tuple[Vec3, Vec3, Vec3],
        fill_color: ColorRGB,
        edge_color: ColorRGB | None = None,
        edge_width: int = 1,
    ) -> ProjectedFace | None:
        """Project a triangle (3 world-space vertices) to screen space.

        Returns a face tuple or None if the triangle is back-facing or has any
        vertex behind the near plane. Shares the painter's-algorithm depth
        with `project_face` — triangles and quads sort together correctly.
        """
        # Rule-5 precondition: this method is specifically for triangles.
        assert len(world_verts) == 3, f"project_triangle expects 3 verts, got {len(world_verts)}"
        projected: list[ScreenPoint] = []
        depth_sum = 0.0
        for vx, vy, vz in world_verts:
            p = self.project_vertex(vx, vy, vz)
            if p is None:
                return None
            projected.append((p[0], p[1]))
            depth_sum += p[2]
        # Rule-5 invariant: all 3 vertices projected without near-plane clip.
        assert len(projected) == 3, "triangle projected to wrong vertex count"
        # Back-face culling: 2D cross product of first two screen-space edges.
        ax = projected[1][0] - projected[0][0]
        ay = projected[1][1] - projected[0][1]
        bx = projected[2][0] - projected[0][0]
        by = projected[2][1] - projected[0][1]
        cross = ax * by - ay * bx
        if cross <= 0:
            return None  # Back-facing
        avg_depth = depth_sum / 3
        return (projected, avg_depth, fill_color, edge_color, edge_width)

    def render_frame(self, screen: pygame.Surface, face_list: list[ProjectedFace]) -> None:
        """Sort faces by depth (painter's algorithm) and draw them.

        Faces are sorted so the farthest (largest clip_w) is drawn first.
        """
        # Rule-5 invariant: nothing structurally prevents an empty list; the
        # sort/draw loop handles that degenerately. The meaningful precondition
        # is that `face_list` elements are well-formed projected faces; we
        # assert arity once per element via the tuple unpack below.

        # list.sort accepts a key callable; Rule 9 explicitly permits lambdas
        # as `key=` arguments to sort-like built-ins.
        face_list.sort(key=lambda f: f[1], reverse=True)

        # pygame.draw.polygon / aalines return a Rect bounding the drawn pixels.
        # Full-clear every frame means dirty-rect tracking adds no benefit; all
        # returned rects are discarded to `_`.
        #
        # Step 31: cube edges are drawn with pygame.draw.aalines (anti-aliased,
        # always 1 screen-pixel wide) instead of the previous polygon-outline
        # draw.  For edge_width > 1 (FORBIDDEN cubes) a second aalines pass is
        # drawn with every point shifted 1 px to the right, giving a visually
        # thicker ~2 px outline without requiring gfxdraw or a surface copy.
        for projected_face in face_list:
            screen_points, _depth, fill_color, edge_color, edge_width = projected_face
            int_points = [(int(x), int(y)) for x, y in screen_points]
            _ = pygame.draw.polygon(screen, fill_color, int_points)
            if edge_color is not None:
                _ = pygame.draw.aalines(screen, edge_color, True, int_points)
                if edge_width > 1:
                    # Second offset pass — 1 px right — simulates a thick outline.
                    offset_pts = [(x + 1, y) for x, y in int_points]
                    _ = pygame.draw.aalines(screen, edge_color, True, offset_pts)
