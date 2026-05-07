# Step 13A — User Review (Turbo Key)

**What Step 13 covers:** A hold-to-turbo key (`F`) that accelerates the wave tick
interval from the normal 1.2 s to 0.25 s while the key is held.  Releasing the key
immediately restores normal speed.  Only active during `WAVE_ACTIVE`; has no effect
during `AVALANCHE` (already at maximum 0.15 s speed) or any other phase.

---

## 1. What changed

| File | Change |
|---|---|
| `constants.py` | Added `TURBO_TICK_INTERVAL: float = 0.25` and `KEY_TURBO: int = pygame.K_f` |
| `game_manager.py` | Imported `TICK_INTERVAL` + `TURBO_TICK_INTERVAL`; added `set_turbo(enabled: bool)` method |
| `main.py` | Imported `KEY_TURBO`; added `KEYDOWN F` → `set_turbo(True)`, `KEYUP F` → `set_turbo(False)`, and `ACTIVEEVENT gain=0` → `set_turbo(False)` |
| `hud.py` | Appended `"   Turbo: F"` to the bottom hint line |

No wave data, grid, or scoring logic was changed.

---

## 2. How to test

### 2a. Basic hold-to-turbo

1. Run the game: `bash run_dev.sh` → open `http://localhost:8000`.
2. Start a wave (press any key at the title screen, wait for `WAVE_ACTIVE`).
3. **Hold `F`.** Cubes should visibly advance faster — approximately 5× the normal
   rate (tick every 0.25 s vs. 1.2 s).
4. **Release `F`.** Speed should return to normal immediately.
5. Repeat: hold, release, hold, release.  No stuttering or overshoot.

### 2b. Speed is discrete and correct

| Mode | Tick interval | Description |
|---|---|---|
| Normal | 1.2 s | Cubes take ~1.2 s between row advances |
| **Turbo** | **0.25 s** | Cubes take ~0.25 s between row advances (~5× faster) |
| Avalanche | 0.15 s | After crush — already faster than turbo |

### 2c. Turbo does not fire outside WAVE_ACTIVE

| Phase | Expected behaviour |
|---|---|
| Title screen | Hold F → no effect |
| WAVE_RISING (between-wave pause) | Hold F → no effect |
| AVALANCHE | Hold F → no effect (speed already at 0.15 s) |
| GAME_OVER / VICTORY | Hold F → no effect |

### 2d. Tab-switch / focus-loss safety

1. During `WAVE_ACTIVE`, hold `F` (turbo active).
2. Switch to another app or click away from the browser tab.
3. Return focus to the game.
4. **Wave should be running at normal speed** — turbo must not be stuck on.

### 2e. Turbo survives phase transitions cleanly

1. Hold `F` while the last cube of a wave clears → wave transitions to
   `WAVE_RISING`.  After the 2 s pause, the next wave starts at **normal speed**
   (turbo is not carried over).
2. Release `F` at any point; speed should always return to 1.2 s.

### 2f. HUD hint

The bottom hint line should now read:
```
Move: WASD / Arrows   Mark: SPACE   Trigger: X / Enter   Detonate: Z   Turbo: F
```

---

## 3. Success criteria

- [ ] **Hold F speeds up cubes** visibly (~5× faster) during `WAVE_ACTIVE`.
- [ ] **Release F restores normal speed** immediately, no overshoot.
- [ ] **No effect** in TITLE, WAVE_RISING, AVALANCHE, GAME_OVER, VICTORY.
- [ ] **Turbo clears on focus loss** — switching tabs and returning leaves speed normal.
- [ ] **HUD hint updated** — `"Turbo: F"` visible at bottom of screen.
- [ ] **Game remains fully playable** — marks, triggers, detonations all work at turbo speed.

---

## 4. Expert panel findings (Step 13A)

| Reviewer | Verdict | Finding | Resolution |
|---|---|---|---|
| Vision Lead | APPROVED | 0.25 s interval well-calibrated; hold-to-turbo correct UX; phase-gating design-sound; retro aesthetic preserved. | No change needed. |
| Code Quality | APPROVED | KEYUP outside pause guard is intentional and correct (set_turbo is a no-op outside WAVE_ACTIVE anyway). All Power of Ten rules satisfied. | No change needed. |
| UX Tester | APPROVED | Hold-to-turbo intuitive; wave transitions safe; 0.25 s fast enough to feel useful, slow enough to react. Optional future enhancement: turbo-active HUD indicator. | No change needed. |
| Platform Engineer | CONCERNS → APPROVED | Tab-switch KEYUP may not fire in WASM; turbo could remain stuck on after focus loss. `reset_for_new_wave` already resets tick_interval so Fix 3 was not needed. | Added `game.set_turbo(False)` on `ACTIVEEVENT gain=0` in `_drain_events`. |

---

## 5. What to tell me after you review

- **"Step 13 approved, proceed"** — move on to Step 14 (Esc pause menu).
- **"Approved, plus this fix: [specific change]"** — I'll apply and re-verify.
- **"Changes needed: [X, Y, Z]"** — I'll address and re-run the panel.
