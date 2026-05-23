"""Grid state: 2D integer array of tile states.

The grid is the authoritative source for what a player can stand on and what
cubes can traverse. Rendering reads this data each frame — it never writes.

Coordinates: `(x, z)` where `x` is the column (0..width-1) and `z` is the row
(0 = front/camera-side, depth-1 = back). This matches the world-space
convention in `cube_data.py`.
"""

from collections.abc import Iterator

from constants import GRID_DEPTH, GRID_WIDTH, TileState


class GridManager:
    """Owns the platform tile grid.

    Tile layout is a flat `list[TileState]` of length `width * depth` indexed
    as `_tiles[z * width + x]`. A flat list is cheaper to copy and iterate
    under WASM than a list-of-lists, and the bounds check is centralized.

    Mark lifecycle (Step 4 fleshes this out further):
      - `mark_tile(x, z)` sets the tile to `MARKED`, clears any previous mark.
      - `clear_mark()` resets the currently marked tile back to `PLATFORM`.
      - Only one mark is active at a time.
    """

    def __init__(self, width: int = GRID_WIDTH, depth: int = GRID_DEPTH) -> None:
        if width <= 0 or depth <= 0:
            raise ValueError(f"grid dimensions must be positive, got {width}x{depth}")
        self._width: int = width
        self._initial_depth: int = depth  # baseline depth; resize/reset return to this
        self._depth: int = depth
        self._tiles: list[TileState] = [TileState.PLATFORM] * (width * depth)
        self._marked: tuple[int, int] | None = None
        assert len(self._tiles) == width * depth, "tile storage size must match dimensions"

    @property
    def width(self) -> int:
        return self._width

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def marked_position(self) -> tuple[int, int] | None:
        """Currently marked tile, or None if nothing is marked."""
        return self._marked

    @property
    def front_edge_z(self) -> int:
        """First z-row from the front that contains at least one non-void tile.

        Returns 0 when no rows have been deleted (normal starting state).
        Returns `depth` when every tile is void (degenerate — not reachable
        in normal gameplay). Used by WaveManager so cubes drop at the new
        platform front edge after penalty row deletions, rather than
        continuing to tumble over empty space.
        """
        assert len(self._tiles) == self._width * self._depth, (
            "tile storage size diverged from width * depth"
        )
        for z in range(self._depth):
            if any(
                self._tiles[z * self._width + x] != TileState.VOID
                for x in range(self._width)
            ):
                return z
        return self._depth

    def reset(self) -> None:
        """Restore every tile to PLATFORM and clear any active mark.

        Called when the player restarts the game from GAME_OVER or VICTORY.
        Resets _depth to _initial_depth so Perfect-wave grid growth is discarded.
        """
        self._depth = self._initial_depth
        self._tiles = [TileState.PLATFORM] * (self._width * self._depth)
        self._marked = None
        assert len(self._tiles) == self._width * self._depth, (
            "tile storage size wrong after reset"
        )

    def resize(self, new_width: int) -> None:
        """Change the active grid width and reset all tiles to PLATFORM.

        Clears every tile (hard reset). Use `set_active_width` when tile state
        (e.g. void rows from penalties) must be preserved across the resize.
        Callers should pass STAGE_GRID_WIDTHS[stage_index] from constants.
        """
        from constants import GRID_WIDTH  # local import avoids circular at module level
        if not (1 <= new_width <= GRID_WIDTH):
            raise ValueError(
                f"new_width {new_width} must be in [1, GRID_WIDTH={GRID_WIDTH}]"
            )
        self._width = new_width
        self._depth = self._initial_depth  # discard any Perfect-wave depth growth
        self._tiles = [TileState.PLATFORM] * (new_width * self._depth)
        self._marked = None
        assert len(self._tiles) == self._width * self._depth, (
            "tile storage size wrong after resize"
        )

    def set_active_width(self, new_width: int) -> None:
        """Change the active grid width while preserving existing tile state.

        Unlike `resize()`, which resets all tiles to PLATFORM, this method
        reformats the tile storage so each row has `new_width` columns:
        - Existing columns are copied verbatim (VOID rows from penalties stay).
        - New columns beyond the old width are initialised to PLATFORM.
        - Columns beyond `new_width` (shrinking) are dropped.

        Called at stage transitions so deleted rows carry forward while the
        visual grid matches the new stage's wave-pattern width. In normal
        forward play the grid only grows (7→9→11), so no columns are lost.

        Pre-allocates the full new tile list before copying so no unbounded
        `append` occurs (Rule 3).
        """
        from constants import GRID_WIDTH  # local import avoids circular at module level
        if not (1 <= new_width <= GRID_WIDTH):
            raise ValueError(
                f"new_width {new_width} must be in [1, GRID_WIDTH={GRID_WIDTH}]"
            )
        if new_width == self._width:
            return  # no-op: width unchanged
        old_width = self._width
        copy_cols = min(old_width, new_width)
        new_tiles: list[TileState] = [TileState.PLATFORM] * (new_width * self._depth)
        for z in range(self._depth):
            old_start = z * old_width
            new_start = z * new_width
            for x in range(copy_cols):
                new_tiles[new_start + x] = self._tiles[old_start + x]
            # New columns beyond old_width: propagate VOID when the entire row
            # is void (penalty-deleted rows must not appear as PLATFORM on the
            # expanded side — asymmetric tile state causes visual corruption).
            if new_width > copy_cols:
                row_is_void = all(
                    new_tiles[new_start + x] == TileState.VOID
                    for x in range(copy_cols)
                )
                if row_is_void:
                    for x in range(copy_cols, new_width):
                        new_tiles[new_start + x] = TileState.VOID
        self._tiles = new_tiles
        self._width = new_width
        # Clear mark if it fell outside the new width.
        if self._marked is not None and self._marked[0] >= new_width:
            self._marked = None
        assert len(self._tiles) == self._width * self._depth, (
            "tile storage size wrong after set_active_width"
        )

    def in_bounds(self, x: int, z: int) -> bool:
        """Coordinate-range check. Does not consult tile state."""
        return 0 <= x < self._width and 0 <= z < self._depth

    def get_tile(self, x: int, z: int) -> TileState:
        """Read a tile. Raises IndexError if `(x, z)` is out of bounds."""
        if not self.in_bounds(x, z):
            raise IndexError(f"grid coords ({x}, {z}) out of bounds "
                             f"[0..{self._width}) x [0..{self._depth})")
        return self._tiles[z * self._width + x]

    def set_tile(self, x: int, z: int, state: TileState) -> None:
        """Write a tile. Raises IndexError if `(x, z)` is out of bounds."""
        if not self.in_bounds(x, z):
            raise IndexError(f"grid coords ({x}, {z}) out of bounds "
                             f"[0..{self._width}) x [0..{self._depth})")
        self._tiles[z * self._width + x] = state

    def is_valid_position(self, x: int, z: int) -> bool:
        """True iff `(x, z)` is in bounds AND not a void tile.

        This is the single source of truth the player and crush detector use
        to decide whether a square is standable. Keep semantics narrow: a
        marked tile or trap tile IS valid (you can stand on them).
        """
        if not self.in_bounds(x, z):
            return False
        return self._tiles[z * self._width + x] != TileState.VOID

    def iter_tiles(self) -> Iterator[tuple[int, int, TileState]]:
        """Yield every non-void tile as `(x, z, state)`, row by row from front.

        Void tiles are skipped so the renderer never has to handle them.
        Bounded by `width * depth`; the upper bound is implicit in the
        two nested for-loops over finite iterables.

        **Contract:** callers must not mutate the grid (`set_tile`, `mark_tile`,
        `clear_mark`, future row-delete) while consuming this iterator. The
        backing list's length never changes under Step 2-5 mutations, so the
        index math stays valid, but a mid-iteration state change can produce
        a rendered frame with mixed before/after state. Consume the iterator
        eagerly (e.g. into a list) if mutation during iteration is required.
        """
        # Rule-5 invariant: tile storage matches declared dimensions. Step 6
        # mutates tiles in place (row deletion), so the guarantee that nothing
        # grew or shrank the backing list is load-bearing for the indexing math.
        assert len(self._tiles) == self._width * self._depth, (
            "tile storage size diverged from width * depth"
        )
        for z in range(self._depth):
            for x in range(self._width):
                state = self._tiles[z * self._width + x]
                if state != TileState.VOID:
                    yield (x, z, state)

    # --- Mark lifecycle ------------------------------------------------------

    def mark_tile(self, x: int, z: int) -> None:
        """Place a mark at `(x, z)`; clears any previous mark first.

        Attempting to mark a void tile or an out-of-bounds tile is a caller
        error (the UI should gate this on `is_valid_position` first).
        """
        if not self.is_valid_position(x, z):
            raise ValueError(f"cannot mark invalid tile ({x}, {z})")
        self.clear_mark()
        self.set_tile(x, z, TileState.MARKED)
        self._marked = (x, z)

    def clear_mark(self) -> None:
        """Clear the active mark (no-op if nothing is marked).

        Restores the previously-marked tile to `PLATFORM`. Void tiles and
        traps cannot be marked, so resetting to PLATFORM is always safe here.
        """
        if self._marked is None:
            return
        mx, mz = self._marked
        assert self.in_bounds(mx, mz), "marked position left the grid — corrupted state"
        # Only overwrite if the tile is still MARKED; a row deletion or other
        # mutation could have already flipped it to VOID since the mark was set.
        if self._tiles[mz * self._width + mx] == TileState.MARKED:
            self._tiles[mz * self._width + mx] = TileState.PLATFORM
        self._marked = None

    # --- Row deletion --------------------------------------------------------

    def delete_front_row(self) -> bool:
        """Void every tile in the front-most non-void row. Returns True if deleted.

        Scans from z=0 (camera-side / bottom-of-screen edge) toward z=depth-1,
        voiding the first row that has at least one non-void tile.  Any active
        mark in that row is also cleared (the tile becomes VOID so the mark
        reference must not outlive the tile).
        Called by GameManager when a penalty threshold triggers row deletion.
        """
        for z in range(self._depth):
            row_has_tile = any(
                self._tiles[z * self._width + x] != TileState.VOID
                for x in range(self._width)
            )
            if not row_has_tile:
                continue
            for x in range(self._width):
                self._tiles[z * self._width + x] = TileState.VOID
            if self._marked is not None and self._marked[1] == z:
                # Tile is being voided — bypass clear_mark() to avoid overwriting
                # the now-VOID tile back to PLATFORM. Zero _marked directly.
                self._marked = None
            assert all(
                self._tiles[z * self._width + x] == TileState.VOID
                for x in range(self._width)
            ), f"row {z} not fully voided after delete_front_row"
            return True
        return False

    def restore_front_row(self) -> bool:
        """Restore the row immediately in front of the current platform edge.

        Returns True if a row was restored; False when the grid is fully intact
        (`front_edge_z == 0`) and there is nothing to restore.

        Finds `front_edge_z` — the first non-void row from z=0 — then restores
        the row at `front_edge_z - 1`, which is always directly adjacent to the
        existing platform.  This ensures the restored row is seamlessly
        connected to the rest of the platform with no gap, regardless of how
        many rows have previously been deleted.

        Contrast with a naïve "first all-void row from z=0" scan: when two rows
        have been deleted, that approach would restore z=0 while z=1 remains
        void, creating a disconnected island unreachable by the player.
        """
        assert len(self._tiles) == self._width * self._depth, (
            "tile storage size diverged from width * depth"
        )
        front = self.front_edge_z
        if front == 0:
            # Grid fully intact — grow by one PLATFORM row appended at the back
            # (z = self._depth).  Existing z-indices are unaffected; waves pack
            # from GRID_DEPTH-1=59 and are not touched.  The extra row raises
            # surviving_rows for the score and IQ calculations, matching the
            # original I.Q. behaviour where Perfect clears on a full grid expand
            # the platform beyond the stage's starting row count.
            self._tiles.extend([TileState.PLATFORM] * self._width)
            self._depth += 1
            assert len(self._tiles) == self._width * self._depth, (
                "tile storage size wrong after Perfect-wave grid growth"
            )
            return True
        restore_z = front - 1
        assert 0 <= restore_z < self._depth, (
            f"restore_z {restore_z} out of range — front_edge_z invariant violated"
        )
        # Every row before front_edge_z must be entirely void (delete_front_row
        # always voids complete rows), so restore_z should be all-void here.
        assert all(
            self._tiles[restore_z * self._width + x] == TileState.VOID
            for x in range(self._width)
        ), f"row {restore_z} expected all-void before restore — tile storage may be corrupt"
        for x in range(self._width):
            self._tiles[restore_z * self._width + x] = TileState.PLATFORM
        assert all(
            self._tiles[restore_z * self._width + x] == TileState.PLATFORM
            for x in range(self._width)
        ), f"row {restore_z} not fully restored after restore_front_row"
        return True
