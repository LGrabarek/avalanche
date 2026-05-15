"""Wave patterns for all 10 stages — hand-designed puzzle rows.

Each WaveData holds:
  * `rows`: tuple of rows ordered back → front (row 0 is the back-most row
    of the wave, row 1 is one step closer to the player, etc.).
    Each row is a tuple of `row_width` entries: CubeType | None, where
    row_width matches the active grid width for that stage (7, 9, or 11).
  * `ideal_steps`: minimum input actions (marks + triggers + detonates) to
    achieve a Perfect outcome, pre-computed offline and embedded here. The
    original game calls these the "Ideal Step" values; the research document
    (Research/Intelligent Qube Technical Reproduction Research.md §Heuristics)
    explains how they were baked into the Group.Dat puzzle data to avoid a
    costly BFS at runtime.

Mirror flag: at spawn time the caller rolls a 50% check and passes the result
to `spawn_positions(mirror=…)`. A mirrored wave reverses the X-axis, doubling
effective variety without extra data — exactly what Group.Dat does.

Step 28 note: `spawn_positions` accepts a `z_start` keyword overriding the
default back-wall placement.  GameManager._spawn_all_waves_pending uses
`_compute_wave_z_starts` to place every wave.

Step 33 stage layout (GRID_DEPTH=60, WAVE_GAP_ROWS=0):
  All stages: 4 waves.  Waves are BACK-PACKED from z=59 (GRID_DEPTH-1) toward
  the player.  Wave 3 always has its back row at z=59; wave 0 is closest to
  the player.  z_back values below are the back row of each wave [0..3].
  Rows/wave and active width follow STAGE_ROWS_PER_WAVE / STAGE_GRID_WIDTHS.

  Stage 1:  4w × 2r × 7col  z_back[0..3] = 53,55,57,59
  Stage 2:  4w × 3r × 7col  z_back[0..3] = 50,53,56,59
  Stage 3:  4w × 3r × 7col  (same packing as Stage 2)
  Stage 4:  4w × 4r × 7col  z_back[0..3] = 47,51,55,59
  Stage 5:  4w × 4r × 9col  (same packing as Stage 4)
  Stage 6:  4w × 5r × 9col  z_back[0..3] = 44,49,54,59
  Stage 7:  4w × 5r × 9col  (same packing as Stage 6)
  Stage 8:  4w × 6r × 9col  z_back[0..3] = 41,47,53,59
  Stage 9:  4w × 6r × 11col (same packing as Stage 8)
  Stage 10: 4w × 7r × 11col z_back[0..3] = 38,45,52,59  (≤ GRID_DEPTH-1 ✓)

ADVANTAGE blast safety rule: in any row, an ADVANTAGE cube and a FORBIDDEN
cube must be at least 2 columns apart so the ±1-column same-row blast never
captures a FORBIDDEN cube unintentionally (capturing FORBIDDEN triggers a
row-delete penalty).  All rows in this module obey that constraint.

Ideal-step formula:
  * Each standalone NORMAL cube:      2 steps  (mark + trigger)
  * Each ADVANTAGE + detonate:        3 steps  (mark + trigger + Z)
    Blast catches cubes ±1 col in the SAME ROW only; adjacent rows are not
    affected in ideal-play calculations.
  * FORBIDDEN cubes:                  0 steps  (let fall off the edge)
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

# Stage 1 waves — 2 rows per wave.  Row 0 is the back-most (furthest from
# player); row 1 is one step closer.  All rows are fully filled (7 wide).

# Wave 1 — Intro.  Both rows solid NORMAL; no blasting possible.
# Optimal: 14 × 2 (mark + trigger each) = 28 steps.
_W1_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _N, _N, _N, _N),   # row 0 (back)  — 7 NORMAL
    (_N, _N, _N, _N, _N, _N, _N),   # row 1 (front) — 7 NORMAL
)
_W1_IDEAL: int = 28

# Wave 2 — First ADVANTAGE at col 3 (back row centre).  Blast catches cols
# 2 & 4; 4 NORMAL in back row and 7 in front row captured individually.
# Optimal: 3 (ADV+detonate) + 4×2 (back) + 7×2 (front) = 25.
_W2_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _A, _N, _N, _N),   # row 0 (back)  — 6 NORMAL + 1 ADVANTAGE
    (_N, _N, _N, _N, _N, _N, _N),   # row 1 (front) — 7 NORMAL
)
_W2_IDEAL: int = 25

# Wave 3 — FORBIDDEN introduced.  ADVANTAGE at cols 1 & 5 in back row.
# Both blasts sweep the outer 2 columns; FORBIDDEN let fall off.
# Front row all-NORMAL captured individually.
# Optimal: 2×3 (ADV+detonate) + 7×2 (front row) = 20.
_W3_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _A, _N),   # row 0 (back)  — 4 NORMAL + 2 ADV + 1 FORBIDDEN
    (_N, _N, _N, _N, _N, _N, _N),   # row 1 (front) — 7 NORMAL
)
_W3_IDEAL: int = 20

# Wave 4 — Full challenge.  ADVANTAGE at corners (cols 0, 6); FORBIDDEN at
# cols 2 & 4.  Corner blasts each catch 1 flanking NORMAL; col 3 NORMAL and
# entire front row captured individually.
# Optimal: 2×3 (ADV+detonate) + 1×2 (col 3) + 7×2 (front row) = 26.
_W4_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _F, _N, _A),   # row 0 (back)  — 3 NORMAL + 2 ADV + 2 FORBIDDEN
    (_N, _N, _N, _N, _N, _N, _N),   # row 1 (front) — 7 NORMAL
)
_W4_IDEAL: int = 26


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
        # Step 32: rows may be narrower than GRID_WIDTH (e.g. 7-wide for stages 1–4,
        # 9-wide for stages 5–8, 11-wide for stages 9–10). Validate that:
        #   1. every row has the same width (pattern integrity), and
        #   2. that width is within [1, GRID_WIDTH] (fits in the grid).
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
        self._rows: tuple[tuple[CubeType | None, ...], ...] = rows
        self._ideal_steps: int = ideal_steps

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
        """Return `(grid_x, grid_z, cube_type)` for every cube in the wave.

        `z_start`, when given, is the z coordinate of row 0 (the back-most
        row).  Row 1 maps to `z_start - 1`, row 2 to `z_start - 2`, etc.
        When omitted, row 0 defaults to `GRID_DEPTH - 1` (original behaviour).

        If `mirror` is True the X-axis is flipped so column 0 becomes column
        GRID_WIDTH-1 and vice-versa, doubling the effective pattern count
        without extra data.
        """
        if z_start is not None and not (0 <= z_start < GRID_DEPTH):
            raise ValueError(
                f"z_start {z_start} outside [0, {GRID_DEPTH})"
            )
        positions: list[tuple[int, int, CubeType]] = []
        # Step 32: row width may be 7, 9, or 11 — use actual width for both the
        # mirror flip and the theoretical-maximum bound, not the module-level
        # GRID_WIDTH constant (which is now 11, the largest possible width).
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
# Stage 2 ramps up density and ADVANTAGE/FORBIDDEN interplay.  Each wave
# has 3 rows (back, middle, front).  Ideal-step counts assume efficient
# blast chaining on the back row; the two dense front rows are captured
# individually.  Adding one 7-NORMAL row costs 7×2 = 14 extra steps vs
# the equivalent 2-row Stage-1 version.
# ---------------------------------------------------------------------------

# Wave S2-1 — FORBIDDEN introduced early.  ADVANTAGE at col 2 (back row)
# with FORBIDDEN at col 5 (distance 3 — safe from the ±1 blast).
# Blast A@col2: col1+col2+col3 = 3 steps.  Remaining back N: col0,col4,col6 = 3×2.
# Optimal: 3 (ADV+detonate) + 3×2 (remaining back N) + 7×2 (mid) + 7×2 (front) = 37.
_S2W1_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _A, _N, _N, _F, _N),   # row 0 (back)   — 4 NORMAL + 1 ADVANTAGE + 1 FORBIDDEN
    (_N, _N, _N, _N, _N, _N, _N),   # row 1 (middle) — 7 NORMAL
    (_N, _N, _N, _N, _N, _N, _N),   # row 2 (front)  — 7 NORMAL
)
_S2W1_IDEAL: int = 37

# Wave S2-2 — Two ADVANTAGE flanking a centre FORBIDDEN (back row); two
# dense rows follow.  Both ADV blasts sweep the outer halves of the back row.
# Optimal: 2×3 (ADV+detonate) + 2×2 (remaining back N) + 7×2 (mid) + 7×2 (front) = 32.
_S2W2_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _A, _N),   # row 0 (back)   — 4 NORMAL + 2 ADVANTAGE + 1 FORBIDDEN
    (_N, _N, _N, _N, _N, _N, _N),   # row 1 (middle) — 7 NORMAL
    (_N, _N, _N, _N, _N, _N, _N),   # row 2 (front)  — 7 NORMAL
)
_S2W2_IDEAL: int = 32

# Wave S2-3 — Three ADVANTAGE spread across the back row; each blast sweeps
# its ±1 neighbours, covering all 4 inter-A Normals.  Two dense rows follow.
# Blast A@col1,col3,col5: 3×3=9 steps; all back-row N caught in blasts (0 remaining).
# Optimal: 3×3 (ADV+detonate) + 0 remaining back N + 7×2 (mid) + 7×2 (front) = 37.
_S2W3_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _A, _N, _A, _N),   # row 0 (back)   — 4 NORMAL + 3 ADVANTAGE
    (_N, _N, _N, _N, _N, _N, _N),   # row 1 (middle) — 7 NORMAL
    (_N, _N, _N, _N, _N, _N, _N),   # row 2 (front)  — 7 NORMAL
)
_S2W3_IDEAL: int = 37

# Wave S2-4 — Full 3-row challenge.  ADVANTAGE at corners with two FORBIDDEN
# in the middle (back row); two dense rows follow.  Corner ADV blasts each
# catch 1 flanking NORMAL; col 3 NORMAL and both dense rows captured individually.
# Optimal: 2×3 (ADV+detonate) + 1×2 (col 3 N) + 7×2 (mid) + 7×2 (front) = 36.
_S2W4_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _F, _N, _A),   # row 0 (back)   — 3 NORMAL + 2 ADVANTAGE + 2 FORBIDDEN
    (_N, _N, _N, _N, _N, _N, _N),   # row 1 (middle) — 7 NORMAL
    (_N, _N, _N, _N, _N, _N, _N),   # row 2 (front)  — 7 NORMAL
)
_S2W4_IDEAL: int = 36


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
# Stage 3 — 4 waves × 3 rows × 7 cols  (same packing as Stage 2)
# ---------------------------------------------------------------------------
# Same grid width and row count as Stage 2 but harder patterns: more FORBIDDEN
# density and tighter ADVANTAGE chains.  Stage-2 Wave-4's back row pattern
# (corner ADV + inner FORBIDDEN) opens as the Stage-3 intro wave.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Stage 3 wave data — 3 rows × 7 cols  (same grid as Stage 2, harder patterns)
# ---------------------------------------------------------------------------
# Stage-2 Wave-4's back-row pattern opens Stage 3; FORBIDDEN spreads into the
# middle row from Wave 3 onward, and Wave 4 chains ADVANTAGE blasts in all rows.
# Ideal steps: 36 → 30 → 28 → 19  (decreasing = harder routing each wave).
# ---------------------------------------------------------------------------

# S3-W1 — Corner A + inner F in back; two dense NORMAL rows.
# Row 0: A@0→N@1; A@6→N@5; N@3 individual. 2×3+1×2=8.
# Rows 1–2: 7N each. ideal = 8+14+14 = 36.
_S3W1_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _F, _N, _A),   # row 0 (back)   — 3N + 2A + 2F
    (_N, _N, _N, _N, _N, _N, _N),   # row 1 (middle) — 7N
    (_N, _N, _N, _N, _N, _N, _N),   # row 2 (front)  — 7N
)
_S3W1_IDEAL: int = 36

# S3-W2 — Flanking A + centre F in back; symmetric inner F in middle.
# Row 0: A@1→N@0,N@2; A@5→N@4,N@6; F@3 falls. 2×3=6.
# Row 1: 5N+2F. 5×2=10.  Row 2: 7N. ideal = 6+10+14 = 30.
_S3W2_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _A, _N),   # row 0 (back)   — 4N + 2A + 1F
    (_N, _N, _F, _N, _F, _N, _N),   # row 1 (middle) — 5N + 2F
    (_N, _N, _N, _N, _N, _N, _N),   # row 2 (front)  — 7N
)
_S3W2_IDEAL: int = 30

# S3-W3 — Corner A + inner F in back; flanking A in middle (clears all).
# Row 0: 2×3+1×2=8.  Row 1: A@1→N@0,N@2; A@5→N@4,N@6; F@3 falls. 2×3=6.
# Row 2: 7N. ideal = 8+6+14 = 28.
_S3W3_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _F, _N, _A),   # row 0 (back)   — 3N + 2A + 2F
    (_N, _A, _N, _F, _N, _A, _N),   # row 1 (middle) — 4N + 2A + 1F
    (_N, _N, _N, _N, _N, _N, _N),   # row 2 (front)  — 7N
)
_S3W3_IDEAL: int = 28

# S3-W4 — FORBIDDEN in all rows; double-A blast in back and front clears all N.
# Row 0: F,A@2,A@4,F; A@2→N@1,N@3; A@4→N@5; 2×3=6.
# Row 1: A@3→N@2,N@4; N@0,N@6 individual; F@1,F@5 fall. 3+2×2=7.
# Row 2: same as row 0. 2×3=6. ideal = 6+7+6 = 19.
_S3W4_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _A, _N, _F),   # row 0 (back)   — 3N + 2A + 2F
    (_N, _F, _N, _A, _N, _F, _N),   # row 1 (middle) — 4N + 1A + 2F
    (_F, _N, _A, _N, _A, _N, _F),   # row 2 (front)  — 3N + 2A + 2F
)
_S3W4_IDEAL: int = 19

# ---------------------------------------------------------------------------
# Stage 3 wave sequence
# ---------------------------------------------------------------------------

STAGE_3_WAVES: tuple[WaveData, ...] = (
    WaveData(_S3W1_ROWS, _S3W1_IDEAL),
    WaveData(_S3W2_ROWS, _S3W2_IDEAL),
    WaveData(_S3W3_ROWS, _S3W3_IDEAL),
    WaveData(_S3W4_ROWS, _S3W4_IDEAL),
)


# ---------------------------------------------------------------------------
# Stage 4 wave data — 4 rows × 7 cols
# ---------------------------------------------------------------------------
# A fourth row per wave adds 14 more NORMAL captures.  FORBIDDEN spreads into
# the middle rows; the final wave chains double-A blasts in every row.
# Ideal steps: 53 → 44 → 42 → 33  (decreasing).
# ---------------------------------------------------------------------------

# S4-W1 — Centre A in back; three dense NORMAL rows.
# Row 0: A@3→N@2,N@4; N@0,N@1,N@5,N@6 individual. 3+4×2=11.
# Rows 1–3: 7N each. ideal = 11+14+14+14 = 53.
_S4W1_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _A, _N, _N, _N),   # row 0 (back)   — 6N + 1A
    (_N, _N, _N, _N, _N, _N, _N),   # row 1 (mid 1)  — 7N
    (_N, _N, _N, _N, _N, _N, _N),   # row 2 (mid 2)  — 7N
    (_N, _N, _N, _N, _N, _N, _N),   # row 3 (front)  — 7N
)
_S4W1_IDEAL: int = 53

# S4-W2 — Flanking A + centre F in back; symmetric inner F in mid-1.
# Row 0: 2×3=6.  Row 1: 5×2=10.  Rows 2–3: 14 each. ideal = 6+10+14+14 = 44.
_S4W2_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _A, _N),   # row 0 (back)   — 4N + 2A + 1F
    (_N, _N, _F, _N, _F, _N, _N),   # row 1 (mid 1)  — 5N + 2F
    (_N, _N, _N, _N, _N, _N, _N),   # row 2 (mid 2)  — 7N
    (_N, _N, _N, _N, _N, _N, _N),   # row 3 (front)  — 7N
)
_S4W2_IDEAL: int = 44

# S4-W3 — Corner A + inner F in back; symmetric F pairs in mid rows.
# Row 0: 2×3+1×2=8.  Row 1: 5×2=10.  Row 2: 5×2=10.  Row 3: 7×2=14.
# ideal = 8+10+10+14 = 42.
_S4W3_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _F, _N, _A),   # row 0 (back)   — 3N + 2A + 2F
    (_N, _N, _F, _N, _F, _N, _N),   # row 1 (mid 1)  — 5N + 2F
    (_N, _F, _N, _N, _N, _F, _N),   # row 2 (mid 2)  — 5N + 2F
    (_N, _N, _N, _N, _N, _N, _N),   # row 3 (front)  — 7N
)
_S4W3_IDEAL: int = 42

# S4-W4 — Double-A blast in back + mid-1; F throughout; centre A in front.
# Row 0: F,A@2,A@4,F — 2×3=6 (all N cleared by blasts).
# Row 1: A@1→N@0,N@2; A@5→N@4,N@6; F@3 falls. 2×3=6.
# Row 2: 5×2=10.  Row 3: A@3→N@2,N@4; 6 individual N. 3+4×2=11.
# ideal = 6+6+10+11 = 33.
_S4W4_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _A, _N, _F),   # row 0 (back)   — 3N + 2A + 2F
    (_N, _A, _N, _F, _N, _A, _N),   # row 1 (mid 1)  — 4N + 2A + 1F
    (_N, _N, _F, _N, _F, _N, _N),   # row 2 (mid 2)  — 5N + 2F
    (_N, _N, _N, _A, _N, _N, _N),   # row 3 (front)  — 6N + 1A
)
_S4W4_IDEAL: int = 33

# ---------------------------------------------------------------------------
# Stage 4 wave sequence
# ---------------------------------------------------------------------------

STAGE_4_WAVES: tuple[WaveData, ...] = (
    WaveData(_S4W1_ROWS, _S4W1_IDEAL),
    WaveData(_S4W2_ROWS, _S4W2_IDEAL),
    WaveData(_S4W3_ROWS, _S4W3_IDEAL),
    WaveData(_S4W4_ROWS, _S4W4_IDEAL),
)


# ---------------------------------------------------------------------------
# Stage 5 wave data — 4 rows × 9 cols  (grid widens to 9 for the first time)
# ---------------------------------------------------------------------------
# Player spawn moves to col 4 (grid.width//2). Camera centre shifts to x=4.
# Ideal steps: 69 → 58 → 50 → 41  (decreasing).
# Row-width aliases for clarity: cols are 0–8.
# ---------------------------------------------------------------------------

# S5-W1 — Centre A in back; three dense 9-wide NORMAL rows.
# Row 0: A@4→N@3,N@5; N@0,N@1,N@2,N@6,N@7,N@8 individual. 3+6×2=15.
# Rows 1–3: 9N each. ideal = 15+18+18+18 = 69.
_S5W1_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _N, _A, _N, _N, _N, _N),   # row 0 (back)   — 8N + 1A
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 1 (mid 1)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 2 (mid 2)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 3 (front)  — 9N
)
_S5W1_IDEAL: int = 69

# S5-W2 — Flanking A pair + inner F in back; symmetric inner F in mid-1.
# Row 0: A@1→N@0,N@2; A@7→N@6,N@8; F@4 (|1-4|=3 ✓, |7-4|=3 ✓); N@3 individual.
# 2×3+1×2=8.  Row 1: 7N+2F, 7×2=14.  Rows 2–3: 9N. ideal = 8+14+18+18 = 58.
_S5W2_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _N, _F, _N, _N, _A, _N),   # row 0 (back)   — 7N + 2A + 1F (N@3 indiv.)
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),   # row 1 (mid 1)  — 7N + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 2 (mid 2)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 3 (front)  — 9N
)
_S5W2_IDEAL: int = 58

# S5-W3 — Corner A + inner F in back; flanking A + inner F in mid-1.
# Row 0: A@0→N@1; A@8→N@7; F@2,F@6 (|0-2|=2 ✓, |8-6|=2 ✓); N@3,N@4,N@5 indiv.
# 2×3+3×2=12.
# Row 1: A@1→N@0,N@2; A@7→N@6,N@8; F@3,F@5 (|1-3|=2 ✓, |7-5|=2 ✓) fall. 2×3=6.
# Row 2: 7N+2F, 7×2=14.  Row 3: 9N. ideal = 12+6+14+18 = 50.
_S5W3_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _F, _N, _A),   # row 0 (back)   — 5N + 2A + 2F
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),   # row 1 (mid 1)  — 4N + 2A + 2F
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),   # row 2 (mid 2)  — 7N + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 3 (front)  — 9N
)
_S5W3_IDEAL: int = 50

# S5-W4 — Dense F; double-A blasts in back + mid-1; F flanking in front.
# Row 0: F,A@2,F@4,A@6,F — A@2→N@1,N@3; A@6→N@5,N@7; 2×3=6.
# Row 1: A@3→N@2,N@4; A@5→N@6; F@1,F@7 fall; N@0,N@8 indiv. 2×3+2×2=10.
# Row 2: 7N+2F, 7×2=14.
# Row 3: F,A@4,F; A@4→N@3,N@5; N@1,N@2,N@6,N@7 indiv. 3+4×2=11.
# ideal = 6+10+14+11 = 41.
_S5W4_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _A, _N, _F),   # row 0 (back)   — 4N + 2A + 3F
    (_N, _F, _N, _A, _N, _A, _N, _F, _N),   # row 1 (mid 1)  — 5N + 2A + 2F
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),   # row 2 (mid 2)  — 7N + 2F
    (_F, _N, _N, _N, _A, _N, _N, _N, _F),   # row 3 (front)  — 5N + 1A + 2F
)
_S5W4_IDEAL: int = 41

# ---------------------------------------------------------------------------
# Stage 5 wave sequence
# ---------------------------------------------------------------------------

STAGE_5_WAVES: tuple[WaveData, ...] = (
    WaveData(_S5W1_ROWS, _S5W1_IDEAL),
    WaveData(_S5W2_ROWS, _S5W2_IDEAL),
    WaveData(_S5W3_ROWS, _S5W3_IDEAL),
    WaveData(_S5W4_ROWS, _S5W4_IDEAL),
)


# ---------------------------------------------------------------------------
# Stage 6 wave data — 5 rows × 9 cols
# ---------------------------------------------------------------------------
# Five rows per wave versus Stage 5's four adds 18 more cubes.  FORBIDDEN
# density escalates in later waves to force tighter blast routing.
# Ideal steps: 87 → 74 → 68 → 62  (decreasing).
# ---------------------------------------------------------------------------

# S6-W1 — Centre A in back; four dense 9-wide NORMAL rows.
# Row 0: 3+6×2=15.  Rows 1–4: 9N each. ideal = 15+18+18+18+18 = 87.
_S6W1_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _N, _A, _N, _N, _N, _N),   # row 0 (back)   — 8N + 1A
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 1 (mid 1)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 2 (mid 2)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 3 (mid 3)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 4 (front)  — 9N
)
_S6W1_IDEAL: int = 87

# S6-W2 — Flanking A + inner F in back; symmetric inner F in mid-1.
# Row 0: A@1→N@0,N@2; A@7→N@6,N@8; F@3,F@5 fall. 2×3=6.
# Row 1: 7N+2F. 7×2=14.  Rows 2–4: 9N each. ideal = 6+14+18+18+18 = 74.
_S6W2_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),   # row 0 (back)   — 4N + 2A + 2F
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),   # row 1 (mid 1)  — 7N + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 2 (mid 2)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 3 (mid 3)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 4 (front)  — 9N
)
_S6W2_IDEAL: int = 74

# S6-W3 — Corner A + inner F in back; flanking A in mid-1; F in mid-2.
# Row 0: A@0→N@1; A@8→N@7; F@2,F@6; N@3,N@4,N@5 indiv. 2×3+3×2=12.
# Row 1: A@1→N@0,N@2; A@7→N@6,N@8; F@3,F@5 fall. 2×3=6.
# Row 2: 7×2=14.  Rows 3–4: 9N. ideal = 12+6+14+18+18 = 68.
_S6W3_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _F, _N, _A),   # row 0 (back)   — 5N + 2A + 2F
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),   # row 1 (mid 1)  — 4N + 2A + 2F
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),   # row 2 (mid 2)  — 7N + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 3 (mid 3)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 4 (front)  — 9N
)
_S6W3_IDEAL: int = 68

# S6-W4 — Dense F throughout; double-A clears back + mid-1; F in mid rows.
# Row 0: F,A@2,F@4,A@6,F — 2×3=6.
# Row 1: A@3→N@2,N@4; A@5→N@6; N@0,N@8 indiv; F@1,F@7 fall. 2×3+2×2=10.
# Row 2: 7×2=14.  Row 3: 7×2=14.  Row 4: 9N. ideal = 6+10+14+14+18 = 62.
_S6W4_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _A, _N, _F),   # row 0 (back)   — 4N + 2A + 3F
    (_N, _F, _N, _A, _N, _A, _N, _F, _N),   # row 1 (mid 1)  — 5N + 2A + 2F
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),   # row 2 (mid 2)  — 7N + 2F
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),   # row 3 (mid 3)  — 7N + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 4 (front)  — 9N
)
_S6W4_IDEAL: int = 62

# ---------------------------------------------------------------------------
# Stage 6 wave sequence
# ---------------------------------------------------------------------------

STAGE_6_WAVES: tuple[WaveData, ...] = (
    WaveData(_S6W1_ROWS, _S6W1_IDEAL),
    WaveData(_S6W2_ROWS, _S6W2_IDEAL),
    WaveData(_S6W3_ROWS, _S6W3_IDEAL),
    WaveData(_S6W4_ROWS, _S6W4_IDEAL),
)


# ---------------------------------------------------------------------------
# Stage 7 wave data — 5 rows × 9 cols  (same grid as Stage 6, harder patterns)
# ---------------------------------------------------------------------------
# Patterns begin with the flanking-A-clears-all back row (no remaining N),
# escalating to dense F in every row by Wave 4.
# Ideal steps: 83 → 74 → 64 → 52  (decreasing).
# ---------------------------------------------------------------------------

# S7-W1 — Centre A in back; inner F in mid-1; dense NORMAL rows follow.
# Row 0: A@4→N@3,N@5; 6 indiv. 3+6×2=15.  Row 1: 7N+2F, 7×2=14.
# Rows 2–4: 9N. ideal = 15+14+18+18+18 = 83.
_S7W1_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _N, _A, _N, _N, _N, _N),   # row 0 (back)   — 8N + 1A
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),   # row 1 (mid 1)  — 7N + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 2 (mid 2)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 3 (mid 3)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 4 (front)  — 9N
)
_S7W1_IDEAL: int = 83

# S7-W2 — Flanking A + inner F clears back; F in mid-1.
# Row 0: A@1→N@0,N@2; A@7→N@6,N@8; F@3,F@5 fall. 2×3=6.
# Row 1: 7×2=14.  Rows 2–4: 9N. ideal = 6+14+18+18+18 = 74.
_S7W2_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),   # row 0 (back)   — 4N + 2A + 2F
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),   # row 1 (mid 1)  — 7N + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 2 (mid 2)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 3 (mid 3)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 4 (front)  — 9N
)
_S7W2_IDEAL: int = 74

# S7-W3 — Corner A in back; flanking A in mid-1; F spreading into mid-2/3.
# Row 0: A@0→N@1; A@8→N@7; N@3,N@4,N@5 indiv; F@2,F@6. 2×3+3×2=12.
# Row 1: A@1→N@0,N@2; A@7→N@6,N@8; F@3,F@5 fall. 2×3=6.
# Row 2: 7×2=14.  Row 3: 7×2=14.  Row 4: 9N. ideal = 12+6+14+14+18 = 64.
# (N.B. 64 keeps a clear gap from W2=74 and W4=52.)
_S7W3_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _F, _N, _A),   # row 0 (back)   — 5N + 2A + 2F
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),   # row 1 (mid 1)  — 4N + 2A + 2F
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),   # row 2 (mid 2)  — 7N + 2F
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),   # row 3 (mid 3)  — 7N + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 4 (front)  — 9N
)
_S7W3_IDEAL: int = 64

# S7-W4 — Dense F; double-A blasts in back + mid-1; A flanked by F in mid-2.
# Row 0: F,A@2,F@4,A@6,F — 2×3=6.
# Row 1: A@1→N@0,N@2; A@7→N@6,N@8; F@3,F@5 fall. 2×3=6.
# Row 2: A@4→N@3,N@5; N@1,N@2,N@6,N@7 indiv; F@0,F@8 fall. 3+4×2=11.
# Row 3: 7×2=14.  Row 4: centre A. 3+6×2=15.
# ideal = 6+6+11+14+15 = 52.
_S7W4_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _A, _N, _F),   # row 0 (back)   — 4N + 2A + 3F
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),   # row 1 (mid 1)  — 4N + 2A + 2F
    (_F, _N, _N, _N, _A, _N, _N, _N, _F),   # row 2 (mid 2)  — 5N + 1A + 2F
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),   # row 3 (mid 3)  — 7N + 2F
    (_N, _N, _N, _N, _A, _N, _N, _N, _N),   # row 4 (front)  — 8N + 1A
)
_S7W4_IDEAL: int = 52

# ---------------------------------------------------------------------------
# Stage 7 wave sequence
# ---------------------------------------------------------------------------

STAGE_7_WAVES: tuple[WaveData, ...] = (
    WaveData(_S7W1_ROWS, _S7W1_IDEAL),
    WaveData(_S7W2_ROWS, _S7W2_IDEAL),
    WaveData(_S7W3_ROWS, _S7W3_IDEAL),
    WaveData(_S7W4_ROWS, _S7W4_IDEAL),
)


# ---------------------------------------------------------------------------
# Stage 8 wave data — 6 rows × 9 cols
# ---------------------------------------------------------------------------
# Six rows pack the deepest 9-wide wall. Ideal-step values are high because
# there are many NORMAL cubes — the test is sustained pace, not pattern.
# Ideal steps: 105 → 96 → 90 → 76  (decreasing).
# ---------------------------------------------------------------------------

# S8-W1 — Centre A in back; five dense NORMAL rows.
# Row 0: 3+6×2=15.  Rows 1–5: 9N. ideal = 15+18+18+18+18+18 = 105.
_S8W1_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _N, _A, _N, _N, _N, _N),   # row 0 (back)   — 8N + 1A
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 1 (mid 1)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 2 (mid 2)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 3 (mid 3)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 4 (mid 4)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 5 (front)  — 9N
)
_S8W1_IDEAL: int = 105

# S8-W2 — Flanking A + inner F clears back; five dense rows.
# Row 0: 2×3=6.  Rows 1–5: 9N. ideal = 6+18×5 = 96.
_S8W2_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),   # row 0 (back)   — 4N + 2A + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 1 (mid 1)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 2 (mid 2)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 3 (mid 3)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 4 (mid 4)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 5 (front)  — 9N
)
_S8W2_IDEAL: int = 96

# S8-W3 — Corner A in back; flanking A in mid-1; four dense rows.
# Row 0: 2×3+3×2=12.  Row 1: 2×3=6.  Rows 2–5: 9N. ideal = 12+6+18+18+18+18 = 90.
_S8W3_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _F, _N, _A),   # row 0 (back)   — 5N + 2A + 2F
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),   # row 1 (mid 1)  — 4N + 2A + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 2 (mid 2)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 3 (mid 3)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 4 (mid 4)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 5 (front)  — 9N
)
_S8W3_IDEAL: int = 90

# S8-W4 — Double-A blasts clear back + mid-1; F spreads into mid-2 and mid-3.
# Row 0: F,A@2,F@4,A@6,F — 2×3=6.
# Row 1: A@1→N@0,N@2; A@7→N@6,N@8; F@3,F@5 fall. 2×3=6.
# Row 2: 7×2=14.  Row 3: 7×2=14.  Rows 4–5: 9N. ideal = 6+6+14+14+18+18 = 76.
# Corrected ideal: using 7N+2F twice = 14 each.
_S8W4_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _A, _N, _F),   # row 0 (back)   — 4N + 2A + 3F
    (_N, _A, _N, _F, _N, _F, _N, _A, _N),   # row 1 (mid 1)  — 4N + 2A + 2F
    (_N, _N, _F, _N, _N, _N, _F, _N, _N),   # row 2 (mid 2)  — 7N + 2F
    (_N, _N, _N, _F, _N, _F, _N, _N, _N),   # row 3 (mid 3)  — 7N + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 4 (mid 4)  — 9N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N),   # row 5 (front)  — 9N
)
_S8W4_IDEAL: int = 76

# ---------------------------------------------------------------------------
# Stage 8 wave sequence
# ---------------------------------------------------------------------------

STAGE_8_WAVES: tuple[WaveData, ...] = (
    WaveData(_S8W1_ROWS, _S8W1_IDEAL),
    WaveData(_S8W2_ROWS, _S8W2_IDEAL),
    WaveData(_S8W3_ROWS, _S8W3_IDEAL),
    WaveData(_S8W4_ROWS, _S8W4_IDEAL),
)


# ---------------------------------------------------------------------------
# Stage 9 wave data — 6 rows × 11 cols  (grid widens to 11)
# ---------------------------------------------------------------------------
# Player spawn moves to col 5.  Camera centre shifts to x=5.  The wider grid
# means dense NORMAL rows cost 11×2=22 steps each.  High ideal-step counts
# reflect pace, not complexity — later waves introduce F to reduce N targets.
# Ideal steps: 129 → 120 → 110 → 92  (decreasing).
# ---------------------------------------------------------------------------

# S9-W1 — Centre A in back; five dense 11-wide NORMAL rows.
# Row 0: A@5→N@4,N@6; 8 indiv. 3+8×2=19.  Rows 1–5: 11N. ideal = 19+22×5 = 129.
_S9W1_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _N, _N, _A, _N, _N, _N, _N, _N),  # row 0 (back)  — 10N + 1A
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 1 (mid 1) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 2 (mid 2) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 3 (mid 3) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 4 (mid 4) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 5 (front) — 11N
)
_S9W1_IDEAL: int = 129

# S9-W2 — Flanking A pair + inner F in back; five dense rows.
# Row 0: A@1→N@0,N@2; A@9→N@8,N@10; F@4,F@6 (|1-4|=3 ✓, |9-6|=3 ✓); N@3,N@7 indiv.
# 2×3+2×2=10.  Rows 1–5: 11N. ideal = 10+22×5 = 120.
_S9W2_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _N, _F, _N, _F, _N, _N, _A, _N),  # row 0 (back)  — 7N + 2A + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 1 (mid 1) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 2 (mid 2) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 3 (mid 3) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 4 (mid 4) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 5 (front) — 11N
)
_S9W2_IDEAL: int = 120

# S9-W3 — Corner A in back; flanking A in mid-1; four dense rows.
# Row 0: A@0→N@1; A@10→N@9; F@2,F@8 (|0-2|=2 ✓, |10-8|=2 ✓); N@3,N@4,N@5,N@6,N@7 indiv.
# 2×3+5×2=16.
# Row 1: A@2→N@1,N@3; A@8→N@7,N@9; F@4,F@6 (|2-4|=2 ✓, |8-6|=2 ✓) fall. 2×3=6.
# Rows 2–5: 11N. ideal = 16+6+22+22+22+22 = 110.
_S9W3_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _N, _N, _F, _N, _A),  # row 0 (back)  — 7N + 2A + 2F
    (_N, _N, _A, _N, _F, _N, _F, _N, _A, _N, _N),  # row 1 (mid 1) — 5N + 2A + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 2 (mid 2) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 3 (mid 3) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 4 (mid 4) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 5 (front) — 11N
)
_S9W3_IDEAL: int = 110

# S9-W4 — Dense F; double-A blasts in back + mid-1; F in mid-2 + mid-3.
# Row 0: F,A@2,F@4,F@6,A@8,F — A@2→N@1,N@3; A@8→N@7,N@9; 2×3=6.
# Row 1: same pattern as S9-W3 row 1. 2×3=6.
# Row 2: 9N+2F, 9×2=18.  Row 3: 9N+2F, 9×2=18.
# Rows 4–5: 11N. ideal = 6+6+18+18+22+22 = 92.
_S9W4_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _F, _N, _A, _N, _F),  # row 0 (back)  — 4N + 2A + 4F
    (_N, _N, _A, _N, _F, _N, _F, _N, _A, _N, _N),  # row 1 (mid 1) — 5N + 2A + 2F
    (_N, _N, _F, _N, _N, _N, _N, _N, _F, _N, _N),  # row 2 (mid 2) — 9N + 2F
    (_N, _N, _N, _F, _N, _N, _F, _N, _N, _N, _N),  # row 3 (mid 3) — 9N + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 4 (mid 4) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 5 (front) — 11N
)
_S9W4_IDEAL: int = 92

# ---------------------------------------------------------------------------
# Stage 9 wave sequence
# ---------------------------------------------------------------------------

STAGE_9_WAVES: tuple[WaveData, ...] = (
    WaveData(_S9W1_ROWS, _S9W1_IDEAL),
    WaveData(_S9W2_ROWS, _S9W2_IDEAL),
    WaveData(_S9W3_ROWS, _S9W3_IDEAL),
    WaveData(_S9W4_ROWS, _S9W4_IDEAL),
)


# ---------------------------------------------------------------------------
# Stage 10 wave data — 7 rows × 11 cols  (maximum depth and width)
# ---------------------------------------------------------------------------
# Hardest stage: 7-row waves on an 11-wide grid. Dense NORMAL packs give very
# high ideal steps for W1–W2; later waves introduce F to demand tight routing.
# Ideal steps: 151 → 142 → 132 → 114  (decreasing).
# ---------------------------------------------------------------------------

# S10-W1 — Centre A in back; six dense 11-wide NORMAL rows.
# Row 0: 3+8×2=19.  Rows 1–6: 11N. ideal = 19+22×6 = 151.
_S10W1_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _N, _N, _N, _N, _A, _N, _N, _N, _N, _N),  # row 0 (back)  — 10N + 1A
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 1 (mid 1) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 2 (mid 2) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 3 (mid 3) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 4 (mid 4) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 5 (mid 5) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 6 (front) — 11N
)
_S10W1_IDEAL: int = 151

# S10-W2 — Flanking A pair + inner F in back; six dense rows.
# Row 0: 2×3+2×2=10.  Rows 1–6: 11N. ideal = 10+22×6 = 142.
_S10W2_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_N, _A, _N, _N, _F, _N, _F, _N, _N, _A, _N),  # row 0 (back)  — 7N + 2A + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 1 (mid 1) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 2 (mid 2) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 3 (mid 3) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 4 (mid 4) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 5 (mid 5) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 6 (front) — 11N
)
_S10W2_IDEAL: int = 142

# S10-W3 — Corner A in back; flanking A in mid-1; five dense rows.
# Row 0: 2×3+5×2=16.  Row 1: 2×3=6.  Rows 2–6: 11N. ideal = 16+6+22×5 = 132.
_S10W3_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_A, _N, _F, _N, _N, _N, _N, _N, _F, _N, _A),  # row 0 (back)  — 7N + 2A + 2F
    (_N, _N, _A, _N, _F, _N, _F, _N, _A, _N, _N),  # row 1 (mid 1) — 5N + 2A + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 2 (mid 2) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 3 (mid 3) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 4 (mid 4) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 5 (mid 5) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 6 (front) — 11N
)
_S10W3_IDEAL: int = 132

# S10-W4 — Dense F; double-A blasts clear back + mid-1; F in mid-2/3.
# Row 0: F,A@2,F@4,F@6,A@8,F — 2×3=6.
# Row 1: same 11-wide flanking A pattern. 2×3=6.
# Row 2: 9N+2F, 9×2=18.  Row 3: 9N+2F, 9×2=18.  Rows 4–6: 11N.
# ideal = 6+6+18+18+22+22+22 = 114.
_S10W4_ROWS: tuple[tuple[CubeType | None, ...], ...] = (
    (_F, _N, _A, _N, _F, _N, _F, _N, _A, _N, _F),  # row 0 (back)  — 4N + 2A + 4F
    (_N, _N, _A, _N, _F, _N, _F, _N, _A, _N, _N),  # row 1 (mid 1) — 5N + 2A + 2F
    (_N, _N, _F, _N, _N, _N, _N, _N, _F, _N, _N),  # row 2 (mid 2) — 9N + 2F
    (_N, _N, _N, _F, _N, _N, _F, _N, _N, _N, _N),  # row 3 (mid 3) — 9N + 2F
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 4 (mid 4) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 5 (mid 5) — 11N
    (_N, _N, _N, _N, _N, _N, _N, _N, _N, _N, _N),  # row 6 (front) — 11N
)
_S10W4_IDEAL: int = 114

# ---------------------------------------------------------------------------
# Stage 10 wave sequence
# ---------------------------------------------------------------------------

STAGE_10_WAVES: tuple[WaveData, ...] = (
    WaveData(_S10W1_ROWS, _S10W1_IDEAL),
    WaveData(_S10W2_ROWS, _S10W2_IDEAL),
    WaveData(_S10W3_ROWS, _S10W3_IDEAL),
    WaveData(_S10W4_ROWS, _S10W4_IDEAL),
)

# ---------------------------------------------------------------------------
# Master stage table — indexed by stage_index (0-based)
# ---------------------------------------------------------------------------

STAGES: tuple[tuple[WaveData, ...], ...] = (
    STAGE_1_WAVES,
    STAGE_2_WAVES,
    STAGE_3_WAVES,
    STAGE_4_WAVES,
    STAGE_5_WAVES,
    STAGE_6_WAVES,
    STAGE_7_WAVES,
    STAGE_8_WAVES,
    STAGE_9_WAVES,
    STAGE_10_WAVES,
)
