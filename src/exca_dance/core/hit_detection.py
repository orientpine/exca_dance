"""Hit detection and judgment display for Exca Dance."""

from __future__ import annotations
import time
from exca_dance.core.models import JointName, BeatEvent, HitResult, Judgment
from exca_dance.core.constants import JUDGMENT_WINDOWS
from exca_dance.core.scoring import ScoringEngine


class HitDetector:
    """Evaluates beat events against current joint angles and timing."""

    def __init__(self, scoring_engine: ScoringEngine) -> None:
        self._scoring = scoring_engine

    def check_events(
        self,
        current_time_ms: float,
        current_angles: dict[JointName, float],
        active_events: list[BeatEvent],
    ) -> tuple[list[HitResult], list[BeatEvent]]:
        """
        Evaluate events whose time has passed.
        Returns (hit_results, remaining_events).
        """
        hit_results: list[HitResult] = []
        remaining: list[BeatEvent] = []

        for event in active_events:
            if current_time_ms >= event.time_ms:
                timing_error = abs(current_time_ms - event.time_ms)
                if timing_error > JUDGMENT_WINDOWS[Judgment.GOOD]:
                    # Auto-miss: too late
                    result = self._scoring.judge({}, JUDGMENT_WINDOWS[Judgment.GOOD] + 1.0)
                else:
                    angle_errors = {
                        j: abs(current_angles.get(j, 0.0) - target)
                        for j, target in event.target_angles.items()
                    }
                    result = self._scoring.judge(angle_errors, timing_error)
                hit_results.append(result)
            else:
                remaining.append(event)

        return hit_results, remaining

    def get_pending_count(self, active_events: list[BeatEvent]) -> int:
        return len(active_events)


class JudgmentDisplay:
    """Animated judgment text display (PERFECT!, GREAT!, etc.)."""

    DISPLAY_DURATION = 0.6  # seconds

    def __init__(self) -> None:
        self._active: list[dict] = []  # list of {judgment, score, combo, start_time}

    def trigger(self, hit_result: HitResult, combo: int) -> None:
        """Show a new judgment result."""
        self._active.append(
            {
                "judgment": hit_result.judgment,
                "score": hit_result.score,
                "combo": combo,
                "start_time": time.perf_counter(),
            }
        )

    def update(self, dt: float) -> None:
        """Remove expired judgments."""
        now = time.perf_counter()
        self._active = [a for a in self._active if now - a["start_time"] < self.DISPLAY_DURATION]

    def render(self, renderer, text_renderer) -> None:
        """Render active judgment texts (requires GL text renderer)."""
        if text_renderer is None:
            return
        now = time.perf_counter()
        from exca_dance.rendering.theme import NeonTheme
        from exca_dance.core.models import Judgment

        LABELS = {
            Judgment.PERFECT: "PERFECT!",
            Judgment.GREAT: "GREAT!",
            Judgment.GOOD: "GOOD",
            Judgment.MISS: "MISS",
        }

        cx = renderer.width // 2
        cy = renderer.height // 2 - 80

        for item in self._active:
            elapsed = now - item["start_time"]
            progress = elapsed / self.DISPLAY_DURATION  # 0→1
            alpha = max(0.0, 1.0 - progress * 1.5)
            y_offset = int(progress * -40)  # float upward

            color = NeonTheme.judgment_color(item["judgment"])
            rgba = (color.r, color.g, color.b, alpha)
            label = LABELS[item["judgment"]]
            text_renderer.render(label, cx, cy + y_offset, color=rgba, scale=2.0, align="center")

            # Score increment
            if item["score"] > 0:
                score_rgba = (1.0, 1.0, 1.0, alpha * 0.8)
                text_renderer.render(
                    f"+{item['score']}",
                    cx,
                    cy + y_offset + 50,
                    color=score_rgba,
                    scale=1.2,
                    align="center",
                )

    @property
    def active_count(self) -> int:
        return len(self._active)
