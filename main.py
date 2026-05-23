"""Avalanche — I.Q.: Intelligent Qube reproduction.

Pygbag-compatible async entry point.
Step 9A: Wave progression, Perfect bonus, I.Q. scoring, VICTORY overlay.
"""

import asyncio
import math
import random

import pygame

from audio import AudioSystem
from constants import (
    CAM_ZOOM_OUT,
    CAM_ZOOM_SPEED_IN,
    CAM_ZOOM_SPEED_OUT,
    CAMERA_EYE_Y_LERP,
    CAMERA_EYE_Z_LERP,
    CAMERA_EYE_Z_OFFSET,
    CAMERA_FOLLOW_EYE,
    CAMERA_FOLLOW_FOV,
    CAMERA_FOLLOW_SMOOTH,
    CAMERA_POS,
    CAMERA_TARGET,
    CAMERA_WAVE_EYE_Y_SCALE,
    DANGER_TOP_COLOR,
    GRID_DEPTH,
    INTRO_HUMP_WIDTH,
    INTRO_WAVE_AMPLITUDE,
    KEY_DETONATE,
    KEY_MARK,
    KEY_TRIGGER,
    KEY_TRIGGER_ALT,
    KEY_TURBO,
    PENDING_CUBE_COLOR,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SOUND_ENABLED,
    STAGE_GRID_WIDTHS,
    STAGE_INTRO_DURATION,
    ColorRGB,
    GamePhase,
    TileState,
)
from constants import (
    MAX_ARRIVAL_TILES as _MAX_ARRIVAL_TILES,
)
from constants import (
    MAX_CRUMBLE_TILES as _MAX_CRUMBLE_TILES,
)
from cube_data import (
    CONE_SIDES,
    get_cube_faces,
    get_cube_vertices,
    get_marker_cone_faces,
    get_player_character_faces,
    get_table_edge_faces,
    get_tile_face,
)
from effects import (
    MAX_ROW_DELTA_EVENTS as _MAX_ROW_DELTA_EVENTS,
)
from effects import (
    FlashEffects,
)
from fonts import load_font
from game_manager import GameManager
from grid_manager import GridManager
from high_score import MAX_ENTRIES as _HS_MAX_ENTRIES
from high_score import MAX_NAME_LEN as _HS_MAX_NAME_LEN
from hud import Hud
from player import Player
from renderer import ProjectedFace, Renderer
from wave_data import select_all_waves
from wave_manager import MAX_ACTIVE_CUBES, WaveManager

# --- Tuning -------------------------------------------------------------------
DT_CLAMP: float = 0.1             # Cap dt so tab-switch spirals don't explode state
BG_COLOR: tuple[int, int, int] = (0, 0, 0)
DETONATE_FLASH_DUR: float = 0.4   # seconds the right arm stays raised after detonating
TRIGGER_FLASH_DUR: float = 0.4    # seconds the left arm stays raised after triggering
_ARRIVAL_COLOR: tuple[int, int, int] = (255, 200, 80)  # warm-gold start for arrival tiles

# --- Camera -------------------------------------------------------------------
# Phases during which the camera follows the wave front (centre of the
# frontmost active row).  All other phases (TITLE, GAME_OVER, VICTORY) use
# the fixed overview camera (CAMERA_POS / CAMERA_TARGET) so the full grid is
# visible on non-gameplay screens.
_FOLLOW_CAMERA_PHASES: frozenset[GamePhase] = frozenset({
    GamePhase.STAGE_INTRO,   # animation plays while all waves are visible
    GamePhase.WAVE_ACTIVE,
    GamePhase.AVALANCHE,
    GamePhase.WAVE_RISING,
    GamePhase.WAVE_CLEARING,
    GamePhase.PERFECT_CHECK,
    # STAGE_CLEAR: follow camera holds the player's end-of-stage position.
    # The overlay veil covers the 3D scene anyway; switching to overview
    # would cause a jarring zoom-out mid-celebration.
    GamePhase.STAGE_CLEAR,
    # MENU: camera holds still at the player's paused position while the
    # pause overlay is shown. Switching to overview on pause is disorienting.
    GamePhase.MENU,
    # NOTE: GamePhase.ROW_COLLAPSING exists in the enum but is never
    # transitioned to in game_manager.py (reserved for a future animation
    # pass). Add it here when that phase is implemented.
})

# --- Pause menu ---------------------------------------------------------------
MENU_ITEMS: tuple[str, ...] = ("RESUME", "RESTART")
MENU_ITEM_COUNT: int = len(MENU_ITEMS)  # kept in sync with MENU_ITEMS


# --- Frame construction -------------------------------------------------------

def _build_table_edge_faces(
    renderer: Renderer,
    grid: GridManager,
) -> list[ProjectedFace]:
    """Project the table wall quads below the visible grid edges.

    Generates front, left, and right walls that hang TABLE_DEPTH units below
    y=0, updating the front wall z as rows are deleted (front_edge_z changes).
    Wall quads integrate into the painter's-algorithm sort with the grid tiles.
    """
    faces: list[ProjectedFace] = []
    raw = get_table_edge_faces(grid.width, grid.depth, grid.front_edge_z)
    max_wall_faces = grid.width + 2 * (grid.depth - grid.front_edge_z)
    for quad, fill_color, edge_color, edge_width in raw:
        projected = renderer.project_face(quad, fill_color, edge_color, edge_width)
        if projected is not None:
            faces.append(projected)
    assert len(faces) <= max_wall_faces, (
        "projected table faces exceeded theoretical maximum"
    )
    return faces


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
    is_marking: bool,
    is_detonating: bool,
    is_triggering: bool = False,
) -> list[ProjectedFace]:
    """Project the animated player character (head, torso, legs, arms — 36 faces)."""
    faces: list[ProjectedFace] = []
    raw = get_player_character_faces(
        float(player.grid_x), float(player.grid_z),
        player.walk_progress, player.step_parity, player.is_crushed,
        player.facing, is_marking, is_detonating, is_triggering,
    )
    for face_verts, fill_color, edge_color, edge_width in raw:
        projected = renderer.project_face(face_verts, fill_color, edge_color, edge_width)
        if projected is not None:
            assert len(faces) < 36, "character face projection overflow"
            faces.append(projected)
    assert len(faces) <= 36, "character projected face count cannot exceed geometry count"
    return faces


def _build_crumble_faces(
    renderer: Renderer, effects: FlashEffects,
) -> list[ProjectedFace]:
    """Fade deleted tiles from platform colour to black over the crumble duration."""
    faces: list[ProjectedFace] = []
    for gx, gz, progress in effects.iter_crumble_tiles():
        tile_verts, plat_color, _, _ = get_tile_face(gx, gz, TileState.PLATFORM)
        fade = 1.0 - progress
        color = (int(plat_color[0] * fade), int(plat_color[1] * fade),
                 int(plat_color[2] * fade))
        projected = renderer.project_face(tile_verts, color, (0, 0, 0), 0)
        if projected is not None:
            assert len(faces) < _MAX_CRUMBLE_TILES, "crumble face overflow"
            faces.append(projected)
    assert len(faces) <= _MAX_CRUMBLE_TILES, "crumble face count exceeded cap"
    return faces


def _build_arrival_faces(
    renderer: Renderer, effects: FlashEffects,
) -> list[ProjectedFace]:
    """Fade new row tiles from warm-gold to platform colour (Perfect clear reward)."""
    faces: list[ProjectedFace] = []
    for gx, gz, progress in effects.iter_arrival_tiles():
        tile_verts, plat_color, _, _ = get_tile_face(gx, gz, TileState.PLATFORM)
        r = int(_ARRIVAL_COLOR[0] + (plat_color[0] - _ARRIVAL_COLOR[0]) * progress)
        g = int(_ARRIVAL_COLOR[1] + (plat_color[1] - _ARRIVAL_COLOR[1]) * progress)
        b = int(_ARRIVAL_COLOR[2] + (plat_color[2] - _ARRIVAL_COLOR[2]) * progress)
        projected = renderer.project_face(tile_verts, (r, g, b), (0, 0, 0), 0)
        if projected is not None:
            assert len(faces) < _MAX_ARRIVAL_TILES, "arrival face overflow"
            faces.append(projected)
    assert len(faces) <= _MAX_ARRIVAL_TILES, "arrival face count exceeded cap"
    return faces


def _compute_wave_com_z(wave: WaveManager, fallback_z: float) -> float:
    """Mean Z of all active (non-pending) wave cubes, adjusted for tick progress.

    The `+ 0.5 - tick_progress` term gives sub-tile continuity: between ticks
    the COM slides forward in real time instead of jumping at tick boundaries.
    Returns `fallback_z` when no active cubes are present.
    """
    total_z = 0.0
    count = 0
    for _, gz, _, _, pending in wave.iter_cubes():
        if not pending:
            total_z += gz
            count += 1
    if count == 0:
        return fallback_z
    return total_z / count + 0.5 - wave.tick_progress


def _intro_y_bias(gz: int, intro_t: float, z_front_limit: int) -> float:
    """Compute the upward Y offset for a cube at grid-z `gz` during STAGE_INTRO.

    Implements a single cosine hump that sweeps from in front of the wave
    formation (low z, near player) toward the back wall (high z).  The crest
    travels from `z_front_limit - INTRO_HUMP_WIDTH - 1` at t=0 to
    `z_back + INTRO_HUMP_WIDTH` at t=1, so:

      * No cube rises at t=0 (crest is off-screen in front of the formation).
      * No cube rises at t=1 (crest has cleared the back wall — no visual pop).

    Within the hump (dist_passed ∈ [0, INTRO_HUMP_WIDTH]):
        y_bias = AMPLITUDE × cos(π/2 × dist_passed / INTRO_HUMP_WIDTH)
    which gives peak height at the crest (dist=0) and zero at the edges.

    `intro_t`: normalised animation time [0, 1].
    `z_front_limit`: lowest z of wave 0 (from game.wave_front_z).
    """
    if intro_t <= 0.0:
        return 0.0
    fgz = float(gz)
    z_back = float(GRID_DEPTH - 1)
    hump_w = float(INTRO_HUMP_WIDTH)
    crest_start = float(z_front_limit) - hump_w - 1.0
    crest_end = z_back + hump_w
    z_crest = crest_start + intro_t * (crest_end - crest_start)
    dist_passed = z_crest - fgz  # positive = crest has already passed this cube (lower z)
    if dist_passed < 0.0:
        return 0.0  # crest not yet reached this cube (cube at higher z) — floor
    if dist_passed >= hump_w:
        return 0.0  # cube is on the trailing side, past the hump — back to floor
    return INTRO_WAVE_AMPLITUDE * math.cos(math.pi * 0.5 * dist_passed / hump_w)


def _build_cube_faces(
    renderer: Renderer,
    wave: WaveManager,
    danger: frozenset[tuple[int, int]],
    intro_t: float = 0.0,
    z_front_limit: int = 0,
) -> list[ProjectedFace]:
    """Project the six faces of every cube in the wave (active + pending).

    Active cubes use their normal palette.
    Pending cubes (future waves, not yet active) are rendered uniformly in
    PENDING_CUBE_COLOR (grey) so the player can see the wave layout ahead.
    B3e: active cubes in `danger` (one tick from the front edge) have their
    top face overridden with DANGER_TOP_COLOR as a visual telegraph.
    `intro_t` drives the STAGE_INTRO rolling-wave animation: when non-zero,
    cubes receive a cosine-hump Y lift sweeping front-to-back (0.0 = off).
    `z_front_limit` anchors the crest start position (from game.wave_front_z).
    """
    assert 0.0 <= intro_t <= 1.0, f"intro_t {intro_t} outside [0, 1]"
    faces: list[ProjectedFace] = []
    max_faces = MAX_ACTIVE_CUBES * 6
    for gx, gz, progress, cube_type, is_pending in wave.iter_cubes():
        world_verts = get_cube_vertices(gx, gz, progress)
        if intro_t > 0.0:
            y_bias = _intro_y_bias(gz, intro_t, z_front_limit)
            world_verts = tuple(
                (vx, vy + y_bias, vz) for vx, vy, vz in world_verts
            )
        is_danger = (not is_pending) and (gx, gz) in danger
        for face_idx, (face_verts, fill_color, edge_color, edge_width) in enumerate(
            get_cube_faces(world_verts, cube_type)
        ):
            if is_pending:
                # Uniform grey fill + neutral edge: hide cube type until wave
                # activates.  Coloured edges (red FORBIDDEN, green ADVANTAGE)
                # would leak type information before the wave starts.
                color = PENDING_CUBE_COLOR
                eff_edge: ColorRGB | None = (50, 50, 50)
                eff_width = 1
            elif is_danger and face_idx == 0:
                color = DANGER_TOP_COLOR
                eff_edge = edge_color
                eff_width = edge_width
            else:
                color = fill_color
                eff_edge = edge_color
                eff_width = edge_width
            projected = renderer.project_face(face_verts, color, eff_edge, eff_width)
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
    menu_selected: int,
) -> tuple[bool, bool, int, bool, bool]:
    """Process one frame of pygame events.

    Returns (running, paused, menu_selected, det_fired, trig_fired).
    `det_fired` / `trig_fired` are True on the frame the respective key was
    pressed; the caller uses each to set a brief arm-raise timer.

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
    det_fired: bool = False
    trig_fired: bool = False
    for event in events:
        if event.type == pygame.QUIT:
            return False, paused, menu_selected, False, False
        if event.type == pygame.ACTIVEEVENT:
            paused = not bool(event.gain)  # gain=1: focused; gain=0: focus lost
            if not event.gain:
                game.set_turbo(False)  # prevent stuck-turbo if KEYUP is lost on blur
        elif event.type == pygame.KEYDOWN and not paused:
            if game.phase == GamePhase.TITLE:
                game.on_title_advance()  # any key starts the game from the title screen
            elif game.phase == GamePhase.HIGH_SCORE:
                game.on_high_score_key(player)  # any key restarts from TITLE
            elif game.phase in (GamePhase.GAME_OVER, GamePhase.VICTORY):
                game.on_restart_key(player)  # any key → insert score → HIGH_SCORE
            elif game.phase == GamePhase.STAGE_CLEAR:
                game.on_stage_clear_key(player)  # any key advances to next stage
            elif game.phase == GamePhase.NAME_ENTRY:
                _handle_name_entry_keydown(game, player, event)
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
                _ = game.try_mark(player.grid_x, player.grid_z)  # unused
            elif event.key in (KEY_TRIGGER, KEY_TRIGGER_ALT):
                _ = game.on_trigger(player)  # unused: outcome is for Step 10 audio cues
                trig_fired = True
            elif event.key == KEY_DETONATE:
                game.on_detonate(player)  # void: score delta tracked inside game
                det_fired = True
            elif event.key == KEY_TURBO:
                game.set_turbo(True)  # hold-to-turbo: activate on keydown
        elif event.type == pygame.KEYUP and event.key == KEY_TURBO:
            game.set_turbo(False)  # deactivate turbo on key release
    return True, paused, menu_selected, det_fired, trig_fired


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


def _draw_row_deltas(
    screen: pygame.Surface,
    font: pygame.font.Font,
    effects: FlashEffects,
) -> None:
    """Draw floating +1 / -1 row-change labels in the HUD layer.

    Gains (+1, green) float upward from the anchor position.
    Losses (-1, red) float downward. Each label fades from full
    brightness to transparent via surface alpha (set_alpha) so the colour
    stays saturated as it fades — no black-ghost artefact from colour
    multiplication, and no reliance on Unicode arrow glyphs not present
    in all FreeType builds.
    Right-aligned near the screen edge so they never overlap the 3D scene.
    """
    assert len(effects.row_deltas) <= _MAX_ROW_DELTA_EVENTS, (
        "row_deltas count exceeded Rule-3 cap before render"
    )
    for ev in effects.row_deltas:
        alpha = ev.alpha
        if alpha <= 0.0:
            continue   # still in stagger delay or fully expired — nothing to draw
        if ev.delta > 0:
            label = "+1"
            base_color: tuple[int, int, int] = (100, 220, 100)  # green for row gain
        else:
            label = "-1"
            base_color = (220, 80, 80)   # red for row loss
        surf = font.render(label, True, base_color)
        surf.set_alpha(int(alpha * 255))  # fade via surface alpha; returns None
        _ = screen.blit(surf, surf.get_rect(right=SCREEN_WIDTH - 20, top=int(ev.screen_y)))


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
    if game.retry_pending:
        # Again: show a prominent AGAIN! in orange so the player knows this
        # WAVE_RISING pause follows a crush. For non-last slots the next
        # pre-placed pending wave activates; for the last slot it re-spawns.
        retry_surf = big_font.render("AGAIN!", True, (255, 140, 40))
        retry_x = (SCREEN_WIDTH - retry_surf.get_width()) // 2
        _ = screen.blit(retry_surf, (retry_x, text_y))
        text_y += line_h
    elif game.perfect_display:
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
        "Press any key to continue",
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
    big_font: pygame.font.Font,
    small_font: pygame.font.Font,
    game: GameManager,
    hold_ready: bool,
) -> None:
    """Between-stage stats screen: header, per-stage stats panel, and continue prompt.

    Shown after the last wave of a non-final stage completes. The continue
    prompt and input are gated for STAGE_CLEAR_HOLD (4 s) so the player
    has time to read the Perfect waves, IQ gain, rows gained/lost, and surviving
    rows before advancing. Labels are right-aligned to screen centre; values left.
    """
    assert game.stage_index >= 0, "stage_index must be non-negative in STAGE_CLEAR"
    cleared_stage = game.stage_index + 1          # 1-based stage just finished
    next_stage = game.stage_index + 2             # 1-based stage about to start
    iq_gain = game.stage_iq_gain
    rows_lost = game.stage_rows_lost
    rows_gained = game.stage_rows_gained
    perfect = game.stage_perfect_waves
    surviving = game.surviving_rows

    veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 210))
    _ = screen.blit(veil, (0, 0))

    cx = SCREEN_WIDTH // 2
    line_h = big_font.size("A")[1]
    small_h = small_font.size("A")[1]

    title = big_font.render(f"STAGE {cleared_stage} CLEAR", True, (100, 220, 100))
    title_y = SCREEN_HEIGHT // 5
    _ = screen.blit(title, title.get_rect(centerx=cx, top=title_y))

    stats_y = title_y + line_h + 20
    iq_color: tuple[int, int, int] = (160, 220, 255)
    loss_color: tuple[int, int, int] = (220, 80, 80) if rows_lost > 0 else (100, 220, 100)
    stat_rows: tuple[tuple[str, str, tuple[int, int, int]], ...] = (
        ("Perfect waves", f"{perfect} / {game.wave_count}", (220, 220, 220)),
        ("IQ this stage", f"{iq_gain:+,}", iq_color),
        ("Rows gained", str(rows_gained), (100, 220, 100)),
        ("Rows lost", str(rows_lost), loss_color),
        ("Rows surviving", str(surviving), (220, 220, 220)),
    )
    assert len(stat_rows) == 5, "stat_rows count changed — update assertion"
    lbl_right = cx - 20      # labels end just left of centre
    val_left = cx + 20       # values begin just right of centre
    row_step = small_h + 10
    for label, value, color in stat_rows:
        lbl_surf = small_font.render(label, True, (160, 160, 180))
        val_surf = small_font.render(value, True, color)
        _ = screen.blit(lbl_surf, (lbl_right - lbl_surf.get_width(), stats_y))
        _ = screen.blit(val_surf, (val_left, stats_y))
        stats_y += row_step

    score_surf = small_font.render(f"Score: {game.score:,}", True, (220, 220, 220))
    _ = screen.blit(score_surf, score_surf.get_rect(centerx=cx, top=stats_y + 16))

    next_surf = small_font.render(f"Next: Stage {next_stage}", True, (180, 180, 220))
    _ = screen.blit(next_surf, next_surf.get_rect(centerx=cx, bottom=SCREEN_HEIGHT - 56))
    prompt_color: tuple[int, int, int] = (140, 140, 140) if hold_ready else (50, 50, 55)
    prompt = small_font.render("Press any key to continue", True, prompt_color)
    _ = screen.blit(prompt, prompt.get_rect(centerx=cx, bottom=SCREEN_HEIGHT - 28))


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
        "Press any key to continue",
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


# --- Name entry overlay -------------------------------------------------------

def _draw_name_entry_overlay(
    screen: pygame.Surface,
    big_font: pygame.font.Font,
    small_font: pygame.font.Font,
    game: GameManager,
    cursor_visible: bool,
) -> None:
    """Full-screen overlay prompting the player to type their name.

    Shown in NAME_ENTRY phase when the player earns a top-10 score.
    Draws a dark veil, a gold "NEW HIGH SCORE!" title, the earned IQ,
    a name input field with blinking cursor, and a keyboard hint.
    """
    assert len(game.pending_name) <= _HS_MAX_NAME_LEN, (
        f"pending name '{game.pending_name}' exceeded MAX_NAME_LEN — clamp not applied"
    )
    veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 220))
    _ = screen.blit(veil, (0, 0))

    cx = SCREEN_WIDTH // 2
    line_h = big_font.size("A")[1]
    small_h = small_font.size("A")[1]

    title = big_font.render("NEW HIGH SCORE!", True, (255, 215, 0))
    title_y = SCREEN_HEIGHT // 6
    _ = screen.blit(title, title.get_rect(centerx=cx, top=title_y))

    iq_surf = big_font.render(f"I.Q.: {game.pending_iq}", True, (180, 220, 255))
    _ = screen.blit(iq_surf, iq_surf.get_rect(centerx=cx, top=title_y + line_h + 8))

    prompt_y = SCREEN_HEIGHT // 2 - small_h * 2
    prompt = small_font.render("ENTER YOUR NAME:", True, (220, 220, 220))
    _ = screen.blit(prompt, prompt.get_rect(centerx=cx, top=prompt_y))

    name_str = game.pending_name
    cursor_str = "_" if cursor_visible else " "
    display = name_str + cursor_str if len(name_str) < _HS_MAX_NAME_LEN else name_str
    name_surf = big_font.render(display or cursor_str, True, (255, 240, 100))
    _ = screen.blit(name_surf, name_surf.get_rect(centerx=cx, top=prompt_y + small_h + 12))

    hint = "A-Z  Type     Backspace  Delete     Enter  Confirm     Esc  Skip (anonymous)"
    hint_surf = small_font.render(hint, True, (80, 80, 100))
    _ = screen.blit(hint_surf, hint_surf.get_rect(centerx=cx, bottom=SCREEN_HEIGHT - 28))


def _handle_name_entry_keydown(
    game: GameManager,
    player: Player,
    event: pygame.event.Event,
) -> None:
    """Route a KEYDOWN event during NAME_ENTRY to the appropriate game method.

    Enter confirms the typed name (saved as last-used name for next session).
    Esc skips: score is inserted anonymously, last-used name is NOT overwritten.
    Backspace removes the last character.
    Printable ASCII letters, digits, and spaces are appended in uppercase.
    """
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        game.on_name_submit(player)
    elif event.key == pygame.K_ESCAPE:
        game.on_name_skip(player)
    elif event.key == pygame.K_BACKSPACE:
        game.on_name_backspace()
    elif event.unicode:
        uni = event.unicode
        if len(uni) == 1 and (uni.isalpha() or uni.isdigit() or uni == " "):
            game.on_name_char(uni.upper())


# --- High score overlay -------------------------------------------------------

_HS_COL_XS: tuple[int, int, int, int] = (
    SCREEN_WIDTH // 2 - 440,   # rank column centre  (≈200 px)
    SCREEN_WIDTH // 2 - 180,   # name column centre  (≈460 px)
    SCREEN_WIDTH // 2 + 60,    # IQ column centre    (≈700 px)
    SCREEN_WIDTH // 2 + 300,   # stage column centre (≈940 px)
)
_HS_HEADERS: tuple[str, str, str, str] = ("RANK", "NAME", "I.Q.", "STAGE")


def _draw_high_score_overlay(
    screen: pygame.Surface,
    big_font: pygame.font.Font,
    small_font: pygame.font.Font,
    game: GameManager,
) -> None:
    """Full-screen high score table: title, top-10 list with new entry highlighted.

    Shown in the HIGH_SCORE phase after GAME_OVER or VICTORY.  The entry that
    was just inserted is drawn in gold with a '>' prefix; all others are grey.
    An empty table (no qualifying run yet) shows a placeholder message.
    Columns: RANK | NAME | I.Q. | STAGE.
    """
    entries = game.high_score_entries
    last_rank = game.last_score_rank
    assert len(entries) <= _HS_MAX_ENTRIES, (
        f"high score entry count {len(entries)} exceeds _HS_MAX_ENTRIES"
    )
    veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 220))
    _ = screen.blit(veil, (0, 0))

    cx = SCREEN_WIDTH // 2
    line_h = big_font.size("A")[1]
    small_h = small_font.size("A")[1]

    title = big_font.render("HIGH SCORES", True, (255, 215, 0))
    _ = screen.blit(title, title.get_rect(centerx=cx, top=36))

    header_y = 36 + line_h + 14
    for hdr, hx in zip(_HS_HEADERS, _HS_COL_XS, strict=True):
        hs = small_font.render(hdr, True, (140, 140, 170))
        _ = screen.blit(hs, hs.get_rect(centerx=hx, top=header_y))

    row_y = header_y + small_h + 10
    row_h = small_h + 8
    if not entries:
        empty = small_font.render("No scores yet — play to set a record!", True, (100, 100, 120))
        _ = screen.blit(empty, empty.get_rect(centerx=cx, top=row_y))
    else:
        for rank, entry in enumerate(entries):
            color = (255, 215, 0) if rank == last_rank else (190, 190, 200)
            rank_str = f"> {rank + 1}" if rank == last_rank else f"{rank + 1:>2}."
            name_str = entry.name if entry.name else "—"  # em-dash for empty names
            cells = (
                small_font.render(rank_str, True, color),
                small_font.render(name_str, True, color),
                small_font.render(str(entry.iq_score), True, color),
                small_font.render(f"Stage {entry.stage_reached}", True, color),
            )
            for surf, hx in zip(cells, _HS_COL_XS, strict=True):
                _ = screen.blit(surf, surf.get_rect(centerx=hx, top=row_y))
            row_y += row_h

    prompt = small_font.render("Press any key to play again", True, (110, 110, 130))
    _ = screen.blit(prompt, prompt.get_rect(centerx=cx, bottom=SCREEN_HEIGHT - 28))


# --- Camera -------------------------------------------------------------------

def _update_smooth_camera(
    renderer: Renderer,
    player: Player,
    in_follow: bool,
    cam_xz: list[float],
    cam_eye_y: list[float],
    cam_eye_z: list[float],
    cam_zoom: list[float],
    prev_in_follow: bool,
    dt: float,
    wave_index: int,
    grid_center_x: float,
    wave_target_z: float,
    zoom_out: bool,
) -> None:
    """Rebuild the VP matrix with a smooth pivot follow or fixed overview camera.

    When `in_follow` is True:
    - `cam_eye_z[0]` tracks player Z − CAMERA_EYE_Z_OFFSET (eye behind player).
    - `cam_eye_y[0]` tracks the wave-index elevation target.
    - `cam_xz[0]` (look-at X) follows player X; `cam_xz[1]` (look-at Z) follows
      `wave_target_z` — the caller supplies the wave centre-of-mass or freezes it
      during WAVE_CLEARING.
    - `cam_zoom[0]` lerps toward CAM_ZOOM_OUT when `zoom_out`, else toward 1.0.
      The eye is pulled back along the view ray by the zoom factor.
    """
    assert len(cam_xz) == 2, "cam_xz must be a two-element [x, z] list"
    assert len(cam_eye_y) == 1, "cam_eye_y must be a one-element [y] list"
    assert len(cam_eye_z) == 1, "cam_eye_z must be a one-element [z] list"
    assert len(cam_zoom) == 1, "cam_zoom must be a one-element [zoom] list"
    if wave_index < 0:
        raise ValueError(f"wave_index must be non-negative, got {wave_index}")
    if grid_center_x < 0.0:
        raise ValueError(f"grid_center_x must be non-negative, got {grid_center_x}")
    zoom_target = CAM_ZOOM_OUT if zoom_out else 1.0
    zoom_speed = CAM_ZOOM_SPEED_OUT if zoom_out else CAM_ZOOM_SPEED_IN
    cam_zoom[0] += (zoom_target - cam_zoom[0]) * (1.0 - math.exp(-zoom_speed * dt))
    if in_follow:
        wx, _, wz = player.world_pos
        target_eye_z = wz - CAMERA_EYE_Z_OFFSET
        target_eye_y = CAMERA_FOLLOW_EYE[1] * (1.0 + wave_index * CAMERA_WAVE_EYE_Y_SCALE)
        if not prev_in_follow:
            cam_xz[0], cam_xz[1] = wx, wave_target_z
            cam_eye_y[0] = target_eye_y
            cam_eye_z[0] = target_eye_z
        else:
            alpha = 1.0 - math.exp(-CAMERA_FOLLOW_SMOOTH * dt)
            cam_xz[0] += (wx - cam_xz[0]) * alpha
            cam_xz[1] += (wave_target_z - cam_xz[1]) * alpha
            alpha_y = 1.0 - math.exp(-CAMERA_EYE_Y_LERP * dt)
            cam_eye_y[0] += (target_eye_y - cam_eye_y[0]) * alpha_y
            alpha_z = 1.0 - math.exp(-CAMERA_EYE_Z_LERP * dt)
            cam_eye_z[0] += (target_eye_z - cam_eye_z[0]) * alpha_z
        cam_xz[1] = max(cam_eye_z[0] + 0.5, cam_xz[1])
        look_at: tuple[float, float, float] = (cam_xz[0], 0.0, cam_xz[1])
        base_eye: tuple[float, float, float] = (grid_center_x, cam_eye_y[0], cam_eye_z[0])
        zoom = cam_zoom[0]
        zoomed_eye = (
            look_at[0] + (base_eye[0] - look_at[0]) * zoom,
            look_at[1] + (base_eye[1] - look_at[1]) * zoom,
            look_at[2] + (base_eye[2] - look_at[2]) * zoom,
        )
        renderer.rebuild_vp(zoomed_eye, look_at, CAMERA_FOLLOW_FOV)
    else:
        renderer.rebuild_vp(CAMERA_POS, CAMERA_TARGET)


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
    grid = GridManager(width=STAGE_GRID_WIDTHS[0])  # Stage-1 width; grows via set_active_width
    player = Player(grid)
    wave = WaveManager()
    effects = FlashEffects()
    game = GameManager(grid, wave, effects, audio=audio)
    # Draw a fresh pool selection so each run sees a different mix of A/B
    # wave variants.  The seed is unpredictable; _do_restart re-rolls it.
    _rng = random.Random(random.randrange(2**32))
    game.start_game(player, select_all_waves(_rng))
    hud = Hud(player, grid, wave, game)

    scene_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    running = True
    paused: bool = False
    menu_selected: int = 0    # highlighted item index in the pause menu
    cursor_blink: float = 0.0  # cycles 0→1 each second; cursor visible when < 0.5
    detonate_flash: float = 0.0  # seconds remaining for right-arm-raised detonate gesture
    trigger_flash: float = 0.0   # seconds remaining for left-arm-raised trigger gesture
    # Smoothed camera look-at target: [x, z] lerped toward wave COM during WAVE_ACTIVE.
    # cam_eye_y: [y] smoothly interpolates toward the wave-index target each frame.
    # cam_eye_z: [z] smoothly tracks player.world_z - CAMERA_EYE_Z_OFFSET.
    # cam_zoom: [zoom] lerps toward CAM_ZOOM_OUT during row animations, else 1.0.
    _wp0 = player.world_pos
    cam_xz: list[float] = [_wp0[0], _wp0[2]]
    cam_eye_y: list[float] = [CAMERA_FOLLOW_EYE[1]]
    cam_eye_z: list[float] = [CAMERA_FOLLOW_EYE[2]]
    cam_zoom: list[float] = [1.0]
    prev_in_follow: bool = game.phase in _FOLLOW_CAMERA_PHASES

    # Rule 2 — top-level event loop exception. This is the ONE bounded-by-user
    # loop in the application; every nested loop we write must have an
    # explicit upper bound. Exits when `running` becomes False.
    while running:
        dt = clock.tick(0) / 1000.0  # Uncapped — browser rAF governs pacing
        if dt > DT_CLAMP:
            dt = DT_CLAMP

        running, paused, menu_selected, det_fired, trig_fired = _drain_events(
            player, game, paused, menu_selected,
        )
        detonate_flash = DETONATE_FLASH_DUR if det_fired else max(0.0, detonate_flash - dt)
        trigger_flash = TRIGGER_FLASH_DUR if trig_fired else max(0.0, trigger_flash - dt)

        # update() handles WAVE_RISING timer and must run even while frozen
        # so the between-wave pause counts down correctly.
        if not paused:
            game.update(dt, player)

        frozen = game.phase in (
            GamePhase.TITLE, GamePhase.STAGE_INTRO, GamePhase.WAVE_RISING,
            GamePhase.GAME_OVER, GamePhase.VICTORY,
            GamePhase.STAGE_CLEAR, GamePhase.MENU, GamePhase.HIGH_SCORE,
            GamePhase.NAME_ENTRY,
        )
        is_marking: bool = False
        if not paused and not frozen:
            held_keys = pygame.key.get_pressed()
            is_marking = bool(held_keys[KEY_MARK])
            blocked = wave.blocked_tiles()
            player.update(dt, held_keys, blocked, max_col=game.active_wave_width - 1)
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
        cursor_blink = (cursor_blink + dt) % 1.0  # wraps: 0→1 per second

        # --- Camera update ----------------------------------------------------
        # look-at Z: wave COM during WAVE_ACTIVE; frozen during WAVE_CLEARING;
        # player position during all other follow phases.
        if game.phase == GamePhase.WAVE_ACTIVE:
            wave_target_z = _compute_wave_com_z(wave, float(player.grid_z) + 0.5)
        elif game.phase == GamePhase.WAVE_CLEARING:
            wave_target_z = cam_xz[1]  # freeze: camera holds its current position
        else:
            wave_target_z = float(player.grid_z) + 0.5
        in_follow = game.phase in _FOLLOW_CAMERA_PHASES
        _update_smooth_camera(
            renderer, player, in_follow, cam_xz, cam_eye_y, cam_eye_z,
            cam_zoom, prev_in_follow, dt, game.wave_index,
            (grid.width - 1) * 0.5, wave_target_z, effects.has_active_row_anim,
        )
        prev_in_follow = in_follow

        danger = wave.danger_cubes(grid.front_edge_z)
        # Two render passes: grid+cubes+markers first, then player on top so the
        # character is never occluded by tiles or cubes in the painter's sort.
        intro_t = (
            game.intro_elapsed / STAGE_INTRO_DURATION
            if game.phase == GamePhase.STAGE_INTRO
            else 0.0
        )
        face_list: list[ProjectedFace] = []
        face_list.extend(_build_table_edge_faces(renderer, grid))
        face_list.extend(_build_grid_faces(renderer, grid))
        face_list.extend(_build_crumble_faces(renderer, effects))
        face_list.extend(_build_arrival_faces(renderer, effects))
        face_list.extend(
            _build_cube_faces(renderer, wave, danger, intro_t, game.wave_front_z)
        )
        face_list.extend(_build_marker_faces(renderer, grid))
        player_faces = _build_player_faces(
            renderer, player, is_marking, detonate_flash > 0.0,
            is_triggering=trigger_flash > 0.0,
        )

        scene_surf.fill(BG_COLOR)
        renderer.render_frame(scene_surf, face_list)    # grid + cubes + markers
        renderer.render_frame(scene_surf, player_faces) # player drawn on top
        effects.draw(scene_surf, renderer)
        shake_x, shake_y = effects.shake_offset()
        screen.fill(BG_COLOR)
        _ = screen.blit(scene_surf, (shake_x, shake_y))  # unused: dest rect
        hud.draw(screen, font)
        _draw_row_deltas(screen, font, effects)  # floating +1/−1 labels; HUD layer
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
            _draw_stage_clear_overlay(screen, overlay_font, font, game, game.stage_clear_hold_ready)
        elif game.phase == GamePhase.VICTORY:
            _draw_victory_overlay(screen, font, game, game.end_hold_ready)
        elif game.phase == GamePhase.NAME_ENTRY:
            _draw_name_entry_overlay(screen, overlay_font, font, game, cursor_blink < 0.5)
        elif game.phase == GamePhase.HIGH_SCORE:
            _draw_high_score_overlay(screen, overlay_font, font, game)

        pygame.display.flip()
        await asyncio.sleep(0)  # CRITICAL: yield to browser rAF

    pygame.quit()


if __name__ == "__main__":
    # Pygbag invokes main.py as __main__, so this guard preserves the browser
    # entry point while letting tests import the module without auto-running.
    asyncio.run(main())
