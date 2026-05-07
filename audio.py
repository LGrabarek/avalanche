"""Procedural audio system for Avalanche.

All sounds are synthesised from PCM data at initialisation time — no
external audio files are required. Every ``pygame.mixer.Sound`` is
pre-generated once and stored for zero-cost fire-and-forget playback.

If ``pygame.mixer`` fails to initialise (browser format-error, headless CI,
or no audio device) ``AudioSystem._enabled`` is set to False and every
``play_*`` method is a silent no-op.  The rest of the game is unaffected.
"""

import array
import math

import pygame

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

SAMPLE_RATE: int = 22050   # Hz — must match pygame.mixer.pre_init in main.py
_AMP: int = 26000          # Peak amplitude (16-bit signed PCM range: ±32767)
_MAX_SOUNDS: int = 8       # Rule 3 bound: one entry per public play_* method


# ---------------------------------------------------------------------------
# PCM helpers
# ---------------------------------------------------------------------------


def _n(dur: float) -> int:
    """Convert a duration in seconds to an integer sample count.

    Raises ValueError for non-positive durations so callers receive a clear
    diagnostic instead of an empty or wrong-length buffer.
    """
    if dur <= 0.0:
        raise ValueError(f"dur must be positive, got {dur}")
    return int(dur * SAMPLE_RATE)


def _sine_wave(freq: float, dur: float, amp: int = _AMP) -> list[float]:
    """Return ``_n(dur)`` samples of a pure sine wave at ``freq`` Hz."""
    if freq <= 0.0:
        raise ValueError(f"freq must be positive, got {freq}")
    n = _n(dur)
    result = [
        amp * math.sin(2.0 * math.pi * freq * i / SAMPLE_RATE)
        for i in range(n)
    ]
    assert len(result) == n, "sine_wave: sample count mismatch"
    return result


def _square_wave(freq: float, dur: float, amp: int = _AMP) -> list[float]:
    """Return ``_n(dur)`` samples of a square wave at ``freq`` Hz."""
    if freq <= 0.0:
        raise ValueError(f"freq must be positive, got {freq}")
    n = _n(dur)
    result: list[float] = []
    for i in range(n):
        assert len(result) < n, "square_wave: buffer overflow"
        phase_frac = (freq * i / SAMPLE_RATE) % 1.0
        result.append(float(amp) if phase_frac < 0.5 else float(-amp))
    assert len(result) == n, "square_wave: sample count mismatch"
    return result


def _apply_decay(samples: list[float], rate: float) -> list[float]:
    """Apply an exponential amplitude decay envelope to ``samples``.

    ``rate`` is the decay constant in 1/s: higher values fade faster.
    Returns an empty list when ``samples`` is empty.
    """
    if rate <= 0.0:
        raise ValueError(f"rate must be positive, got {rate}")
    n = len(samples)
    if n == 0:
        return []
    result = [
        s * math.exp(-rate * i / SAMPLE_RATE)
        for i, s in enumerate(samples)
    ]
    assert len(result) == n, "apply_decay: length changed"
    return result


def _mix(a: list[float], b: list[float]) -> list[float]:
    """Return the element-wise sum of two equal-length sample lists."""
    if len(a) != len(b):
        raise ValueError(f"mix: length mismatch — {len(a)} vs {len(b)}")
    result = [x + y for x, y in zip(a, b, strict=True)]
    assert len(result) == len(a), "mix: output length mismatch"
    return result


def _to_sound(samples: list[float]) -> pygame.mixer.Sound:
    """Convert a float sample list to a ``pygame.mixer.Sound`` (16-bit PCM).

    Clips values to ±32767 before packing so amplitude overflow produces
    controlled saturation rather than signed-integer wrap-around.
    """
    if not samples:
        raise ValueError("samples must not be empty")
    buf = array.array(
        "h",
        (int(max(-32767.0, min(32767.0, s))) for s in samples),
    )
    return pygame.mixer.Sound(buffer=buf.tobytes())


# ---------------------------------------------------------------------------
# Sound builders — each returns list[float]; converted in AudioSystem.__init__
# ---------------------------------------------------------------------------


def _tick_normal_samples() -> list[float]:
    """Short 220 Hz sine click: wave metronome at normal speed."""
    return _apply_decay(_sine_wave(220.0, 0.06), rate=35.0)


def _tick_avalanche_samples() -> list[float]:
    """Sharper 300 Hz sine tick: faster metronome cadence during avalanche."""
    return _apply_decay(_sine_wave(300.0, 0.05, amp=int(_AMP * 0.8)), rate=45.0)


def _capture_samples() -> list[float]:
    """Ascending two-tone bleep (440 → 660 Hz): reward for a clean capture."""
    lo = _apply_decay(_sine_wave(440.0, 0.08), rate=12.0)
    hi = _apply_decay(_sine_wave(660.0, 0.08), rate=12.0)
    gap = [0.0] * _n(0.03)
    return lo + gap + hi


def _forbidden_buzz_samples() -> list[float]:
    """Low 150 Hz square-wave buzz: harsh signal for a FORBIDDEN capture.

    Amplitude set at 65% of peak so the buzz is assertive — clearly negative
    against the softer (100%) capture bleep — without being overwhelming.
    """
    return _apply_decay(
        _square_wave(150.0, 0.25, amp=int(_AMP * 0.65)), rate=10.0
    )


def _row_delete_samples() -> list[float]:
    """Three-frequency low rumble (55 + 80 + 120 Hz): a row being erased."""
    dur = 0.30
    a = _sine_wave(80.0,  dur, amp=int(_AMP * 0.50))
    b = _sine_wave(120.0, dur, amp=int(_AMP * 0.35))
    c = _sine_wave(55.0,  dur, amp=int(_AMP * 0.25))
    return _apply_decay(_mix(_mix(a, b), c), rate=10.0)


def _wave_clear_samples() -> list[float]:
    """C5–E5–G5 arpeggio: short celebratory fanfare on wave completion."""
    note_dur = 0.12
    gap = [0.0] * _n(0.04)
    c5 = _apply_decay(_sine_wave(523.25, note_dur), rate=8.0)
    e5 = _apply_decay(_sine_wave(659.25, note_dur), rate=8.0)
    g5 = _apply_decay(_sine_wave(784.00, note_dur), rate=8.0)
    return c5 + gap + e5 + gap + g5


def _detonation_samples() -> list[float]:
    """600 → 150 Hz short descending burst: Z-key green trap detonation.

    Uses true phase accumulation (same approach as game_over) so the pitch
    glide is smooth. The fast amplitude fade (100% → 0%) produces a sharp
    percussive attack that reads as an explosion rather than a tone.
    """
    n = _n(0.10)
    samples = [0.0] * n   # pre-allocate: no append, no Rule 3 concern
    phase = 0.0
    for i in range(n):
        t = i / n
        freq = 600.0 - 450.0 * t        # sweep: 600 Hz → 150 Hz
        phase += 2.0 * math.pi * freq / SAMPLE_RATE
        amp = _AMP * (1.0 - t)          # amplitude: 100 % → 0 %
        samples[i] = math.sin(phase) * amp
    assert len(samples) == n, "detonation: sample count mismatch"
    return samples


def _game_over_samples() -> list[float]:
    """400 → 100 Hz frequency sweep with fade: descending sting on game over.

    True phase accumulation ensures a smooth pitch glide with no sample-
    boundary discontinuities.
    """
    n = _n(0.70)
    samples = [0.0] * n   # pre-allocate: no append, no Rule 3 concern
    phase = 0.0
    for i in range(n):
        t = i / n
        freq = 400.0 - 300.0 * t            # linear sweep: 400 Hz → 100 Hz
        phase += 2.0 * math.pi * freq / SAMPLE_RATE
        amp = _AMP * (1.0 - 0.8 * t)        # amplitude: 100 % → 20 %
        samples[i] = math.sin(phase) * amp
    assert len(samples) == n, "game_over: sample count mismatch"
    return samples


# ---------------------------------------------------------------------------
# AudioSystem
# ---------------------------------------------------------------------------


class AudioSystem:
    """Pre-generated procedural sounds for all Avalanche game events.

    Constructed once at startup; every sound is generated and stored as a
    ``pygame.mixer.Sound`` object.  If mixer initialisation fails,
    ``_enabled`` is False and all ``play_*`` calls are silent no-ops.
    """

    def __init__(self) -> None:
        self._enabled: bool = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        try:
            if not pygame.mixer.get_init():
                return
            builders: dict[str, list[float]] = {
                "tick_normal":    _tick_normal_samples(),
                "tick_avalanche": _tick_avalanche_samples(),
                "capture":        _capture_samples(),
                "forbidden":      _forbidden_buzz_samples(),
                "row_delete":     _row_delete_samples(),
                "wave_clear":     _wave_clear_samples(),
                "detonation":     _detonation_samples(),
                "game_over":      _game_over_samples(),
            }
            assert len(builders) == _MAX_SOUNDS, (
                f"sound registry has {len(builders)} entries; expected {_MAX_SOUNDS}"
            )
            for key, pcm in builders.items():
                assert len(self._sounds) < _MAX_SOUNDS, (
                    "AudioSystem: _sounds exceeded _MAX_SOUNDS bound"
                )
                self._sounds[key] = _to_sound(pcm)
            self._enabled = True
        except Exception:  # noqa: BLE001  -- mixer failures are non-fatal
            self._enabled = False

    # --- Public play methods ------------------------------------------------

    def play_tick(self, avalanche: bool = False) -> None:
        """Play the wave-advance metronome click (normal or avalanche cadence)."""
        self._play("tick_avalanche" if avalanche else "tick_normal")

    def play_capture(self) -> None:
        """Play the two-tone reward bleep for a Normal or Advantage capture."""
        self._play("capture")

    def play_forbidden_buzz(self) -> None:
        """Play the low buzz signalling a FORBIDDEN-cube capture."""
        self._play("forbidden")

    def play_row_delete(self) -> None:
        """Play the low rumble when a platform row is erased."""
        self._play("row_delete")

    def play_wave_clear(self) -> None:
        """Play the ascending arpeggio fanfare when a wave is fully cleared."""
        self._play("wave_clear")

    def play_detonation(self) -> None:
        """Play the short descending burst when the Z-key trap area detonates."""
        self._play("detonation")

    def play_game_over(self) -> None:
        """Play the descending frequency sting on game over."""
        self._play("game_over")

    # --- Internal -----------------------------------------------------------

    def _play(self, key: str) -> None:
        """Look up ``key`` in the registry and fire it; no-op when disabled."""
        if not self._enabled:
            return
        sound = self._sounds.get(key)
        if sound is None:
            return
        _ = sound.play()  # unused: returns pygame.Channel; fire-and-forget
