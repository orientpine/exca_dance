"""Visual cue system: ghost excavator + beat timeline indicators."""

from __future__ import annotations
import numpy as np
from exca_dance.core.models import JointName, BeatEvent
from exca_dance.rendering.theme import NeonTheme


class VisualCueRenderer:
    """
    Renders visual cues for the rhythm game:
    - Ghost excavator: semi-transparent target pose
    - Joint angle indicators: arc showing current vs target
    - Beat timeline: scrolling event markers at bottom
    """

    GHOST_ALPHA = 0.30
    GHOST_FADE_MS = 2000.0  # fade in over 2 beats before event

    def __init__(self, renderer, excavator_model_class, fk) -> None:
        self._renderer = renderer
        self._fk = fk
        # Create a separate ghost model instance
        self._ghost_model = excavator_model_class(renderer, fk)
        self._active_target: dict[JointName, float] | None = None
        self._next_event_time_ms: float = 0.0
        self._current_time_ms: float = 0.0
        self._current_angles: dict[JointName, float] = {j: 0.0 for j in JointName}
        self._upcoming_events: list[BeatEvent] = []

    def update(
        self,
        current_time_ms: float,
        current_angles: dict[JointName, float],
        upcoming_events: list[BeatEvent],
    ) -> None:
        """Update cue state each frame."""
        self._current_time_ms = current_time_ms
        self._current_angles = dict(current_angles)
        self._upcoming_events = upcoming_events

        # Find the nearest upcoming event for ghost
        if upcoming_events:
            nearest = min(upcoming_events, key=lambda e: e.time_ms)
            self._active_target = dict(nearest.target_angles)
            self._next_event_time_ms = float(nearest.time_ms)
            # Update ghost model to target pose
            ghost_angles = dict(current_angles)
            ghost_angles.update(nearest.target_angles)
            self._ghost_model.update(ghost_angles)
        else:
            self._active_target = None

    def render_ghost(self, mvp: np.ndarray) -> None:
        """Render semi-transparent ghost excavator at target pose."""
        if self._active_target is None:
            return
        time_to_event = self._next_event_time_ms - self._current_time_ms
        if time_to_event > self.GHOST_FADE_MS or time_to_event < 0:
            return
        # Fade in: alpha 0 → GHOST_ALPHA as event approaches
        alpha = self.GHOST_ALPHA * (1.0 - time_to_event / self.GHOST_FADE_MS)
        alpha = max(0.0, min(self.GHOST_ALPHA, alpha))
        self._ghost_model.render_3d(mvp, alpha=alpha)

    def render_timeline(self, renderer, text_renderer, song_duration_ms: float) -> None:
        """Render scrolling beat timeline at bottom of screen (placeholder)."""
        # Timeline rendering requires 2D drawing primitives
        # This is a minimal implementation — full UI in T17/HUD
        pass

    def get_angle_match_pct(self, joint: JointName) -> float:
        """Return 0-1 how close current angle is to target (1=perfect match)."""
        if self._active_target is None or joint not in self._active_target:
            return 1.0
        target = self._active_target[joint]
        current = self._current_angles.get(joint, 0.0)
        diff = abs(current - target)
        return max(0.0, 1.0 - diff / 30.0)  # 30° = 0% match

    def destroy(self) -> None:
        self._ghost_model.destroy()
