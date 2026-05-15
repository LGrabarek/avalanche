---
name: Cube tumble animation needs "heavy" non-uniform easing
description: The current uniform 90°/tick tumble feels wrong; the original I.Q. tumble has a distinct heavy-cube easing profile — recorded for a future polish step
type: feedback
---

The current cube tumble (Step 3A) interpolates `tumble_progress` linearly from 0→1 over `TICK_INTERVAL`, driving a uniform 90° rotation. Mechanically correct, but the **feel is wrong** versus the 1997 I.Q. original. User-reported memory of the authentic feel:

> "I remember the cube having a physical feel as if they were extremely heavy — moved forward by tumbling initially with great effort, as if decelerating toward the pivot point when each cube is briefly balanced on its edge, then falling with a great thud more rapidly. Then there is a brief pause before the next tumble."

Correct animation profile, in four stages per tick:

1. **Heave phase** — rotation starts slow and *decelerates* as the cube approaches the balance point. Feels like heavy mass being levered over its edge. Occupies roughly the first 40-50% of the tick.
2. **Balance point** — a brief pause (30-80ms) with the cube balanced on its leading edge (rotation angle = 45°, center-of-mass directly above the pivot). Reads as a physical beat.
3. **Thud phase** — rotation accelerates under "gravity" and lands decisively on the next tile. Fast motion in ~20-30% of the tick.
4. **Rest phase** — short stillness (50-100ms) before the next tick begins.

**Why:** the retro feel hard-rule (CLAUDE.md rule 3) is specifically preserved for the punishing difficulty AND the physical identity. The uniform tumble erodes that identity.

**How to apply:** The **rest phase** was pulled forward to Step 4B (2026-04-17) because the absence of any rest period made capture timing feel impossible — the cube was always mid-tumble with no visible "landed" window. `TUMBLE_REST_FRACTION=0.75` added to `constants.py`; `cube_data.py:_lut_sin_cos` now remaps raw progress so the rotation completes at t=0.75 and the cube holds at rest through t=1.0 (0.3s rest window at 1.2s tick). Geometry invariants verified.

The remaining three phases (heave decel, balance point, thud accel) still land in Step 10 — the natural home is with audio, so the "thud" sound + visual acceleration are co-designed. Candidate landing spots:

- **Step 10 (polish)** — add heave/balance/thud on top of the existing rest budget. Audio "thud" metronome triggers when eased progress crosses 1.0 (same event as the rest-phase boundary).
- Rest-phase timing (`TUMBLE_REST_FRACTION`) may want a small retune once Step 5 crush pressure + Step 9 wave speed land. Keep it a named constant so it's one-line adjustable.

**Implementation notes when it's time:**

- Replace `_lut_sin_cos(progress)` at `cube_data.py:52` (or its caller `get_cube_vertices`) with an eased progress curve — piecewise over the four stages. Don't rewrite the rotation math; just reshape the progress→angle mapping so 0..1 raw linear progress maps to 0..1 eased progress with the shape above.
- The LUT (`TUMBLE_SIN_LUT`/`TUMBLE_COS_LUT`) doesn't need to change — it still encodes sin/cos over 0..90°. What changes is which LUT entry gets sampled at raw progress `t`.
- The balance-point pause and rest pause consume tick time, so the 90° rotation completes in ~(70-80%) of `TICK_INTERVAL`, not all of it. Budget roughly: 0-45% rotating to balance (decel), 45-55% balanced, 55-80% falling (accel), 80-100% at rest on new tile.
- The thud can cue the audio metronome (Step 10 polish anyway): SFX trigger when eased progress crosses 1.0.
- Audio-timing and visual-timing should derive from the same eased curve so they stay in sync.
- Test: at the balance point (t≈0.5), the cube's max-y should be √2 ≈ 1.414 (same as linear), but it should *dwell* there visually for ~60ms rather than pass through instantaneously.

Do NOT mix this with the `TICK_INTERVAL` tuning discussion — they're orthogonal. Tick interval is *how often* a cube advances; tumble easing is *how it moves* within one tick. Both land in later steps; keep them in separate commits.
