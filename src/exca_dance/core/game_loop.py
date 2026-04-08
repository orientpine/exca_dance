"""Core game loop for Exca Dance."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, cast

import pygame
from exca_dance.core.models import JointName, BeatMap, BeatEvent
from exca_dance.core.constants import (
    DEFAULT_JOINT_ANGLES,
    JOINT_ANGULAR_VELOCITY,
    SAFETY_SENSOR_GRACE_SEC,
    SAFETY_SENSOR_STALE_SEC,
    SAFETY_VELOCITY_DEADBAND,
)
from exca_dance.core.game_settings import GameSettings
from exca_dance.core.joint_limits import JointLimitsConfig
from exca_dance.core.calibration import CalibrationSettings
from exca_dance.core.gamepad import GamepadManager

logger = logging.getLogger(__name__)

SAFETY_REASON_MIN: str = "MIN"
SAFETY_REASON_MAX: str = "MAX"
SAFETY_REASON_NO_SENSOR: str = "NO_SENSOR"
SAFETY_REASON_STALE: str = "STALE"


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
        joint_limits: JointLimitsConfig | None = None,
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
        self._joint_limits = joint_limits if joint_limits is not None else JointLimitsConfig()

        self._state = GameState.MENU
        self._beatmap: BeatMap | None = None
        self._pending_events: list[BeatEvent] = []
        self._active_event: BeatEvent | None = None
        self._active_deadline_ms: float | None = None
        self._processed_events: list[BeatEvent] = []
        self._all_events_consumed_at_ms: float | None = None

        self._joint_angles: dict[JointName, float] = dict(DEFAULT_JOINT_ANGLES)
        self._held_keys: set[int] = set()

        self._unclamped_angles: dict[JointName, float] = {}
        self._safety_blocked: dict[JointName, str] = {}
        self._safety_armed_at: float = time.perf_counter()

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
            self._reset_safety_state()

    def _reset_safety_state(self) -> None:
        self._unclamped_angles = {}
        self._safety_blocked = {}
        self._safety_armed_at = time.perf_counter()

    def start_song(self, beatmap: BeatMap) -> None:
        self._sync_bridge_if_mode_changed()
        self._beatmap = beatmap

        speed = 1.0
        if self._game_settings is not None:
            speed = self._game_settings.playback_speed
        self._pending_events = _scale_events(beatmap.events, speed)

        self._active_event = None
        self._active_deadline_ms = None
        self._processed_events = []
        self._scoring.reset()
        self._joint_angles = dict(DEFAULT_JOINT_ANGLES)
        self._held_keys.clear()
        self._reset_safety_state()
        if hasattr(self._audio, "load_music_scaled"):
            self._audio.load_music_scaled(beatmap.audio_file, speed)
        else:
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
        self._held_keys.clear()
        self._reset_safety_state()

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
    def active_event(self) -> BeatEvent | None:
        return self._active_event

    @property
    def active_deadline_ms(self) -> float | None:
        return self._active_deadline_ms

    @property
    def last_processed_event(self) -> BeatEvent | None:
        return self._processed_events[-1] if self._processed_events else None

    @property
    def next_pending_event(self) -> BeatEvent | None:
        return self._pending_events[0] if self._pending_events else None

    @property
    def safety_blocked_joints(self) -> dict[JointName, str]:
        """Joints whose outgoing velocity is currently zero-gated by the real-mode safety gate.

        Returns a copy mapping joint → reason code (MIN / MAX / NO_SENSOR / STALE).
        Empty dict in virtual mode or when every joint passes the safety check.
        """
        return dict(self._safety_blocked)

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
        """Real mode: read joint angles from ROS2, apply calibration transform.

        Populates both the display-safe `_joint_angles` (clamped to the
        runtime joint limits for rendering / scoring) and the uncensored
        `_unclamped_angles` that the safety gate consults to detect
        "joint is actually outside the allowed range".
        """
        raw_angles = self._bridge.get_raw_angles()
        for joint, raw_value in raw_angles.items():
            if self._calibration is not None:
                value = self._calibration.transform_angle(joint, raw_value)
            else:
                value = raw_value
            self._unclamped_angles[joint] = value
            lo, hi = self._joint_limits.get(joint)
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

    def _apply_safety_limits(
        self,
        raw_velocities: dict[JointName, float],
    ) -> dict[JointName, float]:
        """Real-mode safety gate — zero per-joint velocity when unsafe.

        Operates in game-coordinate space. Input is the pre-calibration velocity
        dict from `_get_input_velocities()`; the unclamped calibrated sensor
        angles in `self._unclamped_angles` are the ground truth for the range
        check. Both sides live in game coordinates, so direction comparison is
        valid regardless of the independent velocity/angle sign calibrations.

        Fail-close policy:
          * no sensor sample for a joint (and grace window expired) → block
          * sensor sample older than `SAFETY_SENSOR_STALE_SEC` → block
          * `angle <= lo` and velocity is actively negative → block
          * `angle >= hi` and velocity is actively positive → block
          * velocity magnitude below `SAFETY_VELOCITY_DEADBAND` → not "active"

        Blocking sets that joint's outgoing velocity to 0.0. The reason is
        recorded in `self._safety_blocked` for HUD display, and a warning
        is logged only on state transitions to keep log noise bounded.
        """
        safe = dict(raw_velocities)
        new_blocked: dict[JointName, str] = {}

        now = time.perf_counter()
        in_grace = (now - self._safety_armed_at) < SAFETY_SENSOR_GRACE_SEC
        try:
            sensor_timestamps = self._bridge.get_sensor_timestamps()
        except Exception:
            sensor_timestamps = {}

        for joint, vel in raw_velocities.items():
            active = abs(vel) > SAFETY_VELOCITY_DEADBAND

            angle = self._unclamped_angles.get(joint)
            last_update = sensor_timestamps.get(joint)

            if angle is None or last_update is None:
                if in_grace:
                    continue
                if active:
                    safe[joint] = 0.0
                    new_blocked[joint] = SAFETY_REASON_NO_SENSOR
                continue

            if (now - last_update) > SAFETY_SENSOR_STALE_SEC:
                if active:
                    safe[joint] = 0.0
                    new_blocked[joint] = SAFETY_REASON_STALE
                continue

            lo, hi = self._joint_limits.get(joint)
            if angle <= lo and vel < -SAFETY_VELOCITY_DEADBAND:
                safe[joint] = 0.0
                new_blocked[joint] = SAFETY_REASON_MIN
            elif angle >= hi and vel > SAFETY_VELOCITY_DEADBAND:
                safe[joint] = 0.0
                new_blocked[joint] = SAFETY_REASON_MAX

        for joint, reason in new_blocked.items():
            if self._safety_blocked.get(joint) != reason:
                angle = self._unclamped_angles.get(joint)
                angle_str = f"{angle:.2f}°" if angle is not None else "<no data>"
                lo, hi = self._joint_limits.get(joint)
                logger.warning(
                    "SAFETY BLOCK: %s at %s outside [%.2f, %.2f] (%s) — velocity gated to 0",
                    joint.value, angle_str, lo, hi, reason,
                )
        for joint in self._safety_blocked:
            if joint not in new_blocked:
                logger.info("SAFETY CLEAR: %s — safety gate released", joint.value)

        self._safety_blocked = new_blocked
        return safe

    def _send_velocity_to_bridge(self) -> None:
        """Real mode: send calibrated velocity to ROS2 UpperControlCmd.

        Always publishes an explicit dict (never skips), because the ROS2
        subprocess keeps replaying its last velocity when the queue is empty.
        The gate zeroes individual joints instead of suppressing the publish.

        Also forces every velocity to 0.0 unless the game state is PLAYING —
        this protects against held keys / stuck gamepad axes leaking into
        real hardware while the player is in a menu or paused.
        """
        if self._gamepad is not None and not self._gamepad.connected:
            if GameLoop._vel_log_counter % 300 == 1:
                logger.warning("Gamepad disconnected \u2014 sending zero velocities")

        if self._state != GameState.PLAYING:
            zero_raw: dict[JointName, float] = {j: 0.0 for j in JointName}
            self._safety_blocked = {}
            self._bridge.send_velocity(self._calibrate_velocities(zero_raw))
            return

        raw_velocities = self._get_input_velocities()
        safe_velocities = self._apply_safety_limits(raw_velocities)
        calibrated = self._calibrate_velocities(safe_velocities)

        GameLoop._vel_log_counter += 1
        if GameLoop._vel_log_counter % 300 == 0:
            has_input = any(abs(v) > 0.01 for v in calibrated.values())
            logger.info(
                "bridge vel: %s | gamepad=%s | input=%s | blocked=%s",
                {k.value: round(v, 2) for k, v in calibrated.items()},
                self._gamepad.connected if self._gamepad else "N/A",
                has_input,
                {j.value: r for j, r in self._safety_blocked.items()} or None,
            )

        self._bridge.send_velocity(calibrated)

    def _calibrate_velocities(
        self, velocities: dict[JointName, float]
    ) -> dict[JointName, float]:
        calibrated: dict[JointName, float] = {}
        for joint, vel in velocities.items():
            if self._calibration is not None:
                calibrated[joint] = self._calibration.transform_velocity(joint, vel)
            else:
                calibrated[joint] = vel
        return calibrated

    def _update_joints(self, dt: float) -> None:
        if self._mode == "real":
            self._update_joints_from_bridge()
            return

        velocities = self._get_input_velocities()
        for joint, raw in velocities.items():
            if raw == 0.0:
                continue
            delta = raw * JOINT_ANGULAR_VELOCITY * dt
            lo, hi = self._joint_limits.get(joint)
            self._joint_angles[joint] = max(lo, min(hi, self._joint_angles[joint] + delta))

    def _check_beats(self) -> list[Any]:
        from exca_dance.core.constants import JUDGMENT_WINDOWS, MISS_GRACE_MS
        from exca_dance.core.models import Judgment

        current_ms = self._audio.get_position_ms()
        good_window = JUDGMENT_WINDOWS[cast(Judgment, Judgment.GOOD)]
        hit_results: list[Any] = []

        if self._active_event is None and self._pending_events:
            nxt = self._pending_events[0]
            if current_ms >= nxt.time_ms:
                self._active_event = nxt
                active_window = nxt.duration_ms + MISS_GRACE_MS
                self._active_deadline_ms = nxt.time_ms + active_window
                self._pending_events = self._pending_events[1:]

        if self._active_event is not None:
            ev = self._active_event
            deadline = self._active_deadline_ms or 0.0
            active_window = deadline - ev.time_ms
            elapsed_ms = current_ms - ev.time_ms

            angle_errors = {
                j: abs(self._joint_angles.get(j, 0.0) - target)
                for j, target in ev.target_angles.items()
            }
            avg_err = (
                sum(angle_errors.values()) / len(angle_errors)
                if angle_errors
                else 0.0
            )
            hit_threshold = self._scoring.get_good_angle_threshold()

            if avg_err <= hit_threshold:
                scaled = elapsed_ms / active_window * good_window if active_window > 0 else 0.0
                result = self._scoring.judge(angle_errors, scaled)
                hit_results.append(result)
                self._processed_events.append(ev)
                self._active_event = None
                self._active_deadline_ms = None
            elif current_ms >= deadline:
                result = self._scoring.judge({}, good_window + 1)
                hit_results.append(result)
                self._processed_events.append(ev)
                self._active_event = None
                self._active_deadline_ms = None

        return hit_results

    def _check_song_end(self) -> None:
        if (
            not self._pending_events
            and self._active_event is None
            and self._beatmap is not None
        ):
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


def _scale_events(events: list[BeatEvent], speed: float) -> list[BeatEvent]:
    """Scale beat event timings for playback speed. speed=1.0 is identity.

    At speed s, real-time elapses 1/s per audio-ms, so both time_ms and
    duration_ms are divided by s to stay in sync with the scaled audio.
    """
    if abs(speed - 1.0) < 1e-6:
        return list(events)
    scale = 1.0 / speed
    scaled: list[BeatEvent] = []
    for ev in events:
        scaled.append(
            BeatEvent(
                time_ms=int(round(ev.time_ms * scale)),
                target_angles=dict(ev.target_angles),
                duration_ms=max(1, int(round(ev.duration_ms * scale))),
            )
        )
    return scaled
