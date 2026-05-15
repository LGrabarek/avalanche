# Extensibility and retro feel priorities

**Type:** feedback / design rule

The codebase must be modular and designed so that future additions can be integrated and tested easily. The user plans to expand the game beyond the original I.Q. mechanics, taking advantage of modern capabilities.

**However — the retro feel, especially the difficulty, is essential and must be preserved.** The original I.Q. is punishing by design. Do not soften timing, scoring, or crush rules to make the game "fairer."

**Why:** This is a living project, not a one-off clone. The user intends ongoing development with new features.

**How to apply:**
- Design with clear interfaces between systems (grid, waves, scoring, rendering, input).
- Use configuration/constants for tunable values (live in `constants.py`).
- Keep game logic separate from rendering — swapping the renderer or adding new visual effects never touches game-state code.
- Cube types are data-driven via a config registry with behavior hooks (`CubeBehavior` enum) — adding a new cube type means adding an entry, not rewriting logic.
- Wave patterns are data files, not code — future stages/modes load from the same format.
- **But don't over-engineer** — add abstractions when needed, not speculatively.
