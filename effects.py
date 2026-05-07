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
from dataclasses import dataclass
from typing import Protocol

import pygame

from constants import CubeType

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
        self._shake_amplitude: float = 0.0
        self._shake_duration: float = 0.0
        self._shake_elapsed: float = 0.0

    # --- Read-only accessors (useful for tests + HUD) ------------------------

    @property
    def active_count(self) -> int:
        return len(self._flashes)

    # --- Lifecycle -----------------------------------------------------------

    def reset(self) -> None:
        """Clear all active effects. Called when the player restarts the game."""
        self._flashes.clear()
        self._shake_amplitude = 0.0
        self._shake_duration = 0.0
        self._shake_elapsed = 0.0
        assert not self._flashes, "flashes not cleared after reset"

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
        """Advance every particle by `dt` seconds; evict dead particles and empty flashes.

        Fast-paths the empty-list case — most frames have zero flashes,
        so we skip the rebuild allocation entirely.
        """
        if dt < 0.0:
            raise ValueError(f"dt must be non-negative, got {dt}")
        if self._shake_elapsed < self._shake_duration:
            self._shake_elapsed = min(self._shake_elapsed + dt, self._shake_duration)
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
