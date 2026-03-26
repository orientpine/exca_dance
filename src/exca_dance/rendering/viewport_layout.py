"""Multi-viewport layout for Exca Dance gameplay screen."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from exca_dance.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from exca_dance.rendering.viewport import ViewportManager


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
    Manages the multi-panel viewport layout for gameplay:

      ┌─────────────────┬───────────────────┐
      │    main_3d       │     side_2d       │  top 72%
      │   (55% width)    │  kinematic diagram│
      │   perspective    │  (45%, top 65%)   │
      │                  ├───────────────────┤
      │                  │     top_2d        │
      │                  │  swing view       │
      │                  │  (45%, bot 35%)   │
      ├──────────────────┴───────────────────┤
      │          timeline area               │  bottom 28%
      └─────────────────────────────────────-┘
    """

    # Fixed camera for 3D view — 45° elevation, 30° azimuth
    _EYE_3D = np.array([6.0, -8.0, 5.0], dtype="f4")
    _TARGET_3D = np.array([2.0, 0.0, 1.5], dtype="f4")
    _UP_3D = np.array([0.0, 0.0, 1.0], dtype="f4")

    def __init__(
        self,
        renderer: Any,
        width: int = SCREEN_WIDTH,
        height: int = SCREEN_HEIGHT,
    ) -> None:
        self._renderer = renderer
        self._vm = ViewportManager(width, height)
        self._width = width
        self._height = height
        self._build_matrices()

    def _build_matrices(self) -> None:
        """Pre-compute MVP matrices for each viewport (aspect-matched)."""
        # ── 3D perspective ───────────────────────────────────────────
        aspect_3d = self._vm.get_aspect_ratio("main_3d")
        proj_3d = _perspective(45.0, aspect_3d, 0.1, 100.0)
        view_3d = _look_at(self._EYE_3D, self._TARGET_3D, self._UP_3D)
        self._mvp_3d: np.ndarray = (proj_3d @ view_3d).astype("f4")

        # ── Side orthographic (XZ plane, looking along +Y) ──────────
        # Aspect-matched to avoid distortion in the wider side panel.
        aspect_side = self._vm.get_aspect_ratio("side_2d")
        side_half_h = 3.5
        side_half_w = side_half_h * aspect_side
        self._proj_side: np.ndarray = _ortho(
            1.0 - side_half_w,
            1.0 + side_half_w,
            -side_half_h,
            side_half_h,
            near=-50.0,
            far=50.0,
        )
        side_eye = np.array([0.0, -12.0, 3.0], dtype="f4")
        side_center = np.array([2.0, 0.0, 3.0], dtype="f4")
        side_up = np.array([0.0, 0.0, 1.0], dtype="f4")
        self._view_side: np.ndarray = _look_at(side_eye, side_center, side_up)
        self._mvp_side: np.ndarray = (self._proj_side @ self._view_side).astype("f4")

        # ── Top-down orthographic (XY plane, camera looks down -Z) ──
        aspect_top = self._vm.get_aspect_ratio("top_2d")
        top_half_h = 3.5
        top_half_w = top_half_h * aspect_top
        proj_top = _ortho(
            1.0 - top_half_w,
            1.0 + top_half_w,
            -top_half_h,
            top_half_h,
            near=-50.0,
            far=50.0,
        )
        top_eye = np.array([2.0, 0.0, 15.0], dtype="f4")
        top_center = np.array([2.0, 0.0, 0.0], dtype="f4")
        top_up = np.array([0.0, 1.0, 0.0], dtype="f4")
        view_top = _look_at(top_eye, top_center, top_up)
        self._mvp_top: np.ndarray = (proj_top @ view_top).astype("f4")

    # ── Rendering ────────────────────────────────────────────────────

    def render_all(self, excavator_model: Any, joint_angles: dict[str, float]) -> None:
        """Render excavator in main 3D viewport; clear 2D panels and timeline."""
        ctx = self._renderer.ctx

        # 3D main view
        self._vm.set_viewport(ctx, "main_3d")
        ctx.clear(0.04, 0.04, 0.10, viewport=self._vm.get_viewport_rect("main_3d"))
        excavator_model.render_3d(self._mvp_3d)

        # 2D panels — clear only (overlay_2d renders the schematic)
        ctx.clear(0.03, 0.03, 0.07, viewport=self._vm.get_viewport_rect("side_2d"))
        ctx.clear(0.03, 0.03, 0.07, viewport=self._vm.get_viewport_rect("top_2d"))

        # Timeline — clear to deep dark
        ctx.clear(0.025, 0.025, 0.065, viewport=self._vm.timeline_rect)

        # Reset to full viewport
        ctx.viewport = (0, 0, self._width, self._height)

    def render_2d_grid(self, view_name: str) -> None:
        """Draw reference grid in a 2D viewport (top view only for new layout)."""
        import moderngl

        from exca_dance.rendering.theme import NeonTheme

        ctx = self._renderer.ctx
        self._vm.set_viewport(ctx, view_name)

        r, g, b = (
            NeonTheme.TEXT_DIM.r * 0.25,
            NeonTheme.TEXT_DIM.g * 0.25,
            NeonTheme.TEXT_DIM.b * 0.30,
        )
        gr, gg, gb = (
            NeonTheme.NEON_GREEN.r * 0.35,
            NeonTheme.NEON_GREEN.g * 0.35,
            NeonTheme.NEON_GREEN.b * 0.35,
        )

        verts: list[float] = []

        if view_name == "top_2d":
            mvp = self._mvp_top
            # Wider range for aspect-matched top viewport
            for y in range(-6, 7):
                c = (gr, gg, gb) if y == 0 else (r, g, b)
                verts += [-6, y, 0, c[0], c[1], c[2], 12, y, 0, c[0], c[1], c[2]]
            for x in range(-6, 13):
                c = (gr, gg, gb) if x == 0 else (r, g, b)
                verts += [x, -6, 0, c[0], c[1], c[2], x, 6, 0, c[0], c[1], c[2]]
        else:
            mvp = self._mvp_side
            for z in range(-1, 8):
                c = (gr, gg, gb) if z == 0 else (r, g, b)
                verts += [-3, 0, z, c[0], c[1], c[2], 9, 0, z, c[0], c[1], c[2]]
            for x in range(-3, 10):
                c = (gr, gg, gb) if x == 0 else (r, g, b)
                verts += [x, 0, -1, c[0], c[1], c[2], x, 0, 8, c[0], c[1], c[2]]

        if not verts:
            return

        data = np.array(verts, dtype="f4")
        vbo = ctx.buffer(data)
        prog = self._renderer.prog_solid
        vao = ctx.vertex_array(prog, [(vbo, "3f 3f", "in_position", "in_color")])

        prog["mvp"].write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
        prog["alpha"].value = 0.5

        try:
            ctx.disable_direct(moderngl.DEPTH_TEST)
            vao.render(moderngl.LINES)
        finally:
            ctx.enable_direct(moderngl.DEPTH_TEST)
            vao.release()
            vbo.release()

    def render_gameplay_background(self, beat_phase: float = 0.0) -> None:
        """Render ground grid and neon rings in the 3D viewport."""
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
        """Render panel borders and labels for the new layout."""
        import moderngl

        from exca_dance.rendering.theme import NeonTheme

        ctx = self._renderer.ctx
        W = self._width
        H = self._height
        ctx.viewport = (0, 0, W, H)

        cr, cg, cb = NeonTheme.BORDER.r, NeonTheme.BORDER.g, NeonTheme.BORDER.b
        lw = 2.0 / W  # ~1px in NDC
        lh = 2.0 / H

        main_3d = self._vm.get_viewport_rect("main_3d")
        top_2d = self._vm.get_viewport_rect("top_2d")
        tl = self._vm.timeline_rect

        # Helper: GL pixel → NDC
        def nx(px: float) -> float:
            return (px / W) * 2.0 - 1.0

        def ny(py: float) -> float:
            return (py / H) * 2.0 - 1.0

        verts: list[float] = []

        def _quad(x0: float, y0: float, x1: float, y1: float) -> None:
            verts.extend(
                [
                    x0,
                    y0,
                    0,
                    cr,
                    cg,
                    cb,
                    x1,
                    y0,
                    0,
                    cr,
                    cg,
                    cb,
                    x1,
                    y1,
                    0,
                    cr,
                    cg,
                    cb,
                    x0,
                    y0,
                    0,
                    cr,
                    cg,
                    cb,
                    x1,
                    y1,
                    0,
                    cr,
                    cg,
                    cb,
                    x0,
                    y1,
                    0,
                    cr,
                    cg,
                    cb,
                ]
            )

        # 1) Vertical border — right edge of main_3d → full main area height
        vx = nx(main_3d[0] + main_3d[2])
        vy_bot = ny(tl[1] + tl[3])
        _quad(vx, vy_bot, vx + lw, 1.0)

        # 2) Horizontal border — top of timeline → full width
        hy = ny(tl[1] + tl[3])
        _quad(-1.0, hy, 1.0, hy + lh)

        # 3) Horizontal border — between side and top views (right panel only)
        hy2 = ny(top_2d[1] + top_2d[3])
        _quad(vx, hy2, 1.0, hy2 + lh)

        if verts:
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

        # ── Panel labels ─────────────────────────────────────────────
        if text_renderer is not None:
            label_color = NeonTheme.TEXT_DIM.as_tuple()

            # "3D VIEW" — top-left of 3D viewport (screen y = 0)
            text_renderer.render("3D VIEW", 12, 8, color=label_color, scale=0.7)

            # "JOINT DIAGRAM" — top-left of side viewport (screen y = 0)
            side_2d = self._vm.get_viewport_rect("side_2d")
            text_renderer.render(
                "JOINT DIAGRAM",
                side_2d[0] + 12,
                8,
                color=label_color,
                scale=0.7,
            )

            # "TOP VIEW" — top-left of top viewport
            top_screen_y = H - (top_2d[1] + top_2d[3])
            text_renderer.render(
                "TOP VIEW",
                top_2d[0] + 12,
                top_screen_y + 8,
                color=label_color,
                scale=0.7,
            )

    # ── Properties ───────────────────────────────────────────────────

    @property
    def mvp_3d(self) -> np.ndarray:
        return self._mvp_3d

    @property
    def mvp_top(self) -> np.ndarray:
        return self._mvp_top

    @property
    def mvp_side(self) -> np.ndarray:
        return self._mvp_side

    def get_side_mvp_for_swing(self, swing_deg: float) -> np.ndarray:
        """Return a side-view MVP that counter-rotates swing out of the model.

        The 3D excavator has swing rotation baked into its FK geometry.
        Multiplying by Rz(-swing) undoes that rotation so the arm always
        faces the fixed side camera, keeping boom/arm/bucket visible.
        """
        swing_rad = math.radians(swing_deg)
        cs = math.cos(swing_rad)
        ss = math.sin(swing_rad)
        # Rz(-swing): counter-rotate to cancel swing in the geometry
        model = np.array(
            [
                [cs, ss, 0.0, 0.0],
                [-ss, cs, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype="f4",
        )
        return (self._proj_side @ self._view_side @ model).astype("f4")

    @property
    def viewport_manager(self) -> ViewportManager:
        return self._vm
