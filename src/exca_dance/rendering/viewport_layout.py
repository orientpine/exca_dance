"""Multi-viewport layout for Exca Dance gameplay screen."""

from __future__ import annotations
from typing import Any
import numpy as np
from exca_dance.rendering.viewport import ViewportManager
from exca_dance.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT


def _perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    """Build a perspective projection matrix (column-major, OpenGL convention)."""
    f = 1.0 / np.tan(np.radians(fov_deg) / 2.0)
    m = np.zeros((4, 4), dtype="f4")
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def _ortho(
    left: float,
    right: float,
    bottom: float,
    top: float,
    near: float = -10.0,
    far: float = 10.0,
) -> np.ndarray:
    """Build an orthographic projection matrix."""
    m = np.zeros((4, 4), dtype="f4")
    m[0, 0] = 2.0 / (right - left)
    m[1, 1] = 2.0 / (top - bottom)
    m[2, 2] = -2.0 / (far - near)
    m[0, 3] = -(right + left) / (right - left)
    m[1, 3] = -(top + bottom) / (top - bottom)
    m[2, 3] = -(far + near) / (far - near)
    m[3, 3] = 1.0
    return m


def _look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    """Build a view (look-at) matrix."""
    f = target - eye
    f = f / np.linalg.norm(f)
    r = np.cross(f, up)
    r = r / np.linalg.norm(r)
    u = np.cross(r, f)
    m = np.eye(4, dtype="f4")
    m[0, :3] = r
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = -float(np.dot(r, eye))
    m[1, 3] = -float(np.dot(u, eye))
    m[2, 3] = float(np.dot(f, eye))
    return m


class GameViewportLayout:
    """
    Manages the 3-panel viewport layout for gameplay:
      - main_3d:  left 75%, perspective 3D view
      - top_2d:   right 25% top half, orthographic top-down
      - side_2d:  right 25% bottom half, orthographic side view
    """

    # Fixed camera for 3D view — 45° elevation, 30° azimuth
    _EYE_3D = np.array([6.0, -8.0, 5.0], dtype="f4")
    _TARGET_3D = np.array([2.0, 0.0, 1.5], dtype="f4")
    _UP_3D = np.array([0.0, 0.0, 1.0], dtype="f4")

    def __init__(
        self,
        renderer,
        width: int = SCREEN_WIDTH,
        height: int = SCREEN_HEIGHT,
    ) -> None:
        self._renderer = renderer
        self._vm = ViewportManager(width, height)
        self._width = width
        self._height = height
        self._build_matrices()

    def _build_matrices(self) -> None:
        """Pre-compute MVP matrices for each viewport."""
        # 3D perspective
        aspect_3d = self._vm.get_aspect_ratio("main_3d")
        proj_3d = _perspective(45.0, aspect_3d, 0.1, 100.0)
        view_3d = _look_at(self._EYE_3D, self._TARGET_3D, self._UP_3D)
        self._mvp_3d: np.ndarray = (proj_3d @ view_3d).astype("f4")

        # Top-down orthographic (XY plane, camera looks down -Z)
        top_eye = np.array([2.0, 0.0, 15.0], dtype="f4")
        top_center = np.array([2.0, 0.0, 0.0], dtype="f4")
        top_up = np.array([0.0, 1.0, 0.0], dtype="f4")
        view_top = _look_at(top_eye, top_center, top_up)
        proj_top = _ortho(-6.0, 8.0, -5.0, 8.0)
        self._mvp_top: np.ndarray = (proj_top @ view_top).astype("f4")

        # Side orthographic (XZ plane, looking along +Y)
        side_eye = np.array([0.0, -12.0, 3.0], dtype="f4")
        side_center = np.array([2.0, 0.0, 3.0], dtype="f4")
        side_up = np.array([0.0, 0.0, 1.0], dtype="f4")
        view_side = _look_at(side_eye, side_center, side_up)
        proj_side = _ortho(-5.0, 10.0, -2.0, 9.0)
        self._mvp_side: np.ndarray = (proj_side @ view_side).astype("f4")

    def render_all(self, excavator_model, joint_angles: dict[str, float]) -> None:
        """Render excavator in all 3 viewports."""
        ctx = self._renderer.ctx

        # 3D main view
        self._vm.set_viewport(ctx, "main_3d")
        ctx.clear(0.04, 0.04, 0.10, viewport=self._vm.get_viewport_rect("main_3d"))
        excavator_model.render_3d(self._mvp_3d)

        # Top-down view
        self._vm.set_viewport(ctx, "top_2d")
        ctx.clear(0.04, 0.04, 0.10, viewport=self._vm.get_viewport_rect("top_2d"))
        excavator_model.render_2d_top(self._mvp_top)

        # Side view
        self._vm.set_viewport(ctx, "side_2d")
        ctx.clear(0.04, 0.04, 0.10, viewport=self._vm.get_viewport_rect("side_2d"))
        excavator_model.render_2d_side(self._mvp_side)

        # Reset to full viewport
        ctx.viewport = (0, 0, self._width, self._height)

    def render_2d_grid(self, view_name: str) -> None:
        import moderngl

        from exca_dance.rendering.theme import NeonTheme

        ctx = self._renderer.ctx
        self._vm.set_viewport(ctx, view_name)

        r, g, b = (
            NeonTheme.TEXT_DIM.r * 0.4,
            NeonTheme.TEXT_DIM.g * 0.4,
            NeonTheme.TEXT_DIM.b * 0.4,
        )

        gr, gg, gb = (
            NeonTheme.NEON_GREEN.r * 0.5,
            NeonTheme.NEON_GREEN.g * 0.5,
            NeonTheme.NEON_GREEN.b * 0.5,
        )

        verts = []

        if view_name == "top_2d":
            mvp = self._mvp_top
            for y in range(-5, 9):
                c = (gr, gg, gb) if y == 0 else (r, g, b)
                verts += [-6, y, 0, c[0], c[1], c[2], 8, y, 0, c[0], c[1], c[2]]
            for x in range(-6, 9):
                c = (gr, gg, gb) if x == 0 else (r, g, b)
                verts += [x, -5, 0, c[0], c[1], c[2], x, 8, 0, c[0], c[1], c[2]]
        else:
            mvp = self._mvp_side
            for z in range(-2, 9):
                c = (gr, gg, gb) if z == 0 else (r, g, b)
                verts += [-5, 0, z, c[0], c[1], c[2], 10, 0, z, c[0], c[1], c[2]]
            for x in range(-5, 11):
                c = (gr, gg, gb) if x == 0 else (r, g, b)
                verts += [x, 0, -2, c[0], c[1], c[2], x, 0, 9, c[0], c[1], c[2]]

        if not verts:
            return

        data = np.array(verts, dtype="f4")
        vbo = ctx.buffer(data)
        prog = self._renderer.prog_solid
        vao = ctx.vertex_array(prog, [(vbo, "3f 3f", "in_position", "in_color")])

        prog["mvp"].write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
        prog["alpha"].value = 0.3

        try:
            ctx.disable_direct(moderngl.DEPTH_TEST)
            vao.render(moderngl.LINES)
        finally:
            ctx.enable_direct(moderngl.DEPTH_TEST)
            vao.release()
            vbo.release()

    def render_gameplay_background(self, beat_phase: float = 0.0) -> None:
        import moderngl

        from exca_dance.rendering.theme import NeonTheme

        ctx = self._renderer.ctx
        self._vm.set_viewport(ctx, "main_3d")

        beat = max(0.0, min(1.0, beat_phase))

        grid_r, grid_g, grid_b = (0.0, 0.4, 0.6)
        grid_alpha = 0.12 + 0.10 * beat

        verts: list[float] = []

        for y in range(-4, 5):
            verts += [-4, y, 0.0, grid_r, grid_g, grid_b, 8, y, 0.0, grid_r, grid_g, grid_b]
        for x in range(-4, 9):
            verts += [x, -4, 0.0, grid_r, grid_g, grid_b, x, 4, 0.0, grid_r, grid_g, grid_b]

        ring_specs = (
            (3.0, (2.0, 0.0, 0.0), NeonTheme.NEON_PINK, 0.08 + 0.05 * beat),
            (5.0, (2.0, 0.0, 0.0), NeonTheme.NEON_BLUE, 0.05 + 0.03 * beat),
        )

        segments = 32
        circle_verts: list[float] = []
        ring_alphas: list[float] = []
        for radius, center, color, alpha in ring_specs:
            cx, cy, cz = center
            ring_alphas.append(alpha)
            for i in range(segments):
                a0 = (i / segments) * 2.0 * np.pi
                a1 = ((i + 1) / segments) * 2.0 * np.pi
                x0 = cx + radius * np.cos(a0)
                y0 = cy + radius * np.sin(a0)
                x1 = cx + radius * np.cos(a1)
                y1 = cy + radius * np.sin(a1)
                circle_verts += [
                    x0,
                    y0,
                    cz,
                    color.r * 0.6,
                    color.g * 0.6,
                    color.b * 0.6,
                    x1,
                    y1,
                    cz,
                    color.r * 0.6,
                    color.g * 0.6,
                    color.b * 0.6,
                ]

        prog = self._renderer.prog_solid
        prog["mvp"].write(np.ascontiguousarray(self._mvp_3d.astype("f4").T).tobytes())

        if verts:
            grid_data = np.array(verts, dtype="f4")
            grid_vbo = ctx.buffer(grid_data)
            grid_vao = ctx.vertex_array(prog, [(grid_vbo, "3f 3f", "in_position", "in_color")])
            try:
                prog["alpha"].value = grid_alpha
                grid_vao.render(moderngl.LINES)
            finally:
                grid_vao.release()
                grid_vbo.release()

        if circle_verts:
            ring_data = np.array(circle_verts, dtype="f4")
            ring_vbo = ctx.buffer(ring_data)
            ring_vao = ctx.vertex_array(prog, [(ring_vbo, "3f 3f", "in_position", "in_color")])
            try:
                ring_line_count = segments * 2
                start = 0
                for alpha in ring_alphas:
                    prog["alpha"].value = alpha
                    ring_vao.render(moderngl.LINES, vertices=ring_line_count, first=start)
                    start += ring_line_count
            finally:
                ring_vao.release()
                ring_vbo.release()

        ctx.viewport = (0, 0, self._width, self._height)

    def render_viewport_decorations(self, text_renderer: Any | None) -> None:
        import moderngl

        from exca_dance.rendering.theme import NeonTheme

        ctx = self._renderer.ctx
        W = self._width
        H = self._height

        ctx.viewport = (0, 0, W, H)

        border_r, border_g, border_b = (
            NeonTheme.BORDER.r,
            NeonTheme.BORDER.g,
            NeonTheme.BORDER.b,
        )

        vx = (1440 / W) * 2.0 - 1.0
        hy = 1.0 - (540 / H) * 2.0

        lw = 2.0 / W
        lh = 2.0 / H

        r, g, b = border_r, border_g, border_b
        verts = [
            vx,
            -1.0,
            0.0,
            r,
            g,
            b,
            vx + lw,
            -1.0,
            0.0,
            r,
            g,
            b,
            vx + lw,
            1.0,
            0.0,
            r,
            g,
            b,
            vx,
            -1.0,
            0.0,
            r,
            g,
            b,
            vx + lw,
            1.0,
            0.0,
            r,
            g,
            b,
            vx,
            1.0,
            0.0,
            r,
            g,
            b,
            vx,
            hy,
            0.0,
            r,
            g,
            b,
            1.0,
            hy,
            0.0,
            r,
            g,
            b,
            1.0,
            hy + lh,
            0.0,
            r,
            g,
            b,
            vx,
            hy,
            0.0,
            r,
            g,
            b,
            1.0,
            hy + lh,
            0.0,
            r,
            g,
            b,
            vx,
            hy + lh,
            0.0,
            r,
            g,
            b,
        ]
        data = np.array(verts, dtype="f4")
        vbo = ctx.buffer(data)
        prog = self._renderer.prog_solid
        vao = ctx.vertex_array(prog, [(vbo, "3f 3f", "in_position", "in_color")])

        identity = np.eye(4, dtype="f4")
        prog["mvp"].write(np.ascontiguousarray(identity).tobytes())
        prog["alpha"].value = NeonTheme.BORDER.a

        try:
            ctx.disable_direct(moderngl.DEPTH_TEST)
            vao.render(moderngl.TRIANGLES)
        finally:
            ctx.enable_direct(moderngl.DEPTH_TEST)
            vao.release()
            vbo.release()

        if text_renderer is not None:
            label_color = NeonTheme.TEXT_DIM.as_tuple()
            text_renderer.render("3D VIEW", 10, H - 25, color=label_color, scale=0.7)
            text_renderer.render("TOP", W - 470, H - 25, color=label_color, scale=0.7)
            text_renderer.render("SIDE", W - 470, 540 - 25, color=label_color, scale=0.7)

    @property
    def mvp_3d(self) -> np.ndarray:
        return self._mvp_3d

    @property
    def mvp_top(self) -> np.ndarray:
        return self._mvp_top

    @property
    def mvp_side(self) -> np.ndarray:
        return self._mvp_side

    @property
    def viewport_manager(self) -> ViewportManager:
        return self._vm
