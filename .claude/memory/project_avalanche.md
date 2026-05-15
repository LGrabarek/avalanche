# Avalanche project overview

**Type:** project

Avalanche is a reproduction of **I.Q.: Intelligent Qube** (Kurushi in Europe), a 1997 PlayStation spatial puzzle game. The game runs in the browser as a PWA, developed entirely in Python.

**Stack:** Pygame CE + Pygbag (WebAssembly) + PWA (manifest.json + service worker).

**Why:** User wants a browser-based, self-contained, installable game developed purely in Python. No JavaScript frameworks.

**How to apply:** All code must be Pygbag-compatible:
- Async main loop with `await asyncio.sleep(0)` each frame
- No C extensions beyond `pygame-ce`
- No filesystem writes at runtime
- 3D rendering is done in software via manual projection + `pygame.draw.polygon()`

The research document at `Research/Intelligent Qube Technical Reproduction Research.md` is the authoritative reference for game mechanics, scoring algorithms, and architecture.
