# Step 25 — User Review (Audio system, A1)

**What Step 25 covers:**
- New `audio.py` module: 8 procedural sounds synthesised from PCM at startup — no audio files required.
- Sound list:
  - `tick_normal`: 220 Hz sine, 60 ms, decay 35/s — wave metronome at normal speed
  - `tick_avalanche`: 300 Hz sine, 50 ms, 80% amplitude, decay 45/s — higher/faster during avalanche
  - `capture`: 440→660 Hz ascending two-tone bleep, 80 ms each, 30 ms gap — reward for Normal/Advantage
  - `forbidden_buzz`: 150 Hz square wave, 250 ms, 65% amplitude, decay 10/s — FORBIDDEN capture penalty
  - `row_delete`: 55+80+120 Hz sine mix, 300 ms, decay 10/s — row erased rumble
  - `wave_clear`: C5(523)→E5(659)→G5(784) arpeggio, 120 ms each, 40 ms gaps — wave/stage completion fanfare
  - `detonation`: 600→150 Hz sweep, 100 ms — Z-key trap detonation blast
  - `game_over`: 400→100 Hz sweep + amplitude fade, 700 ms — descending game-over sting

---

## 1. What changed

| File | Change |
|---|---|
| `audio.py` | New file: full `AudioSystem` class + PCM helper functions |
| `constants.py` | Added `SOUND_ENABLED: bool = True` |
| `game_manager.py` | Added `audio: AudioSystem \| None = None` param; 11 call-sites wired |
| `main.py` | `pygame.mixer.pre_init()` before `pygame.init()`; creates `AudioSystem`; tick sound in main loop |
| `run_dev.sh` | Added `audio.py` to build copy list |

---

## 2. Design details

### Integration map

| Event | Sound played | Location |
|---|---|---|
| Wave tick (normal phase) | `tick_normal` | `main.py` main loop |
| Wave tick (avalanche phase) | `tick_avalanche` | `main.py` main loop |
| Normal cube captured | `capture` | `_dispatch_capture` SCORE |
| Advantage cube captured | `capture` | `_dispatch_capture` CREATE_TRAP |
| Forbidden cube captured (direct) | `forbidden_buzz` | `_dispatch_capture` ROW_DELETE |
| Forbidden cube hit in blast | `forbidden_buzz` + `row_delete` | `_execute_blast` ROW_DELETE |
| Normal/Advantage cube blasted | `detonation` | `_execute_blast` SCORE / DETONATE_3X3 |
| Row deleted (penalty counter) | `row_delete` | `_count_wave_misses` |
| Row deleted (avalanche penalty) | `row_delete` | `_apply_avalanche_penalties` |
| Wave / stage cleared | `wave_clear` | `_on_wave_cleared` |
| Stage transition confirmed | `wave_clear` | `_on_stage_complete` |
| Game over | `game_over` | `_check_game_over` |

### PCM synthesis approach

All sounds are generated at startup from Python's `array` module using 22 050 Hz mono 16-bit PCM,
then loaded into `pygame.mixer.Sound(buffer=...)`. This path is confirmed WASM-compatible and
requires no audio files bundled with the build. Total PCM memory is approximately 170 KB.

The mixer is initialised with `pygame.mixer.pre_init(frequency=22050, size=-16, channels=1,
buffer=512)` called before `pygame.init()`. A `get_init()` guard at construction time means
the `AudioSystem` degrades silently if the mixer failed to initialise (no audio device,
headless CI, browser autoplay restriction not yet satisfied).

---

## 3. How to test

### 3a. Verify mixer initialised

1. Run `bash run_dev.sh` → open `http://localhost:8000`.
2. Open the browser developer console (F12).
3. Start the game; confirm no audio-related errors appear in the console.
4. Confirm `SOUND_ENABLED = True` in `constants.py` (the default).

### 3b. Tick metronome

1. Start a game. You should hear a short, soft click on every cube advance.
2. Let the wave reach avalanche speed. The click should be noticeably higher-pitched
   and slightly softer (300 Hz vs 220 Hz, 80% amplitude).

### 3c. Capture sounds

1. Mark a Normal (grey) cube with Space, then walk off it to trigger capture →
   you should hear an ascending two-tone bleep (440 Hz then 660 Hz).
2. Mark an Advantage (green) cube and trigger it → same ascending bleep.
3. Mark a Forbidden (purple) cube and trigger it → a low, harsh buzz (square wave).

### 3d. Row delete

1. Let 3 Normal cubes pass without capturing (they reach the front edge) →
   a low rumble should sound as the row is deleted.

### 3e. Wave clear

1. Successfully capture all cubes in a wave → a C-E-G major arpeggio fanfare should
   play before the next wave begins. The same fanfare should play on stage completion.

### 3f. Detonation

1. Capture an Advantage cube to place a green 3×3 trap area.
2. Press Z to detonate → a short percussive descending burst (600→150 Hz sweep).

### 3g. Game over

1. Let the wave advance until it crushes the player → a descending 700 ms sting
   (400→100 Hz sweep with amplitude fade).

### 3h. Graceful degradation

1. Open `constants.py` and set `SOUND_ENABLED = False`.
2. Restart the dev server and load the game.
3. The game should run silently with no errors or exceptions.

---

## 4. Success criteria

- [ ] Tick click audible on every wave advance; higher pitch during avalanche
- [ ] Ascending two-tone bleep on Normal/Advantage capture
- [ ] Low buzz on Forbidden capture
- [ ] Rumble on each row deletion
- [ ] Major arpeggio fanfare on wave clear and stage completion
- [ ] Short percussive burst on Z-key detonation
- [ ] Descending sting on game over
- [ ] No audio errors in browser console
- [ ] `SOUND_ENABLED = False` silences everything; game still runs without errors

---

## 5. Expert panel findings (Step 25)

| Reviewer | Verdict | Finding |
|---|---|---|
| Code Quality | APPROVED | All Power of Ten rules pass; zero ruff/mypy issues |
| Platform Engineer | APPROVED | pre_init sequence correct; `array` + `mixer.Sound(buffer=)` path confirmed WASM-compatible; AudioContext gesture-policy handled by `get_init()` guard; memory nominal (~170 KB PCM total) |
| Vision Lead | APPROVED (after fix) | Sound vocabulary correct and faithful to I.Q. reference; required fix (blast Forbidden: add both buzz + rumble) applied |
| UX Tester | APPROVED (after fixes) | Detonation sound added for blast captures; forbidden buzz amplitude raised from 40% to 65%; stage-continue fanfare added; all blocking concerns addressed |

---

## 6. What to tell me after you review

- **"Step 25 approved, proceed"** — the plan is complete; all steps done.
- **"Sound X is too loud/quiet"** — describe which sound and I'll adjust the amplitude constants.
- **"Sound Y is wrong"** — describe what you hear and what you expected.
- **"No sound at all"** — check the browser console for mixer errors; also try toggling the
  `SOUND_ENABLED` flag to confirm the system initialised.
