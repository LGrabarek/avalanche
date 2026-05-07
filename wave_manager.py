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
    """

    grid_x: int
    grid_z: int
    cube_type: CubeType


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
        return len(self._cubes)

    # --- Population ----------------------------------------------------------

    def spawn_cube(self, grid_x: int, grid_z: int, cube_type: CubeType) -> None:
        """Add a single cube at a grid position.

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
        self._cubes.append(Cube(grid_x, grid_z, cube_type))

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
        """Return the cube resting at `(grid_x, grid_z)` or None.

        "Resting tile" is the cube's committed `(grid_x, grid_z)`; tumble
        progress toward the next tile does not change the answer. A cube is
        considered *at* the tile it last committed to via `_advance_tick`.
        This matches I.Q. capture semantics: a marked tile captures the cube
        that has arrived on it, not the one animating toward it.

        Invariant (Step 3A): at most one cube per tile. `spawn_debug_row`
        never double-spawns and advancement shifts every cube in lockstep,
        so two cubes cannot share a resting tile. Captured here as an
        assertion so Step 5+ patterns that could violate it fail loudly.
        """
        found: Cube | None = None
        for cube in self._cubes:
            if cube.grid_x == grid_x and cube.grid_z == grid_z:
                assert found is None, (
                    f"two cubes share resting tile ({grid_x}, {grid_z}) — "
                    "one-cube-per-tile invariant broken"
                )
                found = cube
        return found

    def capturable_at(self, grid_x: int, grid_z: int) -> Cube | None:
        """Return the cube visually resting on `(grid_x, grid_z)` if capturable.

        Capture is only valid during the trailing rest phase
        (`tick_progress >= TUMBLE_REST_FRACTION`). During the rest phase the
        cube's animation has completed: it sits visually on `cube.grid_z - 1`
        (one tile ahead of its committed grid position). We therefore match
        `cube.grid_z == grid_z + 1` — the player marks the tile the cube is
        *visually* resting on, not its logical committed tile.

        Returns None if the wave is still in the tumble phase, or if no cube
        is visually resting on `(grid_x, grid_z)`.
        """
        if self.tick_progress < TUMBLE_REST_FRACTION:
            return None  # Mid-tumble — captures disallowed until cube lands.
        found: Cube | None = None
        for cube in self._cubes:
            if cube.grid_x == grid_x and cube.grid_z == grid_z + 1:
                assert found is None, (
                    f"two cubes share visual rest tile ({grid_x}, {grid_z}) "
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
        """Commit one tick: all cubes advance -Z; cubes off the front drop.

        `front_drop_z`: cubes with `grid_z < front_drop_z` after advancing are
        captured in `_last_dropped`. When front rows have been voided by penalty
        deletions, this value is > 0, causing cubes to drop at the new platform
        edge rather than continuing over empty space.

        Dropped cubes are captured in `_last_dropped` so `GameManager.on_tick`
        can count missed normals during the avalanche phase.
        """
        assert 0 <= front_drop_z <= GRID_DEPTH, (
            f"front_drop_z {front_drop_z} outside [0, {GRID_DEPTH}]"
        )
        for cube in self._cubes:
            cube.grid_z -= 1
        self._last_dropped = [c for c in self._cubes if c.grid_z < front_drop_z]
        self._cubes = [c for c in self._cubes if c.grid_z >= front_drop_z]
        assert len(self._cubes) <= MAX_ACTIVE_CUBES, (
            "cube count exceeded cap after advance — spawn path broke its precondition"
        )

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
        """Return (grid_x, grid_z) for cubes one tick from the platform's front edge.

        A cube at `front_edge_z + 1` will advance to `front_edge_z` on the
        next tick and is highlighted by the renderer as a visual danger warning
        (B3e telegraph).  Returns an empty frozenset when no cubes are in the
        danger zone or when the wave has no cubes.
        """
        if front_edge_z < 0:
            raise ValueError(f"front_edge_z must be non-negative, got {front_edge_z}")
        return frozenset(
            (cube.grid_x, cube.grid_z)
            for cube in self._cubes
            if cube.grid_z == front_edge_z + 1
        )

    # --- Rendering hand-off --------------------------------------------------

    def iter_cubes(self) -> Iterator[tuple[int, int, float, CubeType]]:
        """Yield `(grid_x, grid_z, tumble_progress, cube_type)` per cube.

        All cubes share the same `tumble_progress` (the wave's tick
        progress); per-cube phase offsets are an intentional non-goal for
        Step 3A — uniform cadence is easier to eyeball and matches the
        original I.Q. behavior.

        **Contract:** callers must not spawn, remove, or mutate cubes while
        consuming this iterator.
        """
        progress = self.tick_progress
        assert 0.0 <= progress <= 1.0, "tick_progress escaped [0, 1] — invariant broken"
        for cube in self._cubes:
            yield (cube.grid_x, cube.grid_z, progress, cube.cube_type)
