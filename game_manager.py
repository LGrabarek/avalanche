"""Game manager — phase state machine, mark/trigger, crush, and avalanche.

Owns game state that spans multiple subsystems: score, phase, mark lifecycle
(delegated to GridManager), capture dispatch (via CubeBehavior registry), and
the crush → avalanche transition.

Step 5A additions:
  * `GamePhase` state machine: WAVE_ACTIVE → AVALANCHE → WAVE_CLEARING.
  * `check_mid_tumble_crush(player, wave)` — per-frame: fires when a cube in
    the player's column passes its balance point (CRUSH_TUMBLE_THRESHOLD).
    Fires before the rest/capture window opens, so the crush cannot be escaped
    by capturing the approaching cube.
  * `on_tick(player, wave)` — called when a tick fires; accumulates avalanche
    penalties. Also a safety-net crush check for direct-spawn edge cases.
  * `_trigger_avalanche(player, wave)` — drops tick interval to the stage-
    appropriate `_cur_avalanche_tick_interval`, crushes the player, clears
    the mark, fires shake. (Step 21 replaced the hardcoded constant.)

Step 6A additions:
  * `_wave_penalty` — counts missed NORMAL/ADVANTAGE cubes during WAVE_ACTIVE.
    Every PENALTY_THRESHOLD misses triggers `grid.delete_front_row()` and then
    `_check_game_over` (player tile voided → GAME_OVER).
  * `_apply_avalanche_penalties` — converts `_avalanche_penalty` accumulated
    during AVALANCHE into row deletions when transitioning to WAVE_CLEARING.
  * `_check_game_over` — transitions to GAME_OVER when the player's tile is
    void (deleted by a penalty row).
  * FORBIDDEN on_capture (ROW_DELETE) — capturing a FORBIDDEN cube immediately
    deletes the front row and checks for GAME_OVER, same outcome as filling the
    penalty counter. `on_trigger` now takes `player` so the ROW_DELETE path can
    call `_check_game_over`.

Step 7A additions:
  * Capturing an ADVANTAGE cube (CREATE_TRAP) now marks the full 3×3 area around
    the captured tile as ADVANTAGE_TRAP, not just the centre tile.
  * `on_detonate(player)` — called when Z is pressed during WAVE_ACTIVE. Collects
    all ADVANTAGE_TRAP tiles, clears them, then fires a 3×3 blast from each.
    NORMAL cubes score `chain_score` (200 pts). ADVANTAGE cubes score, are removed,
    and their 3×3 area is marked as new ADVANTAGE_TRAP tiles — player must press Z
    again to detonate those. FORBIDDEN cubes trigger `delete_front_row` +
    `_check_game_over`. Blocked outside WAVE_ACTIVE.
  * `_execute_blast(cx, cz, player)` — executes one 3×3 blast. Dispatches each
    cube found via `on_detonate` hook.
  * `_mark_trap_area(cx, cz)` — sets all non-void tiles in the 3×3 around
    `(cx, cz)` to ADVANTAGE_TRAP. Shared by CREATE_TRAP capture and DETONATE_3X3
    blast hit.

Step 10B additions:
  * `on_restart_key(player)` — resets all game objects and returns to TITLE.
    Called from main.py on any KEYDOWN during GAME_OVER or VICTORY. No-op
    in other phases. Internally calls `_reset_state` then `start_first_wave`.
  * `_reset_state()` — zeroes score/iq/phase/penalty/wave-tracking fields,
    delegates to grid.reset(), wave.reset_for_new_wave(), effects.reset(),
    and player.reset() in safe dependency order (grid first, then player).

Step 10A additions:
  * `TITLE` phase: `start_first_wave` now enters TITLE instead of spawning
    immediately. Player presses any key → `on_title_advance()` → STAGE_INTRO.
  * `STAGE_INTRO` phase (Step 29): 2.8-second rolling-wave animation before wave 0.
    Replaces the initial WAVE_RISING at stage start; `update` fires `_begin_wave`
    when the timer expires. WAVE_RISING is still used for waves 2-4 within a stage.
  * `WAVE_RISING` phase: 2-second between-wave timer. `update(dt, player)` counts
    down; when it reaches zero `_spawn_wave` fires. `perfect_display` property
    signals main.py whether to show the PERFECT! banner during this window.
  * `on_title_advance()` — TITLE → STAGE_INTRO.
  * `update(dt, player)` — per-frame countdown; triggers wave spawn on expiry.
  * `perfect_display` property — True during WAVE_RISING after a Perfect wave.
  * `_on_wave_cleared` now uncrushs the player and clears the mark immediately
    (before the WAVE_RISING pause) so the transition looks clean.
  * `_spawn_wave` resets `_perfect_display` to False on each new wave.

Step 9A additions:
  * `start_first_wave(player, waves)` — initialize the wave sequence (tuple of
    WaveData) and spawn the first wave. Must be called once before the game loop.
  * `_spawn_wave(player)` — spawn cubes for the current wave index and reset all
    per-wave state (forbidden_captured, had_avalanche, player_steps,
    wave_total_misses, wave_penalty, avalanche_penalty). Uncrushs the player.
  * `_on_wave_cleared(player)` — triggered when wave.cube_count == 0 in both
    WAVE_ACTIVE and AVALANCHE paths. Checks Perfect criteria, applies the step-
    efficiency bonus (up to 10,000 pts), restores one front row on Perfect, then
    advances to the next wave or enters VICTORY.
  * `_calc_perfect_bonus(actual, ideal)` — tier: ≤ideal → 10,000; ≤ideal+20 →
    5,000; ≤ideal+40 → 2,500; else 0.
  * `_calculate_final_iq()` — `int((score + rows*1000) * 1.00 * 0.00060)` for
    Stage 1 (index 0 of the multiplier tables in constants.py).
  * Step counting in `try_mark` / `on_trigger` / `on_detonate` feeds
    `_player_steps` for the Perfect efficiency comparison.
  * `wave_index` / `wave_count` / `iq_score` properties for HUD + VICTORY overlay.
  * `on_tick` now transitions WAVE_ACTIVE → next wave directly when
    `wave.cube_count == 0` (no longer only reachable through AVALANCHE).

Step 21 additions:
  * `_cur_tick_interval` property — returns `STAGE_TICK_INTERVALS[stage_index]`
    (clamped to table length), the normal tick speed for the current stage.
  * `_cur_avalanche_tick_interval` property — same for avalanche speed.
  * `_spawn_wave()` sets `wave.tick_interval` after `reset_for_new_wave()` so
    WaveManager never needs to know which stage is active.
  * `_trigger_avalanche()`, `set_turbo()`, `on_menu_open()` replaced the
    Stage-1-only constants with calls to the new stage-aware properties.
"""

import random

from audio import AudioSystem
from constants import (
    CRUSH_TUMBLE_THRESHOLD,
    CUBE_TYPES,
    END_SCREEN_HOLD,
    GRID_DEPTH,
    IQ_DIFFICULTY_MULTIPLIERS,
    IQ_PERCENTAGE_MULTIPLIERS,
    PENALTY_THRESHOLD,
    PERFECT_BONUS_MAX,
    PLAYER_INITIAL_WAVE_GAP,
    SCORE_ROW_SURVIVAL,
    STAGE_AVALANCHE_TICK_INTERVALS,
    STAGE_GRID_WIDTHS,
    STAGE_INTRO_DURATION,
    STAGE_TICK_INTERVALS,
    TICK_SPEED_DECAY,
    TURBO_TICK_INTERVAL,
    WAVE_GAP_ROWS,
    WAVE_RISING_DURATION,
    CubeBehavior,
    CubeType,
    GamePhase,
    TileState,
)
from effects import FlashEffects
from grid_manager import GridManager
from player import Player
from wave_data import STAGE_POOL_SLOTS, STAGES, WAVE_POOLS, WaveData, select_all_waves
from wave_manager import Cube, WaveManager


class TriggerOutcome:
    """Named outcomes for the return value of `on_trigger`.

    Intentionally a plain class-with-constants rather than an Enum. Callers
    (HUD, future audio cue dispatch) only compare against these identities,
    and keeping them as module-local str constants avoids adding another
    IntEnum to `constants.py` when the values are only ever produced here
    and consumed at one call site in `main.py`. An Enum would be free to
    introduce later if the outcome vocabulary grows or needs serialization.
    """

    NO_MARK: str = "no_mark"           # trigger pressed with no mark active
    MISS: str = "miss"                 # mark existed, no cube on it (or mid-tumble)
    CAPTURED_SCORE: str = "score"      # NORMAL captured → score awarded
    CAPTURED_TRAP: str = "trap"        # ADVANTAGE captured → tile turned trap
    CAPTURED_FORBIDDEN: str = "forbidden"  # FORBIDDEN captured (penalty pending)
    BLOCKED: str = "blocked"           # action disallowed in current phase


class GameManager:
    """Orchestrates mark/trigger flow, scoring, and crush/avalanche state.

    The manager is the single point that knows both the grid and the wave;
    every other module sees only its own data. Phase transitions here own the
    canonical game-state progression for Steps 5–9.
    """

    def __init__(
        self,
        grid: GridManager,
        wave: WaveManager,
        effects: FlashEffects,
        audio: AudioSystem | None = None,
    ) -> None:
        self._grid: GridManager = grid
        self._wave: WaveManager = wave
        self._effects: FlashEffects = effects
        self._audio: AudioSystem | None = audio
        self._score: int = 0
        self._phase: GamePhase = GamePhase.WAVE_ACTIVE
        self._wave_penalty: int = 0      # Missed NORMAL/ADVANTAGE cubes during WAVE_ACTIVE.
        self._avalanche_penalty: int = 0  # Missed NORMAL/ADVANTAGE cubes during AVALANCHE.
        # Wave progression state — populated by start_game().
        self._waves: tuple[WaveData, ...] = ()
        self._wave_index: int = 0
        self._stage_index: int = 0       # 0-based index into STAGES master table.
        # Full run selection: all 10 stages × 4 waves, chosen once per run by
        # select_all_waves(). Populated by start_game(); each stage advance reads
        # self._all_stage_waves[self._stage_index] rather than STAGES directly.
        self._all_stage_waves: tuple[tuple[WaveData, ...], ...] = ()
        # Crush-retry gate: True when the current wave had a player crush.
        # On wave cleared, if this is True the wave queue advances to the next
        # pending wave without counting a clean clear; else normal clean clear.
        self._wave_crushed: bool = False
        # Retry display flag: True while the WAVE_RISING pause is a crush retry
        # (cleared when _begin_wave fires so the actual replayed wave starts clean).
        # Distinct from _wave_crushed, which is cleared before WAVE_RISING starts.
        self._retry_pending: bool = False
        # Post-rising reload flag: when True, the WAVE_RISING expiry calls
        # _reload_remaining_waves (→ STAGE_INTRO) instead of _begin_wave.
        # Set in _on_wave_cleared when the current batch is exhausted (last slot
        # crushed or last slot cleaned with stage not yet complete).
        self._post_rising_reload: bool = False
        # Stage-progress gate: counts clean clears (waves cleared without crush).
        # Stage ends when _clean_clears reaches len(_waves) (= 4). Carries over
        # across wave-batch reloads within the same stage; reset at stage boundary.
        self._clean_clears: int = 0
        # z_back coordinate for each wave's back row — populated by
        # _spawn_all_waves_pending().  Index i matches self._waves[i].
        self._wave_z_starts: list[int] = []
        # Per-wave mirror flag — stored at spawn time so crush-retry
        # can replay the exact same cube layout (same A/B variant +
        # same mirror orientation = byte-identical pattern).
        self._wave_mirrors: list[bool] = []
        self._iq_score: int = 0
        # Per-wave Perfect tracking — reset by _spawn_wave() at each wave start.
        self._forbidden_captured: bool = False   # Any FORBIDDEN captured this wave?
        self._had_avalanche: bool = False         # Crush occurred this wave?
        self._player_steps: int = 0              # Successful input actions this wave.
        self._wave_total_misses: int = 0         # NORMAL/ADVANTAGE missed in WAVE_ACTIVE.
        # Between-wave display state — set by _on_wave_cleared, reset by _spawn_wave.
        self._wave_rising_timer: float = 0.0     # Countdown for WAVE_RISING phase.
        self._perfect_display: bool = False      # Show PERFECT! banner in WAVE_RISING.
        # Stage-intro animation elapsed time.  Counts from 0 to STAGE_INTRO_DURATION
        # while phase == STAGE_INTRO; reset to 0.0 each time STAGE_INTRO is entered.
        self._intro_elapsed: float = 0.0
        # Pause menu state — _pre_menu_phase stores the phase to restore on close.
        self._pre_menu_phase: GamePhase = GamePhase.WAVE_ACTIVE
        # End-screen hold timer — counts up from 0 on entry to GAME_OVER/VICTORY.
        # Restart key is blocked until this reaches END_SCREEN_HOLD seconds.
        self._end_hold_elapsed: float = 0.0
        assert self._score == 0, "score must start at zero"
        assert self._phase == GamePhase.WAVE_ACTIVE, "phase must start WAVE_ACTIVE"

    # --- Read-only accessors -------------------------------------------------

    @property
    def score(self) -> int:
        return self._score

    @property
    def phase(self) -> GamePhase:
        return self._phase

    @property
    def wave_penalty(self) -> int:
        """Missed NORMAL/ADVANTAGE cubes accumulated since last row deletion."""
        return self._wave_penalty

    @property
    def avalanche_penalty(self) -> int:
        """Missed NORMAL/ADVANTAGE cubes accumulated during the current avalanche."""
        return self._avalanche_penalty

    @property
    def wave_index(self) -> int:
        """0-based progress index for the current stage, capped at the last wave.

        Returns _clean_clears but never exceeds _waves_per_stage - 1, so the
        HUD ("Wave {wave_index+1}/{wave_count}") displays "Wave 4/4" at the
        moment the final wave clears rather than "Wave 5/4" before _clean_clears
        is reset in _on_stage_complete.

        Stays fixed on crush (advancing the batch slot does not count as a
        clean clear), so the counter reflects true progress throughout.
        """
        max_idx = max(0, self._waves_per_stage - 1)
        return min(self._clean_clears, max_idx)

    @property
    def wave_count(self) -> int:
        """Total clean clears required to complete the current stage (always 4)."""
        return self._waves_per_stage

    @property
    def stage_index(self) -> int:
        """0-based index of the currently active stage."""
        return self._stage_index

    @property
    def iq_score(self) -> int:
        """Final I.Q. score. Populated when phase transitions to VICTORY."""
        return self._iq_score

    @property
    def perfect_display(self) -> bool:
        """True during WAVE_RISING when the just-cleared wave was Perfect."""
        return self._perfect_display

    @property
    def intro_elapsed(self) -> float:
        """Seconds elapsed since entering STAGE_INTRO (0.0 outside that phase)."""
        return self._intro_elapsed

    @property
    def wave_front_z(self) -> int:
        """Z coordinate of the front row of wave 0 — the row closest to the player.

        Used by `main._intro_y_bias` to clamp the rolling-wave animation so
        the front of wave 0 never lifts off the floor.  Valid once
        `start_first_wave` (which calls `_spawn_all_waves_pending`) has set
        `_wave_z_starts`.
        """
        assert len(self._wave_z_starts) > 0, (
            "wave_front_z called before start_first_wave"
        )
        assert len(self._waves) > 0, (
            "wave_front_z called before start_first_wave"
        )
        return self._wave_z_starts[0] - self._waves[0].row_count + 1

    @property
    def wave_code(self) -> str:
        """Short code for the currently active wave, e.g. 'S3W2B'.

        Returns '---' before the first wave is set (TITLE with empty wave list).
        Used by the HUD to identify which pool variant the player is fighting.
        """
        if not self._waves or self._wave_index >= len(self._waves):
            return "---"
        return self._waves[self._wave_index].code

    @property
    def wave_crushed(self) -> bool:
        """True while the current WAVE_ACTIVE/AVALANCHE phase had a player crush.

        Cleared before WAVE_RISING starts (see _on_wave_cleared retry branch).
        Use `retry_pending` to detect whether the current WAVE_RISING pause is
        a retry — that flag stays True through the pause until _begin_wave fires.
        """
        return self._wave_crushed

    @property
    def retry_pending(self) -> bool:
        """True during the WAVE_RISING pause that follows a crush ("Again" state).

        Set in _on_wave_cleared when _wave_crushed is cleared; drives the
        "AGAIN!" overlay banner and the "[AGAIN]" HUD tag.  Cleared in
        _begin_wave when the next wave activates.
        """
        return self._retry_pending

    @property
    def end_hold_ready(self) -> bool:
        """True once the end-screen hold has elapsed (GAME_OVER / VICTORY).

        The restart key is ignored until this returns True, preventing accidental
        skips when the end condition fires mid-keypress.
        """
        return self._end_hold_elapsed >= END_SCREEN_HOLD

    @property
    def active_wave_width(self) -> int:
        """Number of columns used by wave cubes in the current stage (1-based).

        Stages 1-4 use 7-wide patterns; 5-8 use 9-wide; 9-10 use 11-wide
        (mirrors STAGE_GRID_WIDTHS in constants.py). The grid is always
        GRID_WIDTH=11 wide (Step 33), but movement is clamped to this width
        so the player cannot safely camp in the outer columns that have no cubes.
        """
        idx = min(self._stage_index, len(STAGE_GRID_WIDTHS) - 1)
        result = STAGE_GRID_WIDTHS[idx]
        assert 1 <= result <= 11, f"active_wave_width {result} out of [1, 11]"
        return result

    # --- Stage-indexed helpers -----------------------------------------------

    @property
    def _waves_per_stage(self) -> int:
        """Number of clean clears required to complete the current stage.

        Derived from STAGE_POOL_SLOTS so it automatically matches the pool
        definition (currently 4 for every stage).  Used as the stage-complete
        threshold and as the wave_count denominator so both stay in sync.
        """
        if self._stage_index < len(STAGE_POOL_SLOTS):
            result = len(STAGE_POOL_SLOTS[self._stage_index])
            assert result > 0, f"STAGE_POOL_SLOTS[{self._stage_index}] is empty"
            return result
        return 4  # fallback for legacy / test paths where stage_index is out of range

    @property
    def _cur_tick_interval(self) -> float:
        """Normal wave tick interval for the active stage.

        All stages use STAGE_TICK_INTERVALS[0] as the base.
        Stages 1 and 2 (i=0, i=1) share the base interval because i // 2 = 0
        for both.  A 10 % speed increase applies on every odd stage (3, 5, 7 …)
        while even stages (4, 6, 8 …) hold the same interval as the stage before.
        """
        i = self._stage_index
        result = STAGE_TICK_INTERVALS[0] * (TICK_SPEED_DECAY ** (i // 2))
        assert result > 0.0, f"computed tick interval {result:.4f} is not positive"
        return result

    @property
    def _cur_avalanche_tick_interval(self) -> float:
        """Avalanche tick interval for the active stage (clamped to table)."""
        idx = min(self._stage_index, len(STAGE_AVALANCHE_TICK_INTERVALS) - 1)
        return STAGE_AVALANCHE_TICK_INTERVALS[idx]

    # --- Per-frame update (timers) -------------------------------------------

    def update(self, dt: float, player: Player) -> None:
        """Advance phase timers. Must be called every frame from main.py.

        WAVE_RISING: counts down the between-wave pause; spawns the wave on expiry.
        GAME_OVER / VICTORY: counts up the end-screen hold that gates the restart
          key for END_SCREEN_HOLD seconds, preventing accidental instant skips.
        No-ops in all other phases so it is safe to call unconditionally each frame.
        """
        if dt < 0.0:
            raise ValueError(f"dt must be non-negative, got {dt}")
        if self._phase == GamePhase.STAGE_INTRO:
            self._intro_elapsed = min(self._intro_elapsed + dt, STAGE_INTRO_DURATION)
            assert 0.0 <= self._intro_elapsed <= STAGE_INTRO_DURATION, (
                "intro_elapsed out of [0, STAGE_INTRO_DURATION] bounds"
            )
            if self._intro_elapsed >= STAGE_INTRO_DURATION:
                self._begin_wave(player)
        elif self._phase == GamePhase.WAVE_RISING:
            self._wave_rising_timer = max(0.0, self._wave_rising_timer - dt)
            assert self._wave_rising_timer >= 0.0, "wave rising timer went negative"
            if self._wave_rising_timer == 0.0:
                if self._post_rising_reload:
                    self._post_rising_reload = False
                    self._reload_remaining_waves(player)
                else:
                    self._begin_wave(player)
        elif self._phase in (
            GamePhase.GAME_OVER, GamePhase.VICTORY, GamePhase.STAGE_CLEAR,
        ):
            self._end_hold_elapsed = min(self._end_hold_elapsed + dt, END_SCREEN_HOLD)
            assert 0.0 <= self._end_hold_elapsed <= END_SCREEN_HOLD, (
                "end-screen hold elapsed out of [0, END_SCREEN_HOLD] bounds"
            )

    # --- Per-frame crush check -----------------------------------------------

    def check_mid_tumble_crush(self, player: Player, wave: WaveManager) -> None:
        """Crush the player when an approaching cube passes its balance point.

        Called every frame from main.py. The crush fires at
        CRUSH_TUMBLE_THRESHOLD (half of TUMBLE_REST_FRACTION), which is before
        the capture window opens at TUMBLE_REST_FRACTION. This makes it
        impossible to escape a crush by capturing the incoming cube.
        """
        if self._phase != GamePhase.WAVE_ACTIVE:
            return
        if wave.tick_progress < CRUSH_TUMBLE_THRESHOLD:
            return
        if wave.cube_at(player.grid_x, player.grid_z + 1) is not None:
            self._trigger_avalanche(player, wave)

    # --- Tick hook (post-tick, called from main loop when tick fires) ---------

    def on_tick(self, player: Player, wave: WaveManager) -> None:
        """React to a committed tick: phase-dependent handling.

        WAVE_ACTIVE: if a cube reached the player's tile, trigger avalanche;
        otherwise count missed NORMAL/ADVANTAGE cubes and trigger row deletions
        when the penalty threshold is crossed. Check GAME_OVER after each deletion.
        AVALANCHE: count missed cubes; transition to WAVE_CLEARING (applying
        accumulated avalanche penalties as row deletions) when the wave empties.
        """
        if self._phase == GamePhase.WAVE_ACTIVE:
            if wave.cube_at(player.grid_x, player.grid_z) is not None:
                self._trigger_avalanche(player, wave)
            else:
                self._count_wave_misses(player, wave)
                # When all active cubes are gone advance to the next wave.
                # `_count_wave_misses` may set GAME_OVER; guard before calling
                # _on_wave_cleared. pending cubes from future waves are ignored.
                if self._phase != GamePhase.GAME_OVER and wave.active_cube_count == 0:  # type: ignore[comparison-overlap]  # _count_wave_misses may mutate _phase to GAME_OVER
                    self._on_wave_cleared(player)
        elif self._phase == GamePhase.AVALANCHE:
            self._count_avalanche_misses(wave)
            if wave.active_cube_count == 0:
                self._apply_avalanche_penalties(player)
                if self._phase != GamePhase.GAME_OVER:  # type: ignore[comparison-overlap]  # _apply_avalanche_penalties may mutate _phase to GAME_OVER
                    self._on_wave_cleared(player)

    # --- Mark lifecycle ------------------------------------------------------

    def try_mark(self, grid_x: int, grid_z: int) -> bool:
        """Place/replace a mark on `(grid_x, grid_z)` if it's walkable.

        No-ops silently when not in WAVE_ACTIVE (marks during avalanche are
        meaningless and confusing).
        """
        if self._phase != GamePhase.WAVE_ACTIVE:
            return False
        if not self._grid.is_valid_position(grid_x, grid_z):
            return False
        current = self._grid.get_tile(grid_x, grid_z)
        if current == TileState.ADVANTAGE_TRAP:
            return False
        self._grid.mark_tile(grid_x, grid_z)
        self._player_steps += 1  # successful mark placement = one input action
        return True

    # --- Trigger + capture dispatch ------------------------------------------

    def on_trigger(self, player: Player) -> str:
        """Resolve the active mark. Returns a `TriggerOutcome` tag.

        Blocked during AVALANCHE — mark was already cleared on crush.
        `player` is required so the FORBIDDEN capture path can call
        `_check_game_over` after the row deletion it triggers.
        """
        if self._phase != GamePhase.WAVE_ACTIVE:
            return TriggerOutcome.BLOCKED
        mark = self._grid.marked_position
        if mark is None:
            return TriggerOutcome.NO_MARK
        self._player_steps += 1  # trigger with an active mark = one input action
        mx, mz = mark
        # capturable_at checks visual position during rest phase only;
        # returns None during mid-tumble so the player can't capture a
        # cube that hasn't visually landed on the marked tile yet.
        cube = self._wave.capturable_at(mx, mz)
        if cube is None:
            self._grid.clear_mark()
            return TriggerOutcome.MISS
        self._grid.clear_mark()
        # spawn_flash is called inside _dispatch_capture for success paths (SCORE,
        # CREATE_TRAP). The ROW_DELETE (FORBIDDEN) path deliberately emits no flash —
        # a white success ring on a penalty capture would mislead the player.
        return self._dispatch_capture(cube, mx, mz, player)

    # --- Detonate ------------------------------------------------------------

    def on_detonate(self, player: Player) -> None:
        """Detonate all ADVANTAGE_TRAP tiles; each fires a 3×3 blast.

        All traps are cleared to PLATFORM before any blast resolves so that
        cubes found in the blast area are not confused with the trap tiles.
        New traps created during blasting (from ADVANTAGE cubes hit) are NOT
        detonated in the same Z press — the player must press Z again.
        Blocked in all phases other than WAVE_ACTIVE.
        """
        if self._phase != GamePhase.WAVE_ACTIVE:
            return
        trap_positions: list[tuple[int, int]] = []
        for z in range(self._grid.depth):
            for x in range(self._grid.width):
                if self._grid.get_tile(x, z) == TileState.ADVANTAGE_TRAP:
                    trap_positions.append((x, z))
                    self._grid.set_tile(x, z, TileState.PLATFORM)
        if not trap_positions:
            return
        self._player_steps += 1  # detonate with active traps = one input action
        max_traps = self._grid.width * self._grid.depth
        assert len(trap_positions) <= max_traps, "more traps collected than grid tiles"
        for cx, cz in trap_positions:
            self._execute_blast(cx, cz, player)
            if self._phase == GamePhase.GAME_OVER:  # type: ignore[comparison-overlap]  # _execute_blast may mutate _phase to GAME_OVER
                return

    # --- Turbo -------------------------------------------------------------------

    def set_turbo(self, enabled: bool) -> None:
        """Enable or disable the turbo wave-tick speed.

        Only takes effect during WAVE_ACTIVE.  During AVALANCHE the tick
        interval is already at AVALANCHE_TICK_INTERVAL (0.15 s) — speeding it
        up further would be nonsensical.  During all other phases there is no
        active wave to accelerate.

        The WaveManager.tick_interval setter resets _tick_elapsed when the new
        interval is shorter than the elapsed time, preventing overshoot.
        """
        if self._phase != GamePhase.WAVE_ACTIVE:
            return
        self._wave.tick_interval = TURBO_TICK_INTERVAL if enabled else self._cur_tick_interval

    # --- Pause menu ----------------------------------------------------------

    # Phases from which the pause menu may NOT be opened.
    _MENU_BLOCKED: frozenset[GamePhase] = frozenset({
        GamePhase.TITLE, GamePhase.GAME_OVER, GamePhase.VICTORY,
        GamePhase.STAGE_CLEAR, GamePhase.MENU,
    })

    def on_menu_open(self) -> None:
        """Open the pause menu, freezing all gameplay.

        No-op when already in a non-pauseable phase (TITLE, end-screens, MENU).
        Clears any active turbo so the wave doesn't resume at accelerated speed
        when the menu closes; the player must re-press the turbo key after resuming.
        """
        if self._phase in GameManager._MENU_BLOCKED:
            return
        if self._phase == GamePhase.WAVE_ACTIVE:
            self._wave.tick_interval = self._cur_tick_interval  # clear any active turbo
        self._pre_menu_phase = self._phase
        self._phase = GamePhase.MENU

    def on_menu_close(self) -> None:
        """Close the pause menu, restoring the phase that was active when it opened."""
        if self._phase != GamePhase.MENU:
            return
        self._phase = self._pre_menu_phase

    def on_menu_select(self, item: int, player: Player) -> None:
        """Execute the selected menu item.  0 = Resume, 1 = Restart.

        No-op when not in MENU phase so stray calls are harmless.
        Restart performs a full game reset identical to on_restart_key.
        """
        if self._phase != GamePhase.MENU:
            return
        if item == 0:
            self.on_menu_close()
        elif item == 1:
            assert len(STAGES) > 0, "STAGES must not be empty"
            self._do_restart(player)
        else:
            raise ValueError(f"unknown menu item index {item} — expected 0 or 1")

    # --- Phase transitions (player-initiated) ---------------------------------

    def on_title_advance(self) -> None:
        """Advance from TITLE to STAGE_INTRO, starting the rolling-wave animation.

        Called from main.py on any KEYDOWN while in TITLE. No-op if not in
        TITLE so stray key-events during other phases are harmless.
        STAGE_INTRO replaces the initial WAVE_RISING pause: the animation acts
        as the "get ready" cue, ending by calling _begin_wave automatically.
        """
        if self._phase != GamePhase.TITLE:
            return
        assert self._wave_index == 0, (
            f"expected wave_index 0 on title advance, got {self._wave_index}"
        )
        self._intro_elapsed = 0.0
        self._phase = GamePhase.STAGE_INTRO

    # --- Private helpers -----------------------------------------------------

    def _trigger_avalanche(self, player: Player, wave: WaveManager) -> None:
        """Transition to AVALANCHE: squash the player, accelerate the wave."""
        self._phase = GamePhase.AVALANCHE
        self._had_avalanche = True  # disqualifies Perfect for this wave
        self._wave_crushed = True   # gate: this wave must be replayed before advancing
        player.crush()
        wave.tick_interval = self._cur_avalanche_tick_interval
        self._grid.clear_mark()
        self._effects.trigger_shake(amplitude=10.0, duration=0.6)

    def _count_avalanche_misses(self, wave: WaveManager) -> None:
        """Accumulate missed NORMAL/ADVANTAGE cubes that fell off during avalanche."""
        for cube in wave.last_dropped:
            behavior = CUBE_TYPES[cube.cube_type]["on_missed"]
            if behavior == CubeBehavior.PENALTY:
                self._avalanche_penalty += 1
            else:
                # Closed-set guard: any new on_missed behavior added to CUBE_TYPES
                # must be explicitly handled here or marked NONE. Silently skipping
                # an unrecognised value would mask a wiring error.
                assert behavior == CubeBehavior.NONE, (
                    f"unhandled on_missed behavior {behavior!r} for "
                    f"{cube.cube_type.name} — add a dispatch branch"
                )
        assert self._avalanche_penalty >= 0, "avalanche penalty count went negative"

    def _count_wave_misses(self, player: Player, wave: WaveManager) -> None:
        """Increment wave penalty for each missed cube; delete rows at threshold."""
        for cube in wave.last_dropped:
            behavior = CUBE_TYPES[cube.cube_type]["on_missed"]
            if behavior == CubeBehavior.PENALTY:
                self._wave_penalty += 1
                self._wave_total_misses += 1  # cumulative count for Perfect detection
                if self._wave_penalty >= PENALTY_THRESHOLD:
                    self._wave_penalty -= PENALTY_THRESHOLD
                    _ = self._grid.delete_front_row()  # unused: _check_game_over covers outcome
                    if self._audio is not None:
                        self._audio.play_row_delete()
                    self._check_game_over(player)
                    if self._phase == GamePhase.GAME_OVER:
                        return
            else:
                # Closed-set guard: any new on_missed behavior added to CUBE_TYPES
                # must be explicitly handled here or marked NONE. Silently skipping
                # an unrecognised value would mask a wiring error.
                assert behavior == CubeBehavior.NONE, (
                    f"unhandled on_missed behavior {behavior!r} for "
                    f"{cube.cube_type.name} — add a dispatch branch"
                )
        assert self._wave_penalty >= 0, "wave penalty count went negative"

    def _apply_avalanche_penalties(self, player: Player) -> None:
        """Convert accumulated avalanche misses into row deletions."""
        deletions = self._avalanche_penalty // PENALTY_THRESHOLD
        for _ in range(deletions):
            self._avalanche_penalty -= PENALTY_THRESHOLD
            _ = self._grid.delete_front_row()  # unused bool: _check_game_over covers outcome
            if self._audio is not None:
                self._audio.play_row_delete()
            self._check_game_over(player)
            if self._phase == GamePhase.GAME_OVER:
                return
        assert self._avalanche_penalty >= 0, "avalanche penalty went negative after apply"

    def _check_game_over(self, player: Player) -> None:
        """Transition to GAME_OVER when the player's tile has been voided."""
        if not self._grid.is_valid_position(player.grid_x, player.grid_z):
            self._end_hold_elapsed = 0.0  # fresh countdown on end-screen entry
            self._phase = GamePhase.GAME_OVER
            if self._audio is not None:
                self._audio.play_game_over()

    def _execute_blast(self, cx: int, cz: int, player: Player) -> None:
        """Execute one blast at visual tile `(cx, cz)`.

        Trap tiles are stored at *visual* positions (where cubes land on-screen).
        A cube visually on tile `(cx, cz)` has logical `grid_z == cz + 1` (the
        same offset `capturable_at` uses).  We therefore query `cube_at(cx,
        cz + 1)` so the blast hits exactly the cube sitting on the green tile,
        not the cube one row in front of it.

        SCORE → chain points + remove. DETONATE_3X3 → chain points + remove +
        mark 3×3 as new ADVANTAGE_TRAP (armed, detonated on next Z press).
        ROW_DELETE → remove + delete_front_row + _check_game_over.
        No-op when no cube occupies this tile.
        """
        if not self._grid.in_bounds(cx, cz):
            raise ValueError(f"blast origin ({cx}, {cz}) is out of bounds")
        # cz + 1: logical position of the cube visually resting on tile cz.
        # Mirrors capturable_at's cube.grid_z == grid_z + 1 convention.
        cube = self._wave.cube_at(cx, cz + 1)
        if cube is None:
            return
        info = CUBE_TYPES[cube.cube_type]
        behavior = info["on_detonate"]
        if behavior == CubeBehavior.SCORE:
            self._score += info["chain_score"]
            self._wave.remove_cube(cube)
            self._effects.spawn_flash(cx, cz, cube.cube_type)
            if self._audio is not None:
                self._audio.play_detonation()
        elif behavior == CubeBehavior.DETONATE_3X3:
            self._score += info["chain_score"]
            self._wave.remove_cube(cube)
            self._effects.spawn_flash(cx, cz, cube.cube_type)
            self._mark_trap_area(cx, cz)  # armed; player presses Z to detonate
            if self._audio is not None:
                self._audio.play_detonation()
        elif behavior == CubeBehavior.ROW_DELETE:
            self._wave.remove_cube(cube)
            _ = self._grid.delete_front_row()  # unused: _check_game_over covers it
            if self._audio is not None:
                self._audio.play_forbidden_buzz()  # penalty: Forbidden cube in blast
                self._audio.play_row_delete()       # consequence: row erased
            self._check_game_over(player)
            self._forbidden_captured = True  # disqualifies Perfect for this wave
        else:
            raise ValueError(
                f"unhandled on_detonate behavior {behavior!r} "
                f"for {cube.cube_type.name}"
            )

    def _mark_trap_area(self, cx: int, cz: int) -> None:
        """Set every non-void tile in the 3×3 area around `(cx, cz)` to ADVANTAGE_TRAP.

        Used in two places:
        - `_dispatch_capture` CREATE_TRAP: player captures an ADVANTAGE cube.
        - `_execute_blast` DETONATE_3X3: a blast hits an ADVANTAGE cube in the wave.
        Raises ValueError if the origin `(cx, cz)` is out of bounds.
        Neighbor positions outside the grid are silently clipped (not an error).
        """
        if not self._grid.in_bounds(cx, cz):
            raise ValueError(f"trap origin ({cx}, {cz}) is out of bounds")
        for tz in range(cz - 1, cz + 2):
            for tx in range(cx - 1, cx + 2):
                if not self._grid.in_bounds(tx, tz):
                    continue
                if self._grid.get_tile(tx, tz) == TileState.VOID:
                    continue
                self._grid.set_tile(tx, tz, TileState.ADVANTAGE_TRAP)

    def _dispatch_capture(self, cube: Cube, mx: int, mz: int, player: Player) -> str:
        """Consume `cube` and apply its registry-defined `on_capture` hook.

        Every cube type's hook is mapped to exactly one branch below. Adding
        a new `CubeBehavior` value requires adding a branch here *and* a
        handler path; the trailing `else` makes that contract explicit by
        raising rather than silently dropping the capture.
        """
        # During rest phase, cube.grid_z == mz + 1 (logical tile is one
        # behind the visual tile the player marked).
        assert cube.grid_x == mx and cube.grid_z == mz + 1, (
            f"cube ({cube.grid_x}, {cube.grid_z}) visual tile does not match "
            f"mark ({mx}, {mz}) — expected cube.grid_z == {mz + 1}"
        )
        info = CUBE_TYPES[cube.cube_type]
        behavior = info["on_capture"]
        if behavior == CubeBehavior.SCORE:
            self._score += info["capture_score"]
            self._wave.remove_cube(cube)
            self._effects.spawn_flash(mx, mz, cube.cube_type)  # tint matches cube
            if self._audio is not None:
                self._audio.play_capture()
            return TriggerOutcome.CAPTURED_SCORE
        if behavior == CubeBehavior.CREATE_TRAP:
            self._wave.remove_cube(cube)
            self._mark_trap_area(mx, mz)  # marks the full 3×3 around the capture tile
            self._effects.spawn_flash(mx, mz, cube.cube_type)  # tint matches cube
            if self._audio is not None:
                self._audio.play_capture()
            return TriggerOutcome.CAPTURED_TRAP
        if behavior == CubeBehavior.ROW_DELETE:
            self._wave.remove_cube(cube)
            _ = self._grid.delete_front_row()  # unused: _check_game_over covers outcome
            if self._audio is not None:
                self._audio.play_forbidden_buzz()
            self._check_game_over(player)
            self._forbidden_captured = True  # disqualifies Perfect for this wave
            # No flash: a FORBIDDEN capture is a mistake. A success ring would
            # mislead the player into thinking they scored.
            return TriggerOutcome.CAPTURED_FORBIDDEN
        raise ValueError(
            f"unhandled on_capture behavior {behavior!r} for cube type "
            f"{CubeType(cube.cube_type).name} — add a dispatch branch"
        )

    # --- Wave progression (Step 9A / Step 28) --------------------------------

    def start_first_wave(
        self, player: Player, waves: tuple[WaveData, ...]
    ) -> None:
        """Initialize the wave sequence, spawn all waves as pending, enter TITLE.

        All stage waves are placed immediately as static pending (grey) cubes
        so they are visible on the title screen.  The actual wave advance is
        deferred until the player presses a key (on_title_advance → WAVE_RISING
        → update → _begin_wave).  Raises `ValueError` if `waves` is empty.
        """
        if not waves:
            raise ValueError("waves sequence must not be empty")
        assert len(waves) > 0, "waves invariant double-check after ValueError guard"
        self._waves = waves
        self._wave_index = 0
        self._phase = GamePhase.TITLE
        self._spawn_all_waves_pending(player)
        # Position player PLAYER_INITIAL_WAVE_GAP tiles below wave-0 front so
        # the opening gap is always exactly 6 clear rows regardless of PLAYER_SPAWN_Z.
        # Subsequent wave and stage transitions use the normal persistence logic;
        # this only fires when the wave sequence is (re)initialised from scratch.
        player.position_near_wave(self.wave_front_z, PLAYER_INITIAL_WAVE_GAP)

    def start_game(
        self,
        player: Player,
        all_stage_waves: tuple[tuple[WaveData, ...], ...],
    ) -> None:
        """Store the full run's wave selection and enter the title screen.

        Called from main.py at startup and from _do_restart on each replay.
        Stores `all_stage_waves` (produced by select_all_waves) so every stage
        transition reads chosen pool variants from self._all_stage_waves instead
        of the static STAGES table.  Delegates to start_first_wave for Stage-1
        wave initialisation and TITLE entry.

        Raises ValueError if all_stage_waves is empty or Stage 1 has no waves.
        """
        if not all_stage_waves:
            raise ValueError("all_stage_waves must not be empty")
        if not all_stage_waves[0]:
            raise ValueError("Stage 1 wave sequence must not be empty")
        assert len(all_stage_waves) > 0, "all_stage_waves invariant double-check"
        self._all_stage_waves = all_stage_waves
        self.start_first_wave(player, all_stage_waves[0])

    def on_restart_key(self, player: Player) -> None:
        """Reset all game state and return to TITLE on any key during GAME_OVER/VICTORY.

        No-op in every other phase so stray keypresses are harmless. Also no-op
        during the initial END_SCREEN_HOLD seconds to prevent accidental restarts
        triggered by a key held at the moment the end screen appears.
        """
        if self._phase not in (GamePhase.GAME_OVER, GamePhase.VICTORY):
            return
        if self._end_hold_elapsed < END_SCREEN_HOLD:
            return  # hold not yet elapsed; ignore this keypress
        assert len(STAGES) > 0, "STAGES must not be empty"
        self._do_restart(player)

    def on_stage_clear_key(self, player: Player) -> None:
        """Advance to the next stage on any key during STAGE_CLEAR.

        No-op until the end-screen hold has elapsed, preventing accidental
        skips when the last wave clears mid-keypress. Calls _on_stage_complete
        which resets subsystems and enters WAVE_RISING for the new stage.
        """
        if self._phase != GamePhase.STAGE_CLEAR:
            return
        if self._end_hold_elapsed < END_SCREEN_HOLD:
            return
        self._on_stage_complete(player)

    def _on_stage_complete(self, player: Player) -> None:
        """Transition into the next stage: reset subsystems, enter STAGE_INTRO.

        Increments _stage_index, resets the grid/wave/effects/player for a
        fresh board, clears all per-wave tracking fields, and sets up the new
        stage's wave sequence. Score carries over (not reset) so the cumulative
        total is visible in the VICTORY screen at the end of the final stage.
        STAGE_INTRO replaces the initial WAVE_RISING pause; the rolling-wave
        animation ends by automatically calling _begin_wave for wave 0.
        """
        if self._audio is not None:
            self._audio.play_wave_clear()   # brief fanfare as the new stage begins
        self._stage_index += 1
        # Use the run-wide pool selection if available; fall back to the static
        # STAGES table for callers that bypass start_game (legacy / test paths).
        stage_table = self._all_stage_waves if self._all_stage_waves else STAGES
        assert self._stage_index < len(stage_table), (
            f"stage_index {self._stage_index} out of range [0, {len(stage_table)})"
        )
        # Step 33: grid tile state (row deletions) and player X persist across
        # stage boundaries. Resize the grid to match the new stage's wave-pattern
        # width while preserving void rows (set_active_width, not resize/reset).
        self._grid.set_active_width(STAGE_GRID_WIDTHS[self._stage_index])
        self._wave.reset_for_new_wave()
        self._wave.tick_interval = self._cur_tick_interval  # arm new stage's speed
        self._effects.reset()
        player.uncrush()
        # Reset per-wave and per-stage tracking; score is cumulative.
        self._wave_index = 0
        self._wave_penalty = 0
        self._avalanche_penalty = 0
        self._wave_crushed = False        # no retry gate pending at stage start
        self._retry_pending = False      # no AGAIN! banner pending at stage start
        self._post_rising_reload = False  # no deferred reload pending at stage start
        self._clean_clears = 0           # fresh stage: no clean clears accumulated
        self._forbidden_captured = False
        self._had_avalanche = False
        self._player_steps = 0
        self._wave_total_misses = 0
        self._perfect_display = False
        self._end_hold_elapsed = 0.0
        # Arm the new stage's wave list, spawn all waves as pending, start intro.
        self._waves = stage_table[self._stage_index]
        self._spawn_all_waves_pending(player)
        # Safety clamp (Step 33 BLOCKER fix): if the player advanced deep into
        # Stage N's wave stack they could persist inside Stage N+1's wave 0.
        # Clamp Z to just below the new wave front; X is preserved.
        player.clamp_z_before_wave(self.wave_front_z)
        self._intro_elapsed = 0.0
        self._phase = GamePhase.STAGE_INTRO

    def _do_restart(self, player: Player) -> None:
        """Full reset sequence shared by on_restart_key and on_menu_select (Restart).

        Draws a fresh pool selection via select_all_waves so each run sees a
        different mix of A/B wave variants. Always restarts from Stage 1.
        Resets grid, wave, effects, and player in dependency order (grid first
        so player.reset() finds a valid spawn tile), then zeroes the manager's
        own fields, then enters TITLE via start_game.

        The wave.reset_for_new_wave() call here clears stale cubes immediately
        so none are rendered during the TITLE / WAVE_RISING screens.
        """
        assert len(STAGES) > 0, "STAGES must not be empty"
        self._grid.resize(STAGE_GRID_WIDTHS[0])   # full reset to Stage-1 width
        # grid.resize() must precede player.reset() so the spawn tile is valid.
        self._wave.reset_for_new_wave()  # clear stale cubes before TITLE renders
        self._effects.reset()            # clear flashes and shake
        player.reset()                   # teleport back to spawn
        self._reset_state()              # resets _stage_index to 0
        rng = random.Random(random.randrange(2**32))
        all_stage_waves = select_all_waves(rng)
        self.start_game(player, all_stage_waves)

    def _reset_state(self) -> None:
        """Zero every per-game field back to the same values as __init__.

        Called from _do_restart (end-screen and in-menu paths). Does NOT reset
        grid, wave, player, or effects — the caller handles those in order.
        """
        self._score = 0
        self._iq_score = 0
        self._phase = GamePhase.WAVE_ACTIVE   # overwritten by start_first_wave
        self._wave_penalty = 0
        self._avalanche_penalty = 0
        self._waves = ()
        self._wave_index = 0
        self._stage_index = 0
        self._all_stage_waves = ()     # cleared; start_game repopulates on restart
        self._wave_crushed = False     # cleared; no retry gate pending on fresh start
        self._retry_pending = False    # cleared; no retry pause active on fresh start
        self._post_rising_reload = False  # cleared; no deferred reload pending on fresh start
        self._clean_clears = 0        # cleared; no clean clears counted yet
        self._wave_z_starts = []
        self._wave_mirrors = []
        self._forbidden_captured = False
        self._had_avalanche = False
        self._player_steps = 0
        self._wave_total_misses = 0
        self._wave_rising_timer = 0.0
        self._perfect_display = False
        self._intro_elapsed = 0.0
        self._pre_menu_phase = GamePhase.WAVE_ACTIVE
        self._end_hold_elapsed = 0.0
        assert self._score == 0, "score not zeroed after _reset_state"
        assert self._wave_index == 0, "wave_index not zeroed after _reset_state"
        assert self._stage_index == 0, "stage_index not zeroed after _reset_state"

    def _compute_wave_z_starts(self) -> list[int]:
        """Return z_back for each wave — the z of each wave's back-most row.

        Waves are packed *backward* from z=GRID_DEPTH-1 so the entire stack
        sits against the far wall of the play area (Step 33).  Wave 0 is the
        first to activate (closest to the player); wave n-1 is furthest back.

          z_back[n-1] = GRID_DEPTH − 1
          z_front[i]  = z_back[i] − _waves[i].row_count + 1
          z_back[i-1] = z_front[i] − WAVE_GAP_ROWS − 1

        Example (Stage 1, 2-row waves, GRID_DEPTH=60, WAVE_GAP_ROWS=0):
          z_back[3] = 59  →  z_front[3] = 58
          z_back[2] = 57  →  z_front[2] = 56
          z_back[1] = 55  →  z_front[1] = 54
          z_back[0] = 53  →  z_front[0] = 52  (31 clear tiles ahead of player)

        Example (Stage 10, 7-row waves, GRID_DEPTH=60, WAVE_GAP_ROWS=0):
          z_back[3] = 59  →  z_front[3] = 53
          z_back[2] = 52  →  z_front[2] = 46
          z_back[1] = 45  →  z_front[1] = 39
          z_back[0] = 38  →  z_front[0] = 32  (11 clear tiles ahead of player)
        """
        if not self._waves:
            raise ValueError("_compute_wave_z_starts called with empty waves")
        n = len(self._waves)
        z_starts: list[int] = [0] * n
        z_back = GRID_DEPTH - 1
        # Fill z_starts from the back (wave n-1) to the front (wave 0).
        for i in range(n - 1, -1, -1):
            z_front = z_back - self._waves[i].row_count + 1
            if z_front < 0:
                raise ValueError(
                    f"wave {i} front row z={z_front} < 0 — increase GRID_DEPTH "
                    f"or reduce wave count / row count"
                )
            z_starts[i] = z_back
            z_back = z_front - WAVE_GAP_ROWS - 1
        assert len(z_starts) == len(self._waves), (
            "z_starts length must equal wave count"
        )
        return z_starts

    def _spawn_all_waves_pending(self, player: Player) -> None:
        """Spawn every wave in the current stage as static pending cubes.

        Called at stage start (from start_first_wave and _on_stage_complete)
        so all wave patterns are visible on-screen immediately.  Each cube is
        pending=True: it does not advance until _activate_wave flips it.

        The wave manager must have been reset (reset_for_new_wave) by the
        caller before this method runs so there are no stale cubes.
        """
        assert len(self._waves) > 0, "_spawn_all_waves_pending called with empty waves"
        assert self._wave.cube_count == 0, (
            "_spawn_all_waves_pending called with cubes still present (active or "
            "pending) — call wave.reset_for_new_wave() first"
        )
        self._wave_z_starts = self._compute_wave_z_starts()
        assert len(self._wave_z_starts) == len(self._waves), (
            "z_starts length mismatch after _compute_wave_z_starts"
        )
        self._wave_mirrors = []
        for wave_idx, wave_data in enumerate(self._waves):
            z_start = self._wave_z_starts[wave_idx]
            # Roll mirror once per wave and store it so crush-retry can
            # reproduce the exact same cube layout without re-randomising.
            mirror = random.random() < 0.5
            assert len(self._wave_mirrors) < len(self._waves), (
                "wave_mirrors growth exceeded wave count — loop invariant broken"
            )
            self._wave_mirrors.append(mirror)
            positions = wave_data.spawn_positions(mirror=mirror, z_start=z_start)
            for gx, gz, cube_type in positions:
                self._wave.spawn_cube(gx, gz, cube_type, pending=True)
        assert len(self._wave_mirrors) == len(self._waves), (
            "wave_mirrors length mismatch after _spawn_all_waves_pending"
        )
        assert self._wave.cube_count > 0, (
            "no cubes placed by _spawn_all_waves_pending — wave list may be empty"
        )

    def _activate_wave(self, wave_idx: int) -> None:
        """Flip the pending flag off for all cubes belonging to wave_idx.

        Uses the z range stored in _wave_z_starts to identify which cubes to
        activate.  After this call those cubes will advance on the next tick.
        """
        if not (0 <= wave_idx < len(self._wave_z_starts)):
            raise ValueError(
                f"wave_idx {wave_idx} out of range [0, {len(self._wave_z_starts)})"
            )
        z_back = self._wave_z_starts[wave_idx]
        row_count = self._waves[wave_idx].row_count
        z_front = z_back - row_count + 1
        self._wave.activate_pending(z_front, z_back)

    def _begin_wave(self, player: Player) -> None:
        """Begin the current wave from pre-placed pending cubes.

        Unlike the old _spawn_wave, this method does NOT create new cubes.
        All cubes were already spawned as pending by _spawn_all_waves_pending.
        This method only:
          1. Resets per-wave tracking fields.
          2. Sets the stage-correct tick interval.
          3. Clears the grid mark and uncrushes the player.
          4. Activates this wave's pending cubes via _activate_wave.
          5. Transitions to WAVE_ACTIVE.
        """
        assert len(self._waves) > 0, "_begin_wave called before waves were set"
        assert 0 <= self._wave_index < len(self._waves), (
            f"wave_index {self._wave_index} out of range [0, {len(self._waves)})"
        )
        # Reset per-wave counters and flags.
        self._forbidden_captured = False
        self._had_avalanche = False
        self._player_steps = 0
        self._wave_total_misses = 0
        self._wave_penalty = 0
        self._avalanche_penalty = 0
        self._perfect_display = False
        self._retry_pending = False  # WAVE_RISING retry pause is over; wave is live
        # Restore player and set stage-correct tick speed.
        player.uncrush()
        self._wave.tick_interval = self._cur_tick_interval
        self._grid.clear_mark()
        # Activate this wave's pre-placed cubes.
        self._activate_wave(self._wave_index)
        assert self._wave.active_cube_count > 0, (
            f"wave {self._wave_index} has no active cubes after activation — "
            "_spawn_all_waves_pending may not have placed cubes for this wave"
        )
        self._phase = GamePhase.WAVE_ACTIVE

    def _on_wave_cleared(self, player: Player) -> None:
        """Gate stage completion on clean-clear count; handle crush with Again flag.

        Called when wave.active_cube_count reaches 0.

        Crushed path (_wave_crushed is True):
          _retry_pending is set (drives "AGAIN!" banner and [AGAIN] HUD tag).
          If pending waves remain beyond the current slot, the BACK-MOST
          pending wave is consumed as a retry life: its cubes are removed from
          the grid, _waves and _wave_z_starts shrink, and the current slot is
          respawned at the same z position with a fresh pool variant.  The
          visible row count decreases by one wave each crush.  If all pending
          waves are exhausted (no entry beyond _wave_index), _post_rising_reload
          triggers a full batch reload via STAGE_INTRO after the WAVE_RISING.

        Clean path (_wave_crushed is False):
          Perfect criteria checked and bonus applied. _clean_clears incremented.
          Stage ends the moment _clean_clears reaches _waves_per_stage (= 4).
          Otherwise _wave_index advances. If the batch is exhausted (no more
          pending waves), _post_rising_reload triggers a reload via STAGE_INTRO.
        """
        assert len(self._waves) > 0, "_on_wave_cleared called before waves were set"
        player.uncrush()
        self._grid.clear_mark()
        if self._wave_crushed:
            self._wave_crushed = False
            self._retry_pending = True   # drives "AGAIN!" banner / [AGAIN] HUD tag
            self._perfect_display = False
            if self._wave_index + 1 < len(self._waves):
                # Lives remain: consume the back-most pending wave as a retry
                # token, then respawn the current slot at the same z position.
                self._consume_last_pending_life()
                self._respawn_current_slot()
            else:
                # All pending waves exhausted; full reload after WAVE_RISING.
                self._post_rising_reload = True
            self._wave_rising_timer = WAVE_RISING_DURATION
            self._phase = GamePhase.WAVE_RISING
            return
        # Clean clear: apply Perfect bonus and count it.
        if self._audio is not None:
            self._audio.play_wave_clear()
        wave_data = self._waves[self._wave_index]
        is_perfect = (
            not self._had_avalanche
            and not self._forbidden_captured
            and self._wave_total_misses == 0
        )
        if is_perfect:
            bonus = self._calc_perfect_bonus(self._player_steps, wave_data.ideal_steps)
            self._score += bonus
            _ = self._grid.restore_front_row()
        self._perfect_display = is_perfect
        self._clean_clears += 1
        if self._clean_clears >= self._waves_per_stage:
            # All clean clears earned — stage complete.
            self._end_hold_elapsed = 0.0
            total_stages = (
                len(self._all_stage_waves) if self._all_stage_waves else len(STAGES)
            )
            if self._stage_index >= total_stages - 1:
                self._iq_score = self._calculate_final_iq()
                self._phase = GamePhase.VICTORY
            else:
                self._phase = GamePhase.STAGE_CLEAR
            return
        # Advance to the next slot; if the batch is exhausted, full reload after WAVE_RISING.
        self._wave_index += 1
        if self._wave_index >= len(self._waves):
            # Keep wave_index valid so wave_code shows last slot's code during WAVE_RISING.
            self._wave_index = len(self._waves) - 1
            self._post_rising_reload = True
        self._wave_rising_timer = WAVE_RISING_DURATION
        self._phase = GamePhase.WAVE_RISING

    def _consume_last_pending_life(self) -> None:
        """Remove the back-most pending wave, consuming one crush-retry life.

        Called from the crush path of _on_wave_cleared when pending waves
        remain beyond the current active slot.  Takes the LAST entry in
        _waves (the pre-placed wave furthest from the player) and discards
        its pending cubes via remove_pending_in_range, then shrinks _waves
        and _wave_z_starts by one entry.  The visible row count on screen
        decreases by one wave each call, giving the player a clear signal
        that a life has been spent.
        """
        last_idx = len(self._waves) - 1
        assert last_idx > self._wave_index, (
            f"last_idx {last_idx} <= wave_index {self._wave_index} — "
            "cannot consume the current active slot as a life"
        )
        assert last_idx < len(self._wave_z_starts), (
            f"last_idx {last_idx} out of range for _wave_z_starts"
        )
        z_back = self._wave_z_starts[last_idx]
        row_count = self._waves[last_idx].row_count
        z_front = z_back - row_count + 1
        removed = self._wave.remove_pending_in_range(z_front, z_back)
        assert removed >= 0, "remove_pending_in_range returned a negative count"
        waves_list = list(self._waves)
        _ = waves_list.pop(last_idx)   # consumed; return value unused
        self._waves = tuple(waves_list)
        _ = self._wave_z_starts.pop(last_idx)  # consumed; return value unused
        _ = self._wave_mirrors.pop(last_idx)   # keep parallel with _waves
        assert len(self._waves) == len(self._wave_z_starts), (
            "waves / z_starts length mismatch after consuming a pending life"
        )
        assert len(self._waves) == len(self._wave_mirrors), (
            "waves / mirrors length mismatch after consuming a pending life"
        )

    def _respawn_current_slot(self) -> None:
        """Replay the current wave slot using the EXACT same WaveData and mirror.

        Called after _consume_last_pending_life in the crush-retry path.
        Uses self._waves[_wave_index] (the same A/B variant that crushed the
        player — no re-roll) and self._wave_mirrors[_wave_index] (the same
        mirror orientation — no re-roll).  Together these guarantee an
        identical cube layout: same pattern, same positions, same z depth.
        No new randomness is introduced so the player faces exactly the wave
        that defeated them.
        """
        assert len(self._waves) > 0, "_respawn_current_slot called with no waves"
        assert 0 <= self._wave_index < len(self._waves), (
            f"wave_index {self._wave_index} out of range [0, {len(self._waves)})"
        )
        assert self._wave_index < len(self._wave_z_starts), (
            "_respawn_current_slot: _wave_z_starts not yet computed"
        )
        assert self._wave_index < len(self._wave_mirrors), (
            "_respawn_current_slot: _wave_mirrors not yet computed"
        )
        wave_data = self._waves[self._wave_index]   # same variant, no re-roll
        mirror = self._wave_mirrors[self._wave_index]  # same orientation, no re-roll
        z_start = self._wave_z_starts[self._wave_index]  # same z depth, unchanged
        positions = wave_data.spawn_positions(mirror=mirror, z_start=z_start)
        assert len(positions) > 0, (
            "_respawn_current_slot: wave_data produced no spawn positions"
        )
        for gx, gz, cube_type in positions:
            self._wave.spawn_cube(gx, gz, cube_type, pending=True)
        assert self._wave.cube_count > 0, (
            "_respawn_current_slot placed no cubes — wave data may be empty"
        )

    def _reload_remaining_waves(self, player: Player) -> None:
        """Spawn the remaining needed waves from pool and enter STAGE_INTRO.

        Called from the WAVE_RISING expiry path when _post_rising_reload is set
        (cleared by the caller before this method runs).  Determines how many
        clean clears remain (_waves_per_stage - _clean_clears) and picks fresh
        A/B pool variants for those slots only: STAGE_POOL_SLOTS[stage][clean:].

        All existing cubes are discarded via reset_for_new_wave before
        _spawn_all_waves_pending places the fresh batch, so there are no stale
        pending rows left from the exhausted wave queue.

        _retry_pending is cleared here (not in _begin_wave) so the [AGAIN] HUD
        tag and AGAIN! banner are absent during the STAGE_INTRO animation itself.
        """
        assert self._stage_index < len(STAGE_POOL_SLOTS), (
            f"stage_index {self._stage_index} out of range for STAGE_POOL_SLOTS"
        )
        slots = STAGE_POOL_SLOTS[self._stage_index]
        n_needed = self._waves_per_stage - self._clean_clears
        assert n_needed > 0, (
            f"_reload_remaining_waves called with n_needed={n_needed} — "
            "should not be called when stage is already complete"
        )
        assert self._clean_clears < len(slots), (
            f"_clean_clears {self._clean_clears} >= slot count {len(slots)}"
        )
        new_waves: list[WaveData] = []
        for slot_key in slots[self._clean_clears:]:
            pool = WAVE_POOLS[slot_key]
            assert len(pool) >= 1, f"pool '{slot_key}' is empty"
            variant_idx = random.randrange(len(pool))
            assert len(new_waves) < n_needed, "new_waves exceeded expected count"
            new_waves.append(pool[variant_idx])
        assert len(new_waves) == n_needed, (
            f"expected {n_needed} new waves, built {len(new_waves)}"
        )
        self._waves = tuple(new_waves)
        self._wave_index = 0
        self._retry_pending = False     # clear [AGAIN] tag before STAGE_INTRO
        self._perfect_display = False   # clear PERFECT! flag symmetrically with _retry_pending
        self._wave.reset_for_new_wave() # discard any stale pending cubes
        self._effects.reset()
        self._spawn_all_waves_pending(player)
        player.clamp_z_before_wave(self.wave_front_z)
        self._intro_elapsed = 0.0
        self._phase = GamePhase.STAGE_INTRO

    def _calc_perfect_bonus(self, actual: int, ideal: int) -> int:
        """Return the Perfect step-efficiency score bonus.

        Tiers from the I.Q. research document:
          * actual ≤ ideal          → PERFECT_BONUS_MAX        (10,000)
          * actual ≤ ideal + 20     → PERFECT_BONUS_MAX // 2   (5,000)
          * actual ≤ ideal + 40     → PERFECT_BONUS_MAX // 4   (2,500)
          * else                    → 0  (Perfect row restore still applies)
        """
        assert ideal > 0, f"ideal must be positive, got {ideal}"
        if actual <= ideal:
            return PERFECT_BONUS_MAX
        if actual <= ideal + 20:
            return PERFECT_BONUS_MAX // 2
        if actual <= ideal + 40:
            return PERFECT_BONUS_MAX // 4
        return 0

    def _calculate_final_iq(self) -> int:
        """Compute the Stage-1 I.Q. score: (wave score + row survival) × multipliers.

        Row survival: each non-void row contributes SCORE_ROW_SURVIVAL points.
        Stage-1 multipliers: difficulty × 1.00, i.q. percentage × 0.00060.
        Both are index-0 entries in `IQ_DIFFICULTY_MULTIPLIERS` /
        `IQ_PERCENTAGE_MULTIPLIERS` from `constants.py`.
        """
        surviving_rows = 0
        for z in range(self._grid.depth):
            row_has_tile = any(
                self._grid.get_tile(x, z) != TileState.VOID
                for x in range(self._grid.width)
            )
            if row_has_tile:
                surviving_rows += 1
        row_bonus = surviving_rows * SCORE_ROW_SURVIVAL
        total = self._score + row_bonus
        diff_idx = min(self._stage_index, len(IQ_DIFFICULTY_MULTIPLIERS) - 1)
        pct_idx = min(self._stage_index, len(IQ_PERCENTAGE_MULTIPLIERS) - 1)
        difficulty = IQ_DIFFICULTY_MULTIPLIERS[diff_idx]
        iq_pct = IQ_PERCENTAGE_MULTIPLIERS[pct_idx]
        result = int(total * difficulty * iq_pct)
        assert result >= 0, "IQ score went negative — logic error"
        return result
