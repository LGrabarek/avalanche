"""Wave manager — tick-driven cube advancement across the grid.

Cubes tumble from the back row (high Z) toward the front edge (low Z). Every
`TICK_INTERVAL` seconds the wave "ticks": each cube's integer `grid_z`
decreases by one, and cubes that fell off the front edge are dropped. Between
ticks, `tick_progress` interpolates 0..1 and drives the tumble animation in
`cube_data.get_cube_vertices`.

Coordinate convention matches `grid_manager.py`: `(x, z)` with `z=0` the
front/camera-side row and `z=GRID_DEPTH-1` the back. Cubes advance in -Z.

Step 3A scope: motion + tick cadence only. Capture, crush, and
missed-cube penalty semantics land in Steps 4-6.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from constants import (
    GRID_DEPTH,
    GRID_WIDTH,
    TICK_INTERVAL,
    TUMBLE_REST_FRACTION,
    CubeType,
)

# One wave can spawn at most every-tile-every-column = width * depth cubes.
# Real wave patterns are sparse (≈ one row at a time), so this is a generous
# ceiling rather than a tight bound; tighten in Step 9 if wave patterns push
# against it. Keeping it here (not in constants.py) so the cap travels with
# the subsystem that enforces it.
MAX_ACTIVE_CUBES: int = GRID_WIDTH * GRID_DEPTH


@dataclass
class Cube:
    """A single tumbling cube.

    `grid_x`/`grid_z` are the cube's **current resting tile**. While
    `tick_progress` interpolates 0→1 the cube is visually animating from
    `(grid_x, grid_z)` toward `(grid_x, grid_z - 1)`; the coordinate does
    not update until the tick commits.

    `pending`: when True the cube has been placed for a future wave but has
    not yet been activated.  Pending cubes do NOT advance on tick, are NOT
    capturable, and do NOT contribute to `active_cube_count`.  They DO block
    player movement (blocked_tiles) and are rendered as uniform grey.
    """

    grid_x: int
    grid_z: int
    cube_type: CubeType
    pending: bool = False


class WaveManager:
    """Owns the active cube set and drives tick-based advancement.

    The manager is the logical owner of cube state; rendering reads per-cube
    `(grid_x, grid_z, tumble_progress, cube_type)` tuples via `iter_cubes()`.
    Game logic (capture, miss, crush) will later consume the same state.

    Tick model:
      * `_tick_elapsed` accumulates per-frame `dt`.
      * When it reaches `_tick_interval`, `_advance_tick()` commits: every
        cube's `grid_z` decrements by one and cubes that rolled off the front
        edge (`grid_z < 0`) are removed.
      * Sub-interval overshoot is preserved across ticks so cadence stays
        even. A pathologically long `dt` (tab-switch spiral upstream of
        `DT_CLAMP`) cannot bank multiple ticks in one frame.
    """

    def __init__(self, tick_interval: float = TICK_INTERVAL) -> None:
        if tick_interval <= 0.0:
            raise ValueError(f"tick_interval must be positive, got {tick_interval}")
        self._cubes: list[Cube] = []
        self._tick_elapsed: float = 0.0
        self._tick_interval: float = tick_interval
        self._last_dropped: list[Cube] = []

    # --- Read-only accessors -------------------------------------------------

    @property
    def tick_interval(self) -> float:
        return self._tick_interval

    @tick_interval.setter
    def tick_interval(self, value: float) -> None:
        if value <= 0.0:
            raise ValueError(f"tick_interval must be positive, got {value}")
        self._tick_interval = value
        # A mid-tumble crush sets interval from 1.2s to 0.15s while
        # tick_elapsed may be ~0.33s. Without a clamp the overshoot
        # assertion in update() fires on the very next frame.
        #
        # We clamp to (value - 1e-6) rather than 0.0 so that the next
        # update() call fires a tick on the very next frame instead of
        # restarting the full interval from zero. This prevents the turbo
        # freeze exploit where rapid F taps keep _tick_elapsed near zero
        # indefinitely (wave advances never fire while turbo is flicked on
        # and off). With this fix, pressing F when elapsed > value still
        # fires a tick on the next frame — the wave cannot be frozen.
        #
        # Safety: worst-case overshoot = DT_CLAMP - 1e-6 ≈ 0.1 s, which
        # is less than the minimum interval (AVALANCHE_TICK_INTERVAL = 0.12 s
        # or larger). The assert in update() remains satisfied.
        if self._tick_elapsed >= value:
            self._tick_elapsed = max(0.0, value - 1e-6)

    @property
    def last_dropped(self) -> list[Cube]:
        """Cubes that fell off the front edge on the most recent tick.

        Empty between ticks. Callers read this in the same frame the tick
        fired (e.g. from `GameManager.on_tick`) to count missed normals.
        """
        return self._last_dropped

    @property
    def tick_progress(self) -> float:
        """Fraction of the current tick elapsed, clamped to [0, 1].

        The clamp matters because `_tick_elapsed` can briefly exceed
        `_tick_interval` between the `+= dt` and the `_advance_tick` call
        in the same `update()`; any query in between must still be bounded.
        """
        return min(1.0, max(0.0, self._tick_elapsed / self._tick_interval))

    @property
    def cube_count(self) -> int:
        """Total cube count including pending cubes."""
        return len(self._cubes)

    @property
    def active_cube_count(self) -> int:
        """Count of non-pending (currently advancing) cubes.

        Used by GameManager to detect wave-clear: the wave is finished when
        this reaches zero regardless of how many pending cubes remain.
        """
        return sum(1 for c in self._cubes if not c.pending)

    # --- Population ----------------------------------------------------------

    def spawn_cube(
        self,
        grid_x: int,
        grid_z: int,
        cube_type: CubeType,
        pending: bool = False,
    ) -> None:
        """Add a single cube at a grid position.

        `pending=True` places the cube as a future-wave placeholder: it will
        not advance on tick until `activate_pending` flips it.

        Raises `ValueError` for off-grid coordinates. Rule-3 invariant: we
        guard the `append` with an explicit cap so a runaway spawner cannot
        inflate the cube list without bound.
        """
        if not (0 <= grid_x < GRID_WIDTH):
            raise ValueError(f"grid_x {grid_x} outside [0, {GRID_WIDTH})")
        if not (0 <= grid_z < GRID_DEPTH):
            raise ValueError(f"grid_z {grid_z} outside [0, {GRID_DEPTH})")
        assert len(self._cubes) < MAX_ACTIVE_CUBES, (
            f"cube count would exceed cap of {MAX_ACTIVE_CUBES}"
        )
        self._cubes.append(Cube(grid_x, grid_z, cube_type, pending=pending))

    def spawn_debug_row(self) -> None:
        """Step-3A debug loadout: one cube per column at the back row.

        The pattern mixes all three cube types so the renderer exercises
        every palette on every frame and the user can eyeball tumble,
        visual distinction, and fall-off behavior simultaneously.
        """
        pattern: tuple[CubeType, ...] = (
            CubeType.NORMAL,
            CubeType.NORMAL,
            CubeType.ADVANTAGE,
            CubeType.FORBIDDEN,
            CubeType.ADVANTAGE,
            CubeType.NORMAL,
            CubeType.NORMAL,
        )
        assert len(pattern) == GRID_WIDTH, (
            f"debug pattern must cover every column ({GRID_WIDTH}), got {len(pattern)}"
        )
        back_row = GRID_DEPTH - 1
        for x, cube_type in enumerate(pattern):
            self.spawn_cube(x, back_row, cube_type)

    # --- Per-frame update ----------------------------------------------------

    def update(self, dt: float, front_drop_z: int = 0) -> bool:
        """Advance the tick timer by `dt`. Returns True iff a tick fired.

        `front_drop_z`: cubes whose `grid_z` falls below this value after
        advancing are considered to have rolled off the platform edge and are
        dropped. Defaults to 0 (no rows deleted). Set to `grid.front_edge_z`
        each frame so row deletions update the drop threshold dynamically.

        Commits at most one tick per call. The caller's contract: upstream
        `DT_CLAMP` (in `main.py`) keeps `dt < tick_interval`, so after one
        `_advance_tick` the residual `overshoot` is always in `[0, interval)`.
        This is enforced as an assertion rather than silently clamped — a
        violation means the clamp contract is broken and should fail loudly
        rather than quietly corrupt the cadence.
        """
        if dt < 0.0:
            raise ValueError(f"dt must be non-negative, got {dt}")
        if front_drop_z < 0:
            raise ValueError(f"front_drop_z must be non-negative, got {front_drop_z}")
        self._tick_elapsed += dt
        if self._tick_elapsed < self._tick_interval:
            return False
        self._advance_tick(front_drop_z)
        overshoot = self._tick_elapsed - self._tick_interval
        assert 0.0 <= overshoot < self._tick_interval, (
            f"overshoot {overshoot:.4f}s not in [0, {self._tick_interval}) — "
            "caller violated the dt < tick_interval contract (check DT_CLAMP)"
        )
        self._tick_elapsed = overshoot
        return True

    # --- Spatial query + capture hand-off ------------------------------------

    def cube_at(self, grid_x: int, grid_z: int) -> Cube | None:
        """Return the active (non-pending) cube resting at `(grid_x, grid_z)`.

        Pending cubes are ignored: they have not been activated yet and are
        never crush/capture targets.  At most one active cube per tile.
        """
        found: Cube | None = None
        for cube in self._cubes:
            if cube.pending:
                continue
            if cube.grid_x == grid_x and cube.grid_z == grid_z:
                assert found is None, (
                    f"two active cubes share resting tile ({grid_x}, {grid_z}) — "
                    "one-cube-per-tile invariant broken"
                )
                found = cube
        return found

    def capturable_at(self, grid_x: int, grid_z: int) -> Cube | None:
        """Return the active cube visually resting on `(grid_x, grid_z)` if capturable.

        Pending cubes are never capturable.  Capture is only valid during the
        trailing rest phase (`tick_progress >= TUMBLE_REST_FRACTION`).
        """
        if self.tick_progress < TUMBLE_REST_FRACTION:
            return None  # Mid-tumble — captures disallowed until cube lands.
        found: Cube | None = None
        for cube in self._cubes:
            if cube.pending:
                continue
            if cube.grid_x == grid_x and cube.grid_z == grid_z + 1:
                assert found is None, (
                    f"two active cubes share visual rest tile ({grid_x}, {grid_z}) "
                    "— one-cube-per-tile invariant broken"
                )
                found = cube
        return found

    def blocked_tiles(self) -> frozenset[tuple[int, int]]:
        """Grid positions currently occupied by cubes — player cannot enter these."""
        return frozenset((cube.grid_x, cube.grid_z) for cube in self._cubes)

    def remove_cube(self, cube: Cube) -> None:
        """Remove a specific cube from the active set (capture).

        Raises `ValueError` if the cube is not in the active set — callers
        that obtained the reference via `cube_at` should never hit this, but
        surfacing the bug loudly beats silently no-oping.
        """
        # Identity-based removal: `list.remove` uses __eq__, and dataclass
        # default equality is structural. Two distinct NORMAL cubes at the
        # same (x, z) would be indistinguishable — which can't happen per
        # the one-cube-per-tile invariant, but we still prefer identity to
        # avoid any ambiguity. Manual scan keeps Rule-9 compliance trivial.
        for i, existing in enumerate(self._cubes):
            if existing is cube:
                _ = self._cubes.pop(i)  # unused: side-effect is removal
                return
        raise ValueError(
            f"cube at ({cube.grid_x}, {cube.grid_z}) not in active set"
        )

    # --- Tick commit ---------------------------------------------------------

    def _advance_tick(self, front_drop_z: int = 0) -> None:
        """Commit one tick: active cubes advance -Z; pending cubes stay put.

        `front_drop_z`: active cubes with `grid_z < front_drop_z` after
        advancing are captured in `_last_dropped`.  Pending cubes are always
        retained regardless of z — they are not yet in play.

        Dropped cubes are captured in `_last_dropped` so `GameManager.on_tick`
        can count missed normals during the avalanche phase.
        """
        assert 0 <= front_drop_z <= GRID_DEPTH, (
            f"front_drop_z {front_drop_z} outside [0, {GRID_DEPTH}]"
        )
        for cube in self._cubes:
            if not cube.pending:
                cube.grid_z -= 1
        self._last_dropped = [
            c for c in self._cubes if (not c.pending) and c.grid_z < front_drop_z
        ]
        self._cubes = [
            c for c in self._cubes if c.pending or c.grid_z >= front_drop_z
        ]
        assert len(self._cubes) <= MAX_ACTIVE_CUBES, (
            "cube count exceeded cap after advance — spawn path broke its precondition"
        )

    # --- Pending activation --------------------------------------------------

    def activate_pending(self, z_min: int, z_max: int) -> None:
        """Flip pending cubes whose grid_z is in [z_min, z_max] to active.

        Called by `GameManager._activate_wave` at the start of each wave so
        that wave's pre-placed cubes begin advancing on the next tick.
        Raises `ValueError` if the z range is invalid.
        """
        if not (0 <= z_min <= z_max < GRID_DEPTH):
            raise ValueError(
                f"z range [{z_min}, {z_max}] invalid for GRID_DEPTH {GRID_DEPTH}"
            )
        activated = 0
        for cube in self._cubes:
            if cube.pending and z_min <= cube.grid_z <= z_max:
                cube.pending = False
                activated += 1
        assert activated >= 0, "activate_pending counted negative activations"

    # --- Wave lifecycle ------------------------------------------------------

    def reset_for_new_wave(self) -> None:
        """Clear all cubes and reset the tick elapsed timer for a fresh wave.

        Called by `GameManager._spawn_wave`, `_on_stage_complete`, and
        `_do_restart`. Does NOT reset `_tick_interval` — the caller sets the
        correct stage-indexed interval via `wave.tick_interval = ...` immediately
        after this call (Step 21 per-stage tick table). This keeps WaveManager
        free of stage knowledge.
        """
        self._cubes = []
        self._tick_elapsed = 0.0
        self._last_dropped = []
        assert self.cube_count == 0, "cubes not cleared after reset_for_new_wave"

    # --- Danger query --------------------------------------------------------

    def danger_cubes(self, front_edge_z: int) -> frozenset[tuple[int, int]]:
        """Return (grid_x, grid_z) for active cubes one tick from the front edge.

        Pending cubes are excluded: they do not advance and cannot imminently
        reach the front edge.
        """
        if front_edge_z < 0:
            raise ValueError(f"front_edge_z must be non-negative, got {front_edge_z}")
        return frozenset(
            (cube.grid_x, cube.grid_z)
            for cube in self._cubes
            if (not cube.pending) and cube.grid_z == front_edge_z + 1
        )

    # --- Pending removal -----------------------------------------------------

    def remove_pending_in_range(self, z_front: int, z_back: int) -> int:
        """Remove all pending cubes whose grid_z is in [z_front, z_back].

        Returns the count of cubes removed.  Raises ValueError for an invalid
        z range.  Called by GameManager when a pre-placed pending wave is
        consumed as a crush retry life and must not appear on screen or be
        activated later.
        """
        if not (0 <= z_front <= z_back < GRID_DEPTH):
            raise ValueError(
                f"z range [{z_front}, {z_back}] invalid for GRID_DEPTH {GRID_DEPTH}"
            )
        before = len(self._cubes)
        self._cubes = [
            c for c in self._cubes
            if not (c.pending and z_front <= c.grid_z <= z_back)
        ]
        removed = before - len(self._cubes)
        assert removed >= 0, "remove_pending_in_range removed negative cubes"
        return removed

    # --- Rendering hand-off --------------------------------------------------

    def iter_cubes(self) -> Iterator[tuple[int, int, float, CubeType, bool]]:
        """Yield `(grid_x, grid_z, tumble_progress, cube_type, pending)` per cube.

        Active cubes share the wave's `tumble_progress`.  Pending cubes are
        always yielded at `progress=0.0` so they render as flat-sitting static
        cubes rather than animating in sync with the active wave.

        **Contract:** callers must not spawn, remove, or mutate cubes while
        consuming this iterator.
        """
        progress = self.tick_progress
        assert 0.0 <= progress <= 1.0, "tick_progress escaped [0, 1] — invariant broken"
        for cube in self._cubes:
            cube_progress = 0.0 if cube.pending else progress
            yield (cube.grid_x, cube.grid_z, cube_progress, cube.cube_type, cube.pending)
