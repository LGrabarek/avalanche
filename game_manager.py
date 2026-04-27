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
  * `_trigger_avalanche(player, wave)` — drops tick interval to
    AVALANCHE_TICK_INTERVAL, crushes the player, clears the mark, fires shake.

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
    immediately. Player presses any key → `on_title_advance()` → WAVE_RISING.
  * `WAVE_RISING` phase: 2-second between-wave timer. `update(dt, player)` counts
    down; when it reaches zero `_spawn_wave` fires. `perfect_display` property
    signals main.py whether to show the PERFECT! banner during this window.
  * `on_title_advance()` — TITLE → WAVE_RISING; sets the 2 s timer.
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
"""

import random

from constants import (
    AVALANCHE_TICK_INTERVAL,
    CRUSH_TUMBLE_THRESHOLD,
    CUBE_TYPES,
    IQ_DIFFICULTY_MULTIPLIERS,
    IQ_PERCENTAGE_MULTIPLIERS,
    PENALTY_THRESHOLD,
    PERFECT_BONUS_MAX,
    SCORE_ROW_SURVIVAL,
    WAVE_RISING_DURATION,
    CubeBehavior,
    CubeType,
    GamePhase,
    TileState,
)
from effects import FlashEffects
from grid_manager import GridManager
from player import Player
from wave_data import WaveData
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
    ) -> None:
        self._grid: GridManager = grid
        self._wave: WaveManager = wave
        self._effects: FlashEffects = effects
        self._score: int = 0
        self._phase: GamePhase = GamePhase.WAVE_ACTIVE
        self._wave_penalty: int = 0      # Missed NORMAL/ADVANTAGE cubes during WAVE_ACTIVE.
        self._avalanche_penalty: int = 0  # Missed NORMAL/ADVANTAGE cubes during AVALANCHE.
        # Wave progression state — populated by start_first_wave().
        self._waves: tuple[WaveData, ...] = ()
        self._wave_index: int = 0
        self._iq_score: int = 0
        # Per-wave Perfect tracking — reset by _spawn_wave() at each wave start.
        self._forbidden_captured: bool = False   # Any FORBIDDEN captured this wave?
        self._had_avalanche: bool = False         # Crush occurred this wave?
        self._player_steps: int = 0              # Successful input actions this wave.
        self._wave_total_misses: int = 0         # NORMAL/ADVANTAGE missed in WAVE_ACTIVE.
        # Between-wave display state — set by _on_wave_cleared, reset by _spawn_wave.
        self._wave_rising_timer: float = 0.0     # Countdown for WAVE_RISING phase.
        self._perfect_display: bool = False      # Show PERFECT! banner in WAVE_RISING.
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
        """0-based index of the currently active wave."""
        return self._wave_index

    @property
    def wave_count(self) -> int:
        """Total number of waves in the current stage sequence."""
        return len(self._waves)

    @property
    def iq_score(self) -> int:
        """Final I.Q. score. Populated when phase transitions to VICTORY."""
        return self._iq_score

    @property
    def perfect_display(self) -> bool:
        """True during WAVE_RISING when the just-cleared wave was Perfect."""
        return self._perfect_display

    # --- Per-frame update (timers) -------------------------------------------

    def update(self, dt: float, player: Player) -> None:
        """Advance phase timers. Must be called every frame from main.py.

        Currently handles only WAVE_RISING: counts down the between-wave pause
        and triggers `_spawn_wave` when the timer expires. No-ops in all other
        phases so it is safe to call unconditionally each frame.
        """
        if dt < 0.0:
            raise ValueError(f"dt must be non-negative, got {dt}")
        if self._phase != GamePhase.WAVE_RISING:
            return
        self._wave_rising_timer = max(0.0, self._wave_rising_timer - dt)
        assert self._wave_rising_timer >= 0.0, "wave rising timer went negative"
        if self._wave_rising_timer == 0.0:
            self._spawn_wave(player)

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
                # When all cubes are gone advance to the next wave immediately.
                # `_count_wave_misses` may set GAME_OVER (row deletion under player);
                # guard before calling _on_wave_cleared.
                if self._phase != GamePhase.GAME_OVER and wave.cube_count == 0:  # type: ignore[comparison-overlap]  # _count_wave_misses may mutate _phase to GAME_OVER
                    self._on_wave_cleared(player)
        elif self._phase == GamePhase.AVALANCHE:
            self._count_avalanche_misses(wave)
            if wave.cube_count == 0:
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

    # --- Phase transitions (player-initiated) ---------------------------------

    def on_title_advance(self) -> None:
        """Advance from TITLE to WAVE_RISING, starting the between-wave timer.

        Called from main.py on any KEYDOWN while in TITLE. No-op if not in
        TITLE so stray key-events during other phases are harmless.
        """
        if self._phase != GamePhase.TITLE:
            return
        assert self._wave_index == 0, (
            f"expected wave_index 0 on title advance, got {self._wave_index}"
        )
        self._wave_rising_timer = WAVE_RISING_DURATION
        self._phase = GamePhase.WAVE_RISING

    # --- Private helpers -----------------------------------------------------

    def _trigger_avalanche(self, player: Player, wave: WaveManager) -> None:
        """Transition to AVALANCHE: squash the player, accelerate the wave."""
        self._phase = GamePhase.AVALANCHE
        self._had_avalanche = True  # disqualifies Perfect for this wave
        player.crush()
        wave.tick_interval = AVALANCHE_TICK_INTERVAL
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
            self._check_game_over(player)
            if self._phase == GamePhase.GAME_OVER:
                return
        assert self._avalanche_penalty >= 0, "avalanche penalty went negative after apply"

    def _check_game_over(self, player: Player) -> None:
        """Transition to GAME_OVER when the player's tile has been voided."""
        if not self._grid.is_valid_position(player.grid_x, player.grid_z):
            self._phase = GamePhase.GAME_OVER

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
            self._effects.spawn_flash(cx, cz)
        elif behavior == CubeBehavior.DETONATE_3X3:
            self._score += info["chain_score"]
            self._wave.remove_cube(cube)
            self._effects.spawn_flash(cx, cz)
            self._mark_trap_area(cx, cz)  # armed; player presses Z to detonate
        elif behavior == CubeBehavior.ROW_DELETE:
            self._wave.remove_cube(cube)
            _ = self._grid.delete_front_row()  # unused: _check_game_over covers it
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
            self._effects.spawn_flash(mx, mz)  # success: white ring confirms capture
            return TriggerOutcome.CAPTURED_SCORE
        if behavior == CubeBehavior.CREATE_TRAP:
            self._wave.remove_cube(cube)
            self._mark_trap_area(mx, mz)  # marks the full 3×3 around the capture tile
            self._effects.spawn_flash(mx, mz)  # success: white ring confirms capture
            return TriggerOutcome.CAPTURED_TRAP
        if behavior == CubeBehavior.ROW_DELETE:
            self._wave.remove_cube(cube)
            _ = self._grid.delete_front_row()  # unused: _check_game_over covers outcome
            self._check_game_over(player)
            self._forbidden_captured = True  # disqualifies Perfect for this wave
            # No flash: a FORBIDDEN capture is a mistake. A success ring would
            # mislead the player into thinking they scored. Step 10 may add a
            # distinct red flash here; for now silence is the correct signal.
            return TriggerOutcome.CAPTURED_FORBIDDEN
        raise ValueError(
            f"unhandled on_capture behavior {behavior!r} for cube type "
            f"{CubeType(cube.cube_type).name} — add a dispatch branch"
        )

    # --- Wave progression (Step 9A) ------------------------------------------

    def start_first_wave(
        self, player: Player, waves: tuple[WaveData, ...]
    ) -> None:
        """Initialize the wave sequence and enter the TITLE phase.

        Must be called once from `main.py` after all subsystems are constructed
        and before the game loop starts. The actual wave spawn is deferred until
        the player presses a key (on_title_advance → WAVE_RISING → update →
        _spawn_wave). Raises `ValueError` if `waves` is empty.
        """
        if not waves:
            raise ValueError("waves sequence must not be empty")
        assert len(waves) > 0, "waves invariant double-check after ValueError guard"
        self._waves = waves
        self._wave_index = 0
        self._phase = GamePhase.TITLE

    def on_restart_key(self, player: Player) -> None:
        """Reset all game state and return to TITLE on any key during GAME_OVER/VICTORY.

        No-op in every other phase so stray keypresses are harmless. Resets the
        grid, wave, effects, and player first (in dependency order), then resets
        the manager's own fields, then calls start_first_wave to re-enter TITLE.
        """
        if self._phase not in (GamePhase.GAME_OVER, GamePhase.VICTORY):
            return
        assert len(self._waves) > 0, "waves empty at restart — start_first_wave was never called"
        waves = self._waves
        self._grid.reset()                   # must come before player.reset()
        self._wave.reset_for_new_wave()      # clear stale cubes immediately so they
        # are not rendered during the TITLE / WAVE_RISING screens.  _spawn_wave also
        # calls reset_for_new_wave when the WAVE_RISING timer expires; the double call
        # is intentional — without this one, old cubes remain visible during the 2 s
        # between-wave pause and the title screen.
        self._effects.reset()                # clear flashes and shake
        player.reset()                       # teleport back to spawn
        self._reset_state()
        self.start_first_wave(player, waves)

    def _reset_state(self) -> None:
        """Zero every per-game field back to the same values as __init__.

        Called exclusively from on_restart_key. Does NOT reset grid, wave,
        player, or effects — the caller handles those in the correct order.
        """
        self._score = 0
        self._iq_score = 0
        self._phase = GamePhase.WAVE_ACTIVE   # overwritten by start_first_wave
        self._wave_penalty = 0
        self._avalanche_penalty = 0
        self._waves = ()
        self._wave_index = 0
        self._forbidden_captured = False
        self._had_avalanche = False
        self._player_steps = 0
        self._wave_total_misses = 0
        self._wave_rising_timer = 0.0
        self._perfect_display = False
        assert self._score == 0, "score not zeroed after _reset_state"
        assert self._wave_index == 0, "wave_index not zeroed after _reset_state"

    def _spawn_wave(self, player: Player) -> None:
        """Spawn the current wave index's cubes and reset all per-wave state.

        Resets penalty counters, perfect-tracking flags, and player-step counter.
        Uncrushs the player (safe even if not currently crushed). Clears any
        leftover grid mark. Spawns cubes with a 50% random mirror flip.
        """
        assert len(self._waves) > 0, "_spawn_wave called before waves were set"
        assert 0 <= self._wave_index < len(self._waves), (
            f"wave_index {self._wave_index} out of range [0, {len(self._waves)})"
        )
        wave_data = self._waves[self._wave_index]
        # Reset per-wave counters and flags.
        self._forbidden_captured = False
        self._had_avalanche = False
        self._player_steps = 0
        self._wave_total_misses = 0
        self._wave_penalty = 0
        self._avalanche_penalty = 0
        self._perfect_display = False
        # Restore player and subsystem state for the new wave.
        player.uncrush()
        self._wave.reset_for_new_wave()
        self._grid.clear_mark()
        # Spawn cubes — 50% mirror-flip doubles effective pattern variety.
        mirror = random.random() < 0.5
        positions = wave_data.spawn_positions(mirror=mirror)
        for gx, gz, cube_type in positions:
            self._wave.spawn_cube(gx, gz, cube_type)
        assert self._wave.cube_count > 0, (
            f"wave {self._wave_index} spawned no cubes — wave_data may be empty"
        )
        self._phase = GamePhase.WAVE_ACTIVE

    def _on_wave_cleared(self, player: Player) -> None:
        """Apply Perfect bonus, restore row if earned, then advance to next wave.

        Called when wave.cube_count reaches 0. Checks the three Perfect criteria:
        no avalanche, no FORBIDDEN captured, no missed NORMAL/ADVANTAGE. On Perfect,
        awards a step-efficiency bonus and restores one voided front row. Then either
        spawns the next wave or transitions to VICTORY.
        """
        assert len(self._waves) > 0, "_on_wave_cleared called before waves were set"
        wave_data = self._waves[self._wave_index]
        is_perfect = (
            not self._had_avalanche
            and not self._forbidden_captured
            and self._wave_total_misses == 0
        )
        if is_perfect:
            bonus = self._calc_perfect_bonus(self._player_steps, wave_data.ideal_steps)
            self._score += bonus
            _ = self._grid.restore_front_row()  # best-effort; no-op if grid intact
        # Clean up wave remnants immediately so WAVE_RISING starts from a tidy state.
        player.uncrush()
        self._grid.clear_mark()
        self._perfect_display = is_perfect
        next_index = self._wave_index + 1
        if next_index >= len(self._waves):
            # All waves complete — compute final I.Q. and enter VICTORY.
            self._iq_score = self._calculate_final_iq()
            self._phase = GamePhase.VICTORY
            return
        self._wave_index = next_index
        self._wave_rising_timer = WAVE_RISING_DURATION
        self._phase = GamePhase.WAVE_RISING

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
        difficulty = IQ_DIFFICULTY_MULTIPLIERS[0]
        iq_pct = IQ_PERCENTAGE_MULTIPLIERS[0]
        result = int(total * difficulty * iq_pct)
        assert result >= 0, "IQ score went negative — logic error"
        return result
