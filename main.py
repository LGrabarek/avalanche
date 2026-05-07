"""Avalanche — I.Q.: Intelligent Qube reproduction.

Pygbag-compatible async entry point.
Step 9A: Wave progression, Perfect bonus, I.Q. scoring, VICTORY overlay.
"""

import asyncio

import pygame

from audio import AudioSystem
from constants import (
    DANGER_TOP_COLOR,
    KEY_DETONATE,
    KEY_MARK,
    KEY_TRIGGER,
    KEY_TRIGGER_ALT,
    KEY_TURBO,
    PLAYER_HALF_EXTENT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SOUND_ENABLED,
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
from fonts import load_font
from game_manager import GameManager
from grid_manager import GridManager
from hud import Hud
from player import Player
from renderer import ProjectedFace, Renderer
from wave_data import STAGES
from wave_manager import MAX_ACTIVE_CUBES, WaveManager

# --- Tuning -------------------------------------------------------------------
DT_CLAMP: float = 0.1             # Cap dt so tab-switch spirals don't explode state
BG_COLOR: tuple[int, int, int] = (0, 0, 0)
# B3d: Dark floor ellipse drawn beneath the player between the grid and player
# render passes.  Chosen darker than the tile palette (~90 brightness) so it
# reads as a shadow without being too heavy.
SHADOW_COLOR: tuple[int, int, int] = (30, 30, 40)

# --- Pause menu ---------------------------------------------------------------
MENU_ITEMS: tuple[str, ...] = ("RESUME", "RESTART")
MENU_ITEM_COUNT: int = len(MENU_ITEMS)  # kept in sync with MENU_ITEMS


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


def _build_cube_faces(
    renderer: Renderer,
    wave: WaveManager,
    danger: frozenset[tuple[int, int]],
) -> list[ProjectedFace]:
    """Project the six faces of every live cube in the wave.

    Each cube queries the wave's shared `tumble_progress`, applies the pivot
    rotation via `get_cube_vertices`, then emits 6 color-tagged faces through
    the standard projection + back-face-cull pipeline.

    B3e: cubes in `danger` (one tick from the front edge) have their top face
    (index 0 in _CUBE_FACES) rendered in DANGER_TOP_COLOR as a visual telegraph.
    """
    faces: list[ProjectedFace] = []
    max_faces = MAX_ACTIVE_CUBES * 6
    for gx, gz, progress, cube_type in wave.iter_cubes():
        world_verts = get_cube_vertices(gx, gz, progress)
        is_danger = (gx, gz) in danger
        for face_idx, (face_verts, fill_color, edge_color, edge_width) in enumerate(
            get_cube_faces(world_verts, cube_type)
        ):
            color = DANGER_TOP_COLOR if (is_danger and face_idx == 0) else fill_color
            projected = renderer.project_face(face_verts, color, edge_color, edge_width)
            if projected is not None:
                faces.append(projected)
    assert len(faces) <= max_faces, (
        f"cube face count {len(faces)} exceeded bound {max_faces}"
    )
    return faces


def _draw_player_shadow(
    scene_surf: pygame.Surface,
    renderer: Renderer,
    player: Player,
) -> None:
    """Draw a dark floor ellipse beneath the player as a ground-contact shadow.

    B3d: Projects the four corners of the player footprint at floor level (y=0)
    and uses their screen-space bounding box to size and place the ellipse.
    Called after the grid/cube/marker render pass so the shadow sits on top of
    the tiles, and before the player render pass so the player cube is drawn
    on top of its own shadow.
    """
    px, pz = player.position()
    fpx, fpz = float(px), float(pz)
    he = PLAYER_HALF_EXTENT
    corners = [
        renderer.project_vertex(fpx - he, 0.0, fpz - he),
        renderer.project_vertex(fpx + he, 0.0, fpz - he),
        renderer.project_vertex(fpx + he, 0.0, fpz + he),
        renderer.project_vertex(fpx - he, 0.0, fpz + he),
    ]
    if any(c is None for c in corners):
        return
    valid: list[tuple[float, float, float]] = [c for c in corners if c is not None]
    assert len(valid) == 4, "expected 4 valid shadow corner projections"
    sx_vals = [c[0] for c in valid]
    sy_vals = [c[1] for c in valid]
    ew = max(4, int(max(sx_vals)) - int(min(sx_vals)))
    eh = max(2, int(max(sy_vals)) - int(min(sy_vals)))
    rect = pygame.Rect(int(min(sx_vals)), int(min(sy_vals)), ew, eh)
    _ = pygame.draw.ellipse(scene_surf, SHADOW_COLOR, rect)  # no dirty-rect tracking


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
    menu_selected: int,
) -> tuple[bool, bool, int]:
    """Process one frame of pygame events. Returns (running, paused, menu_selected).

    Step 4A wires two discrete action keys:
      * `KEY_MARK` (SPACE) — place a mark at the player's current tile.
      * `KEY_TRIGGER` (X) / `KEY_TRIGGER_ALT` (ENTER) — resolve the mark.

    These go through KEYDOWN events (not held-key polling) because they
    must fire exactly once per press; holding SPACE should not spam marks.
    Movement stays on `pygame.key.get_pressed()` in the held-keys path.
    Step 6A adds ACTIVEEVENT to pause the game on focus loss.
    Step 14 adds Esc pause menu: opens/closes MENU phase, routes ↑↓ and
    confirm keys, and tracks the highlighted cursor via menu_selected.
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
            return False, paused, menu_selected
        if event.type == pygame.ACTIVEEVENT:
            paused = not bool(event.gain)  # gain=1: focused; gain=0: focus lost
            if not event.gain:
                game.set_turbo(False)  # prevent stuck-turbo if KEYUP is lost on blur
        elif event.type == pygame.KEYDOWN and not paused:
            if game.phase == GamePhase.TITLE:
                game.on_title_advance()  # any key starts the game from the title screen
            elif game.phase in (GamePhase.GAME_OVER, GamePhase.VICTORY):
                game.on_restart_key(player)  # any key restarts from TITLE
            elif game.phase == GamePhase.STAGE_CLEAR:
                game.on_stage_clear_key(player)  # any key advances to next stage
            elif game.phase == GamePhase.MENU:
                if event.key == pygame.K_ESCAPE:
                    game.on_menu_close()          # Esc = Resume (direct close)
                elif event.key in (pygame.K_UP, pygame.K_w):
                    menu_selected = (menu_selected - 1) % MENU_ITEM_COUNT
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    menu_selected = (menu_selected + 1) % MENU_ITEM_COUNT
                elif event.key in (KEY_TRIGGER, KEY_TRIGGER_ALT):
                    game.on_menu_select(menu_selected, player)
                    menu_selected = 0  # reset cursor after any selection
            elif event.key == pygame.K_ESCAPE:
                game.on_menu_open()   # open menu; cursor resets in main()
                menu_selected = 0
            elif event.key == KEY_MARK:
                _ = game.try_mark(player.grid_x, player.grid_z)  # unused: result is advisory
            elif event.key in (KEY_TRIGGER, KEY_TRIGGER_ALT):
                _ = game.on_trigger(player)  # unused: outcome is for Step 10 audio cues
            elif event.key == KEY_DETONATE:
                game.on_detonate(player)  # void: score delta tracked inside game
            elif event.key == KEY_TURBO:
                game.set_turbo(True)  # hold-to-turbo: activate on keydown
        elif event.type == pygame.KEYUP and event.key == KEY_TURBO:
            game.set_turbo(False)  # deactivate turbo on key release
    return True, paused, menu_selected


def _draw_menu_overlay(
    screen: pygame.Surface,
    big_font: pygame.font.Font,
    small_font: pygame.font.Font,
    selected: int,
) -> None:
    """Full-screen pause menu with keyboard-navigable item list.

    Draws a semi-transparent veil, a PAUSED title, two items (RESUME /
    RESTART), and a controls hint.  The selected item is highlighted in gold
    with a '>' prefix; the other is dimmed.
    """
    assert 0 <= selected < MENU_ITEM_COUNT, (
        f"menu cursor {selected} out of range [0, {MENU_ITEM_COUNT})"
    )
    veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 200))
    _ = screen.blit(veil, (0, 0))  # unused: no dirty-rect tracking

    big_line_h = big_font.size("A")[1]
    title_y = SCREEN_HEIGHT // 4
    title_surf = big_font.render("PAUSED", True, (220, 220, 220))
    title_x = (SCREEN_WIDTH - title_surf.get_width()) // 2
    _ = screen.blit(title_surf, (title_x, title_y))

    item_y = title_y + big_line_h * 2
    for i, label in enumerate(MENU_ITEMS):
        color = (255, 240, 100) if i == selected else (140, 140, 140)
        prefix = "> " if i == selected else "  "
        surf = big_font.render(prefix + label, True, color)
        cx = (SCREEN_WIDTH - surf.get_width()) // 2
        _ = screen.blit(surf, (cx, item_y + i * (big_line_h + 8)))

    hint_text = "W/S or Up/Down  Navigate     X / Enter  Confirm     Esc  Resume"
    hint_surf = small_font.render(hint_text, True, (90, 90, 110))
    hint_x = (SCREEN_WIDTH - hint_surf.get_width()) // 2
    hint_y = SCREEN_HEIGHT * 3 // 4
    _ = screen.blit(hint_surf, (hint_x, hint_y))


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
    stage_num = game.stage_index + 1
    wave_label = f"Stage {stage_num}  —  Wave {game.wave_index + 1} / {game.wave_count}"
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
    hold_ready: bool,
) -> None:
    """Centered GAME OVER block with final score and restart prompt.

    The prompt is shown dimmed for the first END_SCREEN_HOLD seconds so an
    accidental keypress at the moment of death cannot skip the screen.  Once
    the hold expires the prompt brightens and keypresses are accepted.
    """
    lines: tuple[str, ...] = (
        "GAME OVER",
        f"Score: {game.score}",
        "Press any key to restart",
    )
    assert len(lines) == 3, "game_over overlay line count changed — update assertion"
    prompt_color: tuple[int, int, int] = (140, 140, 140) if hold_ready else (50, 50, 55)
    colors: tuple[tuple[int, int, int], ...] = (
        (220, 60, 60),
        (220, 220, 220),
        prompt_color,
    )
    line_h = font.size("A")[1]
    total_h = len(lines) * line_h
    start_y = (SCREEN_HEIGHT - total_h) // 2
    for i, text in enumerate(lines):
        surface = font.render(text, True, colors[i])
        cx = (SCREEN_WIDTH - surface.get_width()) // 2
        _ = screen.blit(surface, (cx, start_y + i * line_h))  # no dirty-rect


def _draw_stage_clear_overlay(
    screen: pygame.Surface,
    font: pygame.font.Font,
    game: GameManager,
    hold_ready: bool,
) -> None:
    """Between-stage screen: stage number, running score, and continue prompt.

    Shown after the last wave of a non-final stage completes. The prompt is
    dimmed for END_SCREEN_HOLD seconds so the player has time to read their
    score before input is accepted.
    """
    cleared_stage = game.stage_index + 1    # 1-based stage just finished
    next_stage = game.stage_index + 2       # 1-based stage about to start
    lines: tuple[str, ...] = (
        f"STAGE {cleared_stage} CLEAR",
        f"Score: {game.score}",
        f"Next: Stage {next_stage}",
        "Press any key to continue",
    )
    assert len(lines) == 4, "stage_clear overlay line count changed — update assertion"
    prompt_color: tuple[int, int, int] = (140, 140, 140) if hold_ready else (50, 50, 55)
    colors: tuple[tuple[int, int, int], ...] = (
        (100, 220, 100),    # green — positive stage-complete signal
        (220, 220, 220),
        (180, 180, 220),
        prompt_color,
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
    hold_ready: bool,
) -> None:
    """Centered STAGE CLEAR label with final score and I.Q. readout.

    The prompt is shown dimmed for the first END_SCREEN_HOLD seconds so the
    player has time to read the score before input is accepted.  Once the hold
    expires the prompt brightens and keypresses are accepted.
    """
    lines: tuple[str, ...] = (
        "GAME CLEAR",
        f"Score: {game.score}",
        f"I.Q.: {game.iq_score}",
        "Press any key to restart",
    )
    assert len(lines) == 4, "victory overlay line count changed — update assertion"
    prompt_color: tuple[int, int, int] = (140, 140, 140) if hold_ready else (50, 50, 55)
    colors: tuple[tuple[int, int, int], ...] = (
        (255, 240, 100),
        (220, 220, 220),
        (180, 220, 255),
        prompt_color,
    )
    line_h = font.size("A")[1]
    total_h = len(lines) * line_h
    start_y = (SCREEN_HEIGHT - total_h) // 2
    for i, text in enumerate(lines):
        surface = font.render(text, True, colors[i])
        cx = (SCREEN_WIDTH - surface.get_width()) // 2
        _ = screen.blit(surface, (cx, start_y + i * line_h))  # no dirty-rect


# --- Entry point --------------------------------------------------------------

async def main() -> None:
    # Step 25 (A1): pre-init mixer before pygame.init() so the audio subsystem
    # opens with the correct format. 22050 Hz mono 16-bit matches AudioSystem's
    # SAMPLE_RATE constant. buffer=512 keeps latency low (<12 ms at 22050 Hz).
    pygame.mixer.pre_init(frequency=22050, size=-16, channels=1, buffer=512)
    pygame.init()
    audio: AudioSystem | None = AudioSystem() if SOUND_ENABLED else None
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Avalanche")
    clock = pygame.time.Clock()
    # Step 22 (A3): load_font() uses bundled assets/freesansbold.ttf with an
    # automatic fallback to Font(None, …) if the asset is absent.
    font = load_font(28)
    overlay_font = load_font(64)  # large text for title / wave banners
    renderer = Renderer()
    grid = GridManager()
    player = Player(grid)
    wave = WaveManager()
    effects = FlashEffects()
    game = GameManager(grid, wave, effects, audio=audio)
    game.start_first_wave(player, STAGES[0])
    hud = Hud(player, grid, wave, game)

    scene_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    running = True
    paused: bool = False
    menu_selected: int = 0  # highlighted item index in the pause menu

    # Rule 2 — top-level event loop exception. This is the ONE bounded-by-user
    # loop in the application; every nested loop we write must have an
    # explicit upper bound. Exits when `running` becomes False.
    while running:
        dt = clock.tick(0) / 1000.0  # Uncapped — browser rAF governs pacing
        if dt > DT_CLAMP:
            dt = DT_CLAMP

        running, paused, menu_selected = _drain_events(player, game, paused, menu_selected)

        # update() handles WAVE_RISING timer and must run even while frozen
        # so the between-wave pause counts down correctly.
        if not paused:
            game.update(dt, player)

        frozen = game.phase in (
            GamePhase.TITLE, GamePhase.WAVE_RISING,
            GamePhase.GAME_OVER, GamePhase.VICTORY,
            GamePhase.STAGE_CLEAR, GamePhase.MENU,
        )
        if not paused and not frozen:
            held_keys = pygame.key.get_pressed()
            blocked = wave.blocked_tiles()
            player.update(dt, held_keys, blocked)
            tick_fired = wave.update(dt, grid.front_edge_z)
            if tick_fired:
                # Sample phase BEFORE on_tick: on_tick may transition the
                # phase (e.g. WAVE_ACTIVE → WAVE_RISING on last cube), so
                # we need the phase that was active when the tick fired.
                phase_at_tick = game.phase
                game.on_tick(player, wave)
                if audio is not None and phase_at_tick in (
                    GamePhase.WAVE_ACTIVE, GamePhase.AVALANCHE
                ):
                    audio.play_tick(phase_at_tick == GamePhase.AVALANCHE)
            game.check_mid_tumble_crush(player, wave)
        effects.update(dt)

        player_visual = PlayerVisual.CRUSHED if player.is_crushed else PlayerVisual.NORMAL
        danger = wave.danger_cubes(grid.front_edge_z)
        # B3d/B3e: split face list so the player shadow can be drawn between
        # the grid+cube layer and the player layer, preserving correct depth
        # ordering within each layer while placing the shadow on top of tiles.
        face_list: list[ProjectedFace] = []
        face_list.extend(_build_grid_faces(renderer, grid))
        face_list.extend(_build_cube_faces(renderer, wave, danger))
        face_list.extend(_build_marker_faces(renderer, grid))
        player_faces = _build_player_faces(renderer, player, player_visual)

        scene_surf.fill(BG_COLOR)
        renderer.render_frame(scene_surf, face_list)   # grid + cubes + markers
        _draw_player_shadow(scene_surf, renderer, player)  # shadow on tiles
        renderer.render_frame(scene_surf, player_faces)    # player atop shadow
        effects.draw(scene_surf, renderer)
        shake_x, shake_y = effects.shake_offset()
        screen.fill(BG_COLOR)
        _ = screen.blit(scene_surf, (shake_x, shake_y))  # unused: dest rect
        hud.draw(screen, font)
        if paused:
            _draw_pause_overlay(screen, font)
        elif game.phase == GamePhase.MENU:
            _draw_menu_overlay(screen, overlay_font, font, menu_selected)
        elif game.phase == GamePhase.TITLE:
            _draw_title_overlay(screen, overlay_font, font)
        elif game.phase == GamePhase.WAVE_RISING:
            _draw_wave_rising_overlay(screen, overlay_font, font, game)
        elif game.phase == GamePhase.GAME_OVER:
            _draw_game_over_overlay(screen, font, game, game.end_hold_ready)
        elif game.phase == GamePhase.STAGE_CLEAR:
            _draw_stage_clear_overlay(screen, font, game, game.end_hold_ready)
        elif game.phase == GamePhase.VICTORY:
            _draw_victory_overlay(screen, font, game, game.end_hold_ready)

        pygame.display.flip()
        await asyncio.sleep(0)  # CRITICAL: yield to browser rAF

    pygame.quit()


if __name__ == "__main__":
    # Pygbag invokes main.py as __main__, so this guard preserves the browser
    # entry point while letting tests import the module without auto-running.
    asyncio.run(main())
