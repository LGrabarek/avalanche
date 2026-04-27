"""Wave patterns for Stage 1 — four hand-designed puzzle rows.

Each WaveData holds:
  * `rows`: tuple of rows ordered back → front (row 0 spawns at z=GRID_DEPTH-1,
    row 1 at z=GRID_DEPTH-2, …). Each row is a tuple of GRID_WIDTH entries:
    CubeType | None (None = empty column at that position).
  * `ideal_steps`: minimum input actions (marks + triggers + detonates) to
    achieve a Perfect outcome, pre-computed offline and embedded here. The
    original game calls these the "Ideal Step" values; the research document
    (Research/Intelligent Qube Technical Reproduction Research.md §Heuristics)
    explains how they were baked into the Group.Dat puzzle data to avoid a
    costly BFS at runtime.

Mirror flag: at spawn time the caller rolls a 50% check and passes the result
to `spawn_positions(mirror=…)`. A mirrored wave reverses the X-axis, doubling
effective variety without extra data — exactly what Group.Dat does.

Grid note: PLAYER_SPAWN_Z = GRID_DEPTH − 1 − 3 = 21. Waves capped at 2 rows
each so the front-most spawn row (GRID_DEPTH − 2 = 23) is safely behind the
player's starting position.
"""

from constants import GRID_DEPTH, GRID_WIDTH, CubeType

# Short aliases used only inside this module for compact row definitions.
_N = CubeType.NORMAL
_A = CubeType.ADVANTAGE
_F = CubeType.FORBIDDEN
_X: None = None   # empty column

# ---------------------------------------------------------------------------
# Four Stage-1 wave patterns
# ---------------------------------------------------------------------------
# Row format: 7 columns indexed 0–6.
# Ideal-step derivation:
#   * Each standalone NORMAL/ADVANTAGE capture = 2 steps (mark + trigger).
#   * Capturing an ADVANTAGE then detonating = 3 steps (mark + trigger + Z).
#     One detonation can capture up to 4 neighbouring cubes from the same row,
#     saving steps vs. individual captures.
# ---------------------------------------------------------------------------

# Wave 1 — Intro.  Alternating NORMAL only; 7 cubes; no blasting possible.
# Optimal: 7 × (mark + trigger) = 14 steps.
_W1_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _X, _N, _X, _N, _X, _N),   # z=24 — 4 NORMAL (cols 0,2,4,6)
    (_X, _N, _X, _N, _X, _N, _X),   # z=23 — 3 NORMAL (cols 1,3,5)
)
_W1_IDEAL: int = 14

# Wave 2 — First ADVANTAGE.  One ADVANTAGE at col 3 (centre); 4 NORMAL each
# row; detonation blast catches 2–3 NORMAL cubes in the surrounding tiles.
# Optimal: 2 (ADVANTAGE) + 1 (detonate) + 5 × 2 (remaining NORMAL) = 13.
_W2_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _X, _A, _X, _N, _N),   # z=24 — 4 NORMAL + 1 ADVANTAGE
    (_N, _X, _N, _X, _N, _X, _N),   # z=23 — 4 NORMAL
)
_W2_IDEAL: int = 13

# Wave 3 — FORBIDDEN introduced.  ADVANTAGE at cols 1 & 5 flank a FORBIDDEN
# at col 3; NORMAL fill the gaps.  Two blasts can sweep most of row z=23.
# FORBIDDEN not captured (letting it fall off is safe and saves 2 steps).
# Optimal: 2×2 (ADVANTAGE) + 2×1 (detonate) + 4×2 (remaining NORMAL) = 14.
_W3_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _X, _F, _X, _A, _N),   # z=24 — 2 NORMAL + 2 ADV + 1 FORBIDDEN
    (_N, _X, _N, _X, _N, _X, _N),   # z=23 — 4 NORMAL
)
_W3_IDEAL: int = 14

# Wave 4 — Full challenge.  ADVANTAGE at corners (cols 0, 6); two FORBIDDEN
# in the middle; dense NORMAL row below.  Both ADVANTAGE blasts together
# cover the outer NORMAL strips; inner NORMAL captured individually.
# Optimal: 16 steps (2×2 ADVANTAGE + 1 detonate + remaining individual).
_W4_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _F, _N, _A),   # z=24 — 2 NORMAL + 2 ADV + 2 FORBIDDEN
    (_N, _N, _X, _N, _X, _N, _N),   # z=23 — 5 NORMAL
)
_W4_IDEAL: int = 16


# ---------------------------------------------------------------------------
# WaveData class
# ---------------------------------------------------------------------------

class WaveData:
    """Immutable wave pattern with spawn-position and cube-count helpers."""

    def __init__(
        self,
        rows: tuple[tuple[CubeType | None, ...], ...],
        ideal_steps: int,
    ) -> None:
        if ideal_steps <= 0:
            raise ValueError(f"ideal_steps must be positive, got {ideal_steps}")
        if not rows:
            raise ValueError("rows must not be empty")
        for i, row in enumerate(rows):
            if len(row) != GRID_WIDTH:
                raise ValueError(
                    f"row {i} has {len(row)} columns, expected {GRID_WIDTH}"
                )
        if len(rows) > GRID_DEPTH:
            raise ValueError(
                f"wave has {len(rows)} rows, exceeds GRID_DEPTH {GRID_DEPTH}"
            )
        self._rows: tuple[tuple[CubeType | None, ...], ...] = rows
        self._ideal_steps: int = ideal_steps

    @property
    def ideal_steps(self) -> int:
        return self._ideal_steps

    @property
    def row_count(self) -> int:
        return len(self._rows)

    def spawn_positions(self, mirror: bool = False) -> list[tuple[int, int, CubeType]]:
        """Return `(grid_x, grid_z, cube_type)` for every cube in the wave.

        Row 0 maps to `z = GRID_DEPTH - 1` (back wall), row 1 to
        `z = GRID_DEPTH - 2`, etc.  If `mirror` is True the X-axis is flipped
        so column 0 becomes column GRID_WIDTH-1 and vice-versa, doubling the
        effective pattern count without extra data.
        """
        positions: list[tuple[int, int, CubeType]] = []
        max_positions = GRID_WIDTH * len(self._rows)
        for row_idx, row in enumerate(self._rows):
            grid_z = GRID_DEPTH - 1 - row_idx
            for col, cube_type in enumerate(row):
                if cube_type is None:
                    continue
                grid_x = (GRID_WIDTH - 1 - col) if mirror else col
                assert len(positions) < max_positions, (
                    "spawn_positions exceeded theoretical maximum — row data corrupted"
                )
                positions.append((grid_x, grid_z, cube_type))
        return positions

    def target_cube_count(self) -> int:
        """Count NORMAL + ADVANTAGE cubes (the Perfect-detection targets)."""
        count = 0
        for row in self._rows:
            for cube_type in row:
                if cube_type in (CubeType.NORMAL, CubeType.ADVANTAGE):
                    count += 1
        assert count >= 0, "target_cube_count went negative — logic error"
        return count


# ---------------------------------------------------------------------------
# Stage 1 wave sequence — 4 waves in order
# ---------------------------------------------------------------------------

STAGE_1_WAVES: tuple[WaveData, ...] = (
    WaveData(_W1_ROWS, _W1_IDEAL),
    WaveData(_W2_ROWS, _W2_IDEAL),
    WaveData(_W3_ROWS, _W3_IDEAL),
    WaveData(_W4_ROWS, _W4_IDEAL),
)
