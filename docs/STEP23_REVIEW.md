# Step 23 — User Review (Movement perpendicular priority, A8)

**What Step 23 covers:**
- When the player holds a Z-axis key (FORWARD = UP arrow / W) and an X-axis key
  (LEFT / RIGHT arrow) simultaneously, the Z-axis direction now wins.
- Matches the original I.Q.: Intelligent Qube behaviour (the PSX D-pad made true
  diagonal input physically impossible; this rule reproduces that on keyboard).

---

## 1. What changed

| File | Change |
|---|---|
| `player.py` | Z-axis priority guard added to `_first_held_direction()`; docstrings updated |

No other files changed. No constants, no assets, no game logic.

---

## 2. Design details

### Before Step 23

`_first_held_direction` resolved perpendicular conflicts by returning the first
direction in `MOVEMENT_KEYS` iteration order: **LEFT → RIGHT → FORWARD → BACKWARD**.
So when both LEFT and FORWARD were held, LEFT won — silently, by accident of dict
ordering. This introduced a keyboard handicap that didn't exist in the original game.

### After Step 23

After the opposing-pair cancellation pass (LEFT+RIGHT cancel each other, as before),
a new guard fires:

```python
z_dirs = held_dirs & {Direction.FORWARD, Direction.BACKWARD}
x_dirs = held_dirs & {Direction.LEFT, Direction.RIGHT}
if z_dirs and x_dirs:
    held_dirs = z_dirs
```

When exactly one Z-axis and one X-axis direction survive, only the Z-axis one is kept.
This means:

| Keys held | Old behaviour | New behaviour |
|---|---|---|
| LEFT + FORWARD | LEFT wins (iteration order accident) | FORWARD wins |
| RIGHT + FORWARD | RIGHT wins | FORWARD wins |
| LEFT + BACKWARD | LEFT wins | BACKWARD wins |
| RIGHT + BACKWARD | RIGHT wins | BACKWARD wins |
| LEFT + RIGHT (opposite) | Neither (cancelled) | Neither (unchanged) |
| FORWARD + BACKWARD (opposite) | Neither (cancelled) | Neither (unchanged) |
| Single key only | That key | Unchanged |

### Why Z wins

- The wave advances along the Z axis (toward the player). Survival is primarily a
  Z-axis problem: you need to run or dodge in depth to avoid the wave.
- In a panic, a player is most likely holding FORWARD (to escape) while accidentally
  clipping a lateral key. The old behaviour would stall their escape; the new
  behaviour continues it.
- An accidental FORWARD move is survivable (moves away from the wave). An accidental
  stall while trying to escape is not.

---

## 3. How to test

### 3a. Perpendicular hold — the key scenario

1. Run `bash run_dev.sh` → open `http://localhost:8000`.
2. Start a game (press Space/Enter on the title screen).
3. Position your player anywhere in the middle of the grid.
4. **Hold UP (FORWARD) and then, while still holding UP, also hold LEFT.**
5. Observe: the player should move **up** (away from the wave) — not left.
6. Release both, hold UP + RIGHT: player moves **up**, not right.
7. Release both, hold DOWN + LEFT: player moves **down** (toward wave), not left.
8. Release both, hold DOWN + RIGHT: player moves **down**, not right.

### 3b. Single-key movement unchanged

Confirm that pressing only one directional key at a time still moves the player
correctly in all four directions. No regression.

### 3c. Opposite-axis cancel unchanged

Hold LEFT + RIGHT simultaneously: player should not move (same as before).
Hold UP + DOWN simultaneously: player should not move (same as before).

### 3d. Cooldown behaviour unchanged

Rapid tapping and held-key movement cooldown should feel identical to before.

### 3e. No regressions

- All wave mechanics, captures, triggers, scoring, and game-over detection unchanged.
- No Python errors or warnings in the console.

---

## 4. Success criteria

- [ ] Holding FORWARD + LEFT moves the player FORWARD (not LEFT).
- [ ] Holding FORWARD + RIGHT moves the player FORWARD (not RIGHT).
- [ ] Holding BACKWARD + LEFT moves the player BACKWARD (not LEFT).
- [ ] Holding BACKWARD + RIGHT moves the player BACKWARD (not RIGHT).
- [ ] Single-key movement works correctly in all four directions.
- [ ] Opposite-axis (LEFT+RIGHT, UP+DOWN) still cancels to no movement.
- [ ] No regressions in any previously-approved game mechanic.

---

## 5. Expert panel findings (Step 23)

| Reviewer | Verdict | Finding |
|---|---|---|
| Vision Lead | APPROVED | Z-priority faithful to D-pad hardware; correct resolution of a keyboard-specific gap the original never had |
| Code Quality | APPROVED | Set intersection logic exhaustive and correct; guard fires only on genuine perpendicular case; Rule 4 / Rule 5 / Rule 10 all satisfied |
| UX Tester | APPROVED | Z-winning is the survivable direction in all panic scenarios; old X-winning was an ordering artifact with no design justification |
| Platform Engineer | APPROVED | Pure Python set arithmetic on ≤4 elements; no WASM concern; zero compatibility risk |

No changes required by the panel.

---

## 6. What to tell me after you review

- **"Step 23 approved, proceed"** — move on to Step 24 (Camera rework, A7).
- **"Approved, plus this fix: [specific change]"** — apply and re-verify.
- **"Diagonal movement still feels wrong"** — describe what you observed and which
  keys were held.
- **"Changes needed: [X, Y, Z]"** — address and re-run panel.
