"""Visual effects — capture-flash feedback for mark/trigger hits.

Effects are purely cosmetic: they read game state and emit draw calls, but
never mutate score, grid, or wave. Keeping them in their own module
preserves the logic/visuals split (CLAUDE.md rule 2) and gives Step 10
polish a single place to expand into particles, shake, and screen-edge
miss-flashes without touching gameplay.

Step 4A scope: one effect type — `_Flash`. A capture on a tile spawns a
ring that expands and fades over ~0.4s above the captured tile. Rendered
after the 3D scene so the ring reads on top of the grid.

Intentionally *not* here yet:
  * Screen-edge miss-flash (Step 6 — paired with penalty counter pulse).
  * Camera shake (Step 10 polish — Step 5's avalanche shake is implemented).
  * Particles / sparkle trails (Step 10 polish).
  * Perfect celebration (Step 9).
"""

import math
from dataclasses import dataclass
from typing import Protocol

import pygame

# --- Tuning -------------------------------------------------------------------
# Values picked by eye on a 960x640 canvas. Tune further in Step 10.

FLASH_DURATION: float = 0.4          # Seconds from spawn to disappear
FLASH_RADIUS_START: float = 6.0      # Pixels at t=0
FLASH_RADIUS_END: float = 48.0       # Pixels at t=duration
FLASH_RING_WIDTH_START: int = 5      # Ring thickness at t=0
FLASH_RING_WIDTH_END: int = 1        # Ring thickness at t=duration
FLASH_COLOR: tuple[int, int, int] = (240, 240, 255)

# Per-flash world-space hover height above the tile top so the ring doesn't
# z-fight with the tile polygon. Tile tops live at y=0; 0.05 is well clear
# and projects to a point in front of the player's tile face.
FLASH_HOVER_Y: float = 0.05

# Rule-3 cap: a single TRIGGER spawns one flash; Step 7's 3x3 blast will
# spawn up to 9 in a frame. Ceiling generously so a pathological test can't
# inflate the list without bound.
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
class _Flash:
    """A single capture flash: ring that expands and fades over time."""

    grid_x: int
    grid_z: int
    elapsed: float  # Seconds since spawn


class FlashEffects:
    """Owns the active-flash list and advances it each frame.

    The manager is a thin wrapper over a bounded `list[_Flash]`. Spawn adds;
    update advances `elapsed` and evicts expired entries; draw projects each
    flash's grid tile center to screen and draws a ring. Empty state is
    valid and common — most frames have zero flashes.
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

    def spawn_flash(self, grid_x: int, grid_z: int) -> None:
        """Register a new capture flash at the given tile.

        Silently drops the new flash if the active set is already at its
        cap — under normal play we never hit this, but dropping beats
        raising so a rogue upstream (e.g. a Step 7 blast that somehow
        triggers >32 captures in one frame) doesn't abort the frame.
        """
        if len(self._flashes) >= MAX_ACTIVE_FLASHES:
            return  # Cap reached — silently drop; see docstring.
        self._flashes.append(_Flash(grid_x=grid_x, grid_z=grid_z, elapsed=0.0))
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
        return (ox, oy)

    def update(self, dt: float) -> None:
        """Advance every flash by `dt` seconds; evict expired entries.

        Fast-paths the empty-list case — most frames have zero flashes,
        so we skip the comprehension rebuild and its allocation entirely.
        (Platform finding, Step 4A panel.)
        """
        if dt < 0.0:
            raise ValueError(f"dt must be non-negative, got {dt}")
        if self._shake_elapsed < self._shake_duration:
            self._shake_elapsed = min(self._shake_elapsed + dt, self._shake_duration)
        if not self._flashes:
            return
        for flash in self._flashes:
            flash.elapsed += dt
        self._flashes = [f for f in self._flashes if f.elapsed < FLASH_DURATION]
        assert len(self._flashes) <= MAX_ACTIVE_FLASHES, (
            "flash list exceeded cap after eviction — impossible unless spawn is broken"
        )

    # --- Rendering -----------------------------------------------------------

    def draw(self, screen: pygame.Surface, projector: _VertexProjector) -> None:
        """Draw every active flash as an expanding ring.

        Flashes whose tile center projects behind the near plane are
        silently skipped — those tiles are already outside the viewport so
        there is nothing to draw. This is not an error path.
        """
        for flash in self._flashes:
            t = flash.elapsed / FLASH_DURATION
            # Clamp defensively: update() evicts at t>=1.0, but a reentrant
            # draw before the next update could see t in [1.0, 1.0+ε).
            if t < 0.0:
                t = 0.0
            elif t > 1.0:
                t = 1.0
            world_y = FLASH_HOVER_Y
            projected = projector.project_vertex(
                float(flash.grid_x), world_y, float(flash.grid_z),
            )
            if projected is None:
                continue
            sx, sy, _depth = projected
            radius = FLASH_RADIUS_START + (FLASH_RADIUS_END - FLASH_RADIUS_START) * t
            width_f = (
                FLASH_RING_WIDTH_START
                + (FLASH_RING_WIDTH_END - FLASH_RING_WIDTH_START) * t
            )
            width = max(1, int(round(width_f)))
            _ = pygame.draw.circle(  # unused: rect is not consumed
                screen, FLASH_COLOR, (int(sx), int(sy)), int(radius), width,
            )
