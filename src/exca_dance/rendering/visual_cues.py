"""Visual cue system: ghost excavator + beat timeline indicators."""

from __future__ import annotations

# pyright: reportPrivateUsage=false, reportUnknownMemberType=false
from typing import Protocol, cast
import numpy as np
import moderngl
from exca_dance.core.kinematics import ExcavatorFK
from exca_dance.core.models import JointName, BeatEvent
from exca_dance.rendering.excavator_model import ExcavatorModel
from exca_dance.rendering.renderer import GameRenderer
from exca_dance.rendering.theme import NeonTheme


class TextRendererProtocol(Protocol):
    def render(
        self,
        text: str,
        x: int,
        y: int,
        color: tuple[float, float, float, float],
        scale: float = 1.0,
        align: str = "left",
    ) -> None: ...


class VisualCueRenderer:
    """
    Renders visual cues for the rhythm game:
    - Ghost excavator: semi-transparent target pose
    - Joint angle indicators: arc showing current vs target
    - Beat timeline: scrolling event markers at bottom
    """

    GHOST_FADE_MS: float = 2000.0  # fade in over 2 beats before event

    def __init__(
        self,
        renderer: GameRenderer,
        excavator_model_class: type[ExcavatorModel],
        fk: ExcavatorFK,
    ) -> None:
        self._renderer: GameRenderer = renderer
        self._fk: ExcavatorFK = fk
        # Ghost model uses distinct violet/purple colors
        ghost_colors = {
            "base": NeonTheme.GHOST_SWING.as_rgb(),
            "turret": NeonTheme.GHOST_SWING.as_rgb(),
            JointName.BOOM: NeonTheme.GHOST_BOOM.as_rgb(),
            JointName.ARM: NeonTheme.GHOST_ARM.as_rgb(),
            JointName.BUCKET: NeonTheme.GHOST_BUCKET.as_rgb(),
        }
        self._ghost_model: ExcavatorModel = excavator_model_class(
            renderer, fk, joint_colors=ghost_colors
        )
        self._active_target: dict[JointName, float] | None = None
        self._next_event_time_ms: float = 0.0
        self._current_time_ms: float = 0.0
        self._current_angles: dict[JointName, float] = {j: 0.0 for j in JointName}
        self._upcoming_events: list[BeatEvent] = []
        self._prev_ghost_angles: dict[JointName, float] | None = None
        self._ghost_glow_base: np.ndarray | None = None
        self._ghost_glow_vbo: moderngl.Buffer | None = None
        self._ghost_glow_vao: moderngl.VertexArray | None = None

    def _rebuild_ghost_glow(self) -> None:
        if self._ghost_model._vbo is None or self._ghost_model._vertex_count <= 0:
            self._ghost_glow_base = None
            return

        raw = np.frombuffer(self._ghost_model._vbo.read(), dtype="f4")
        if raw.size % 6 != 0:
            self._ghost_glow_base = None
            return

        self._ghost_glow_base = raw.reshape(-1, 6).copy()
        ctx = self._renderer.ctx
        if self._ghost_glow_vbo is not None:
            self._ghost_glow_vbo.release()
        if self._ghost_glow_vao is not None:
            self._ghost_glow_vao.release()

        glow_data = np.empty((self._ghost_glow_base.shape[0], 7), dtype="f4")
        glow_data[:, :6] = self._ghost_glow_base
        glow_data[:, 6] = 0.0
        self._ghost_glow_vbo = ctx.buffer(glow_data.tobytes())
        self._ghost_glow_vao = ctx.vertex_array(
            self._renderer.prog_additive,
            [(self._ghost_glow_vbo, "3f 4f", "in_position", "in_color")],
        )

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
            if self._prev_ghost_angles is None or any(
                abs(ghost_angles.get(k, 0) - self._prev_ghost_angles.get(k, 0)) > 0.01
                for k in ghost_angles
            ):
                self._ghost_model.update(ghost_angles)
                self._prev_ghost_angles = dict(ghost_angles)
                self._rebuild_ghost_glow()
        else:
            self._active_target = None
            self._prev_ghost_angles = None

    def render_ghost(self, mvp: np.ndarray) -> None:
        """Render semi-transparent ghost excavator at target pose."""
        if self._active_target is None:
            return
        time_to_event = self._next_event_time_ms - self._current_time_ms
        if time_to_event > self.GHOST_FADE_MS or time_to_event < 0:
            return
        # Fade in: alpha 0 → GHOST_ALPHA as event approaches
        ghost_alpha = NeonTheme.GHOST_ALPHA
        alpha = ghost_alpha * (1.0 - time_to_event / self.GHOST_FADE_MS)
        alpha = max(0.0, min(ghost_alpha, alpha))
        self._ghost_model.render_3d(mvp, alpha=alpha)

        glow_alpha = alpha * 0.25
        if glow_alpha > 0.01 and self._ghost_glow_vao is not None:
            if self._ghost_glow_vbo is not None and self._ghost_glow_base is not None:
                glow_data = np.empty((self._ghost_glow_base.shape[0], 7), dtype="f4")
                glow_data[:, :6] = self._ghost_glow_base
                glow_data[:, 6] = glow_alpha
                self._ghost_glow_vbo.write(glow_data.tobytes())

            ctx = self._renderer.ctx
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
            try:
                mvp_uniform = cast(moderngl.Uniform, self._ghost_glow_vao.program["mvp"])
                mvp_uniform.write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
                self._ghost_glow_vao.render(moderngl.TRIANGLES)
            finally:
                ctx.blend_func = moderngl.DEFAULT_BLENDING

    def render_timeline(
        self,
        renderer: GameRenderer,
        text_renderer: TextRendererProtocol | None,
        song_duration_ms: float,
    ) -> None:
        _ = song_duration_ms
        if text_renderer is None:
            return

        W = renderer.width
        H = renderer.height

        timeline_x = 0
        timeline_y = H - 40
        timeline_w = int(W * 0.75)
        timeline_h = 30

        cx = timeline_w // 2

        for event in self._upcoming_events:
            time_to_event = event.time_ms - self._current_time_ms
            if 0 < time_to_event <= 3000:
                x_offset = int((time_to_event / 3000.0) * (timeline_w // 2))
                dot_x = timeline_x + cx + x_offset
                dot_y = timeline_y + timeline_h // 2
                text_renderer.render(
                    "●",
                    dot_x,
                    dot_y,
                    color=NeonTheme.NEON_ORANGE.as_tuple(),
                    scale=0.6,
                    align="center",
                )

        text_renderer.render(
            "▼",
            timeline_x + cx,
            timeline_y,
            color=NeonTheme.NEON_PINK.as_tuple(),
            scale=0.8,
            align="center",
        )

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
