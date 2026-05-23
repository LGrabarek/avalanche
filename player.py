"""Player avatar — grid-snapped movement gated by an input cooldown.

The player lives on the grid at integer `(x, z)` coordinates. There is no
sub-tile position: every move is a discrete hop to an adjacent tile. Movement
is polled (held-key) with a short cooldown between moves so tapping the key
feels instant but holding it doesn't spray through the grid.

Invariant: after every `update()` the player stands on a walkable tile.
"""

from collections.abc import Sequence

from constants import (
    GRID_WIDTH,
    MOVE_COOLDOWN,
    MOVEMENT_KEYS,
    PLAYER_SPAWN_X,
    PLAYER_SPAWN_Z,
    Direction,
)
from grid_manager import GridManager


class Player:
    """Grid-snapped player avatar with cooldown-gated movement."""

    def __init__(
        self,
        grid: GridManager,
        spawn_x: int = PLAYER_SPAWN_X,
        spawn_z: int = PLAYER_SPAWN_Z,
    ) -> None:
        if not grid.is_valid_position(spawn_x, spawn_z):
            raise ValueError(
                f"spawn position ({spawn_x}, {spawn_z}) is not a walkable tile"
            )
        self._grid: GridManager = grid
        self._grid_x: int = spawn_x
        self._grid_z: int = spawn_z
        # `_cooldown` is seconds until the next move is allowed. Starts at 0
        # so the very first held-key frame moves immediately (no perceived lag).
        self._cooldown: float = 0.0
        self._crushed: bool = False
        # Step 41: walk-animation state.
        # _step_parity flips each successful move so legs alternate each step.
        # _cooldown already decays each frame; walk_progress derives from it.
        self._step_parity: bool = False
        # Step 42: facing direction — last direction the player moved.
        # Default FORWARD so the character starts facing the wave (back to camera).
        self._facing: Direction = Direction.FORWARD

    # --- Public read-only accessors ------------------------------------------

    @property
    def grid_x(self) -> int:
        return self._grid_x

    @property
    def grid_z(self) -> int:
        return self._grid_z

    @property
    def is_crushed(self) -> bool:
        return self._crushed

    @property
    def walk_progress(self) -> float:
        """Normalised walk cycle in [0, 1].

        1.0 = just took a step; decays linearly to 0.0 = idle / fully rested.
        `sin(π × walk_progress)` peaks at 0.5 (mid-cooldown) and is 0 at both
        ends, so legs always return to centre when still and when landing.
        """
        if MOVE_COOLDOWN <= 0.0:
            return 0.0
        return self._cooldown / MOVE_COOLDOWN

    @property
    def step_parity(self) -> bool:
        """Flips each step; drives alternating leg lead in the walk cycle."""
        return self._step_parity

    @property
    def facing(self) -> Direction:
        """Last movement direction; drives character head orientation."""
        return self._facing

    @property
    def world_pos(self) -> tuple[float, float, float]:
        """World-space position at the centre of the player's current tile.

        The +0.5 XZ offset centres the camera on the tile interior rather
        than the tile origin.  y=0.0 (floor level) is intentional: aiming
        the camera at the floor keeps the player cube in the upper half of
        the viewport, leaving more vertical screen real estate showing the
        approaching wave below.  Aiming at y=0.5 (cube midpoint) would
        vertically centre the player but compress the foreground where
        tactical decisions happen.  Used by main.py to position the
        follow camera each frame.
        """
        return (self._grid_x + 0.5, 0.0, self._grid_z + 0.5)

    def position(self) -> tuple[int, int]:
        """Return the current tile-grid position as `(grid_x, grid_z)`."""
        return (self._grid_x, self._grid_z)

    def reset(self) -> None:
        """Return the player to spawn, uncrush, and zero the movement cooldown.

        The grid must be fully intact (all tiles PLATFORM) before calling so
        the spawn position is guaranteed walkable. Call `grid.resize()` or
        `grid.reset()` first (resize implicitly resets tiles).

        Spawn X is always the centre of the *current* grid width so the player
        lands in the middle of the platform regardless of whether the width
        changed this stage (Step 32: grids are 7, 9, or 11 wide by stage).
        """
        spawn_x = self._grid.width // 2
        if not self._grid.is_valid_position(spawn_x, PLAYER_SPAWN_Z):
            raise ValueError(
                f"spawn ({spawn_x}, {PLAYER_SPAWN_Z}) not walkable — "
                "resize/reset the grid before resetting the player"
            )
        self._grid_x = spawn_x
        self._grid_z = PLAYER_SPAWN_Z
        self._crushed = False
        self._cooldown = 0.0
        self._step_parity = False
        self._facing = Direction.FORWARD
        assert self._grid.is_valid_position(self._grid_x, self._grid_z), (
            "player spawn not walkable after reset"
        )

    def crush(self) -> None:
        """Mark the player as crushed, disabling all movement."""
        self._crushed = True

    def uncrush(self) -> None:
        """Restore the player to the un-crushed state at the start of a new wave.

        Called by GameManager when transitioning from WAVE_CLEARING into the
        next wave.  Does not reposition the player — they stay where they are.
        """
        self._crushed = False

    def position_near_wave(self, wave_front_z: int, gap: int) -> None:
        """Place the player `gap` tiles below the wave front at game start.

        Called by GameManager immediately after spawning Stage 1 Wave 1 cubes
        to position the player a fixed number of tiles below wave-0's front face.
        """
        if gap <= 0:
            raise ValueError(f"gap must be positive, got {gap}")
        if wave_front_z <= 0:
            raise ValueError(f"wave_front_z must be positive, got {wave_front_z}")
        target_z = wave_front_z - gap
        if target_z < 0:
            raise ValueError(
                f"wave_front_z={wave_front_z} − gap={gap} = {target_z} < 0"
            )
        if not self._grid.is_valid_position(self._grid_x, target_z):
            raise ValueError(
                f"target tile ({self._grid_x}, {target_z}) is not walkable"
            )
        self._grid_z = target_z
        assert self._grid.is_valid_position(self._grid_x, self._grid_z), (
            "player not on walkable tile after position_near_wave"
        )

    def clamp_z_before_wave(self, wave_front_z: int) -> None:
        """Ensure the player is not inside or immediately adjacent to the new wave.

        If the player's tile Z ≥ wave_front_z − 1, pull them back to the
        nearest valid tile at or below wave_front_z − 2.  This 2-tile buffer
        gives the player one full reaction tile between themselves and the
        wave face during the frozen STAGE_INTRO countdown.  No-op when safe.
        """
        if wave_front_z <= 1:
            raise ValueError(f"wave_front_z must be > 1, got {wave_front_z}")
        if self._grid_z < wave_front_z - 1:
            return  # already have 2-tile buffer — no-op
        # Scan downward from wave_front_z-2 for the nearest walkable tile.
        tile_x = self._grid_x
        max_scan = wave_front_z - 1
        for scan in range(max_scan):
            assert scan < max_scan, "clamp scan exceeded bound"
            target_z = wave_front_z - 2 - scan
            if target_z < 0:
                break
            if self._grid.is_valid_position(tile_x, target_z):
                self._grid_z = target_z
                assert self._grid.is_valid_position(tile_x, self._grid_z), (
                    "player not on walkable tile after Z clamp"
                )
                return
        raise ValueError(
            f"no walkable tile below wave_front_z={wave_front_z} "
            f"in column {tile_x} — all rows voided"
        )

    # --- Per-frame update -----------------------------------------------------

    def update(
        self,
        dt: float,
        held_keys: Sequence[bool],
        wave_blocked: frozenset[tuple[int, int]] | None = None,
        max_col: int = GRID_WIDTH - 1,
    ) -> None:
        """Advance the cooldown and, if a movement key is held, move one tile.

        `max_col` is the inclusive right tile-column boundary.
        """
        if dt < 0.0:
            raise ValueError(f"dt must be non-negative, got {dt}")
        if max_col < 0 or max_col >= GRID_WIDTH:
            raise ValueError(f"max_col {max_col} not in [0, {GRID_WIDTH - 1}]")
        if self._crushed:
            return
        if self._cooldown > 0.0:
            self._cooldown = max(0.0, self._cooldown - dt)
            return
        direction = _first_held_direction(held_keys)
        if direction is None:
            return
        if self.try_move(direction, wave_blocked, max_col):
            self._cooldown = MOVE_COOLDOWN

    # --- Movement primitive --------------------------------------------------

    def try_move(
        self,
        direction: Direction,
        wave_blocked: frozenset[tuple[int, int]] | None = None,
        max_col: int = GRID_WIDTH - 1,
    ) -> bool:
        """Attempt a single tile step. Returns True iff the move happened.

        Refuses moves that would enter a void tile, a wave-blocked tile, or
        exceed `max_col` (inclusive tile-level right boundary).
        """
        if max_col < 0 or max_col >= GRID_WIDTH:
            raise ValueError(f"max_col {max_col} not in [0, {GRID_WIDTH - 1}]")
        dx, dz = direction.value
        new_x = self._grid_x + dx
        new_z = self._grid_z + dz
        if new_x < 0 or new_z < 0:
            return False
        if not self._grid.is_valid_position(new_x, new_z):
            return False
        if new_x > max_col:
            return False
        if wave_blocked is not None and (new_x, new_z) in wave_blocked:
            return False
        # Commit the move.
        self._grid_x = new_x
        self._grid_z = new_z
        self._step_parity = not self._step_parity
        self._facing = direction
        assert self._grid.is_valid_position(self._grid_x, self._grid_z), (
            "player landed on a non-walkable tile — blocking check failed"
        )
        return True


# --- Module-level helper ------------------------------------------------------

_OPPOSITE_DIRECTION: dict[Direction, Direction] = {
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
    Direction.FORWARD: Direction.BACKWARD,
    Direction.BACKWARD: Direction.FORWARD,
}


def _first_held_direction(held_keys: Sequence[bool]) -> Direction | None:
    """Return the resolved single `Direction` the player is requesting, or None.

    Resolution rules:
      * Opposite-axis conflicts cancel (LEFT+RIGHT → None, FORWARD+BACKWARD
        → None). Silently picking one of two opposing held keys is a classic
        frustration source in tile puzzlers — especially here, where a wrong
        move can get you crushed.
      * Perpendicular conflicts (one Z-axis key + one X-axis key held together)
        resolve in favour of the Z-axis (FORWARD / BACKWARD). This matches the
        original I.Q. behaviour: depth movement (towards or away from the
        advancing wave) is more critical than lateral repositioning, so the
        game prefers the direction that keeps the player out of harm's way.
    """
    if len(held_keys) == 0:
        raise ValueError("held_keys sequence is empty")
    held_dirs: set[Direction] = set()
    for direction, keys in MOVEMENT_KEYS.items():
        for key in keys:
            if held_keys[key]:
                held_dirs.add(direction)
                break
    if not held_dirs:
        return None
    for direction in tuple(held_dirs):
        opposite = _OPPOSITE_DIRECTION[direction]
        if opposite in held_dirs:
            held_dirs.discard(direction)
            held_dirs.discard(opposite)
    if not held_dirs:
        return None
    z_dirs = held_dirs & {Direction.FORWARD, Direction.BACKWARD}
    x_dirs = held_dirs & {Direction.LEFT, Direction.RIGHT}
    if z_dirs and x_dirs:
        held_dirs = z_dirs
    for direction in MOVEMENT_KEYS:
        if direction in held_dirs:
            return direction
    return None  # unreachable — held_dirs ⊆ MOVEMENT_KEYS.keys()
