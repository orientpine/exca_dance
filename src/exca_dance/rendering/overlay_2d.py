"""2D joint comparison overlay for top/side viewports."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from exca_dance.core.kinematics import ExcavatorFK
    from exca_dance.core.models import JointName
    from exca_dance.rendering.renderer import GameRenderer


class Overlay2DRenderer:
    """Renders current vs target pose as colored line segments.

    Draws in the orthographic 2D viewports (top and side) using
    ``prog_solid`` with ``"3f 3f"`` format and ``moderngl.LINES``.
    """

    def __init__(
        self,
        renderer: GameRenderer,
        fk: ExcavatorFK,
    ) -> None:
        self._renderer: GameRenderer = renderer
        self._fk: ExcavatorFK = fk

    # ── internal helpers ──────────────────────────────────────────

    def _get_world_positions(
        self,
        viewport_name: str,
        angles: dict[JointName, float],
    ) -> list[tuple[float, float, float]]:
        """Convert FK 2D joint positions to 3D world coords."""
        if viewport_name == "top_2d":
            pts = self._fk.get_joint_positions_2d_top(angles)
            return [(x, y, 0.0) for x, y in pts]
        # side_2d: FK returns (x, z) tuples
        pts = self._fk.get_joint_positions_2d_side(angles)
        return [(x, 0.0, z) for x, z in pts]

    @staticmethod
    def _build_line_verts(
        positions: list[tuple[float, float, float]],
        color: tuple[float, float, float],
    ) -> list[float]:
        """Build GL_LINES vertex pairs for consecutive joints.

        Each pair of consecutive positions produces one line segment
        (2 vertices × 6 floats = pos3 + color3).
        """
        verts: list[float] = []
        cr, cg, cb = color
        for i in range(len(positions) - 1):
            x0, y0, z0 = positions[i]
            x1, y1, z1 = positions[i + 1]
            verts += [x0, y0, z0, cr, cg, cb]
            verts += [x1, y1, z1, cr, cg, cb]
        return verts

    def _project_to_screen(
        self,
        world_pos: tuple[float, float, float],
        mvp: np.ndarray,
        vp: tuple[int, int, int, int],
    ) -> tuple[int, int] | None:
        """Project a world position to pygame screen pixel coords.

        Args:
            world_pos: (x, y, z) in world space.
            mvp: 4x4 model-view-projection matrix (row-major).
            vp: Current GL viewport ``(x, y, w, h)``.

        Returns:
            ``(px, py)`` in pygame coords (top-left origin) or
            ``None`` if projection is degenerate.
        """
        p = np.array(
            [world_pos[0], world_pos[1], world_pos[2], 1.0],
            dtype="f4",
        )
        clip = mvp @ p
        if abs(clip[3]) < 1e-6:
            return None

        ndc_x = clip[0] / clip[3]
        ndc_y = clip[1] / clip[3]

        vp_x, vp_y, vp_w, vp_h = vp
        px = (ndc_x + 1.0) * vp_w / 2.0
        py = (ndc_y + 1.0) * vp_h / 2.0

        gl_x = vp_x + px
        gl_y = vp_y + py

        screen_h = self._renderer.height
        return (int(gl_x), int(screen_h - gl_y))

    # ── public API ────────────────────────────────────────────────

    def render(
        self,
        viewport_name: str,
        mvp: np.ndarray,
        current_angles: dict[JointName, float],
        target_angles: dict[JointName, float] | None,
        text_renderer: Any | None,
        match_pct: dict[JointName, float] | None,
    ) -> None:
        """Render 2D joint overlay in the given viewport.

        Draws the current pose as cyan line segments and the target
        pose (when provided) as violet line segments.  Optionally
        renders per-joint match percentage as text near each joint.

        The caller must set the GL viewport (via ``set_viewport``)
        before calling this method.  If text is rendered, the
        viewport is temporarily reset to full screen.
        """
        import moderngl

        from exca_dance.rendering.theme import NeonTheme

        ctx = self._renderer.ctx
        prog = self._renderer.prog_solid

        current_color = NeonTheme.NEON_BLUE.as_rgb()
        target_color = NeonTheme.GHOST_OUTLINE.as_rgb()

        current_pos = self._get_world_positions(
            viewport_name,
            current_angles,
        )
        verts = self._build_line_verts(current_pos, current_color)

        if target_angles is not None:
            target_pos = self._get_world_positions(
                viewport_name,
                target_angles,
            )
            verts += self._build_line_verts(
                target_pos,
                target_color,
            )

        if not verts:
            return

        # Capture viewport rect for text projection
        vp = ctx.viewport

        data = np.array(verts, dtype="f4")
        vbo = ctx.buffer(data.tobytes())
        vao = ctx.vertex_array(
            prog,
            [(vbo, "3f 3f", "in_position", "in_color")],
        )

        try:
            prog["mvp"].write(
                np.ascontiguousarray(
                    mvp.astype("f4").T,
                ).tobytes()
            )
            prog["alpha"].value = 1.0
            ctx.disable_direct(moderngl.DEPTH_TEST)
            vao.render(moderngl.LINES)
        finally:
            ctx.enable_direct(moderngl.DEPTH_TEST)
            vao.release()
            vbo.release()

        # Per-joint match text (requires full-screen viewport)
        if text_renderer is not None and match_pct is not None and current_pos:
            screen_pts = [self._project_to_screen(p, mvp, vp) for p in current_pos]
            ctx.viewport = (
                0,
                0,
                self._renderer.width,
                self._renderer.height,
            )
            self._render_match_text(
                screen_pts,
                match_pct,
                text_renderer,
            )

    def _render_match_text(
        self,
        screen_positions: list[tuple[int, int] | None],
        match_pct: dict[JointName, float],
        text_renderer: Any,
    ) -> None:
        """Render per-joint match % at projected screen positions."""
        from exca_dance.core.models import JointName

        # FK output order: base(0), swing(1), boom(2), arm(3), bucket(4)
        joint_map: dict[int, JointName] = {
            1: JointName.SWING,
            2: JointName.BOOM,
            3: JointName.ARM,
            4: JointName.BUCKET,
        }

        for idx, jname in joint_map.items():
            if idx >= len(screen_positions):
                continue
            if jname not in match_pct:
                continue
            pos = screen_positions[idx]
            if pos is None:
                continue
            sx, sy = pos
            pct = match_pct[jname]
            text_renderer.render(
                f"{int(pct)}%",
                sx + 8,
                sy - 8,
                color=(1.0, 1.0, 1.0, 1.0),
                scale=0.6,
            )
