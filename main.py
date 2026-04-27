"""Avalanche — I.Q.: Intelligent Qube reproduction.

Pygbag-compatible async entry point.
Step 9A: Wave progression, Perfect bonus, I.Q. scoring, VICTORY overlay.
"""

import asyncio

import pygame

from constants import (
    KEY_DETONATE,
    KEY_MARK,
    KEY_TRIGGER,
    KEY_TRIGGER_ALT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    GamePhase,
)
from cube_data import (
    CONE_SIDES,
    PlayerVisual,
    get_cube_faces,
    get_cube_vertices,
    get_marker_cone_faces,
    get_player_faces,
    get_player_vertices,
    get_tile_face,
)
from effects import FlashEffects
from game_manager import GameManager
from grid_manager import GridManager
from hud import Hud
from player import Player
from renderer import ProjectedFace, Renderer
from wave_data import STAGE_1_WAVES
from wave_manager import MAX_ACTIVE_CUBES, WaveManager

# --- Tuning -------------------------------------------------------------------
DT_CLAMP: float = 0.1             # Cap dt so tab-switch spirals don't explode state
FPS_SAMPLES_MAX: int = 60         # Rolling-dt window size
BG_COLOR: tuple[int, int, int] = (0, 0, 0)


# --- Frame construction -------------------------------------------------------

def _build_grid_faces(renderer: Renderer, grid: GridManager) -> list[ProjectedFace]:
    """Project every non-void tile in the grid; return the visible faces."""
    faces: list[ProjectedFace] = []
    max_tiles = grid.width * grid.depth
    for gx, gz, state in grid.iter_tiles():
        tile_verts, fill_color, edge_color, edge_width = get_tile_face(gx, gz, state)
        projected = renderer.project_face(tile_verts, fill_color, edge_color, edge_width)
        if projected is not None:
            faces.append(projected)
    assert len(faces) <= max_tiles, "more grid faces than tiles on the grid"
    return faces


def _build_player_faces(
    renderer: Renderer,
    player: Player,
    visual: str = PlayerVisual.NORMAL,
) -> list[ProjectedFace]:
    """Project the six faces of the player cube."""
    faces: list[ProjectedFace] = []
    px, pz = player.position()
    scale_y = 0.15 if visual == PlayerVisual.CRUSHED else 1.0
    world_verts = get_player_vertices(px, pz, scale_y)
    for face_verts, fill_color, edge_color, edge_width in get_player_faces(world_verts, visual):
        projected = renderer.project_face(face_verts, fill_color, edge_color, edge_width)
        if projected is not None:
            faces.append(projected)
    assert len(faces) <= 6, "player cube emitted more faces than geometry allows"
    return faces


def _build_cube_faces(renderer: Renderer, wave: WaveManager) -> list[ProjectedFace]:
    """Project the six faces of every live cube in the wave.

    Each cube queries the wave's shared `tumble_progress`, applies the pivot
    rotation via `get_cube_vertices`, then emits 6 color-tagged faces through
    the standard projection + back-face-cull pipeline.
    """
    faces: list[ProjectedFace] = []
    max_faces = MAX_ACTIVE_CUBES * 6
    for gx, gz, progress, cube_type in wave.iter_cubes():
        world_verts = get_cube_vertices(gx, gz, progress)
        for face_verts, fill_color, edge_color, edge_width in get_cube_faces(
            world_verts, cube_type,
        ):
            projected = renderer.project_face(face_verts, fill_color, edge_color, edge_width)
            if projected is not None:
                faces.append(projected)
    assert len(faces) <= max_faces, (
        f"cube face count {len(faces)} exceeded bound {max_faces}"
    )
    return faces


def _build_marker_faces(renderer: Renderer, grid: GridManager) -> list[ProjectedFace]:
    """Project floating inverted-cone markers above MARKED and ADVANTAGE_TRAP tiles.

    Only tiles with a cone colour entry in `_CONE_COLORS` produce faces;
    PLATFORM tiles return an empty list from `get_marker_cone_faces` and are
    skipped cheaply. All visible cone faces are sorted with the rest of the
    scene via the painter's algorithm, so depth ordering is automatic.
    """
    faces: list[ProjectedFace] = []
    max_tiles = grid.width * grid.depth
    for gx, gz, state in grid.iter_tiles():
        cone_faces = get_marker_cone_faces(gx, gz, state)
        for tri_verts, fill_color, edge_color, edge_width in cone_faces:
            projected = renderer.project_triangle(tri_verts, fill_color, edge_color, edge_width)
            if projected is not None:
                faces.append(projected)
    # Rule-3 postcondition: CONE_SIDES triangles per tile, bounded by tile count.
    assert len(faces) <= max_tiles * CONE_SIDES, (
        f"marker cone face count {len(faces)} exceeded theoretical maximum"
    )
    return faces


# --- Loop helpers -------------------------------------------------------------

MAX_EVENTS_PER_FRAME: int = 1024


def _drain_events(
    player: Player,
    game: GameManager,
    paused: bool,
) -> tuple[bool, bool]:
    """Process one frame of pygame events. Returns (running, paused).

    Step 4A wires two discrete action keys:
      * `KEY_MARK` (SPACE) — place a mark at the player's current tile.
      * `KEY_TRIGGER` (X) / `KEY_TRIGGER_ALT` (ENTER) — resolve the mark.

    These go through KEYDOWN events (not held-key polling) because they
    must fire exactly once per press; holding SPACE should not spam marks.
    Movement stays on `pygame.key.get_pressed()` in the held-keys path.
    Step 6A adds ACTIVEEVENT to pause the game on focus loss.
    """
    events = pygame.event.get()
    # Rule-5 check: pygame should never hand us a pathologically-long queue,
    # but an external tool could flood it. A single frame processing >1k
    # events is a runtime failure mode worth surfacing rather than hanging.
    assert len(events) < MAX_EVENTS_PER_FRAME, (
        f"event queue flooded ({len(events)} events in one frame)"
    )
    for event in events:
        if event.type == pygame.QUIT:
            return False, paused
        if event.type == pygame.ACTIVEEVENT:
            paused = not bool(event.gain)  # gain=1: focused; gain=0: focus lost
        elif event.type == pygame.KEYDOWN and not paused:
            if game.phase == GamePhase.TITLE:
                game.on_title_advance()  # any key starts the game from the title screen
            elif game.phase in (GamePhase.GAME_OVER, GamePhase.VICTORY):
                game.on_restart_key(player)  # any key restarts from TITLE
            elif event.key == KEY_MARK:
                _ = game.try_mark(player.grid_x, player.grid_z)  # unused: result is advisory
            elif event.key in (KEY_TRIGGER, KEY_TRIGGER_ALT):
                _ = game.on_trigger(player)  # unused: outcome is for Step 10 audio cues
            elif event.key == KEY_DETONATE:
                game.on_detonate(player)  # void: score delta tracked inside game
    return True, paused


def _draw_pause_overlay(screen: pygame.Surface, font: pygame.font.Font) -> None:
    """Centered PAUSED label — shown when the window loses focus."""
    label = font.render("PAUSED", True, (220, 220, 220))
    cx = (SCREEN_WIDTH - label.get_width()) // 2
    cy = (SCREEN_HEIGHT - label.get_height()) // 2
    _ = screen.blit(label, (cx, cy))  # unused: no dirty-rect tracking


def _draw_title_overlay(
    screen: pygame.Surface,
    big_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    """Full-screen title card: dark veil + game name + press-any-key prompt."""
    veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 180))
    _ = screen.blit(veil, (0, 0))
    title = big_font.render("AVALANCHE", True, (255, 240, 100))
    title_x = (SCREEN_WIDTH - title.get_width()) // 2
    title_y = SCREEN_HEIGHT // 3 - title.get_height() // 2
    _ = screen.blit(title, (title_x, title_y))
    prompt = small_font.render("Press any key to begin", True, (180, 180, 180))
    prompt_x = (SCREEN_WIDTH - prompt.get_width()) // 2
    prompt_y = 2 * SCREEN_HEIGHT // 3 - prompt.get_height() // 2
    _ = screen.blit(prompt, (prompt_x, prompt_y))


def _draw_wave_rising_overlay(
    screen: pygame.Surface,
    big_font: pygame.font.Font,
    small_font: pygame.font.Font,
    game: GameManager,
) -> None:
    """Semi-transparent between-wave banner: optional PERFECT! + wave counter."""
    line_h = big_font.size("A")[1]
    banner_h = line_h * 3         # fixed height — room for two lines + padding
    banner_y = (SCREEN_HEIGHT - banner_h) // 2
    banner = pygame.Surface((SCREEN_WIDTH, banner_h), pygame.SRCALPHA)
    banner.fill((0, 0, 0, 160))
    _ = screen.blit(banner, (0, banner_y))
    text_y = banner_y + line_h // 2
    if game.perfect_display:
        perf = big_font.render("PERFECT!", True, (255, 220, 50))
        perf_x = (SCREEN_WIDTH - perf.get_width()) // 2
        _ = screen.blit(perf, (perf_x, text_y))
        text_y += line_h
    wave_label = f"Wave {game.wave_index + 1} / {game.wave_count}"
    wave_surf = big_font.render(wave_label, True, (220, 220, 220))
    wave_x = (SCREEN_WIDTH - wave_surf.get_width()) // 2
    _ = screen.blit(wave_surf, (wave_x, text_y))
    # Rule-5: banner must sit within the screen bounds.
    assert banner_y >= 0 and banner_y + banner_h <= SCREEN_HEIGHT, (
        "wave_rising banner overflowed screen bounds"
    )


def _draw_game_over_overlay(
    screen: pygame.Surface,
    font: pygame.font.Font,
    game: GameManager,
) -> None:
    """Centered GAME OVER block with final score and restart prompt."""
    lines: tuple[str, ...] = (
        "GAME OVER",
        f"Score: {game.score}",
        "Press any key to restart",
    )
    assert len(lines) == 3, "game_over overlay line count changed — update assertion"
    colors: tuple[tuple[int, int, int], ...] = (
        (220, 60, 60),
        (220, 220, 220),
        (140, 140, 140),
    )
    line_h = font.size("A")[1]
    total_h = len(lines) * line_h
    start_y = (SCREEN_HEIGHT - total_h) // 2
    for i, text in enumerate(lines):
        surface = font.render(text, True, colors[i])
        cx = (SCREEN_WIDTH - surface.get_width()) // 2
        _ = screen.blit(surface, (cx, start_y + i * line_h))  # no dirty-rect


def _draw_victory_overlay(
    screen: pygame.Surface,
    font: pygame.font.Font,
    game: GameManager,
) -> None:
    """Centered STAGE CLEAR label with final score and I.Q. readout."""
    lines: tuple[str, ...] = (
        "STAGE CLEAR",
        f"Score: {game.score}",
        f"I.Q.: {game.iq_score}",
        "Press any key to restart",
    )
    assert len(lines) == 4, "victory overlay line count changed — update assertion"
    colors: tuple[tuple[int, int, int], ...] = (
        (255, 240, 100),
        (220, 220, 220),
        (180, 220, 255),
        (140, 140, 140),
    )
    line_h = font.size("A")[1]
    total_h = len(lines) * line_h
    start_y = (SCREEN_HEIGHT - total_h) // 2
    for i, text in enumerate(lines):
        surface = font.render(text, True, colors[i])
        cx = (SCREEN_WIDTH - surface.get_width()) // 2
        _ = screen.blit(surface, (cx, start_y + i * line_h))  # no dirty-rect


def _update_fps(samples: list[float], dt: float) -> float:
    """Append dt to a bounded rolling window and return the current FPS.

    The window is hard-capped at FPS_SAMPLES_MAX. Rule 3 requires the bound
    check to GUARD the append — we trim first, then append, then assert the
    invariant. This ordering makes the precondition visible at the append
    site rather than leaving it to a trailing cleanup.
    """
    if dt > 1e-6:
        if len(samples) >= FPS_SAMPLES_MAX:
            _ = samples.pop(0)  # unused: side-effect is trimming the oldest sample
        samples.append(dt)
        assert len(samples) <= FPS_SAMPLES_MAX, "fps sample window exceeded cap"
    total = sum(samples)
    if total <= 0.0:
        return 0.0
    return len(samples) / total


# --- Entry point --------------------------------------------------------------

async def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Avalanche")
    clock = pygame.time.Clock()
    # Pygame's bundled freesansbold.ttf works under WASM (no SysFont).
    font = pygame.font.Font(None, 28)
    overlay_font = pygame.font.Font(None, 64)  # large text for title / wave banners
    renderer = Renderer()
    grid = GridManager()
    player = Player(grid)
    wave = WaveManager()
    effects = FlashEffects()
    game = GameManager(grid, wave, effects)
    game.start_first_wave(player, STAGE_1_WAVES)
    hud = Hud(player, grid, wave, game)

    scene_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    fps_samples: list[float] = []
    running = True
    paused: bool = False

    # Rule 2 — top-level event loop exception. This is the ONE bounded-by-user
    # loop in the application; every nested loop we write must have an
    # explicit upper bound. Exits when `running` becomes False.
    while running:
        dt = clock.tick(0) / 1000.0  # Uncapped — browser rAF governs pacing
        if dt > DT_CLAMP:
            dt = DT_CLAMP

        running, paused = _drain_events(player, game, paused)

        # update() handles WAVE_RISING timer and must run even while frozen
        # so the between-wave pause counts down correctly.
        if not paused:
            game.update(dt, player)

        frozen = game.phase in (
            GamePhase.TITLE, GamePhase.WAVE_RISING,
            GamePhase.GAME_OVER, GamePhase.VICTORY,
        )
        if not paused and not frozen:
            held_keys = pygame.key.get_pressed()
            blocked = wave.blocked_tiles()
            player.update(dt, held_keys, blocked)
            tick_fired = wave.update(dt, grid.front_edge_z)
            if tick_fired:
                game.on_tick(player, wave)
            game.check_mid_tumble_crush(player, wave)
        effects.update(dt)

        fps_display = _update_fps(fps_samples, dt)

        player_visual = PlayerVisual.CRUSHED if player.is_crushed else PlayerVisual.NORMAL
        face_list: list[ProjectedFace] = []
        face_list.extend(_build_grid_faces(renderer, grid))
        face_list.extend(_build_cube_faces(renderer, wave))
        face_list.extend(_build_player_faces(renderer, player, player_visual))
        face_list.extend(_build_marker_faces(renderer, grid))

        scene_surf.fill(BG_COLOR)
        renderer.render_frame(scene_surf, face_list)
        effects.draw(scene_surf, renderer)
        shake_x, shake_y = effects.shake_offset()
        screen.fill(BG_COLOR)
        _ = screen.blit(scene_surf, (shake_x, shake_y))  # unused: dest rect
        hud.draw(screen, font, fps_display, len(face_list))
        if paused:
            _draw_pause_overlay(screen, font)
        elif game.phase == GamePhase.TITLE:
            _draw_title_overlay(screen, overlay_font, font)
        elif game.phase == GamePhase.WAVE_RISING:
            _draw_wave_rising_overlay(screen, overlay_font, font, game)
        elif game.phase == GamePhase.GAME_OVER:
            _draw_game_over_overlay(screen, font, game)
        elif game.phase == GamePhase.VICTORY:
            _draw_victory_overlay(screen, font, game)

        pygame.display.flip()
        await asyncio.sleep(0)  # CRITICAL: yield to browser rAF

    pygame.quit()


if __name__ == "__main__":
    # Pygbag invokes main.py as __main__, so this guard preserves the browser
    # entry point while letting tests import the module without auto-running.
    asyncio.run(main())
