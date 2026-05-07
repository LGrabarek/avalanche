#!/bin/bash
# Dev server script: copies game files to a clean temp dir and runs pygbag.
# This avoids pygbag packaging the .venv directory (Windows path bug in pygbag).

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="/tmp/avalanche_build"

# Clean and recreate
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Copy only game Python files
for f in main.py constants.py renderer.py cube_data.py grid_manager.py wave_manager.py \
         wave_data.py player.py game_manager.py hud.py effects.py fonts.py audio.py; do
    [ -f "$PROJ_DIR/$f" ] && cp "$PROJ_DIR/$f" "$BUILD_DIR/"
done

# Copy assets if they exist
[ -d "$PROJ_DIR/assets" ] && cp -r "$PROJ_DIR/assets" "$BUILD_DIR/"

# Copy PWA static files so pygbag's shutil.copytree picks them up and
# copies them into build/web/ (the web root served to the browser).
[ -d "$PROJ_DIR/static" ] && cp -r "$PROJ_DIR/static" "$BUILD_DIR/"

# Copy custom HTML template and pygbag.ini into the build dir so pygbag
# finds them relative to its CWD ($BUILD_DIR).
[ -f "$PROJ_DIR/custom.tmpl" ] && cp "$PROJ_DIR/custom.tmpl" "$BUILD_DIR/"
[ -f "$PROJ_DIR/pygbag.ini"  ] && cp "$PROJ_DIR/pygbag.ini"  "$BUILD_DIR/"

cd "$BUILD_DIR"

# Resolve uv across shells. Prefer a native uv (not cross-filesystem) so we
# don't collide with an existing .venv on the Windows side.
#   - git-bash on Windows: `uv` on PATH is the Windows uv.exe (fine)
#   - WSL (used by preview_start): native Linux uv at /root/.local/bin/uv
UV_BIN=""
for candidate in \
    "$(command -v uv 2>/dev/null)" \
    "$HOME/.local/bin/uv" \
    "/root/.local/bin/uv" \
    "$HOME/.local/bin/uv.exe" \
    "/c/Users/Luke/.local/bin/uv.exe" \
    "/mnt/c/Users/Luke/.local/bin/uv.exe"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
        UV_BIN="$candidate"
        break
    fi
done
if [ -z "$UV_BIN" ]; then
    echo "ERROR: uv not found on PATH or common locations." >&2
    exit 1
fi
echo "Using uv: $UV_BIN"

# `uvx` runs pygbag in a tool-scoped, ephemeral venv — does NOT create or
# touch .venv in the project dir. Critical on WSL, where /mnt/f/.../.venv
# contains Windows executables that Linux uv cannot remove (I/O error).
# Pygbag version is pinned so a silent upstream change (URL templating,
# loader behavior, etc.) can't break the build mid-project. Bump deliberately.
PYGBAG_VERSION="0.9.3"

# Default --bind is 'localhost' (127.0.0.1). WSL2's wslrelay.exe natively
# forwards Windows localhost:<port> to WSL 127.0.0.1:<port>, so this works
# from the Windows host too. (Do NOT use 0.0.0.0 — pygbag templates the bind
# address into the page's asset URLs, and browsers reject http://0.0.0.0:...)
# --template custom.tmpl uses our PWA-aware template (manifest link, SW
# registration, canvas auto-focus) instead of the default CDN template.
exec "$UV_BIN" tool run --from "pygbag==$PYGBAG_VERSION" pygbag \
    --ume_block 0 --disable-sound-format-error \
    --template custom.tmpl main.py
