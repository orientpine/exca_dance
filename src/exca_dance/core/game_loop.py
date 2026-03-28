"""Core game loop for Exca Dance."""

from __future__ import annotations

from typing import Any, cast

import pygame
from exca_dance.core.models import JointName, BeatMap, BeatEvent
from exca_dance.core.constants import DEFAULT_JOINT_ANGLES, JOINT_ANGULAR_VELOCITY, JOINT_LIMITS


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
    ) -> None:
        self._renderer = renderer
        self._audio = audio
        self._fk = fk
        self._scoring = scoring
        self._keybinding = keybinding
        self._bridge = bridge
        self._viewport_layout = viewport_layout
        self._excavator_model = excavator_model
        self._mode = mode

        self._state = GameState.MENU
        self._beatmap: BeatMap | None = None
        self._pending_events: list[BeatEvent] = []
        self._processed_events: list[BeatEvent] = []
        self._all_events_consumed_at_ms: float | None = None

        # Joint angles (degrees)
        self._joint_angles: dict[JointName, float] = dict(DEFAULT_JOINT_ANGLES)
        # Keys currently held down
        self._held_keys: set[int] = set()

        self._clock = pygame.time.Clock()
        self._running = False
        self._debug_fps = False

        # Callbacks for screen transitions
        self._on_song_end = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def start_song(self, beatmap: BeatMap) -> None:
        """Load and start playing a beat map."""
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

    # ------------------------------------------------------------------ #
    # Per-frame update (called by screen/state manager)
    # ------------------------------------------------------------------ #

    def tick(self, dt: float) -> list[Any]:
        """
        Process one frame. Returns list of HitResult from this frame.
        dt: delta time in seconds.
        """
        hit_results = []

        if self._state == GameState.PLAYING:
            self._update_joints(dt)
            hit_results = self._check_beats()
            self._check_song_end()

        # Always update bridge with current angles
        if self._mode != "real":
            self._bridge.send_command(self._joint_angles)
        # Update excavator model
        self._excavator_model.update(self._joint_angles)

        return hit_results

    def handle_event(self, event: pygame.event.Event) -> None:
        """Process a pygame event."""
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
        elif event.type == pygame.ACTIVEEVENT:
            # Auto-pause on focus loss
            if hasattr(event, "gain") and event.gain == 0 and event.state == 1:
                if self._state == GameState.PLAYING:
                    self.pause()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _update_joints_from_bridge(self) -> None:
        angles = self._bridge.get_current_angles()
        for joint, value in angles.items():
            lo, hi = JOINT_LIMITS[joint]
            self._joint_angles[joint] = max(lo, min(hi, value))

    def _update_joints(self, dt: float) -> None:
        """Apply angular velocity to joints based on held keys."""
        if self._mode == "real":
            self._update_joints_from_bridge()
            return
        for key in self._held_keys:
            result = self._keybinding.get_joint_for_key(key)
            if result is None:
                continue
            joint, direction = result
            delta = direction * JOINT_ANGULAR_VELOCITY * dt
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
