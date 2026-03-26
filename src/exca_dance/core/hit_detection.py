"""Hit detection and judgment display for Exca Dance.

DJMAX Respect-style judgment display with phased animation,
additive glow layers, and ring particle explosions.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
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
        large: bool = False,
    ) -> None: ...


# ── Easing functions ───────────────────────────────────────────


def _ease_out_back(t: float) -> float:
    """Overshoot pop easing (rubber band effect)."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1.0 + c3 * pow(t - 1.0, 3) + c1 * pow(t - 1.0, 2)


def _ease_out_quad(t: float) -> float:
    return 1.0 - (1.0 - t) * (1.0 - t)


def _ease_in_quad(t: float) -> float:
    return t * t


def _ease_in_quint(t: float) -> float:
    return t * t * t * t * t


# ── Animation helpers ──────────────────────────────────────────


def _hit_anim(elapsed: float) -> tuple[float, float, int]:
    """Non-MISS phased animation (pop → settle → hold → expand-fade).

    Phase 1 (0-80ms):    Scale 0.5 → 1.15 (OutBack overshoot)
    Phase 2 (80-180ms):  Scale 1.15 → 0.95 (OutQuad settle)
    Phase 3 (180-500ms): Scale 0.95 → 1.0 (hold, alpha=1)
    Phase 4 (500-800ms): Scale 1.0 → 1.4 (expand), alpha fade

    Returns ``(scale, alpha, y_offset)``.
    """
    if elapsed < 0.08:
        t = elapsed / 0.08
        scale = 0.5 + 0.65 * _ease_out_back(t)
        return (scale, 1.0, 0)
    if elapsed < 0.18:
        t = (elapsed - 0.08) / 0.10
        scale = 1.15 - 0.20 * _ease_out_quad(t)
        return (scale, 1.0, 0)
    if elapsed < 0.50:
        t = (elapsed - 0.18) / 0.32
        scale = 0.95 + 0.05 * t
        return (scale, 1.0, 0)
    t = min(1.0, (elapsed - 0.50) / 0.30)
    scale = 1.0 + 0.4 * _ease_out_quad(t)
    alpha = 1.0 - _ease_out_quad(t)
    return (scale, max(0.0, alpha), 0)


def _miss_anim(
    elapsed: float,
) -> tuple[float, float, int, float]:
    """MISS animation: scale-down → fall + rotate + fade.

    Returns ``(scale, alpha, y_offset, rotation_deg)``.
    """
    if elapsed < 0.10:
        t = elapsed / 0.10
        scale = 1.4 - 0.4 * _ease_out_quad(t)
        return (scale, 1.0, 0, 0.0)
    t = min(1.0, (elapsed - 0.10) / 0.70)
    y_off = int(80 * _ease_in_quint(t))
    rot = 30.0 * _ease_in_quint(t)
    alpha = 1.0 - _ease_out_quad(t)
    return (1.0, max(0.0, alpha), y_off, rot)


# ── Particle data ──────────────────────────────────────────────


@dataclass
class _Particle:
    """Single ring particle with start → target position."""

    x: float
    y: float
    target_x: float
    target_y: float
    size: float
    color: tuple[float, float, float, float]


@dataclass
class _ParticleGroup:
    """Group of particles spawned by a single judgment hit."""

    particles: list[_Particle] = field(default_factory=list)
    start_time: float = 0.0
    duration: float = 0.6


# ── Judgment entry ─────────────────────────────────────────────


class _JudgmentEntry(TypedDict):
    judgment: Judgment
    score: int
    combo: int
    start_time: float


# ── Labels ─────────────────────────────────────────────────────

_LABELS = {
    Judgment.PERFECT: "PERFECT!",
    Judgment.GREAT: "GREAT!",
    Judgment.GOOD: "GOOD",
    Judgment.MISS: "MISS",
}


# ── Main display class ────────────────────────────────────────


@final
class JudgmentDisplay:
    """DJMAX-style animated judgment display with glow + particles."""

    DISPLAY_DURATION = 0.8
    PARTICLE_DURATION = 0.6

    def __init__(self) -> None:
        self._active: list[_JudgmentEntry] = []
        self._particles: list[_ParticleGroup] = []
        self.flash_alpha: float = 0.0
        self.flash_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
        self.flash_start: float = 0.0
        self.flash_duration: float = 0.0

    # ── Public API ─────────────────────────────────────────────

    def trigger(self, hit_result: HitResult, combo: int) -> None:
        """Show a new judgment with particles and screen flash."""
        now = time.perf_counter()
        self._active.append(
            _JudgmentEntry(
                judgment=hit_result.judgment,
                score=hit_result.score,
                combo=combo,
                start_time=now,
            )
        )

        # Enhanced screen flash per judgment type
        j = hit_result.judgment
        if j == Judgment.PERFECT:
            self.flash_alpha = 0.25
            self.flash_color = (1.0, 1.0, 1.0)
            self.flash_duration = 0.08
            self.flash_start = now
        elif j == Judgment.GREAT:
            self.flash_alpha = 0.12
            self.flash_color = (0.3, 0.9, 1.0)
            self.flash_duration = 0.05
            self.flash_start = now
        elif j == Judgment.MISS:
            self.flash_alpha = 0.15
            self.flash_color = (1.0, 0.1, 0.1)
            self.flash_duration = 0.06
            self.flash_start = now

        # Ring particle explosion (non-MISS only)
        if j != Judgment.MISS:
            self._spawn_particles(j, now)

    def update(self, _dt: float) -> None:
        """Remove expired judgments and particles."""
        now = time.perf_counter()
        dur = self.DISPLAY_DURATION
        self._active = [a for a in self._active if now - a["start_time"] < dur]
        self._particles = [p for p in self._particles if now - p.start_time < p.duration]

    def render(self, renderer: _Renderer, text_renderer: _TextRenderer) -> None:
        """Render particles, glow layers, and judgment text."""
        now = time.perf_counter()
        from exca_dance.rendering.theme import NeonTheme

        # Position: top area of main 3D viewport, ABOVE excavator
        cx = int(renderer.width * 0.375)
        cy = int(renderer.height * 0.15)

        # Particles first (render behind text)
        self._render_particles(now, cx, cy, text_renderer)

        # Judgment entries with glow
        for item in self._active:
            elapsed = now - item["start_time"]
            judgment = item["judgment"]
            label = _LABELS[judgment]
            color = NeonTheme.judgment_color(judgment)
            glow = NeonTheme.judgment_glow_color(judgment)

            if judgment == Judgment.MISS:
                scale, alpha, y_off, _rot = _miss_anim(elapsed)
            else:
                scale, alpha, y_off = _hit_anim(elapsed)

            if alpha <= 0.0:
                continue

            draw_y = cy + y_off
            base = 2.0

            # Glow pass 1: outer halo (1.5× scale, dim)
            outer_a = alpha * glow.a * 0.4
            if outer_a > 0.01:
                text_renderer.render(
                    label,
                    cx,
                    draw_y,
                    color=(glow.r, glow.g, glow.b, outer_a),
                    scale=base * scale * 1.5,
                    align="center",
                    large=True,
                )

            # Glow pass 2: inner halo (1.2× scale)
            inner_a = alpha * glow.a * 0.7
            if inner_a > 0.01:
                text_renderer.render(
                    label,
                    cx,
                    draw_y,
                    color=(glow.r, glow.g, glow.b, inner_a),
                    scale=base * scale * 1.2,
                    align="center",
                    large=True,
                )

            # Core text (white-tinted judgment color)
            cr = min(1.0, color.r * 0.7 + 0.3)
            cg = min(1.0, color.g * 0.7 + 0.3)
            cb = min(1.0, color.b * 0.7 + 0.3)
            text_renderer.render(
                label,
                cx,
                draw_y,
                color=(cr, cg, cb, alpha),
                scale=base * scale,
                align="center",
                large=True,
            )

            # Score increment below judgment text
            if item["score"] > 0:
                score_a = alpha * 0.8
                text_renderer.render(
                    f"+{item['score']}",
                    cx,
                    draw_y + 55,
                    color=(1.0, 1.0, 1.0, score_a),
                    scale=1.2,
                    align="center",
                )

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def current_flash(
        self,
    ) -> tuple[tuple[float, float, float] | None, float]:
        if self.flash_duration <= 0.0 or self.flash_alpha <= 0.0:
            return (None, 0.0)

        elapsed = time.perf_counter() - self.flash_start
        if elapsed >= self.flash_duration:
            return (None, 0.0)

        remaining = 1.0 - (elapsed / self.flash_duration)
        alpha = max(0.0, self.flash_alpha * remaining)
        return (self.flash_color, alpha)

    # ── Internal ───────────────────────────────────────────────

    def _spawn_particles(self, judgment: Judgment, now: float) -> None:
        """Spawn 8 particles in a ring pattern."""
        from exca_dance.rendering.theme import NeonTheme

        glow = NeonTheme.judgment_glow_color(judgment)
        base_c = (glow.r, glow.g, glow.b, 0.9)
        white_c = (1.0, 1.0, 1.0, 0.7)

        count = 8
        radius = 60.0
        parts: list[_Particle] = []
        for i in range(count):
            angle = (2.0 * math.pi * i) / count
            tx = math.cos(angle) * radius
            ty = math.sin(angle) * radius
            c = base_c if i % 2 == 0 else white_c
            parts.append(
                _Particle(
                    x=tx * 0.3,
                    y=ty * 0.3,
                    target_x=tx,
                    target_y=ty,
                    size=4.0,
                    color=c,
                )
            )
        self._particles.append(
            _ParticleGroup(
                particles=parts,
                start_time=now,
                duration=self.PARTICLE_DURATION,
            )
        )

    def _render_particles(
        self,
        now: float,
        cx: int,
        cy: int,
        text_renderer: _TextRenderer,
    ) -> None:
        """Render ring particle groups as colored dot characters."""
        for pg in self._particles:
            elapsed = now - pg.start_time
            progress = min(1.0, elapsed / pg.duration)
            # OutQuint easing for spread (over 400ms)
            spread_t = min(1.0, elapsed / 0.4)
            spread = 1.0 - pow(1.0 - spread_t, 5)
            fade = max(0.0, 1.0 - _ease_in_quad(progress))

            for p in pg.particles:
                px = cx + p.x + (p.target_x - p.x) * spread
                py = cy + p.y + (p.target_y - p.y) * spread
                r, g, b, a = p.color
                pa = a * fade
                if pa > 0.01:
                    text_renderer.render(
                        "●",
                        int(px),
                        int(py),
                        color=(r, g, b, pa),
                        scale=0.5,
                        align="center",
                    )
