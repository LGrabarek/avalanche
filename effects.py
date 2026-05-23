"""Visual effects — capture-flash feedback for mark/trigger hits.

Effects are purely cosmetic: they read game state and emit draw calls, but
never mutate score, grid, or wave. Keeping them in their own module
preserves the logic/visuals split (CLAUDE.md rule 2) and gives future
polish steps a single place to add particles, shake, and screen-edge
miss-flashes without touching gameplay.

Step 4A scope: one effect type — `_Flash`. A capture on a tile spawns a
ring that expands and fades over ~0.4s above the captured tile. Rendered
after the 3D scene so the ring reads on top of the grid.

Step 15 (B4 + A5): the single-frame expanding ring is replaced with a
multi-frame particle burst. Each capture spawns 10 (NORMAL/FORBIDDEN) or
16 (ADVANTAGE) particles radiating outward in screen space from the tile
centre, coloured by cube type (white / green / red) and fading to black as
they age.
"""

import math
import random
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

import pygame

from constants import (
    CRUMBLE_PRE_ZOOM_DELAY,
    MAX_ARRIVAL_TILES,
    MAX_CRUMBLE_TILES,
    ROW_ARRIVAL_DURATION,
    ROW_CRUMBLE_DURATION,
    ROW_CRUMBLE_STAGGER,
    CubeType,
)

# --- Tuning -------------------------------------------------------------------

# Per-flash world-space hover height so particles originate above the tile top.
# Tile tops live at y=0; 0.05 is well clear and avoids z-fighting.
FLASH_HOVER_Y: float = 0.05

# Particle lifetime (seconds). Uniform random in [MIN, MAX] per particle.
PARTICLE_LIFE_MIN: float = 0.30
PARTICLE_LIFE_MAX: float = 0.55

# Radial speed (pixels/second) for the two cube-type tiers.
# ADVANTAGE gets more particles AND higher speed for a more dramatic burst.
PARTICLE_SPEED_NORMAL: float = 150.0     # NORMAL / FORBIDDEN captures
PARTICLE_SPEED_ADVANTAGE: float = 220.0  # ADVANTAGE captures / blast hits

# Particle counts per flash tier.
PARTICLE_COUNT_NORMAL: int = 10
PARTICLE_COUNT_ADVANTAGE: int = 16

# Particle radius in pixels (screen space). Fixed size; fade is via colour.
PARTICLE_RADIUS: int = 2

# Tint colours by cube type.
FLASH_COLORS: dict[CubeType, tuple[int, int, int]] = {
    CubeType.NORMAL:    (240, 240, 255),  # white-blue
    # bright yellow-green — separates visually from ADVANTAGE_TRAP tile (80, 200, 80)
    CubeType.ADVANTAGE: (160, 255, 100),
    CubeType.FORBIDDEN: (220,  80,  80),  # red (reserved — FORBIDDEN has no flash yet)
}

# Rule-3 cap: a single TRIGGER spawns one flash; a 3×3 blast spawns up to 9.
# 32 is generous for normal play and keeps the list trivially bounded.
MAX_ACTIVE_FLASHES: int = 32

# Row-delta label animation constants.
# Labels float 40 px/s up (gains) or down (losses) over ROW_DELTA_LIFETIME seconds,
# fading from full brightness at spawn to transparent at expiry.
# When multiple events fire in the same frame (e.g. two simultaneous avalanche
# penalties), each successive event is delayed by ROW_DELTA_STAGGER seconds so
# they appear one at a time rather than stacking invisibly.
ROW_DELTA_LIFETIME: float = 1.5     # seconds of animation once the event starts
ROW_DELTA_FLOAT_SPEED: float = 40.0  # pixels per second
ROW_DELTA_ANCHOR_Y: int = 120       # initial screen-Y for freshly spawned labels
ROW_DELTA_STAGGER: float = 1.0      # seconds between successive simultaneous events
MAX_ROW_DELTA_EVENTS: int = 16      # Rule-3 cap

# Shake frequencies for the two-axis oscillation. Mutually prime (base-12
# relationship) so the x/y Lissajous pattern stays fresh over short shakes.
SHAKE_FREQ_X: float = 60.0   # radians/sec
SHAKE_FREQ_Y: float = 47.0   # radians/sec


class _VertexProjector(Protocol):
    """Minimal interface flashes need from the renderer.

    Declared as a Protocol instead of importing `Renderer` directly so
    `effects.py` stays decoupled from the rendering backend — swapping in a
    different projector for tests or a future WebGL port requires nothing
    more than a matching signature.
    """

    def project_vertex(
        self, x: float, y: float, z: float,
    ) -> tuple[float, float, float] | None:
        ...


@dataclass
class _Particle:
    """One particle in a capture-flash burst."""

    angle: float                     # radians — direction of travel
    speed: float                     # pixels / second
    life: float                      # seconds remaining (decremented by update)
    max_life: float                  # initial life; constant — used for fade ratio
    color: tuple[int, int, int]      # base colour; alpha-faded toward black in draw


@dataclass
class RowDeltaEvent:
    """One floating row-change label shown in the HUD layer.

    Spawned by FlashEffects.spawn_row_delta() whenever a row is gained
    (+1, green, floats upward) or lost (−1, red, floats downward).
    `elapsed` counts from 0 to ROW_DELTA_LIFETIME; `screen_y` drifts from
    the fixed anchor toward the screen edge as `elapsed` grows.
    """

    delta: int       # +1 (row restored / Perfect) or -1 (row deleted)
    elapsed: float   # negative = waiting for stagger delay; 0+ = animating
    screen_y: float  # current screen-Y (decreases for gains, increases for losses)

    @property
    def alpha(self) -> float:
        """Fade ratio: 0.0 during delay, 1.0 at animation start → 0.0 at expiry."""
        if self.elapsed < 0.0:
            return 0.0          # still in the initial stagger delay — not yet visible
        return max(0.0, 1.0 - self.elapsed / ROW_DELTA_LIFETIME)


@dataclass
class _CrumbleTile:
    """One tile in a row-crumble animation.

    `elapsed` starts negative (pre-zoom delay); fading is visible once elapsed >= 0.
    """

    grid_x: int
    grid_z: int
    elapsed: float   # seconds; negative = pre-zoom delay; 0+ = fading
    duration: float  # total fade duration (ROW_CRUMBLE_DURATION)


@dataclass
class _ArrivalTile:
    """One tile in a row-arrival (Perfect clear) animation.

    Same elapsed convention as _CrumbleTile.
    """

    grid_x: int
    grid_z: int
    elapsed: float
    duration: float


@dataclass
class _Flash:
    """A capture flash: origin tile + a list of live particles."""

    grid_x: int
    grid_z: int
    elapsed: float                  # seconds since spawn (for debug/future audio)
    cube_type: CubeType             # which type produced this flash
    particles: list[_Particle]      # live particle set; shrinks as particles die


class FlashEffects:
    """Owns the active-flash list and advances it each frame.

    The manager is a thin wrapper over a bounded `list[_Flash]`. Spawn adds;
    update advances each particle's life and evicts exhausted entries; draw
    projects each flash's tile centre to screen and scatters the particles
    from that origin. Empty state is valid and common — most frames have
    zero flashes.
    """

    def __init__(self) -> None:
        self._flashes: list[_Flash] = []
        self._row_deltas: list[RowDeltaEvent] = []
        self._crumble_tiles: list[_CrumbleTile] = []
        self._arrival_tiles: list[_ArrivalTile] = []
        self._shake_amplitude: float = 0.0
        self._shake_duration: float = 0.0
        self._shake_elapsed: float = 0.0
        # Stagger gate: decays by dt each frame; successive spawns add ROW_DELTA_STAGGER
        # so simultaneous events are separated in time rather than stacking visually.
        self._next_delta_delay: float = 0.0

    # --- Read-only accessors (useful for tests + HUD) ------------------------

    @property
    def active_count(self) -> int:
        return len(self._flashes)

    # --- Lifecycle -----------------------------------------------------------

    def reset(self) -> None:
        """Clear all active effects. Called when the player restarts the game."""
        self._flashes.clear()
        self._row_deltas.clear()
        self._crumble_tiles.clear()
        self._arrival_tiles.clear()
        self._shake_amplitude = 0.0
        self._shake_duration = 0.0
        self._shake_elapsed = 0.0
        self._next_delta_delay = 0.0
        assert not self._flashes, "flashes not cleared after reset"
        assert not self._row_deltas, "row_deltas not cleared after reset"
        assert not self._crumble_tiles, "crumble_tiles not cleared after reset"
        assert not self._arrival_tiles, "arrival_tiles not cleared after reset"

    @property
    def row_deltas(self) -> tuple[RowDeltaEvent, ...]:
        """Immutable snapshot of active row-delta labels for the HUD renderer."""
        return tuple(self._row_deltas)

    def spawn_row_delta(self, delta: int) -> None:
        """Spawn a floating +1 or −1 row label at the HUD anchor position.

        Successive calls in the same frame (e.g. two avalanche penalties) are
        staggered by ROW_DELTA_STAGGER seconds via a negative initial elapsed,
        so events appear one at a time instead of stacking invisibly.
        Silently drops when at the cap — the visual feedback is cosmetic; a
        dropped event cannot cause any state inconsistency.
        """
        assert delta in (1, -1), f"row delta must be +1 or -1, got {delta}"
        if len(self._row_deltas) >= MAX_ROW_DELTA_EVENTS:
            return  # cap reached — drop silently (cosmetic-only; no state impact)
        delay = self._next_delta_delay
        event = RowDeltaEvent(
            delta=delta,
            elapsed=-delay,          # negative = waiting; 0+ = animating
            screen_y=float(ROW_DELTA_ANCHOR_Y),
        )
        # Accumulate stagger for the next spawn; cap to avoid runaway delay.
        self._next_delta_delay = min(
            self._next_delta_delay + ROW_DELTA_STAGGER, ROW_DELTA_STAGGER * 4
        )
        self._row_deltas.append(event)
        assert len(self._row_deltas) <= MAX_ROW_DELTA_EVENTS, (
            "row_deltas exceeded cap after guarded append"
        )

    def _update_row_deltas(self, dt: float) -> None:
        """Advance every row-delta label; evict expired ones.

        elapsed counts from -delay (waiting) through 0 (start) to
        ROW_DELTA_LIFETIME (expiry).  Drift only applies once elapsed >= 0.
        Gains (+1) float upward (screen_y -= speed * dt).
        Losses (-1) float downward (screen_y += speed * dt).
        """
        alive: list[RowDeltaEvent] = []
        for ev in self._row_deltas:
            ev.elapsed += dt
            if ev.elapsed < ROW_DELTA_LIFETIME:
                if ev.elapsed >= 0.0:   # animation started; stagger delay done
                    ev.screen_y -= float(ev.delta) * ROW_DELTA_FLOAT_SPEED * dt
                alive.append(ev)
        self._row_deltas = alive
        assert len(self._row_deltas) <= MAX_ROW_DELTA_EVENTS, (
            "row_deltas exceeded cap after eviction — impossible unless spawn is broken"
        )

    def spawn_row_crumbles(self, z_rows: list[int], grid_width: int) -> None:
        """Spawn crumble tiles for one or more Z rows.

        `z_rows` may be in any order; row_idx is the list position and controls
        the stagger delay so the first entry crumbles first.  Silently drops
        tiles beyond MAX_CRUMBLE_TILES.
        """
        if grid_width <= 0:
            raise ValueError(f"grid_width must be positive, got {grid_width}")
        for row_idx, gz in enumerate(z_rows):
            start = -(CRUMBLE_PRE_ZOOM_DELAY + row_idx * ROW_CRUMBLE_STAGGER)
            for gx in range(grid_width):
                if len(self._crumble_tiles) >= MAX_CRUMBLE_TILES:
                    return
                self._crumble_tiles.append(
                    _CrumbleTile(grid_x=gx, grid_z=gz, elapsed=start,
                                 duration=ROW_CRUMBLE_DURATION)
                )
        assert len(self._crumble_tiles) <= MAX_CRUMBLE_TILES, (
            "crumble_tiles exceeded cap after spawn"
        )

    def spawn_row_arrival(self, gz: int, grid_width: int) -> None:
        """Spawn arrival highlight tiles for one row (Perfect clear)."""
        if grid_width <= 0:
            raise ValueError(f"grid_width must be positive, got {grid_width}")
        start = -CRUMBLE_PRE_ZOOM_DELAY
        for gx in range(grid_width):
            if len(self._arrival_tiles) >= MAX_ARRIVAL_TILES:
                return
            self._arrival_tiles.append(
                _ArrivalTile(grid_x=gx, grid_z=gz, elapsed=start,
                             duration=ROW_ARRIVAL_DURATION)
            )
        assert len(self._arrival_tiles) <= MAX_ARRIVAL_TILES, (
            "arrival_tiles exceeded cap after spawn"
        )

    def iter_crumble_tiles(self) -> Iterator[tuple[int, int, float]]:
        """Yield (grid_x, grid_z, progress) for tiles in the visible fade phase."""
        for tile in self._crumble_tiles:
            if tile.elapsed >= 0.0 and tile.duration > 0.0:
                yield (tile.grid_x, tile.grid_z, min(1.0, tile.elapsed / tile.duration))

    def iter_arrival_tiles(self) -> Iterator[tuple[int, int, float]]:
        """Yield (grid_x, grid_z, progress) for tiles in the visible fade phase."""
        for tile in self._arrival_tiles:
            if tile.elapsed >= 0.0 and tile.duration > 0.0:
                yield (tile.grid_x, tile.grid_z, min(1.0, tile.elapsed / tile.duration))

    @property
    def has_active_row_anim(self) -> bool:
        """True while any crumble or arrival tile is alive (including pre-zoom delay)."""
        return bool(self._crumble_tiles) or bool(self._arrival_tiles)

    def _update_row_anims(self, dt: float) -> None:
        """Advance crumble and arrival timers; evict fully-faded tiles."""
        alive_c: list[_CrumbleTile] = []
        for ct in self._crumble_tiles:
            ct.elapsed += dt
            if ct.elapsed < ct.duration:
                alive_c.append(ct)
        self._crumble_tiles = alive_c
        assert len(self._crumble_tiles) <= MAX_CRUMBLE_TILES, (
            "crumble_tiles exceeded cap after eviction — impossible unless spawn is broken"
        )
        alive_a: list[_ArrivalTile] = []
        for at in self._arrival_tiles:
            at.elapsed += dt
            if at.elapsed < at.duration:
                alive_a.append(at)
        self._arrival_tiles = alive_a
        assert len(self._arrival_tiles) <= MAX_ARRIVAL_TILES, (
            "arrival_tiles exceeded cap after eviction — impossible unless spawn is broken"
        )

    def spawn_flash(self, grid_x: int, grid_z: int, cube_type: CubeType) -> None:
        """Register a capture flash at the given tile.

        Generates a burst of particles radiating outward from the tile centre.
        ADVANTAGE cubes produce a larger, faster burst. Silently drops the
        flash when the active set is at its cap — dropping beats raising in
        a pathological blast scenario.
        """
        if len(self._flashes) >= MAX_ACTIVE_FLASHES:
            return  # cap reached — drop silently; see docstring
        color = FLASH_COLORS[cube_type]
        if cube_type == CubeType.ADVANTAGE:
            count = PARTICLE_COUNT_ADVANTAGE
            speed_max = PARTICLE_SPEED_ADVANTAGE
        else:
            count = PARTICLE_COUNT_NORMAL
            speed_max = PARTICLE_SPEED_NORMAL
        particles: list[_Particle] = []
        for i in range(count):
            angle = (i / count) * 2.0 * math.pi + random.uniform(-0.3, 0.3)
            speed = random.uniform(speed_max * 0.6, speed_max)
            life = random.uniform(PARTICLE_LIFE_MIN, PARTICLE_LIFE_MAX)
            particles.append(_Particle(
                angle=angle, speed=speed, life=life, max_life=life, color=color,
            ))
        assert len(particles) == count, (
            f"particle count mismatch: expected {count}, got {len(particles)}"
        )
        self._flashes.append(_Flash(
            grid_x=grid_x, grid_z=grid_z, elapsed=0.0,
            cube_type=cube_type, particles=particles,
        ))
        assert len(self._flashes) <= MAX_ACTIVE_FLASHES, (
            "flash list exceeded cap after guarded append"
        )

    def trigger_shake(self, amplitude: float, duration: float) -> None:
        """Start a screen-shake effect; resets elapsed so re-triggers restart cleanly."""
        if amplitude <= 0.0:
            raise ValueError(f"amplitude must be positive, got {amplitude}")
        if duration <= 0.0:
            raise ValueError(f"duration must be positive, got {duration}")
        self._shake_amplitude = amplitude
        self._shake_duration = duration
        self._shake_elapsed = 0.0

    def shake_offset(self) -> tuple[int, int]:
        """Current pixel offset to blit the scene surface at. (0, 0) when idle.

        Decays to zero as `_shake_elapsed` approaches `_shake_duration`.
        """
        if self._shake_duration <= 0.0 or self._shake_elapsed >= self._shake_duration:
            return (0, 0)
        rem = 1.0 - self._shake_elapsed / self._shake_duration
        ox = int(self._shake_amplitude * rem * math.sin(self._shake_elapsed * SHAKE_FREQ_X))
        oy = int(self._shake_amplitude * rem * math.cos(self._shake_elapsed * SHAKE_FREQ_Y))
        assert -self._shake_amplitude <= ox <= self._shake_amplitude, (
            "shake x offset escaped amplitude bounds"
        )
        assert -self._shake_amplitude <= oy <= self._shake_amplitude, (
            "shake y offset escaped amplitude bounds"
        )
        return (ox, oy)

    def update(self, dt: float) -> None:
        """Advance particles and row-delta labels by `dt` seconds.

        Row-delta labels always update; the flash update fast-paths the
        empty-list case — most frames have zero flashes.
        """
        if dt < 0.0:
            raise ValueError(f"dt must be non-negative, got {dt}")
        if self._shake_elapsed < self._shake_duration:
            self._shake_elapsed = min(self._shake_elapsed + dt, self._shake_duration)
        self._next_delta_delay = max(0.0, self._next_delta_delay - dt)
        self._update_row_deltas(dt)
        self._update_row_anims(dt)
        if not self._flashes:
            return
        for flash in self._flashes:
            flash.elapsed += dt
            for particle in flash.particles:
                particle.life -= dt
            flash.particles = [p for p in flash.particles if p.life > 0.0]
        self._flashes = [f for f in self._flashes if f.particles]
        assert len(self._flashes) <= MAX_ACTIVE_FLASHES, (
            "flash list exceeded cap after eviction — impossible unless spawn is broken"
        )

    # --- Rendering -----------------------------------------------------------

    def draw(self, screen: pygame.Surface, projector: _VertexProjector) -> None:
        """Draw every live particle as a small coloured dot, fading to black with age.

        Each flash projects its tile centre once; all particles in that flash
        radiate outward from that screen-space origin.  Flashes whose origin
        projects behind the near plane are skipped — those tiles are outside
        the viewport anyway.
        """
        for flash in self._flashes:
            projected = projector.project_vertex(
                float(flash.grid_x), FLASH_HOVER_Y, float(flash.grid_z),
            )
            if projected is None:
                continue
            origin_x, origin_y, _depth = projected
            for particle in flash.particles:
                if particle.max_life <= 0.0:
                    continue  # defensive: should never occur given PARTICLE_LIFE_MIN > 0
                alpha_frac = max(0.0, particle.life / particle.max_life)
                t = particle.max_life - particle.life
                px = origin_x + math.cos(particle.angle) * particle.speed * t
                py = origin_y + math.sin(particle.angle) * particle.speed * t
                r, g, b = particle.color
                faded = (int(r * alpha_frac), int(g * alpha_frac), int(b * alpha_frac))
                _ = pygame.draw.circle(  # unused: rect is not consumed
                    screen, faded, (int(px), int(py)), PARTICLE_RADIUS,
                )
