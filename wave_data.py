"""Wave patterns for all 10 stages — hand-designed puzzle rows (pool redesign).

Each WaveData holds:
  * `code`: unique identifier string (e.g. ``S1W0A``).
  * `rows`: tuple of rows ordered back → front (row 0 is the back-most row
    of the wave, row 1 is one step closer to the player, etc.).
    Each row is a tuple of `row_width` entries: CubeType | None, where
    row_width matches the active grid width for that stage (7, 9, or 11).
  * `ideal_steps`: minimum input actions (marks + triggers + detonates) to
    achieve a Perfect outcome, pre-computed offline and embedded here.

Mirror flag: at spawn time the caller rolls a 50% check and passes the result
to `spawn_positions(mirror=…)`. A mirrored wave reverses the X-axis, doubling
effective variety without extra data — exactly what Group.Dat does.

Step 28 note: `spawn_positions` accepts a `z_start` keyword overriding the
default back-wall placement.  GameManager._spawn_all_waves_pending uses
`_compute_wave_z_starts` to place every wave.

Pool system: each wave slot has a pool of 2 variants (A and B).  Call
`select_all_waves(rng)` once at game start to randomly pick one variant per
slot for the entire run.

ADVANTAGE blast safety rule: in any row, an ADVANTAGE cube and a FORBIDDEN
cube must be at least 2 columns apart so the ±1-column same-row blast never
captures a FORBIDDEN cube unintentionally.  All rows in this module obey that
constraint.

Ideal-step formula:
  * Each standalone NORMAL cube:      2 steps  (mark + trigger)
  * Each ADVANTAGE + detonate:        3 steps  (mark + trigger + Z)
    Blast catches cubes ±1 col in the SAME ROW only.
  * FORBIDDEN cubes:                  0 steps  (let fall off the edge)
"""

import random as _random

from constants import GRID_DEPTH, GRID_WIDTH, CubeType

# Short aliases used only inside this module for compact row definitions.
_N = CubeType.NORMAL
_A = CubeType.ADVANTAGE
_F = CubeType.FORBIDDEN
_X: None = None   # empty column


# ---------------------------------------------------------------------------
# WaveData class
# ---------------------------------------------------------------------------

class WaveData:
    """Immutable wave pattern with spawn-position and cube-count helpers."""

    def __init__(
        self,
        code: str,
        rows: tuple[tuple[CubeType | None, ...], ...],
        ideal_steps: int,
    ) -> None:
        if not code:
            raise ValueError("code must be non-empty")
        if ideal_steps <= 0:
            raise ValueError(f"ideal_steps must be positive, got {ideal_steps}")
        if not rows:
            raise ValueError("rows must not be empty")
        row_width = len(rows[0])
        if not (1 <= row_width <= GRID_WIDTH):
            raise ValueError(
                f"row width {row_width} must be in [1, GRID_WIDTH={GRID_WIDTH}]"
            )
        for i, row in enumerate(rows):
            if len(row) != row_width:
                raise ValueError(
                    f"row {i} has {len(row)} columns, expected {row_width}"
                )
        if len(rows) > GRID_DEPTH:
            raise ValueError(
                f"wave has {len(rows)} rows, exceeds GRID_DEPTH {GRID_DEPTH}"
            )
        self._code: str = code
        self._rows: tuple[tuple[CubeType | None, ...], ...] = rows
        self._ideal_steps: int = ideal_steps

    @property
    def code(self) -> str:
        return self._code

    @property
    def ideal_steps(self) -> int:
        return self._ideal_steps

    @property
    def row_count(self) -> int:
        return len(self._rows)

    def spawn_positions(
        self,
        mirror: bool = False,
        z_start: int | None = None,
    ) -> list[tuple[int, int, CubeType]]:
        """Return `(grid_x, grid_z, cube_type)` for every cube in the wave."""
        if z_start is not None and not (0 <= z_start < GRID_DEPTH):
            raise ValueError(
                f"z_start {z_start} outside [0, {GRID_DEPTH})"
            )
        positions: list[tuple[int, int, CubeType]] = []
        row_width = len(self._rows[0])
        max_positions = row_width * len(self._rows)
        for row_idx, row in enumerate(self._rows):
            grid_z = (GRID_DEPTH - 1 - row_idx) if z_start is None else (z_start - row_idx)
            for col, cube_type in enumerate(row):
                if cube_type is None:
                    continue
                grid_x = (row_width - 1 - col) if mirror else col
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
# Stage 1 — 2 rows × 7 cols
# ---------------------------------------------------------------------------

# S1W0 — A variant: all-Normal intro
_S1W0A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S1W0A_IDEAL: int = 28

# S1W0 — B variant: gap at col3, rest Normal
# back: 6N (no col3); front: 7N
# back: 6×2=12; front: 14. total=26
_S1W0B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _X, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S1W0B_IDEAL: int = 26

# S1W1 — A variant: A at col3 (centre back)
_S1W1A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _A, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S1W1A_IDEAL: int = 25

# S1W1 — B variant: A at col1
# A@1→N@0,N@2 (3); N@3,4,5,6 individual (4×2=8); front: 14. total=25
_S1W1B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S1W1B_IDEAL: int = 25

# S1W2 — A variant: A@1,5 + F@3
_S1W2A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S1W2A_IDEAL: int = 20

# S1W2 — B variant: A@0,6 + F@3
# A@0→N@1 (3); A@6→N@5 (3); N@2,N@4 individual (2×2=4); back=10; front=14. total=24
_S1W2B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _N, _F, _N, _N, _A),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S1W2B_IDEAL: int = 24

# S1W3 — A variant: A@0,6 + F@2,4
_S1W3A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _F, _N, _A),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S1W3A_IDEAL: int = 26

# S1W3 — B variant: A@0,6 + F@2 only
# A@0→N@1 (3); A@6→N@5 (3); N@3,N@4 individual (2×2=4); back=10; front=14. total=24
_S1W3B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _A),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S1W3B_IDEAL: int = 24


# ---------------------------------------------------------------------------
# Stage 2 — 3 rows × 7 cols
# ---------------------------------------------------------------------------

# S2W0 — A variant: A at col2 (off-centre)
_S2W0A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _A, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S2W0A_IDEAL: int = 39

# S2W0 — B variant: A at col4
# A@4→N@3,N@5 (3); N@0,1,2,6 individual (4×2=8); back=11; mid=14; front=14. total=39
_S2W0B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _N, _A, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S2W0B_IDEAL: int = 39

# S2W1 — A variant: A@1,5 + F@3
_S2W1A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S2W1A_IDEAL: int = 32

# S2W1 — B variant: A@0,6 + F@3
# A@0→N@1 (3); A@6→N@5 (3); N@2,N@4 individual (2×2=4); back=10; mid=14; front=14. total=38
_S2W1B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _N, _F, _N, _N, _A),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S2W1B_IDEAL: int = 38

# S2W2 — A variant: A@1,3,5
_S2W2A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _A, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S2W2A_IDEAL: int = 37

# S2W2 — B variant: A@0,2,4
# A@0→N@1(3); A@2→N@1(gone),N@3(3); A@4→N@3(gone),N@5(3); N@6 individual(2).
# back=11; mid=14; front=14. total=39.
_S2W2B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _A, _N, _A, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S2W2B_IDEAL: int = 39

# S2W3 — A variant: A@0,6 + F@2,4
_S2W3A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _F, _N, _A),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S2W3A_IDEAL: int = 36

# S2W3 — B variant: A@0,6 + F@2
# A@0→N@1 (3); A@6→N@5 (3); N@3,N@4 individual (2×2=4); back=10; mid=14; front=14. total=38
_S2W3B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _A),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S2W3B_IDEAL: int = 38


# ---------------------------------------------------------------------------
# Stage 3 — 3 rows × 7 cols
# ---------------------------------------------------------------------------

# S3W0 — A variant: F@0,6 + A@3
_S3W0A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _N, _A, _N, _N, _F),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S3W0A_IDEAL: int = 35

# S3W0 — B variant: F@0,6 + A@2
# |2-0|=2 ✓, |2-6|=4 ✓
# A@2→N@1,N@3 (3); N@4,N@5 individual (2×2=4); back=7; mid=14; front=14. total=35
_S3W0B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _N, _N, _F),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S3W0B_IDEAL: int = 35

# S3W1 — A variant: A@1,5 + F@3 back; F@2,4 mid; 7N front
_S3W1A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _A, _N),
    (_N, _N, _F, _N, _F, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S3W1A_IDEAL: int = 30

# S3W1 — B variant: A@0,6 + F@3 back; F@1,5 mid; 7N front
# |0-3|=3 ✓, |6-3|=3 ✓
# back: A@0→N@1 (3); A@6→N@5 (3); N@2,N@4 individual (2×2=4); back=10
# mid: F@1,F@5 fall; 5N individual (5×2=10)
# front: 14. total=34
_S3W1B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _N, _F, _N, _N, _A),
    (_N, _F, _N, _N, _N, _F, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S3W1B_IDEAL: int = 34

# S3W2 — A variant: A@1,5 + F@3 back; A@0,6 + F@2,4 mid; 7N front
_S3W2A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _A, _N),
    (_A, _N, _F, _N, _F, _N, _A),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S3W2A_IDEAL: int = 28

# S3W2 — B variant: A@1,5 + F@3 back; A@0,6 + F@2,4 mid (swapped rows from A)
# back (was mid of A): A@0→N@1 (3); A@6→N@5 (3); F@2,4 fall; N@3 individual (2). back=8
# mid (was back of A): A@1→N@0,N@2 (3); A@5→N@4,N@6 (3); F@3 falls. mid=6
# front: 14. total=28
_S3W2B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _F, _N, _A),
    (_N, _A, _N, _F, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S3W2B_IDEAL: int = 28

# S3W3 — A variant: A@2,4 + F@0,6 back; A@3 + F@1,5 mid; A@2,4 + F@0,6 front
_S3W3A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _A, _N, _F),
    (_N, _F, _N, _A, _N, _F, _N),
    (_F, _N, _A, _N, _A, _N, _F),
)
_S3W3A_IDEAL: int = 19

# S3W3 — B variant: F@0,6 + A@2,4 back; F@1,5 + A@3 mid; A@1,5 + F@3 front
# |2-0|=2 ✓, |4-6|=2 ✓, |2-4| — no F between. |3-1|=2 ✓, |3-5|=2 ✓
# back: 2×3=6
# mid: A@3→N@2,N@4 (3); N@0,N@6 individual (2×2=4). mid=7
# front: A@1→N@0,N@2 (3); A@5→N@4,N@6 (3); F@3 falls. front=6
# total=19
_S3W3B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _A, _N, _F),
    (_N, _F, _N, _A, _N, _F, _N),
    (_N, _A, _N, _F, _N, _A, _N),
)
_S3W3B_IDEAL: int = 19


# ---------------------------------------------------------------------------
# Stage 4 — 4 rows × 7 cols
# ---------------------------------------------------------------------------

# S4W0 — A variant: A@1 + gap@3 back; 3×7N
_S4W0A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _X, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S4W0A_IDEAL: int = 51

# S4W0 — B variant: A@5 + gap@3 back; 3×7N (right-skewed)
# A@5→N@4,N@6 (3); N@0,1,2 individual (3×2=6); back=9; 3×14=42. total=51
_S4W0B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _X, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S4W0B_IDEAL: int = 51

# S4W1 — A variant: A@1,5 + F@3 back; F@2,4 mid-1; 2×7N
_S4W1A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _A, _N),
    (_N, _N, _F, _N, _F, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S4W1A_IDEAL: int = 44

# S4W1 — B variant: A@0,6 + F@3 back; F@2,4 mid-1; 2×7N
# A@0→N@1 (3); A@6→N@5 (3); N@2,N@4 individual (2×2=4); back=10
# mid-1: 5N+2F, 5×2=10; 2×14=28. total=48
_S4W1B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _N, _F, _N, _N, _A),
    (_N, _N, _F, _N, _F, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S4W1B_IDEAL: int = 48

# S4W2 — A variant: A@0,6 + F@2,4 back; F@2,4 mid-1; F@1,5 mid-2; 7N front
_S4W2A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _F, _N, _A),
    (_N, _N, _F, _N, _F, _N, _N),
    (_N, _F, _N, _N, _N, _F, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S4W2A_IDEAL: int = 42

# S4W2 — B variant: A@1,5 + F@3 back; F@1,5 mid-1; 2×7N
# back: A@1→N@0,N@2 (3); A@5→N@4,N@6 (3); back=6
# mid-1: F@1,5 fall; 5N individual (5×2=10); 2×14=28. total=44
_S4W2B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _A, _N),
    (_N, _F, _N, _N, _N, _F, _N),
    (_N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N),
)
_S4W2B_IDEAL: int = 44

# S4W3 — A variant: F@0,6+A@2,4 back; A@1,5+F@3 mid-1; F@2,4 mid-2; A@3 front
_S4W3A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _A, _N, _F),
    (_N, _A, _N, _F, _N, _A, _N),
    (_N, _N, _F, _N, _F, _N, _N),
    (_N, _N, _N, _A, _N, _N, _N),
)
_S4W3A_IDEAL: int = 33

# S4W3 — B variant: F@0,6+A@2,4 back; A@1,5+F@3 mid-1; F@2,4 mid-2; A@3 front
# (same structure, different front: A@3 same but different mid-2)
# back: 2×3=6. mid-1: 2×3=6. mid-2: 5×2=10. front: A@3→N@2,N@4(3); N@0,1,5,6(4×2=8)=11.
# total=33
_S4W3B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _A, _N, _F),
    (_N, _A, _N, _F, _N, _A, _N),
    (_N, _N, _F, _N, _F, _N, _N),
    (_N, _N, _N, _A, _N, _N, _N),
)
_S4W3B_IDEAL: int = 33


# ---------------------------------------------------------------------------
# Stage 5 — 4 rows × 9 cols
# ---------------------------------------------------------------------------

# S5W0 — A variant: A@2,6 back; 3×9N
_S5W0A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _A, _N, _N, _N, _A, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S5W0A_IDEAL: int = 66

# S5W0 — B variant: A@3,6 back; 3×9N
# A@3→N@2,N@4 (3); A@6→N@5,N@7 (3); N@0,N@1,N@8 individual (3×2=6); back=12; 3×18=54. total=66
_S5W0B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _A, _N, _N, _A, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S5W0B_IDEAL: int = 66

# S5W1 — A variant: A@1,7 + F@4 back; F@2,6 mid-1; 2×9N
_S5W1A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _N, _F, _N, _N, _A, _N),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S5W1A_IDEAL: int = 58

# S5W1 — B variant: A@0,8 + F@4 back; F@1,7 mid-1; 2×9N
# |0-4|=4 ✓, |8-4|=4 ✓
# back: A@0→N@1 (3); A@8→N@7 (3); N@2,3,5,6 individual (4×2=8); back=14
# mid-1: F@1,7 fall; 7N individual (7×2=14); 2×18=36. total=64
_S5W1B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _N, _N, _F, _N, _N, _N, _A),
    (_N, _F, _N, _N, _N, _N, _N, _F, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S5W1B_IDEAL: int = 64

# S5W2 — A variant: A@0,8 + F@2,6 back; A@1,7 + F@3,5 mid-1; F@2,6 mid-2; 9N front
_S5W2A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _F, _N, _A),
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S5W2A_IDEAL: int = 50

# S5W2 — B variant: A@1,7 + F@3,5 back; F@2,6 mid-1; 2×9N
# |1-3|=2 ✓, |7-5|=2 ✓
# back: A@1→N@0,N@2 (3); A@7→N@6,N@8 (3); F@3,5 fall. back=6
# mid-1: F@2,6 fall; 7N individual (7×2=14); 2×18=36. total=56
_S5W2B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S5W2B_IDEAL: int = 56

# S5W3 — A variant: F@0,4+A@2,6 back; F@1,7+A@3,5 mid-1; F@2,6 mid-2; F@0,8+A@4 front
_S5W3A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _A, _N, _F),
    (_N, _F, _N, _A, _N, _A, _N, _F, _N),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_F, _N, _N, _N, _A, _N, _N, _N, _F),
)
_S5W3A_IDEAL: int = 41

# S5W3 — B variant: F@0,4,8+A@2,6 back; A@3,5+F@1,7 mid-1; F@2,6 mid-2; F@0,8+A@4 front
# |2-0|=2 ✓, |2-4|=2 ✓, |6-4|=2 ✓, |6-8|=2 ✓
# back: A@2→N@1,N@3 (3); A@6→N@5,N@7 (3); back=6
# |3-1|=2 ✓, |5-7|=2 ✓
# mid-1: A@3→N@2,N@4 (3); A@5→N@4(gone),N@6 (3); N@0,N@8 individual (4). mid-1=10
# mid-2: 7N+2F, 7×2=14
# front: A@4→N@3,N@5 (3); N@1,2,6,7 individual (4×2=8). front=11
# total=6+10+14+11=41
_S5W3B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _A, _N, _F),
    (_N, _F, _N, _A, _N, _A, _N, _F, _N),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_F, _N, _N, _N, _A, _N, _N, _N, _F),
)
_S5W3B_IDEAL: int = 41


# ---------------------------------------------------------------------------
# Stage 6 — 5 rows × 9 cols
# ---------------------------------------------------------------------------

# S6W0 — A variant: A@1,7 + F@4 back; 4×9N
_S6W0A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _N, _F, _N, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S6W0A_IDEAL: int = 82

# S6W0 — B variant: A@2,6 + F@4 back; 4×9N
# |2-4|=2 ✓, |6-4|=2 ✓
# back: A@2→N@1,N@3 (3); A@6→N@5,N@7 (3); N@0,N@8 individual (2×2=4); F@4 falls. back=10
# 4×18=72. total=82
_S6W0B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _A, _N, _F, _N, _A, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S6W0B_IDEAL: int = 82

# S6W1 — A variant: A@1,7 + F@3,5 back; F@3,5 mid-1; 3×9N
_S6W1A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S6W1A_IDEAL: int = 74

# S6W1 — B variant: A@0,8 + F@3,5 back; F@3,5 mid-1; 3×9N
# |0-3|=3 ✓, |8-5|=3 ✓
# back: A@0→N@1 (3); A@8→N@7 (3); N@2,N@6 individual (2×2=4); F@3,5 fall. back=10
# mid-1: 7N+2F, 7×2=14; 3×18=54. total=78
_S6W1B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _N, _F, _N, _F, _N, _N, _A),
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S6W1B_IDEAL: int = 78

# S6W2 — A variant: A@0,8 + F@2,6 back; A@1,7 + F@3,5 mid-1; F@2,6 mid-2; 2×9N
_S6W2A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _F, _N, _A),
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S6W2A_IDEAL: int = 68

# S6W2 — B variant: A@0,8 + F@2,6 back; A@1,7 + F@3,5 mid-1; F@2,6 mid-2; 2×9N
# (swapped back/mid-1 from A, same rows in different order)
# back: A@0→N@1(3); A@8→N@7(3); N@3,4,5(3×2=6); F@2,6 fall. back=12
# mid-1: A@1→N@0,N@2(3); A@7→N@6,N@8(3); F@3,5 fall. mid-1=6
# mid-2: 7N+2F, 7×2=14. 2×18=36. total=68
_S6W2B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _F, _N, _A),
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S6W2B_IDEAL: int = 68

# S6W3 — A variant: F@0,4+A@2,6 back; A@3,5+F@1,7 mid-1; F@2,6 mid-2; F@3,5 mid-3; 9N front
_S6W3A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _A, _N, _F),
    (_N, _F, _N, _A, _N, _A, _N, _F, _N),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S6W3A_IDEAL: int = 62

# S6W3 — B variant: same pattern (identical structure)
# back: 2×3=6. mid-1: A@3→N@2,N@4(3); A@5→N@4(gone),N@6(3); N@0,N@8(4). mid-1=10.
# mid-2: 14. mid-3: 14. front: 18. total=62
_S6W3B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _A, _N, _F),
    (_N, _F, _N, _A, _N, _A, _N, _F, _N),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S6W3B_IDEAL: int = 62


# ---------------------------------------------------------------------------
# Stage 7 — 5 rows × 9 cols
# ---------------------------------------------------------------------------

# S7W0 — A variant: F@1,7 back; 4×9N
_S7W0A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _F, _N, _N, _N, _N, _N, _F, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S7W0A_IDEAL: int = 86

# S7W0 — B variant: F@0,8 back (edge-adjacent); 4×9N
# 7N in back, F@0,8 fall. back=7×2=14. 4×18=72. total=86
_S7W0B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _N, _N, _N, _N, _N, _N, _F),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S7W0B_IDEAL: int = 86

# S7W1 — A variant: A@1,7 + F@3,5 back; F@2,6 mid-1; 3×9N
_S7W1A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S7W1A_IDEAL: int = 74

# S7W1 — B variant: A@1,7 + F@3,5 back; F@3,5 mid-1; 3×9N
# back: A@1→N@0,N@2(3); A@7→N@6,N@8(3); back=6
# mid-1: 7N+2F, 7×2=14; 3×18=54. total=74
_S7W1B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S7W1B_IDEAL: int = 74

# S7W2 — A variant: A@0,8 + F@2,6 back; A@1,7 + F@3,5 mid-1; F@2,6 mid-2; F@3,5 mid-3; 9N front
_S7W2A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _F, _N, _A),
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S7W2A_IDEAL: int = 64

# S7W2 — B variant: A@0,8 + F@2,6 back; A@1,7 + F@3,5 mid-1; F@3,5 mid-2; 2×9N
# back: 12. mid-1: 6. mid-2: 7×2=14. 2×18=36. total=68
_S7W2B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _F, _N, _A),
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S7W2B_IDEAL: int = 68

# S7W3 — A variant: F@0,4+A@2,6 back; A@1,7+F@3,5 mid-1; F@0,8+A@4 mid-2; F@2,6 mid-3; A@4 front
_S7W3A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _A, _N, _F),
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_F, _N, _N, _N, _A, _N, _N, _N, _F),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _N, _A, _N, _N, _N, _N),
)
_S7W3A_IDEAL: int = 52

# S7W3 — B variant: F@0,4+A@2,6 back; A@0,8+F@2,6 mid-1; F@0,8+A@4 mid-2; F@2,6 mid-3; 9N front
# back: 2×3=6.
# mid-1: A@0→N@1(3); A@8→N@7(3); N@3,4,5(3×2=6); F@2,6 fall. mid-1=12.
# mid-2: A@4→N@3,N@5(3); N@1,2,6,7(4×2=8). mid-2=11.
# mid-3: 7×2=14. front: 9×2=18. total=6+12+11+14+... wait that is too many rows.
# Use 4 special rows + 1 normal: back+mid-1+mid-2+mid-3+front
# total=6+6+11+14+18=55
_S7W3B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _A, _N, _F),
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_F, _N, _N, _N, _A, _N, _N, _N, _F),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S7W3B_IDEAL: int = 55


# ---------------------------------------------------------------------------
# Stage 8 — 6 rows × 9 cols
# ---------------------------------------------------------------------------

# S8W0 — A variant: A@0 back; 5×9N
_S8W0A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S8W0A_IDEAL: int = 107

# S8W0 — B variant: A@8 back (far-right corner); 5×9N
# A@8→N@7(3); N@0..6(7×2=14). back=17. 5×18=90. total=107
_S8W0B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _N, _N, _N, _N, _N, _A),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S8W0B_IDEAL: int = 107

# S8W1 — A variant: A@1,7 + F@3,5 back; 5×9N
_S8W1A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S8W1A_IDEAL: int = 96

# S8W1 — B variant: A@1,7 + F@3,5 back (centre F variant); 5×9N
# back: A@1→N@0,N@2(3); A@7→N@6,N@8(3); F@3,5 fall. back=6. 5×18=90. total=96
_S8W1B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S8W1B_IDEAL: int = 96

# S8W2 — A variant: A@0,8 + F@2,6 back; A@1,7+F@3,5 mid-1; 4×9N
_S8W2A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _F, _N, _A),
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S8W2A_IDEAL: int = 90

# S8W2 — B variant: A@0,8+F@2,6 back; A@1,7+F@3,5 mid-1 (identical to A — same ideal)
# back: A@0→N@1(3); A@8→N@7(3); N@3,4,5(3×2=6); F@2,6 fall. back=12
# mid-1: A@1→N@0,N@2(3); A@7→N@6,N@8(3); F@3,5 fall. mid-1=6. 4×18=72. total=90
_S8W2B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _F, _N, _A),
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S8W2B_IDEAL: int = 90

# S8W3 — A variant: F@0,4+A@2,6 back; A@1,7+F@3,5 mid-1; F@2,6 mid-2; F@3,5 mid-3; 2×9N
_S8W3A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _A, _N, _F),
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S8W3A_IDEAL: int = 76

# S8W3 — B variant: F@0,4+A@2,6 back; A@1,7+F@3,5 mid-1; F@0,8+A@4 mid-2; F@3,5 mid-3; 2×9N
# back: 2×3=6. mid-1: 2×3=6.
# mid-2: A@4→N@3,N@5(3); N@1,2,6,7(4×2=8). mid-2=11.
# mid-3: 7×2=14. 2×18=36. total=6+6+11+14+36=73
_S8W3B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _A, _N, _F),
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),
    (_F, _N, _N, _N, _A, _N, _N, _N, _F),
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S8W3B_IDEAL: int = 73


# ---------------------------------------------------------------------------
# Stage 9 — 6 rows × 11 cols
# ---------------------------------------------------------------------------

# S9W0 — A variant: F@1,9 + A@5 back; 5×11N
_S9W0A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _F, _N, _N, _N, _A, _N, _N, _N, _F, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S9W0A_IDEAL: int = 125

# S9W0 — B variant: F@1,9 + A@4 back; 5×11N
# |4-1|=3 ✓, |4-9|=5 ✓
# A@4→N@3,N@5(3); N@0,N@2,N@6,N@7,N@8,N@10(6×2=12); F@1,9 fall. back=15. 5×22=110. total=125
_S9W0B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _F, _N, _N, _A, _N, _N, _N, _N, _F, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S9W0B_IDEAL: int = 125

# S9W1 — A variant: A@1,9 + F@4,6 back; 5×11N
_S9W1A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _N, _F, _N, _F, _N, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S9W1A_IDEAL: int = 120

# S9W1 — B variant: A@0,10 + F@4,6 back; 5×11N
# |0-4|=4 ✓, |10-6|=4 ✓
# A@0→N@1(3); A@10→N@9(3); N@2,3,7,8(4×2=8); F@4,6 fall. back=14. 5×22=110. total=124
_S9W1B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _N, _N, _F, _N, _F, _N, _N, _N, _A),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S9W1B_IDEAL: int = 124

# S9W2 — A variant: A@0,10 + F@2,8 back; A@2,8 + F@4,6 mid-1; 4×11N
_S9W2A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _N, _N, _F, _N, _A),
    (_N, _N, _A, _N, _F, _N, _F, _N, _A, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S9W2A_IDEAL: int = 110

# S9W2 — B variant: A@0,10 + F@2,8 back; A@2,8 + F@4,6 mid-1; 4×11N
# back: A@0→N@1(3); A@10→N@9(3); N@3,4,5,6(4×2=8); F@2,8 fall. back=14.
# mid-1: A@2→N@1,N@3(3); A@8→N@7,N@9(3); F@4,6 fall. mid-1=6. 4×22=88. total=108
_S9W2B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _N, _N, _F, _N, _A),
    (_N, _N, _A, _N, _F, _N, _F, _N, _A, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S9W2B_IDEAL: int = 108

# S9W3 — A variant: F@0,4,6,10 + A@2,8 back; A@2,8 + F@4,6 mid-1; F@2,8 mid-2; F@3,6 mid-3; 2×11N
_S9W3A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _F, _N, _A, _N, _F),
    (_N, _N, _A, _N, _F, _N, _F, _N, _A, _N, _N),
    (_N, _N, _F, _N, _N, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _F, _N, _N, _F, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S9W3A_IDEAL: int = 92

# S9W3 — B variant: F@0,4,6,10 + A@2,8 back; A@2,8+F@4,6 mid-1; F@2,8 mid-2; F@3,6 mid-3; 2×11N
# back: A@2→N@1,N@3(3); A@8→N@7,N@9(3). back=6.
# mid-1: A@2→N@1,N@3(3); A@8→N@7,N@9(3); F@4,6 fall. mid-1=6.
# mid-2: 9×2=18. mid-3: 9×2=18. 2×22=44. total=92
_S9W3B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _F, _N, _A, _N, _F),
    (_N, _N, _A, _N, _F, _N, _F, _N, _A, _N, _N),
    (_N, _N, _F, _N, _N, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _F, _N, _N, _F, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S9W3B_IDEAL: int = 92


# ---------------------------------------------------------------------------
# Stage 10 — 7 rows × 11 cols
# ---------------------------------------------------------------------------

# S10W0 — A variant: A@2,5,8 back; 6×11N
_S10W0A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _A, _N, _N, _A, _N, _N, _A, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S10W0A_IDEAL: int = 145

# S10W0 — B variant: A@1,4,6,9 back; 6×11N
# A@1→N@0,N@2(3); A@4→N@3,N@5(3); A@6→N@5(gone),N@7(3); A@9→N@8,N@10(3).
# back=12; 6×22=132. total=144.
_S10W0B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _N, _A, _N, _A, _N, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S10W0B_IDEAL: int = 144

# S10W1 — A variant: A@1,9 + F@4,6 back; 6×11N
_S10W1A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _N, _F, _N, _F, _N, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S10W1A_IDEAL: int = 142

# S10W1 — B variant: A@1,9 + F@4,6 back (same layout, different ideal due to cols)
# A@1→N@0,N@2(3); A@9→N@8,N@10(3); N@3,7(2×2=4); F@4,6 fall. back=10. 6×22=132. total=142
_S10W1B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _N, _F, _N, _F, _N, _N, _A, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S10W1B_IDEAL: int = 142

# S10W2 — A variant: A@0,10 + F@2,8 back; A@2,8 + F@4,6 mid-1; 5×11N
_S10W2A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _N, _N, _F, _N, _A),
    (_N, _N, _A, _N, _F, _N, _F, _N, _A, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S10W2A_IDEAL: int = 132

# S10W2 — B variant: A@0,10 + F@2,8 back; A@2,8 + F@4,6 mid-1; 5×11N
# back: A@0→N@1(3); A@10→N@9(3); N@3,4,5,6(4×2=8); F@2,8 fall. back=14.
# mid-1: A@2→N@1,N@3(3); A@8→N@7,N@9(3); F@4,6 fall. mid-1=6. 5×22=110. total=130
_S10W2B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _N, _N, _F, _N, _A),
    (_N, _N, _A, _N, _F, _N, _F, _N, _A, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S10W2B_IDEAL: int = 130

# S10W3 — A variant: F@0,4,6,10+A@2,8 back; A@2,8+F@4,6 mid-1; F@2,8 mid-2; F@3,6 mid-3; 3×11N
_S10W3A_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _F, _N, _A, _N, _F),
    (_N, _N, _A, _N, _F, _N, _F, _N, _A, _N, _N),
    (_N, _N, _F, _N, _N, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _F, _N, _N, _F, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S10W3A_IDEAL: int = 114

# S10W3 — B variant: same layout as A (identical structure, same ideal)
# back: 2×3=6. mid-1: 2×3=6. mid-2: 9×2=18. mid-3: 9×2=18. 3×22=66. total=114
_S10W3B_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _F, _N, _A, _N, _F),
    (_N, _N, _A, _N, _F, _N, _F, _N, _A, _N, _N),
    (_N, _N, _F, _N, _N, _N, _N, _N, _F, _N, _N),
    (_N, _N, _N, _F, _N, _N, _F, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),
)
_S10W3B_IDEAL: int = 114


# ---------------------------------------------------------------------------
# WAVE_POOLS — keyed by pool name "S{stage}W{slot}"
# Each pool is a tuple of exactly 2 WaveData objects: (A variant, B variant)
# ---------------------------------------------------------------------------

WAVE_POOLS: dict[str, tuple[WaveData, ...]] = {
    # Stage 1
    "S1W0": (WaveData("S1W0A", _S1W0A_ROWS, _S1W0A_IDEAL),
             WaveData("S1W0B", _S1W0B_ROWS, _S1W0B_IDEAL)),
    "S1W1": (WaveData("S1W1A", _S1W1A_ROWS, _S1W1A_IDEAL),
             WaveData("S1W1B", _S1W1B_ROWS, _S1W1B_IDEAL)),
    "S1W2": (WaveData("S1W2A", _S1W2A_ROWS, _S1W2A_IDEAL),
             WaveData("S1W2B", _S1W2B_ROWS, _S1W2B_IDEAL)),
    "S1W3": (WaveData("S1W3A", _S1W3A_ROWS, _S1W3A_IDEAL),
             WaveData("S1W3B", _S1W3B_ROWS, _S1W3B_IDEAL)),
    # Stage 2
    "S2W0": (WaveData("S2W0A", _S2W0A_ROWS, _S2W0A_IDEAL),
             WaveData("S2W0B", _S2W0B_ROWS, _S2W0B_IDEAL)),
    "S2W1": (WaveData("S2W1A", _S2W1A_ROWS, _S2W1A_IDEAL),
             WaveData("S2W1B", _S2W1B_ROWS, _S2W1B_IDEAL)),
    "S2W2": (WaveData("S2W2A", _S2W2A_ROWS, _S2W2A_IDEAL),
             WaveData("S2W2B", _S2W2B_ROWS, _S2W2B_IDEAL)),
    "S2W3": (WaveData("S2W3A", _S2W3A_ROWS, _S2W3A_IDEAL),
             WaveData("S2W3B", _S2W3B_ROWS, _S2W3B_IDEAL)),
    # Stage 3
    "S3W0": (WaveData("S3W0A", _S3W0A_ROWS, _S3W0A_IDEAL),
             WaveData("S3W0B", _S3W0B_ROWS, _S3W0B_IDEAL)),
    "S3W1": (WaveData("S3W1A", _S3W1A_ROWS, _S3W1A_IDEAL),
             WaveData("S3W1B", _S3W1B_ROWS, _S3W1B_IDEAL)),
    "S3W2": (WaveData("S3W2A", _S3W2A_ROWS, _S3W2A_IDEAL),
             WaveData("S3W2B", _S3W2B_ROWS, _S3W2B_IDEAL)),
    "S3W3": (WaveData("S3W3A", _S3W3A_ROWS, _S3W3A_IDEAL),
             WaveData("S3W3B", _S3W3B_ROWS, _S3W3B_IDEAL)),
    # Stage 4
    "S4W0": (WaveData("S4W0A", _S4W0A_ROWS, _S4W0A_IDEAL),
             WaveData("S4W0B", _S4W0B_ROWS, _S4W0B_IDEAL)),
    "S4W1": (WaveData("S4W1A", _S4W1A_ROWS, _S4W1A_IDEAL),
             WaveData("S4W1B", _S4W1B_ROWS, _S4W1B_IDEAL)),
    "S4W2": (WaveData("S4W2A", _S4W2A_ROWS, _S4W2A_IDEAL),
             WaveData("S4W2B", _S4W2B_ROWS, _S4W2B_IDEAL)),
    "S4W3": (WaveData("S4W3A", _S4W3A_ROWS, _S4W3A_IDEAL),
             WaveData("S4W3B", _S4W3B_ROWS, _S4W3B_IDEAL)),
    # Stage 5
    "S5W0": (WaveData("S5W0A", _S5W0A_ROWS, _S5W0A_IDEAL),
             WaveData("S5W0B", _S5W0B_ROWS, _S5W0B_IDEAL)),
    "S5W1": (WaveData("S5W1A", _S5W1A_ROWS, _S5W1A_IDEAL),
             WaveData("S5W1B", _S5W1B_ROWS, _S5W1B_IDEAL)),
    "S5W2": (WaveData("S5W2A", _S5W2A_ROWS, _S5W2A_IDEAL),
             WaveData("S5W2B", _S5W2B_ROWS, _S5W2B_IDEAL)),
    "S5W3": (WaveData("S5W3A", _S5W3A_ROWS, _S5W3A_IDEAL),
             WaveData("S5W3B", _S5W3B_ROWS, _S5W3B_IDEAL)),
    # Stage 6
    "S6W0": (WaveData("S6W0A", _S6W0A_ROWS, _S6W0A_IDEAL),
             WaveData("S6W0B", _S6W0B_ROWS, _S6W0B_IDEAL)),
    "S6W1": (WaveData("S6W1A", _S6W1A_ROWS, _S6W1A_IDEAL),
             WaveData("S6W1B", _S6W1B_ROWS, _S6W1B_IDEAL)),
    "S6W2": (WaveData("S6W2A", _S6W2A_ROWS, _S6W2A_IDEAL),
             WaveData("S6W2B", _S6W2B_ROWS, _S6W2B_IDEAL)),
    "S6W3": (WaveData("S6W3A", _S6W3A_ROWS, _S6W3A_IDEAL),
             WaveData("S6W3B", _S6W3B_ROWS, _S6W3B_IDEAL)),
    # Stage 7
    "S7W0": (WaveData("S7W0A", _S7W0A_ROWS, _S7W0A_IDEAL),
             WaveData("S7W0B", _S7W0B_ROWS, _S7W0B_IDEAL)),
    "S7W1": (WaveData("S7W1A", _S7W1A_ROWS, _S7W1A_IDEAL),
             WaveData("S7W1B", _S7W1B_ROWS, _S7W1B_IDEAL)),
    "S7W2": (WaveData("S7W2A", _S7W2A_ROWS, _S7W2A_IDEAL),
             WaveData("S7W2B", _S7W2B_ROWS, _S7W2B_IDEAL)),
    "S7W3": (WaveData("S7W3A", _S7W3A_ROWS, _S7W3A_IDEAL),
             WaveData("S7W3B", _S7W3B_ROWS, _S7W3B_IDEAL)),
    # Stage 8
    "S8W0": (WaveData("S8W0A", _S8W0A_ROWS, _S8W0A_IDEAL),
             WaveData("S8W0B", _S8W0B_ROWS, _S8W0B_IDEAL)),
    "S8W1": (WaveData("S8W1A", _S8W1A_ROWS, _S8W1A_IDEAL),
             WaveData("S8W1B", _S8W1B_ROWS, _S8W1B_IDEAL)),
    "S8W2": (WaveData("S8W2A", _S8W2A_ROWS, _S8W2A_IDEAL),
             WaveData("S8W2B", _S8W2B_ROWS, _S8W2B_IDEAL)),
    "S8W3": (WaveData("S8W3A", _S8W3A_ROWS, _S8W3A_IDEAL),
             WaveData("S8W3B", _S8W3B_ROWS, _S8W3B_IDEAL)),
    # Stage 9
    "S9W0": (WaveData("S9W0A", _S9W0A_ROWS, _S9W0A_IDEAL),
             WaveData("S9W0B", _S9W0B_ROWS, _S9W0B_IDEAL)),
    "S9W1": (WaveData("S9W1A", _S9W1A_ROWS, _S9W1A_IDEAL),
             WaveData("S9W1B", _S9W1B_ROWS, _S9W1B_IDEAL)),
    "S9W2": (WaveData("S9W2A", _S9W2A_ROWS, _S9W2A_IDEAL),
             WaveData("S9W2B", _S9W2B_ROWS, _S9W2B_IDEAL)),
    "S9W3": (WaveData("S9W3A", _S9W3A_ROWS, _S9W3A_IDEAL),
             WaveData("S9W3B", _S9W3B_ROWS, _S9W3B_IDEAL)),
    # Stage 10
    "S10W0": (WaveData("S10W0A", _S10W0A_ROWS, _S10W0A_IDEAL),
              WaveData("S10W0B", _S10W0B_ROWS, _S10W0B_IDEAL)),
    "S10W1": (WaveData("S10W1A", _S10W1A_ROWS, _S10W1A_IDEAL),
              WaveData("S10W1B", _S10W1B_ROWS, _S10W1B_IDEAL)),
    "S10W2": (WaveData("S10W2A", _S10W2A_ROWS, _S10W2A_IDEAL),
              WaveData("S10W2B", _S10W2B_ROWS, _S10W2B_IDEAL)),
    "S10W3": (WaveData("S10W3A", _S10W3A_ROWS, _S10W3A_IDEAL),
              WaveData("S10W3B", _S10W3B_ROWS, _S10W3B_IDEAL)),
}

# ---------------------------------------------------------------------------
# STAGE_POOL_SLOTS — 10 stages × 4 wave slots each
# ---------------------------------------------------------------------------

STAGE_POOL_SLOTS: tuple[tuple[str, str, str, str], ...] = (
    ("S1W0", "S1W1", "S1W2", "S1W3"),    # Stage 1
    ("S2W0", "S2W1", "S2W2", "S2W3"),    # Stage 2
    ("S3W0", "S3W1", "S3W2", "S3W3"),    # Stage 3
    ("S4W0", "S4W1", "S4W2", "S4W3"),    # Stage 4
    ("S5W0", "S5W1", "S5W2", "S5W3"),    # Stage 5
    ("S6W0", "S6W1", "S6W2", "S6W3"),    # Stage 6
    ("S7W0", "S7W1", "S7W2", "S7W3"),    # Stage 7
    ("S8W0", "S8W1", "S8W2", "S8W3"),    # Stage 8
    ("S9W0", "S9W1", "S9W2", "S9W3"),    # Stage 9
    ("S10W0", "S10W1", "S10W2", "S10W3"),  # Stage 10
)


def select_all_waves(rng: _random.Random) -> tuple[tuple[WaveData, ...], ...]:
    """Select one WaveData per slot for every stage.

    Returns a tuple of 10 stage-wave tuples. Each inner tuple has 4 WaveData
    objects, one per wave slot, randomly selected from the slot's pool.
    Called once at game start; the selection is fixed for the entire run.
    The caller passes an explicit rng (random.Random) so tests can seed it.
    """
    result: list[tuple[WaveData, ...]] = []
    assert len(STAGE_POOL_SLOTS) == 10, "STAGE_POOL_SLOTS must have 10 entries"
    for stage_slots in STAGE_POOL_SLOTS:
        stage_waves: list[WaveData] = []
        for pool_key in stage_slots:
            pool = WAVE_POOLS[pool_key]
            assert len(pool) >= 1, f"pool {pool_key!r} is empty"
            stage_waves.append(rng.choice(pool))
        assert len(stage_waves) == 4, f"stage must have 4 waves, got {len(stage_waves)}"
        result.append(tuple(stage_waves))
    assert len(result) == 10, "select_all_waves must return 10 stage-wave tuples"
    return tuple(result)


# ---------------------------------------------------------------------------
# STAGES: backward-compat tuple using the A-variant waves only.
# Used by code that hasn't been updated to use select_all_waves yet.
# Will be removed once all callers switch to select_all_waves.
# ---------------------------------------------------------------------------

STAGES: tuple[tuple[WaveData, ...], ...] = tuple(
    tuple(WAVE_POOLS[slot][0] for slot in stage_slots)
    for stage_slots in STAGE_POOL_SLOTS
)
