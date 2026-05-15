# Pygbag configuration and quirks

**Type:** reference

## Running the dev server

Preferred: `bash run_dev.sh` (Git Bash on Windows or WSL). The script launches pygbag pinned to a known-good version via `uv tool run`, which uses an ephemeral cache venv and never touches the project's `.venv`.

```bash
# What run_dev.sh effectively does:
uv tool run --from pygbag==0.9.3 pygbag --ume_block 0 --disable-sound-format-error main.py
```

- `--ume_block 0`: disables user-media-engagement block (otherwise the page waits for a click before starting)
- `--disable-sound-format-error`: required because `.venv` contains pygame example `.wav` files in unsupported format; pygbag scans them even when directories are "ignored"

## pygbag.ini format

Uses Python's `configparser` with a `[DEPENDENCIES]` section:

```ini
[DEPENDENCIES]
ignoredirs = [".venv", ".claude", ".git", "build", "Research", "docs", "__pycache__"]
ignorefiles = ["uv.lock", "README.md", "CLAUDE.md", "pyproject.toml"]
```

**Known issue:** the ignore config is read but pygbag's audio format check still scans ignored directories. The `--disable-sound-format-error` flag is the workaround.

## Build output

- Build artifacts go to `build/web/` relative to the app folder.
- Serves on port 8000 by default.
- Uses Python 3.12 WASM from CDN (`pygame-web.github.io/cdn/0.9.3/cpython312/`).
- The `.venv` content gets packaged but doesn't affect runtime — the WASM interpreter uses its own bundled Python.

## Networking quirks

- **Do NOT use `--bind 0.0.0.0`.** Pygbag templates the bind address directly into asset URLs, and browsers reject `http://0.0.0.0:...` with `ERR_ADDRESS_INVALID`. Stick with the default `--bind localhost`.
- **WSL2:** `wslrelay.exe` natively forwards Windows `localhost:<port>` to WSL `127.0.0.1:<port>`, so running the server from WSL and opening it from a Windows browser Just Works.
- **Port 8000 already in use:** check with `netstat -ano | findstr :8000` (Windows) or `ss -ltnp | grep :8000` (Linux). Leftover `python.exe` from earlier pygbag runs can silently hold the port and cause `ERR_EMPTY_RESPONSE`.

## Browser runtime quirks

- **Hidden tabs pause `requestAnimationFrame`**, which stalls pygbag's `await asyncio.sleep(0)` loop. Expected — the loop resumes when the tab is foregrounded. Relevant for any headless-browser screenshot tool: if `document.hidden=true`, the canvas may never progress past 1×1.
- **`pygame.Clock.get_fps()` is unreliable** with `clock.tick(0)` in WASM. Use a rolling dt average instead (see `main.py`).
- **No `pygame.SysFont`** under WASM. Use `pygame.font.Font(None, size)` for pygame's built-in `freesansbold.ttf`, or bundle a `.ttf` in `assets/`.
