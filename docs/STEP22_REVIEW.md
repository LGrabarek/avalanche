# Step 22 — User Review (Bundled .ttf font, A3)

**What Step 22 covers:**
- New `assets/freesansbold.ttf` — pygame's own default font, bundled so Pygbag
  packs it into the WASM APK (not downloaded; copied from the local pygame install).
- New `fonts.py` — `load_font(size)` helper with size cache and WASM-resilient fallback.
- `main.py` — both `pygame.font.Font(None, ...)` calls replaced with `load_font(...)`.

---

## 1. What changed

| File | Change |
|---|---|
| `assets/freesansbold.ttf` | New — pygame's default font (97 KB); bundled for WASM |
| `fonts.py` | New — `load_font(size)` with size cache + `FileNotFoundError` fallback |
| `main.py` | `from fonts import load_font`; `Font(None, 28)` → `load_font(28)`; `Font(None, 64)` → `load_font(64)` |

No changes to `hud.py`, `renderer.py`, `constants.py`, `wave_manager.py`, or any game-logic file.

---

## 2. Design details

### Why bundle the font?

`pygame.font.Font(None, size)` works on desktop because pygame ships `freesansbold.ttf`
alongside its binary. Under Pygbag/WASM, `Font(None, …)` may resolve to the system font
cache at build time — but that cache is not available in the browser sandbox at runtime.
Bundling the font explicitly ensures it is packed into the WASM APK by pygbag.

### `fonts.py` — key properties

```python
_FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "freesansbold.ttf")
MAX_CACHED_FONT_SIZES = 16   # Rule 3 ceiling; only 2 sizes used in practice (28, 64)

def load_font(size: int) -> pygame.font.Font:
    # 1. Raises ValueError for size ≤ 0
    # 2. Returns cached Font on second call with same size
    # 3. Tries pygame.font.Font(_FONT_PATH, size)
    # 4. Falls back to pygame.font.Font(None, size) on FileNotFoundError / OSError
```

- **Visual appearance**: `freesansbold.ttf` is byte-for-byte identical to what
  `Font(None, size)` loaded before — no visual change expected.
- **Fallback**: if the asset file is absent (unconfigured checkout, WASM load failure),
  the game continues to run exactly as before Step 22.
- **Cache lifetime**: valid for one `pygame.font.init()` session (the full app lifetime
  in the current architecture).

### Pygbag bundling

`pygbag.ini` lists `ignoredirs` as `.venv`, `.claude`, `.git`, `build`, `Research`,
`docs`, `__pycache__`, `static`, `scripts`. The new `assets/` directory is **not**
in this list, so pygbag will bundle it into the WASM APK automatically.

---

## 3. How to test

### 3a. Visual regression check (most important)

1. Run `bash run_dev.sh` → open `http://localhost:8000`.
2. Play through the title screen, a wave, the pause menu, and a game-over screen.
3. All text — HUD stats, overlays (PAUSED, GAME OVER, GAME CLEAR, STAGE CLEAR),
   wave-rising banner, controls hint — should look **identical** to before.
4. No blurriness, size change, or missing characters.

### 3b. Confirm font loads from assets/ (desktop)

Run this one-liner from the project root:

```bash
uv run python -c "
import pygame; pygame.init()
from fonts import load_font, _FONT_PATH
import os
print('Path:', _FONT_PATH)
print('Exists:', os.path.exists(_FONT_PATH))
f = load_font(28)
s = f.render('Avalanche', True, (255,255,255))
print('Rendered size:', s.get_size())
print('OK')
pygame.quit()
"
```

Expected output:
```
Path: F:\Python\Avalanche\assets\freesansbold.ttf
Exists: True
Rendered size: (a positive width, 31)
OK
```

### 3c. Fallback works (optional)

Temporarily rename `assets/freesansbold.ttf` to `assets/freesansbold.ttf.bak`, then
run `python main.py` (desktop). The game should still start and display text normally
(via the `Font(None, size)` fallback). Rename the file back when done.

### 3d. No regressions

- All gameplay mechanics from Steps 1–21 behave identically.
- HUD layout, overlay text, menu rendering all unchanged.
- No Python errors or warnings in the console.

---

## 4. Success criteria

- [ ] All text looks visually identical to before Step 22.
- [ ] `load_font` smoke test prints `Exists: True` and a positive render size.
- [ ] No crashes or import errors on startup.
- [ ] No regressions in any previously-approved game mechanic.

---

## 5. Expert panel findings (Step 22)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED | `freesansbold.ttf` identical to pygame's internal default; no visual change | No change needed |
| Code Quality | APPROVED | Advisory: `_cache` has no clear/reset path; stale if `pygame.font` re-init | Added session-lifetime comment to `_cache` in `fonts.py` |
| UX Tester | APPROVED | Fallback path genuine (`FileNotFoundError` → `Font(None,size)`); no stale-cache scenario | No change needed |
| Platform Engineer | APPROVED | `os.path.dirname(__file__)` correct in Pygbag virtual FS; `assets/` will be bundled; SDL_RWops path confirmed WASM-compatible | No change needed |

---

## 6. What to tell me after you review

- **"Step 22 approved, proceed"** — move on to Step 23 (Movement perpendicular priority, A8).
- **"Approved, plus this fix: [specific change]"** — apply and re-verify.
- **"Text looks different"** — describe what changed (size? blur? different letterforms?).
- **"Changes needed: [X, Y, Z]"** — address and re-run panel.
