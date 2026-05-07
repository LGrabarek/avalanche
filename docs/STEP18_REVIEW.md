# Step 18 — User Review (Transition Hold Animations)

**What Step 18 covers (A6):**
- GAME_OVER and VICTORY overlays now hold for `END_SCREEN_HOLD = 2.0` seconds before
  the "Press any key to restart" prompt becomes active.
- During the hold the prompt is shown **dimmed** — `(50, 50, 55)` — so players see it
  coming but know it is not yet active.
- Once the hold expires the prompt brightens to `(140, 140, 140)` and keypresses are
  accepted normally.
- This prevents the common accidental skip that occurred when the end condition fired
  mid-keypress.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | Added `END_SCREEN_HOLD: float = 2.0` near `WAVE_RISING_DURATION` |
| `game_manager.py` | New field `_end_hold_elapsed`; `update()` now advances hold timer in GAME_OVER/VICTORY; new `end_hold_ready` property; `on_restart_key()` returns early while hold < 2 s; `_check_game_over()` and VICTORY entry in `_on_wave_cleared()` reset timer on entry; `_reset_state()` zeroes it |
| `main.py` | Both `_draw_game_over_overlay` and `_draw_victory_overlay` accept `hold_ready: bool`; prompt rendered dim during hold, bright when ready; call sites pass `game.end_hold_ready` |

No wave data, scoring, grid, or rendering pipeline was changed.

---

## 2. Design details

### Hold timer

```
Phase entered (GAME_OVER or VICTORY)
  → _end_hold_elapsed = 0.0
  → update() adds dt each frame (clamped to END_SCREEN_HOLD)
  → on_restart_key() blocks until elapsed >= END_SCREEN_HOLD
  → overlay renders prompt at (50,50,55) dim color
  ─── 2 seconds ───
  → end_hold_ready = True
  → prompt brightens to (140,140,140)
  → any keypress triggers restart
```

### DT_CLAMP safety
`dt` is clamped to `0.1 s` max before `update()`. The hold timer therefore accumulates in ≤0.1 s steps; `min(elapsed + dt, END_SCREEN_HOLD)` ensures it never exceeds the ceiling regardless of frame-rate spikes or tab-switch returns.

### Paused behavior
`game.update()` only runs when `not paused`. If the window loses focus during the hold, the timer freezes — correct behavior, as a background tab cannot accidentally expire the hold.

---

## 3. How to test

### 3a. Accidental-skip prevention (GAME OVER path)
1. Run `bash run_dev.sh` → open `http://localhost:8000`.
2. Start a wave. Stand still and let the avalanche crush you.
3. The GAME OVER overlay should appear. **Immediately press and hold any key.**
4. For the first ~2 seconds, nothing should happen — the "Press any key to restart"
   line should appear dimly and input should be ignored.
5. After ~2 seconds the dim prompt should brighten. Pressing a key now restarts.

### 3b. Victory hold
1. Clear all 4 waves cleanly.
2. The STAGE CLEAR overlay appears with Score + I.Q.
3. The "Press any key to restart" line appears dimmed for ~2 seconds, then brightens.
4. Pressing a key while dim: no restart. After brightening: restart accepted.

### 3c. Dim-to-bright visual
- Dim color: `(50, 50, 55)` — very dark grey, barely visible, like inactive text.
- Bright color: `(140, 140, 140)` — same as all other secondary overlay text.
- The switch is instantaneous (no fade animation), so the prompt snaps from dark to
  normal brightness the moment the hold expires.

### 3d. No regressions
- Title screen, wave progression, pause menu, scoring all work as before.
- Restarting from the pause menu (in-game Esc → Restart) is unaffected — this path
  goes through `on_menu_select`, which bypasses `on_restart_key` entirely.

---

## 4. Success criteria

- [ ] Pressing a key immediately at death does NOT instantly restart.
- [ ] The "Press any key to restart" prompt is visible (dim) from the first frame of the
  end screen — the overlay never looks like a frozen/broken screen.
- [ ] After ~2 seconds the prompt visibly brightens and keypresses restart the game.
- [ ] VICTORY overlay behaves identically.
- [ ] No gameplay regression.

---

## 5. Expert panel findings (Step 18)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED (conditional) | Empty string during hold made the overlay look frozen; layout shifted by ~half a line on prompt appearance. Also recommended reducing hold from 3.0 → 2.0 s to match PLAN.md spec. | Changed to always show "Press any key to restart" — dim `(50,50,55)` during hold, bright `(140,140,140)` after. Reduced `END_SCREEN_HOLD` 3.0 → 2.0. |
| UX Tester | APPROVED (conditional) | Same empty-string concern: 3 seconds of static silence reads as a hang to new players. Recommended dim prompt in both overlays. | Same fix as above. |
| Code Quality | APPROVED | No issues. `update()` assert on hold timer mirrors existing wave-timer pattern — intentionally consistent. | No change needed. |
| Platform Engineer | APPROVED | `min(elapsed + dt, END_SCREEN_HOLD)` + assert is float-safe; DT_CLAMP ensures ≤0.1 s increments; paused-gate behavior on focus loss is correct for both desktop and WASM rAF-pause paths. | No change needed. |

---

## 6. What to tell me after you review

- **"Step 18 approved, proceed"** — move on to Step 19 (grid texture + player shadow +
  danger telegraph, B3c+d+e).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel.
