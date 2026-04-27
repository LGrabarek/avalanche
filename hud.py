"""HUD — overlay text showing performance, player state, wave state, score.

Extracted from `main.py` at Step 4 (per `docs/PLAN.md`) so the overlay has
its own testable surface and Step 10 can grow richer widgets (wave counter,
penalty meter, I.Q. display, controls legend) without inflating the main
loop. The HUD is render-only: it reads state and blits text; it never
writes to game state.

Step 4A additions vs. the inlined Step 3 version:
  * `Score: N`
  * Mark indicator: `Mark: (x, z)` or `Mark: ---`
  * Controls hint line (wave 1 only — Step 10 will gate on wave number;
    for now it always shows because waves aren't a concept yet).
"""

import pygame

from constants import PENALTY_THRESHOLD, SCREEN_HEIGHT
from game_manager import GameManager
from grid_manager import GridManager
from player import Player
from wave_manager import WaveManager

# --- Tuning -------------------------------------------------------------------

HUD_COLOR: tuple[int, int, int] = (200, 200, 200)
HUD_HINT_COLOR: tuple[int, int, int] = (140, 140, 160)
HUD_LINE_X: int = 10
HUD_LINE_HEIGHT: int = 26
HUD_FIRST_LINE_Y: int = 10

# Bottom-anchored hints (controls legend). Placed above the bottom edge so
# the front-row tiles stay visible. 6 lines of cushion keeps it off the
# front-row tiles on the 640-tall canvas.
HUD_HINT_MARGIN_BOTTOM: int = 14


class Hud:
    """Stateless overlay renderer.

    Holds references to the game subsystems so the main loop passes only
    the surface + font + fps. Keeping those two as arguments (rather than
    stashing them) lets the main loop reuse the same font for all HUD
    lines without routing pygame types through the constructor.
    """

    def __init__(
        self,
        player: Player,
        grid: GridManager,
        wave: WaveManager,
        game: GameManager,
    ) -> None:
        self._player: Player = player
        self._grid: GridManager = grid
        self._wave: WaveManager = wave
        self._game: GameManager = game

    def draw(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        fps: float,
        poly_count: int,
    ) -> None:
        """Render the full HUD (top-left stat block + bottom-left hint line)."""
        self._draw_stat_block(screen, font, fps, poly_count)
        self._draw_hint_line(screen, font)

    # --- Private helpers -----------------------------------------------------

    def _draw_stat_block(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        fps: float,
        poly_count: int,
    ) -> None:
        """Top-left stat block. 7 lines, line-height driven."""
        mark_str = self._format_mark()
        wave_num = self._game.wave_index + 1
        wave_total = self._game.wave_count
        wave_str = f"{wave_num}/{wave_total}" if wave_total > 0 else "---"
        lines: tuple[str, ...] = (
            f"FPS: {fps:.0f}",
            f"Polys: {poly_count}",
            f"Pos: ({self._player.grid_x}, {self._player.grid_z})",
            f"Cubes: {self._wave.cube_count}  Tick: {self._wave.tick_progress:.2f}",
            f"Score: {self._game.score}  Mark: {mark_str}",
            f"Penalty: {self._game.wave_penalty}/{PENALTY_THRESHOLD}",
            f"Wave: {wave_str}",
        )
        # Rule-5 invariant: line count must match the fixed y-advance loop.
        assert len(lines) == 7, (
            f"HUD stat block expected 7 lines, got {len(lines)} — "
            "update the invariant if intentionally changing the layout"
        )
        for i, text in enumerate(lines):
            surface = font.render(text, True, HUD_COLOR)
            _ = screen.blit(  # unused: no dirty-rect tracking
                surface,
                (HUD_LINE_X, HUD_FIRST_LINE_Y + i * HUD_LINE_HEIGHT),
            )

    def _format_mark(self) -> str:
        """Render the current mark position, or a dash placeholder."""
        mark = self._grid.marked_position
        if mark is None:
            return "---"
        mx, mz = mark
        return f"({mx}, {mz})"

    def _draw_hint_line(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
    ) -> None:
        """Bottom-left one-liner reminding the player which keys do what.

        Step 7A adds the Detonate binding (Z key).
        """
        hint_text = "Move: WASD / Arrows   Mark: SPACE   Trigger: X / Enter   Detonate: Z"
        surface = font.render(hint_text, True, HUD_HINT_COLOR)
        hint_h = surface.get_height()
        y = SCREEN_HEIGHT - hint_h - HUD_HINT_MARGIN_BOTTOM
        _ = screen.blit(surface, (HUD_LINE_X, y))  # unused: no dirty-rect tracking
