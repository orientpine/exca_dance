"""Hit detection and judgment display for Exca Dance."""

from __future__ import annotations
import time
from typing import Protocol, TypedDict, final
from exca_dance.core.models import HitResult, Judgment


class _Renderer(Protocol):
    width: int
    height: int


class _TextRenderer(Protocol):
    def render(
        self,
        text: str,
        x: int,
        y: int,
        *,
        color: object,
        scale: float,
        align: str,
    ) -> None: ...


class _JudgmentEntry(TypedDict):
    judgment: Judgment
    score: int
    combo: int
    start_time: float


@final
class JudgmentDisplay:
    """Animated judgment text display (PERFECT!, GREAT!, etc.)."""

    DISPLAY_DURATION = 0.6  # seconds

    def __init__(self) -> None:
        self._active: list[_JudgmentEntry] = []
        self.flash_alpha: float = 0.0
        self.flash_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
        self.flash_start: float = 0.0
        self.flash_duration: float = 0.0

    def trigger(self, hit_result: HitResult, combo: int) -> None:
        """Show a new judgment result."""
        now = time.perf_counter()
        self._active.append(
            {
                "judgment": hit_result.judgment,
                "score": hit_result.score,
                "combo": combo,
                "start_time": now,
            }
        )

        if hit_result.judgment == Judgment.PERFECT:
            self.flash_alpha = 0.15
            self.flash_color = (1.0, 1.0, 1.0)
            self.flash_duration = 0.05
            self.flash_start = now
        elif hit_result.judgment == Judgment.MISS:
            self.flash_alpha = 0.08
            self.flash_color = (1.0, 0.1, 0.1)
            self.flash_duration = 0.03
            self.flash_start = now

    def update(self, _dt: float) -> None:
        """Remove expired judgments."""
        now = time.perf_counter()
        self._active = [a for a in self._active if now - a["start_time"] < self.DISPLAY_DURATION]

    def render(self, renderer: _Renderer, text_renderer: _TextRenderer) -> None:
        """Render active judgment texts (requires GL text renderer)."""
        now = time.perf_counter()
        from exca_dance.rendering.theme import NeonTheme
        from exca_dance.core.models import Judgment

        LABELS = {
            Judgment.PERFECT: "PERFECT!",
            Judgment.GREAT: "GREAT!",
            Judgment.GOOD: "GOOD",
            Judgment.MISS: "MISS",
        }

        cx = int(renderer.width * 0.375)
        cy = renderer.height // 2 - 80

        for item in self._active:
            elapsed = now - item["start_time"]
            progress = elapsed / self.DISPLAY_DURATION  # 0→1
            alpha = max(0.0, 1.0 - progress * 1.5)
            y_offset = int(progress * -40)  # float upward
            base_scale = 2.0
            if elapsed < 0.3:
                scale = base_scale * (1.5 - 0.5 * (elapsed / 0.3))
            else:
                scale = base_scale

            color = NeonTheme.judgment_color(item["judgment"])
            rgba = (color.r, color.g, color.b, alpha)
            label = LABELS[item["judgment"]]
            text_renderer.render(label, cx, cy + y_offset, color=rgba, scale=scale, align="center")

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

    @property
    def current_flash(self) -> tuple[tuple[float, float, float] | None, float]:
        if self.flash_duration <= 0.0 or self.flash_alpha <= 0.0:
            return (None, 0.0)

        elapsed = time.perf_counter() - self.flash_start
        if elapsed >= self.flash_duration:
            return (None, 0.0)

        remaining = 1.0 - (elapsed / self.flash_duration)
        alpha = max(0.0, self.flash_alpha * remaining)
        return (self.flash_color, alpha)
