"""Font loader with size cache and WASM-resilient fallback.

Step 22 (A3): bundles freesansbold.ttf in assets/ so Pygbag packs it into
the WASM APK.  The loader caches Font objects by size so repeated calls
within a session never re-parse the .ttf file.  If the asset is absent (e.g.
a fresh checkout without the font, or a WASM load failure) it falls back to
pygame.font.Font(None, size) — the pre-Step-22 behaviour — so the game
remains playable without the bundled asset.

Must only be called after pygame.font.init() (i.e. after pygame.init()).
"""

import os

import pygame

# CWD-relative path.  Pygbag always sets the working directory to the game
# root before main.py runs, so this resolves correctly in both desktop and
# WASM.  Using os.path.dirname(__file__) is NOT safe in Pygbag: __file__
# may resolve to an unexpected virtual-filesystem path in the WASM sandbox.
_FONT_PATH: str = os.path.join("assets", "freesansbold.ttf")

# Maximum distinct font sizes that can be cached in one session.
# In practice only 2 sizes are used (28 + 64); 16 is a generous ceiling.
# Rule 3: load_font asserts len(_cache) < this before each new entry.
MAX_CACHED_FONT_SIZES: int = 16

# Valid for the lifetime of one pygame.font.init() session.  If pygame.font
# is ever torn down and re-initialised the cached Font objects would become
# stale.  The current codebase never does this — main() owns the full pygame
# lifetime and _cache is only populated after pygame.init() is called.
_cache: dict[int, pygame.font.Font] = {}


def load_font(size: int) -> pygame.font.Font:
    """Return a cached Font at `size` using the bundled assets/freesansbold.ttf.

    Raises ValueError for non-positive sizes.  Falls back to
    pygame.font.Font(None, size) if the bundled asset cannot be opened so
    the game remains functional on unconfigured checkouts or WASM load errors.
    """
    if size <= 0:
        raise ValueError(f"font size must be positive, got {size}")
    cached = _cache.get(size)
    if cached is not None:
        return cached
    assert len(_cache) < MAX_CACHED_FONT_SIZES, (
        f"font cache overflow — more than {MAX_CACHED_FONT_SIZES} distinct "
        "sizes requested"
    )
    try:
        font: pygame.font.Font = pygame.font.Font(_FONT_PATH, size)
    except (FileNotFoundError, OSError, pygame.error):
        # pygame.font.Font() raises pygame.error (not OSError) when SDL
        # cannot open the file — e.g. wrong path in WASM virtual FS.
        # FileNotFoundError / OSError cover the desktop / test-runner case.
        font = pygame.font.Font(None, size)
    _cache[size] = font
    return font
