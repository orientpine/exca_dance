"""Core game loop for Exca Dance."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, cast

import pygame
from exca_dance.core.models import JointName, BeatMap, BeatEvent
from exca_dance.core.constants import DEFAULT_JOINT_ANGLES, JOINT_ANGULAR_VELOCITY, JOINT_LIMITS
from exca_dance.core.game_settings import GameSettings
from exca_dance.core.calibration import CalibrationSettings
from exca_dance.core.gamepad import GamepadManager

logger = logging.getLogger(__name__)


class GameState:
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"
    MENU = "menu"


class GameLoop:
    """
    Central game loop orchestrator.
    Handles: input → joint update → beat check → render dispatch.
    """

    def __init__(
        self,
        renderer,
        audio,
        fk,
        scoring,
        keybinding,
        bridge,
        viewport_layout,
        excavator_model,
        *,
        mode: str = "virtual",
        game_settings: GameSettings | None = None,
        bridge_factory: Callable[[str], Any] | None = None,
        gamepad: GamepadManager | None = None,
        calibration: CalibrationSettings | None = None,
    ) -> None:
        self._renderer = renderer
        self._audio = audio
        self._fk = fk
        self._scoring = scoring
        self._keybinding = keybinding
        self._bridge = bridge
        self._viewport_layout = viewport_layout
        self._excavator_model = excavator_model
        self._game_settings = game_settings
        self._fallback_mode = mode
        self._bridge_factory = bridge_factory
        self._active_bridge_mode = game_settings.mode if game_settings is not None else mode
        self._gamepad = gamepad
        self._calibration = calibration

        self._state = GameState.MENU
        self._beatmap: BeatMap | None = None
        self._pending_events: list[BeatEvent] = []
        self._processed_events: list[BeatEvent] = []
        self._all_events_consumed_at_ms: float | None = None

        self._joint_angles: dict[JointName, float] = dict(DEFAULT_JOINT_ANGLES)
        self._held_keys: set[int] = set()

        self._clock = pygame.time.Clock()
        self._running = False
        self._debug_fps = False

        self._on_song_end = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    @property
    def _mode(self) -> str:
        if self._game_settings is not None:
            return self._game_settings.mode
        return self._fallback_mode

    def _sync_bridge_if_mode_changed(self) -> None:
        current = self._mode
        if current != self._active_bridge_mode and self._bridge_factory is not None:
            self._bridge.disconnect()
            self._bridge = self._bridge_factory(current)
            self._active_bridge_mode = current

    def start_song(self, beatmap: BeatMap) -> None:
        self._sync_bridge_if_mode_changed()
        self._beatmap = beatmap
        self._pending_events = list(beatmap.events)  # already sorted by time_ms
        self._processed_events = []
        self._scoring.reset()
        self._joint_angles = dict(DEFAULT_JOINT_ANGLES)
        self._held_keys.clear()
        self._audio.load_music(beatmap.audio_file)
        self._audio.play()
        self._all_events_consumed_at_ms = None
        self._state = GameState.PLAYING

    def pause(self) -> None:
        if self._state == GameState.PLAYING:
            self._audio.pause()
            self._state = GameState.PAUSED

    def resume(self) -> None:
        if self._state == GameState.PAUSED:
            self._audio.resume()
            self._state = GameState.PLAYING

    def stop(self) -> None:
        self._audio.stop()
        self._state = GameState.MENU

    def set_on_song_end(self, callback) -> None:
        self._on_song_end = callback

    @property
    def state(self) -> str:
        return self._state

    @property
    def joint_angles(self) -> dict[JointName, float]:
        return dict(self._joint_angles)

    @property
    def current_time_ms(self) -> float:
        return self._audio.get_position_ms()

    @property
    def last_processed_event(self) -> BeatEvent | None:
        """Return the most recently scored beat event, or None."""
        return self._processed_events[-1] if self._processed_events else None

    # ------------------------------------------------------------------ #
    # Per-frame update (called by screen/state manager)
    # ------------------------------------------------------------------ #

    def update_bridge(self) -> None:
        """Real mode: read sensors + send velocity. Call every frame from main loop."""
        if self._mode != "real":
            return
        self._update_joints_from_bridge()
        self._send_velocity_to_bridge()
        self._excavator_model.update(self._joint_angles)

    def tick(self, dt: float) -> list[Any]:
        """
        Process one frame. Returns list of HitResult from this frame.
        dt: delta time in seconds.
        """
        hit_results = []

        if self._state == GameState.PLAYING:
            if self._mode != "real":
                self._update_joints(dt)
            hit_results = self._check_beats()
            self._check_song_end()

        if self._mode != "real":
            self._bridge.send_command(self._joint_angles)
            self._excavator_model.update(self._joint_angles)

        return hit_results

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self._held_keys.add(event.key)
            if event.key == pygame.K_F3:
                self._debug_fps = not self._debug_fps
            if event.key == pygame.K_ESCAPE:
                if self._state == GameState.PLAYING:
                    self.pause()
                elif self._state == GameState.PAUSED:
                    self.resume()
        elif event.type == pygame.KEYUP:
            self._held_keys.discard(event.key)
        elif self._gamepad is not None and self._gamepad.is_start(event):
            if self._state == GameState.PLAYING:
                self.pause()
            elif self._state == GameState.PAUSED:
                self.resume()
        elif event.type == pygame.ACTIVEEVENT:
            # Auto-pause on focus loss
            if hasattr(event, "gain") and event.gain == 0 and event.state == 1:
                if self._state == GameState.PLAYING:
                    self.pause()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _update_joints_from_bridge(self) -> None:
        """Real mode: read joint angles from ROS2, apply calibration transform."""
        raw_angles = self._bridge.get_raw_angles()
        for joint, raw_value in raw_angles.items():
            if self._calibration is not None:
                value = self._calibration.transform_angle(joint, raw_value)
            else:
                value = raw_value
            lo, hi = JOINT_LIMITS[joint]
            self._joint_angles[joint] = max(lo, min(hi, value))

    def _get_input_velocities(self) -> dict[JointName, float]:
        """Collect keyboard + gamepad input as -1.0~1.0 per joint."""
        input_per_joint: dict[JointName, float] = {j: 0.0 for j in JointName}

        for key in self._held_keys:
            result = self._keybinding.get_joint_for_key(key)
            if result is None:
                continue
            joint, direction = result
            input_per_joint[joint] += float(direction)

        if self._gamepad is not None:
            for joint in JointName:
                input_per_joint[joint] += self._gamepad.get_joint_input(joint)

        # Clamp to -1.0~1.0
        return {j: max(-1.0, min(1.0, v)) for j, v in input_per_joint.items()}

    _vel_log_counter: int = 0

    def _send_velocity_to_bridge(self) -> None:
        """Real mode: send calibrated velocity to ROS2 UpperControlCmd."""
        if self._gamepad is not None and not self._gamepad.connected:
            if GameLoop._vel_log_counter % 300 == 1:
                logger.warning("Gamepad disconnected \u2014 sending zero velocities")

        raw_velocities = self._get_input_velocities()
        calibrated: dict[JointName, float] = {}
        for joint, vel in raw_velocities.items():
            if self._calibration is not None:
                calibrated[joint] = self._calibration.transform_velocity(joint, vel)
            else:
                calibrated[joint] = vel

        # Periodic diagnostic log (every ~5 seconds at 60 FPS)
        GameLoop._vel_log_counter += 1
        if GameLoop._vel_log_counter % 300 == 0:
            has_input = any(abs(v) > 0.01 for v in calibrated.values())
            logger.info(
                "bridge vel: %s | gamepad=%s | input=%s",
                {k.value: round(v, 2) for k, v in calibrated.items()},
                self._gamepad.connected if self._gamepad else "N/A",
                has_input,
            )

        self._bridge.send_velocity(calibrated)

    def _update_joints(self, dt: float) -> None:
        if self._mode == "real":
            self._update_joints_from_bridge()
            return

        velocities = self._get_input_velocities()
        for joint, raw in velocities.items():
            if raw == 0.0:
                continue
            delta = raw * JOINT_ANGULAR_VELOCITY * dt
            lo, hi = JOINT_LIMITS[joint]
            self._joint_angles[joint] = max(lo, min(hi, self._joint_angles[joint] + delta))

    def _check_beats(self) -> list[Any]:
        """Evaluate beat events whose time has passed."""
        from exca_dance.core.constants import JUDGMENT_WINDOWS
        from exca_dance.core.models import Judgment

        current_ms = self._audio.get_position_ms()
        good_window = JUDGMENT_WINDOWS[cast(Judgment, Judgment.GOOD)]
        hit_results: list[Any] = []
        remaining = []

        for event in self._pending_events:
            if current_ms >= event.time_ms:
                timing_error = abs(current_ms - event.time_ms)
                # Auto-miss if past GOOD window
                if timing_error > good_window:
                    result = self._scoring.judge({}, good_window + 1)
                else:
                    angle_errors = {
                        j: abs(self._joint_angles.get(j, 0.0) - target)
                        for j, target in event.target_angles.items()
                    }
                    result = self._scoring.judge(angle_errors, timing_error)
                hit_results.append(result)
                self._processed_events.append(event)
            else:
                remaining.append(event)

        self._pending_events = remaining
        return hit_results

    def _check_song_end(self) -> None:
        """Detect song completion."""
        if not self._pending_events and self._beatmap is not None:
            current_ms = self._audio.get_position_ms()

            if self._all_events_consumed_at_ms is None:
                self._all_events_consumed_at_ms = current_ms

            if not self._audio.is_playing():
                self._state = GameState.FINISHED
                if self._on_song_end:
                    self._on_song_end(self._scoring)
                return

            if current_ms - self._all_events_consumed_at_ms >= 3000.0:
                self._state = GameState.FINISHED
                if self._on_song_end:
                    self._on_song_end(self._scoring)

    def get_upcoming_events(self, lookahead_ms: float = 3000.0) -> list[BeatEvent]:
        """Return events within the next lookahead_ms milliseconds."""
        current_ms = self._audio.get_position_ms()
        return [e for e in self._pending_events if e.time_ms <= current_ms + lookahead_ms]
