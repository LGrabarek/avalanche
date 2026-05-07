"""Player avatar — grid-snapped movement gated by an input cooldown.

The player lives on the grid at integer `(x, z)` coordinates. There is no
sub-tile position: every move is a discrete hop to an adjacent tile. Movement
is polled (held-key) with a short cooldown between moves so tapping the key
feels instant but holding it doesn't spray through the grid.

Invariant: after every `update()` the player stands on a walkable tile.
"""

from collections.abc import Sequence

from constants import (
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

    def position(self) -> tuple[int, int]:
        """Return the current grid position as `(x, z)`."""
        return (self._grid_x, self._grid_z)

    def reset(self) -> None:
        """Return the player to spawn, uncrush, and zero the movement cooldown.

        The grid must be fully intact (all tiles PLATFORM) before calling so
        the spawn position is guaranteed walkable. Call `grid.reset()` first.
        """
        if not self._grid.is_valid_position(PLAYER_SPAWN_X, PLAYER_SPAWN_Z):
            raise ValueError(
                f"spawn ({PLAYER_SPAWN_X}, {PLAYER_SPAWN_Z}) not walkable — "
                "reset the grid before resetting the player"
            )
        self._grid_x = PLAYER_SPAWN_X
        self._grid_z = PLAYER_SPAWN_Z
        self._crushed = False
        self._cooldown = 0.0
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

    # --- Per-frame update -----------------------------------------------------

    def update(
        self,
        dt: float,
        held_keys: Sequence[bool],
        wave_blocked: frozenset[tuple[int, int]] | None = None,
    ) -> None:
        """Advance the cooldown and, if a movement key is held, move one tile.

        `held_keys` is the raw `pygame.key.get_pressed()` sequence. Opposite-
        axis holds cancel (LEFT+RIGHT or FORWARD+BACKWARD → no move), so a
        player "leaning on the keyboard" doesn't snap a silent direction.
        `wave_blocked` is the set of tiles currently occupied by wave cubes;
        the player cannot enter those tiles (same blocking as void tiles).
        When a Z-axis key (FORWARD/BACKWARD) and an X-axis key (LEFT/RIGHT) are
        held simultaneously, the Z-axis wins (Step 23 perpendicular priority).
        """
        if dt < 0.0:
            raise ValueError(f"dt must be non-negative, got {dt}")
        if self._crushed:
            return
        if self._cooldown > 0.0:
            self._cooldown = max(0.0, self._cooldown - dt)
            return
        direction = _first_held_direction(held_keys)
        if direction is None:
            return
        if self.try_move(direction, wave_blocked):
            self._cooldown = MOVE_COOLDOWN

    # --- Movement primitive --------------------------------------------------

    def try_move(
        self,
        direction: Direction,
        wave_blocked: frozenset[tuple[int, int]] | None = None,
    ) -> bool:
        """Attempt a single-tile move. Returns True iff the move happened.

        Refuses moves that would leave the player off the grid, onto a VOID
        tile, or into a tile currently occupied by a wave cube.
        """
        dx, dz = direction.value
        new_x = self._grid_x + dx
        new_z = self._grid_z + dz
        if not self._grid.is_valid_position(new_x, new_z):
            return False
        if wave_blocked is not None and (new_x, new_z) in wave_blocked:
            return False
        self._grid_x = new_x
        self._grid_z = new_z
        assert self._grid.is_valid_position(self._grid_x, self._grid_z), (
            "player landed on a non-walkable tile — is_valid_position lied"
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

    In pygame parlance "pressed" is edge-triggered (`KEYDOWN`); this function
    inspects held state, hence the "held" naming. `held_keys[key]` is forwarded
    directly to pygame's `ScancodeWrapper`, which accepts any `K_*` value (it
    internally maps to a scancode, even though arrow-key K_* constants are
    numerically larger than the wrapper's length). We deliberately do not
    bound-check `key` against `len(held_keys)` here.
    """
    # Rule-5 precondition: reject an empty sequence — the one legitimately-
    # wrong input shape. Every real ScancodeWrapper has the same fixed length.
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
    # Cancel opposing pairs. Iterating over a copy so we can mutate the set.
    for direction in tuple(held_dirs):
        opposite = _OPPOSITE_DIRECTION[direction]
        if opposite in held_dirs:
            held_dirs.discard(direction)
            held_dirs.discard(opposite)
    if not held_dirs:
        return None
    # Z-axis priority (Step 23): when one FORWARD/BACKWARD and one LEFT/RIGHT
    # key survive cancellation, keep only the Z-axis direction. This matches
    # the original I.Q. control feel — depth movement takes precedence because
    # the player is more likely to be dodging an incoming wave than sidestepping.
    z_dirs = held_dirs & {Direction.FORWARD, Direction.BACKWARD}
    x_dirs = held_dirs & {Direction.LEFT, Direction.RIGHT}
    if z_dirs and x_dirs:
        held_dirs = z_dirs
    # Return the first surviving direction in the canonical iteration order.
    for direction in MOVEMENT_KEYS:
        if direction in held_dirs:
            return direction
    return None  # unreachable — held_dirs ⊆ MOVEMENT_KEYS.keys()
