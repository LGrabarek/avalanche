"""Wave patterns for Stages 1 and 2 — hand-designed puzzle rows.

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

Grid note: PLAYER_SPAWN_Z = GRID_DEPTH − 1 − 3 = 21. Stage-1 waves use 2 rows
(front-most at z=23); Stage-2 waves use up to 3 rows (front-most at z=22).
All spawn rows are behind the player's starting position so the player never
shares a tile with a freshly-spawned cube.
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


# ---------------------------------------------------------------------------
# Four Stage-2 wave patterns — harder layouts, more FORBIDDEN, 3-row waves
# ---------------------------------------------------------------------------
# Stage 2 ramps up density and ADVANTAGE/FORBIDDEN interplay.  Ideal-step
# counts assume efficient blast chaining; the ±20 and ±40 bonus tiers in
# _calc_perfect_bonus still reward slightly-over-ideal play.
# ---------------------------------------------------------------------------

# Wave S2-1 — FORBIDDEN introduced early.  Centre FORBIDDEN at col 3 flanked
# by a single ADVANTAGE at col 2; four NORMAL fill the remaining cols.  Sparse
# second row keeps total pressure manageable for the stage opener.
# Optimal: 2 (ADV mark+trigger) + 1 (detonate) + blast catches ~2 NORMAL
#          + remaining 5 NORMAL individually = ~13 steps.
_S2W1_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _A, _F, _N, _N, _N),   # z=24 — 4 NORMAL + 1 ADVANTAGE + 1 FORBIDDEN
    (_N, _X, _N, _X, _N, _X, _N),   # z=23 — 4 NORMAL (sparse)
)
_S2W1_IDEAL: int = 13

# Wave S2-2 — Two ADVANTAGE flanking a centre FORBIDDEN; dense second row.
# Both ADVANTAGE blasts together can sweep the outer halves of row z=23.
# Optimal: 2×(mark+trigger) + 2×1 (detonate) + ~6 remaining NORMAL = ~17 steps.
_S2W2_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _A, _N),   # z=24 — 4 NORMAL + 2 ADVANTAGE + 1 FORBIDDEN
    (_N, _N, _N, _X, _N, _N, _N),   # z=23 — 6 NORMAL (dense)
)
_S2W2_IDEAL: int = 17

# Wave S2-3 — Three ADVANTAGE spread across the row; sparse second row.
# Chaining all three blasts clears most of the wave with minimal individual
# captures needed; ideal is lower than S2-2 despite more total cubes.
# Optimal: 3×(2+1) = 9 for ADVs + blast chain removes ~4 NORMAL = ~15 steps.
_S2W3_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _A, _N, _A, _N),   # z=24 — 4 NORMAL + 3 ADVANTAGE
    (_N, _X, _N, _X, _N, _X, _N),   # z=23 — 4 NORMAL (sparse)
)
_S2W3_IDEAL: int = 15

# Wave S2-4 — Full 3-row challenge.  ADVANTAGE at corners with two FORBIDDEN
# in the middle; two dense rows follow.  Corner ADV blasts cover the outer
# NORMAL strips; inner NORMAL and middle row captured individually.
# Optimal: 2×(2+1) + ~14 individual NORMAL = ~20 steps.
_S2W4_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _F, _N, _A),   # z=24 — 2 NORMAL + 2 ADVANTAGE + 2 FORBIDDEN
    (_N, _N, _X, _N, _X, _N, _N),   # z=23 — 5 NORMAL
    (_N, _X, _N, _X, _N, _X, _N),   # z=22 — 4 NORMAL
)
_S2W4_IDEAL: int = 20


# ---------------------------------------------------------------------------
# Stage 2 wave sequence — 4 waves in order
# ---------------------------------------------------------------------------

STAGE_2_WAVES: tuple[WaveData, ...] = (
    WaveData(_S2W1_ROWS, _S2W1_IDEAL),
    WaveData(_S2W2_ROWS, _S2W2_IDEAL),
    WaveData(_S2W3_ROWS, _S2W3_IDEAL),
    WaveData(_S2W4_ROWS, _S2W4_IDEAL),
)


# ---------------------------------------------------------------------------
# Master stage table — indexed by stage_index (0-based)
# ---------------------------------------------------------------------------

STAGES: tuple[tuple[WaveData, ...], ...] = (
    STAGE_1_WAVES,
    STAGE_2_WAVES,
)
