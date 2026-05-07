# Step 17 — User Review (HUD Font Render Caching)

**What Step 17 covers (A4):**
- `hud.py` now caches rendered `pygame.Surface` objects per HUD label.
- `font.render()` is called only when a label's text **or color** changes from the
  previously cached value. Identical values → the stored surface is blitted directly,
  skipping rasterization entirely.
- Static lines (the hint row) are rendered once on first draw and reused forever.
- Volatile lines (`fps`, `cubes`/tick-progress) still re-render every frame because
  their text changes every frame — no false savings.
- Net saving under normal play: **≈ 5–6 of 8 `font.render()` calls avoided per frame**,
  which matters most under the 3–5× WASM overhead.

---

## 1. What changed

| File | Change |
|---|---|
| `hud.py` | Added `MAX_HUD_CACHE_ENTRIES = 8`; added `_cache: dict[str, tuple[str, ColorRGB, pygame.Surface]]`; added `_render()` cache helper; refactored `_draw_stat_block` to use label/text pairs tuple; updated `_draw_hint_line` to route through `_render`; added `pos` local var in stat-block loop (Rule 9 / line-length); updated hint text (added Esc: Menu, Turbo: hold F); added Rule-7 blit comments; added Rule-5 note to `_format_mark` docstring |

No game logic, wave data, scoring, grid, or rendering pipeline was changed.

---

## 2. Cache design

```
_cache: dict[str, tuple[str, ColorRGB, pygame.Surface]]
              │           │     │          └─ cached surface
              │           │     └─ color used when rendering
              │           └─ text used when rendering
              └─ label key (e.g. "fps", "score", "hint")
```

Cache hit condition: `cached_text == text AND cached_color == color`

**Rule 3 guard:** The overflow assert fires only when a *new* label key is inserted
(`label not in self._cache`). Updating an existing key's text/color does not grow the
dict and skips the assert — correct behaviour.

**Bound:** `MAX_HUD_CACHE_ENTRIES = 8` exactly matches the 7 stat labels
(`fps`, `polys`, `pos`, `cubes`, `score`, `penalty`, `wave`) plus the `hint` label.
The `assert len(stats) == 7` in `_draw_stat_block` keeps the stat count and cache bound
in sync — a developer adding a new stat row will hit that assert immediately.

---

## 3. Hint text update

| Before | After |
|---|---|
| `Move: WASD/Arrows  Mark: SPACE  Trigger: X/Enter  Detonate: Z  Turbo: F` | `Move: WASD  Mark: SPACE  Trigger: X  Detonate: Z  Turbo: hold F  Esc: Menu` |

- **Added `Esc: Menu`** — the pause menu (Step 14) was missing from the hint entirely.
- **`Turbo: hold F`** — clarifies the hold-key UX (tap F does nothing; hold is required).
- **Dropped `/Arrows` and `/Enter`** — secondary bindings removed to stay within the
  100-char line limit. Arrow keys still work; X still accepts Enter as an alternative.

---

## 4. How to test

### 4a. Performance — cache visible via FPS counter

1. Run `bash run_dev.sh` → open `http://localhost:8000`.
2. Note FPS in the top-left. It should be stable (60 fps or your monitor's refresh).
3. No visual difference from before — this is a CPU-only optimisation.

### 4b. All 8 HUD lines still display

1. Start a wave. Verify all seven stat lines appear (FPS, Polys, Pos, Cubes/Tick,
   Score/Mark, Penalty, Wave).
2. Scroll to the bottom of the screen — the hint line should read:
   `Move: WASD  Mark: SPACE  Trigger: X  Detonate: Z  Turbo: hold F  Esc: Menu`

### 4c. Live values update correctly (cache doesn't go stale)

| Action | Expected HUD update |
|---|---|
| Move player | `Pos:` changes immediately |
| Capture a cube | `Score:` increments |
| Mark a position | `Score: N  Mark: (x, z)` updates |
| Let a wave advance | `Wave:` increments between waves |
| Step on FORBIDDEN | `Penalty:` increments |
| Hold `F` | `Cubes: N  Tick:` advances faster |
| Press `Esc` | Pause menu opens (Esc is now on hint line) |

### 4d. Cache overflow never fires in normal play

1. Play through multiple waves. No `AssertionError: HUD cache overflow` should appear.
2. The assert would only fire if a 9th distinct label key were added to `_render` — not
   possible without a code change that would also need `MAX_HUD_CACHE_ENTRIES` bumped.

### 4e. No regressions

- Scoring, marking, triggering, wave advancement, menu, turbo all work exactly as
  before — this is a render-layer change only.

---

## 5. Success criteria

- [ ] All 7 stat lines display with correct live values.
- [ ] Hint line reads: `Move: WASD  Mark: SPACE  Trigger: X  Detonate: Z  Turbo: hold F  Esc: Menu`
- [ ] `Esc` opens the pause menu (now discoverable via the hint).
- [ ] No `AssertionError` during a full play session.
- [ ] No gameplay regression.

---

## 6. Expert panel findings (Step 17)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED (conditional) | `color` not in cache key — latent wrong-color bug if same label later called with a different color (e.g. penalty-line highlight). | Added `color` to cache tuple: `(text, color, surface)`. Hit condition now checks both `cached[0] == text and cached[1] == color`. |
| Code Quality | APPROVED (conditional) | Two `_ = screen.blit(...)` calls had no inline comment (Rule 7). `_format_mark` has branching, outside strict ≤5-line no-branching exemption. | Added `# dirty rect unused; full redraw` comments. Extracted `pos` variable in stat loop to keep the blit line short enough for inline comment. Added Rule-5 note to `_format_mark` docstring. |
| UX Tester | APPROVED (conditional) | Esc (pause menu) absent from hint line. "Turbo: F" doesn't communicate hold-to-activate. | Updated hint text: added `Esc: Menu`, changed `Turbo: F` → `Turbo: hold F`; dropped secondary bindings `/Arrows`/`/Enter` to fit 100-char limit. |
| Platform Engineer | APPROVED (conditional) | Same color-key gap as Vision Lead. Noted that `cubes` label (contains `tick_progress:.2f`) gets zero cache benefit — re-renders every frame — which is accurate but expected. | Same color fix as above. "cubes" behaviour noted in docstring comment (saves 5–6 not 6–7 per the original doc claim). |

---

## 7. What to tell me after you review

- **"Step 17 approved, proceed"** — move on to Step 18 (Transition hold animations, A6).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel.
