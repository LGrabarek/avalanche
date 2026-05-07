# Step 14A — User Review (Esc Pause Menu)

**What Step 14 covers:** An Esc-key pause menu that opens a two-item overlay
(RESUME / RESTART) from any active gameplay phase, freezes the wave, and restores
the exact game state on Resume.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | Added `GamePhase.MENU = "menu"` |
| `game_manager.py` | Added `_pre_menu_phase` field, `on_menu_open()`, `on_menu_close()`, `on_menu_select(item, player)`, `_do_restart()` helper; refactored `on_restart_key` to use `_do_restart` |
| `main.py` | Added `MENU_ITEMS`/`MENU_ITEM_COUNT` constants; updated `_drain_events` to accept/return `menu_selected`; added Esc/↑↓/confirm key handling; added `_draw_menu_overlay`; added `MENU` to frozen set and overlay dispatch |

No wave data, scoring, grid, or HUD logic was changed.

---

## 2. How to test

### 2a. Open and close the menu

1. Run `bash run_dev.sh` → open `http://localhost:8000`.
2. Start a wave (press any key at title, wait for `WAVE_ACTIVE`).
3. Press **Esc**. A semi-transparent overlay should appear with:
   - **PAUSED** heading (large text)
   - **`> RESUME`** highlighted in gold with a `>` cursor
   - `  RESTART` dimmed below it
   - Hint line: `↑↓  Navigate     X / Enter  Confirm     Esc  Resume`
4. The wave should be **completely frozen** — cubes do not advance while the menu is open.
5. Press **Esc** again. The overlay should disappear and the wave resumes exactly where it was.

### 2b. Navigate and Resume

1. Open the menu (Esc).
2. Press **↓** (or **S**). `RESTART` should become highlighted (gold + `>`), `RESUME` dimmed.
3. Press **↑** (or **W**). `RESUME` is highlighted again.
4. Press **X** or **Enter**. The menu should close; game resumes from the exact state.

### 2c. Navigate and Restart

1. Open the menu (Esc).
2. Press **↓** to highlight `RESTART`.
3. Press **X** or **Enter**. The game should restart from the **title screen** (Wave 1, score 0).
   > ⚠️ There is no confirmation step — RESTART executes immediately.

### 2d. Menu resets cursor to RESUME on each open

1. Open the menu, navigate to `RESTART`.
2. Close the menu (Esc or Resume).
3. Re-open the menu. The cursor should be back on `RESUME`, not `RESTART`.

### 2e. Menu blocked in non-gameplay phases

| Phase | Press Esc | Expected |
|---|---|---|
| Title screen | Esc | No effect (any key advances title) |
| `WAVE_RISING` (between waves) | Esc | Menu **opens** (countdown pauses) |
| `GAME_OVER` / `VICTORY` | Esc | No effect (any key restarts) |

> `WAVE_RISING` intentionally allows the menu — the countdown is paused while open.

### 2f. Game scene visible behind the menu

While the menu is open, the frozen game scene (grid, cubes, player) should be visible
through the dark semi-transparent veil. This lets the player review their situation
before choosing to resume or restart.

### 2g. Focus-loss while menu is open

1. Open the menu (Esc).
2. Switch to another app / click outside the browser tab.
3. The simple **PAUSED** focus-loss overlay should replace the menu overlay.
4. Switch back. The pause menu should reappear (game is still in `MENU` phase).

---

## 3. Success criteria

- [ ] **Esc opens menu** mid-wave; wave visibly freezes.
- [ ] **↑↓ / W S** navigate between RESUME and RESTART.
- [ ] **Esc / X / Enter on RESUME** closes the menu; game continues from exact state.
- [ ] **X / Enter on RESTART** resets to title screen (score 0, Wave 1).
- [ ] **Cursor resets to RESUME** each time the menu opens.
- [ ] **Menu blocked** from TITLE, GAME_OVER, VICTORY.
- [ ] **Menu opens from AVALANCHE** (mid-crush) — wave stays frozen until closed.
- [ ] **Scene visible** through the dark veil while menu is open.
- [ ] **Focus-loss overlay takes precedence** over the menu overlay.

---

## 4. Expert panel findings (Step 14A)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED | All design choices sound. Optional note: consider Restart confirmation if speedrun modes added later. No fixes required now. | No change needed. |
| Code Quality | APPROVED | `_drain_events` total line span including docstring is 62 (12 over if counting all lines), but code-only body is 39 lines — within Rule 4's 50-line limit. `_MENU_BLOCKED: frozenset[GamePhase]` class variable is correct Python/mypy. All other Power of Ten rules satisfied. | No change needed. |
| UX Tester | APPROVED | Hint line clear and readable. W/S navigation confirmed. Cursor resets to RESUME on open. Focus-loss overlay takes precedence. Restart has no confirmation — acceptable for a puzzle game. | No change needed. |
| Platform Engineer | APPROVED | SRCALPHA surface allocation per menu frame is the same pattern used by title/wave overlays — acceptable since menu is low-frequency. Esc browser conflict not a concern (game does not use fullscreen API). `game.update()` is a safe no-op during MENU phase. | No change needed. |

---

## 5. What to tell me after you review

- **"Step 14 approved, proceed"** — move on to Step 15 (capture animations + flash tinting).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel.
