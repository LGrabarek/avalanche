"""HUD — overlay text showing performance, player state, wave state, score.

Extracted from `main.py` at Step 4 (per `docs/PLAN.md`) so the overlay has
its own testable surface and Step 10 can grow richer widgets (wave counter,
penalty meter, I.Q. display, controls legend) without inflating the main
loop. The HUD is render-only: it reads state and blits text; it never
writes to game state.

Step 4A additions vs. the inlined Step 3 version:
  * `Score: N`
  * Mark indicator: `Mark: (x, z)` or `Mark: ---`
  * Controls hint line.

Step 17A: surface cache added. `font.render()` is skipped when the text for a
HUD line is identical to the cached value for that label. Static lines (the
hint row) are rendered once and reused every frame. Volatile lines (FPS, tick
progress) re-render only on change. Under normal play this saves 6–7 of 8
`font.render()` calls per frame.
"""

import pygame

from constants import PENALTY_THRESHOLD, SCREEN_HEIGHT, ColorRGB
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

# Surface cache bound: 4 stat labels + 1 hint label.
# If a new HUD line is added, bump this constant accordingly.
MAX_HUD_CACHE_ENTRIES: int = 5


class Hud:
    """Overlay renderer with surface caching.

    Holds references to the game subsystems so the main loop passes only
    the surface + font + fps. Keeping those two as arguments (rather than
    stashing them) lets the main loop reuse the same font for all HUD
    lines without routing pygame types through the constructor.

    The surface cache (_cache) stores the last-rendered Surface per label.
    font.render() is called only when the text for a label changes; static
    lines (the hint row) are rendered once and reused every frame.
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
        # label → (last rendered text, color, cached Surface). Populated lazily.
        self._cache: dict[str, tuple[str, ColorRGB, pygame.Surface]] = {}

    def draw(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
    ) -> None:
        """Render the full HUD (top-left stat block + bottom-left hint line)."""
        self._draw_stat_block(screen, font)
        self._draw_hint_line(screen, font)

    # --- Private helpers -----------------------------------------------------

    def _render(
        self,
        label: str,
        text: str,
        font: pygame.font.Font,
        color: ColorRGB,
    ) -> pygame.Surface:
        """Return a cached Surface for `text`/`color`, re-rendering only on change.

        On first call for a new `label`, allocates a surface and stores it.
        On subsequent calls, skips font.render() if both text and color are
        identical to the cached values. The cache is bounded by
        MAX_HUD_CACHE_ENTRIES.
        """
        cached = self._cache.get(label)
        if cached is not None and cached[0] == text and cached[1] == color:
            return cached[2]
        if label not in self._cache:
            assert len(self._cache) < MAX_HUD_CACHE_ENTRIES, (
                f"HUD cache overflow — more than {MAX_HUD_CACHE_ENTRIES} labels used"
            )
        surface = font.render(text, True, color)
        self._cache[label] = (text, color, surface)
        return surface

    def _draw_stat_block(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
    ) -> None:
        """Top-left stat block. 4 lines, line-height driven."""
        mark_str = self._format_mark()
        stage_num = self._game.stage_index + 1
        wave_num = self._game.wave_index + 1
        wave_total = self._game.wave_count
        wave_str = f"{wave_num}/{wave_total}" if wave_total > 0 else "---"
        stats: tuple[tuple[str, str], ...] = (
            ("score",   f"Score: {self._game.score}  Mark: {mark_str}"),
            ("penalty", f"Penalty: {self._game.wave_penalty}/{PENALTY_THRESHOLD}"),
            ("stage",   f"Stage: {stage_num}"),
            ("wave",    f"Wave: {wave_str}"),
        )
        # Rule-5 invariant: line count must match the fixed y-advance loop.
        assert len(stats) == 4, (
            f"HUD stat block expected 4 lines, got {len(stats)} — "
            "update the invariant if intentionally changing the layout"
        )
        for i, (label, text) in enumerate(stats):
            surface = self._render(label, text, font, HUD_COLOR)
            pos = (HUD_LINE_X, HUD_FIRST_LINE_Y + i * HUD_LINE_HEIGHT)
            _ = screen.blit(surface, pos)  # dirty rect unused; full redraw

    def _format_mark(self) -> str:
        """Render the current mark position, or a dash placeholder.

        Rule-5 note: the branch is the function's entire purpose; both arms
        are fully typed (Optional[tuple[int,int]] → str). No padding check
        needed — the type system proves the invariant already.
        """
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
        """Bottom-left one-liner reminding the player which keys do what."""
        hint_text = "Move: WASD  Mark: SPACE  Trigger: X  Detonate: Z  Turbo: hold F  Esc: Menu"
        surface = self._render("hint", hint_text, font, HUD_HINT_COLOR)
        hint_h = surface.get_height()
        y = SCREEN_HEIGHT - hint_h - HUD_HINT_MARGIN_BOTTOM
        _ = screen.blit(surface, (HUD_LINE_X, y))  # dirty rect unused; full redraw
