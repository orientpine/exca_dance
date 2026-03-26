"""High-visibility 2D schematic overlay for top/side viewports.

Replaces the thin GL_LINES overlay with thick quad-based line segments,
filled circles at joint pivots, per-joint color coding, and match-quality
indicators.  Designed to be the *sole* renderer in the 2D panels (the 3D
ExcavatorModel is no longer drawn there).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from exca_dance.core.kinematics import ExcavatorFK
    from exca_dance.core.models import JointName
    from exca_dance.rendering.renderer import GameRenderer

# ── Per-link colors ──────────────────────────────────────────────────
# Index 0 = base→swing, 1 = boom, 2 = arm, 3 = bucket
_CURRENT_LINK_COLORS: list[tuple[float, float, float]] = [
    (0.45, 0.45, 0.55),  # base→swing: steel gray
    (1.0, 0.4, 0.0),  # boom: orange
    (1.0, 0.8, 0.0),  # arm: yellow
    (0.0, 0.8, 1.0),  # bucket: cyan
]

_TARGET_LINK_COLORS: list[tuple[float, float, float]] = [
    (0.5, 0.3, 0.9),  # base: violet
    (0.6, 0.4, 1.0),  # boom: vivid violet
    (0.8, 0.5, 1.0),  # arm: lavender
    (1.0, 0.7, 1.0),  # bucket: bright violet
]


class Overlay2DRenderer:
    """Renders high-visibility 2D schematics of current vs target pose.

    Uses thick quad-based line segments and filled circles instead of
    1-pixel ``GL_LINES``.  Renders both the current (bright per-joint
    colors) and target (violet/ghost) poses so the player can see the
    gap at a glance.
    """

    # Geometry tuning (world units — ortho projections map ~8–9 units
    # across 480 px, so 0.20 ≈ 11 px which is nicely visible).
    LINK_WIDTH: float = 0.20
    TARGET_LINK_WIDTH: float = 0.12
    JOINT_RADIUS: float = 0.16
    TARGET_JOINT_RADIUS: float = 0.10
    MATCH_RING_RADIUS: float = 0.24
    CIRCLE_SEGMENTS: int = 16
    ARROW_SIZE: float = 0.25
    ARROW_OFFSET: float = 0.40

    def __init__(
        self,
        renderer: GameRenderer,
        fk: ExcavatorFK,
    ) -> None:
        self._renderer: GameRenderer = renderer
        self._fk: ExcavatorFK = fk

    # ── Thick-line geometry (quads) ──────────────────────────────────

    @staticmethod
    def _thick_line_top(
        p1: tuple[float, float],
        p2: tuple[float, float],
        width: float,
        color: tuple[float, float, float],
    ) -> list[float]:
        """Quad for a thick segment in the XY plane (z=0)."""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-6:
            return []
        hw = width / 2.0
        nx = -dy / length * hw
        ny = dx / length * hw
        r, g, b = color
        # Four corners → two triangles
        ax, ay = p1[0] + nx, p1[1] + ny
        bx, by = p1[0] - nx, p1[1] - ny
        cx, cy = p2[0] + nx, p2[1] + ny
        ex, ey = p2[0] - nx, p2[1] - ny
        return [
            ax,
            ay,
            0.0,
            r,
            g,
            b,
            bx,
            by,
            0.0,
            r,
            g,
            b,
            cx,
            cy,
            0.0,
            r,
            g,
            b,
            bx,
            by,
            0.0,
            r,
            g,
            b,
            ex,
            ey,
            0.0,
            r,
            g,
            b,
            cx,
            cy,
            0.0,
            r,
            g,
            b,
        ]

    @staticmethod
    def _thick_line_side(
        p1: tuple[float, float],
        p2: tuple[float, float],
        width: float,
        color: tuple[float, float, float],
    ) -> list[float]:
        """Quad for a thick segment in the XZ plane (y=0)."""
        dx = p2[0] - p1[0]
        dz = p2[1] - p1[1]
        length = math.sqrt(dx * dx + dz * dz)
        if length < 1e-6:
            return []
        hw = width / 2.0
        nx = -dz / length * hw
        nz = dx / length * hw
        r, g, b = color
        ax, az = p1[0] + nx, p1[1] + nz
        bx, bz = p1[0] - nx, p1[1] - nz
        cx, cz = p2[0] + nx, p2[1] + nz
        ex, ez = p2[0] - nx, p2[1] - nz
        return [
            ax,
            0.0,
            az,
            r,
            g,
            b,
            bx,
            0.0,
            bz,
            r,
            g,
            b,
            cx,
            0.0,
            cz,
            r,
            g,
            b,
            bx,
            0.0,
            bz,
            r,
            g,
            b,
            ex,
            0.0,
            ez,
            r,
            g,
            b,
            cx,
            0.0,
            cz,
            r,
            g,
            b,
        ]

    # ── Circle geometry (triangle fan) ───────────────────────────────

    @staticmethod
    def _circle_top(
        center: tuple[float, float],
        radius: float,
        color: tuple[float, float, float],
        segments: int = 16,
    ) -> list[float]:
        """Filled circle in XY plane (z=0)."""
        cx, cy = center
        r, g, b = color
        verts: list[float] = []
        for i in range(segments):
            a0 = (i / segments) * 2.0 * math.pi
            a1 = ((i + 1) / segments) * 2.0 * math.pi
            verts += [
                cx,
                cy,
                0.0,
                r,
                g,
                b,
                cx + radius * math.cos(a0),
                cy + radius * math.sin(a0),
                0.0,
                r,
                g,
                b,
                cx + radius * math.cos(a1),
                cy + radius * math.sin(a1),
                0.0,
                r,
                g,
                b,
            ]
        return verts

    @staticmethod
    def _circle_side(
        center: tuple[float, float],
        radius: float,
        color: tuple[float, float, float],
        segments: int = 16,
    ) -> list[float]:
        """Filled circle in XZ plane (y=0)."""
        cx, cz = center
        r, g, b = color
        verts: list[float] = []
        for i in range(segments):
            a0 = (i / segments) * 2.0 * math.pi
            a1 = ((i + 1) / segments) * 2.0 * math.pi
            verts += [
                cx,
                0.0,
                cz,
                r,
                g,
                b,
                cx + radius * math.cos(a0),
                0.0,
                cz + radius * math.sin(a0),
                r,
                g,
                b,
                cx + radius * math.cos(a1),
                0.0,
                cz + radius * math.sin(a1),
                r,
                g,
                b,
            ]
        return verts

    # ── Direction arrow geometry ─────────────────────────────────────

    @staticmethod
    def _arrow_top(
        origin: tuple[float, float],
        target: tuple[float, float],
        size: float,
        offset: float,
        color: tuple[float, float, float],
    ) -> list[float]:
        """Small triangle arrow pointing from *origin* toward *target* (XY)."""
        dx = target[0] - origin[0]
        dy = target[1] - origin[1]
        length = math.sqrt(dx * dx + dy * dy)
        if length < 0.15:
            return []
        dx /= length
        dy /= length
        r, g, b = color
        tip_x = origin[0] + dx * offset
        tip_y = origin[1] + dy * offset
        base_x = origin[0] + dx * (offset - size)
        base_y = origin[1] + dy * (offset - size)
        px, py = -dy * size * 0.45, dx * size * 0.45
        return [
            tip_x,
            tip_y,
            0.0,
            r,
            g,
            b,
            base_x + px,
            base_y + py,
            0.0,
            r,
            g,
            b,
            base_x - px,
            base_y - py,
            0.0,
            r,
            g,
            b,
        ]

    @staticmethod
    def _arrow_side(
        origin: tuple[float, float],
        target: tuple[float, float],
        size: float,
        offset: float,
        color: tuple[float, float, float],
    ) -> list[float]:
        """Small triangle arrow pointing from *origin* toward *target* (XZ)."""
        dx = target[0] - origin[0]
        dz = target[1] - origin[1]
        length = math.sqrt(dx * dx + dz * dz)
        if length < 0.15:
            return []
        dx /= length
        dz /= length
        r, g, b = color
        tip_x = origin[0] + dx * offset
        tip_z = origin[1] + dz * offset
        base_x = origin[0] + dx * (offset - size)
        base_z = origin[1] + dz * (offset - size)
        px, pz = -dz * size * 0.45, dx * size * 0.45
        return [
            tip_x,
            0.0,
            tip_z,
            r,
            g,
            b,
            base_x + px,
            0.0,
            base_z + pz,
            r,
            g,
            b,
            base_x - px,
            0.0,
            base_z - pz,
            r,
            g,
            b,
        ]

    # ── Composite builders ───────────────────────────────────────────

    def _build_pose(
        self,
        viewport_name: str,
        positions: list[tuple[float, float]],
        link_colors: list[tuple[float, float, float]],
        joint_color: tuple[float, float, float],
        link_width: float,
        joint_radius: float,
    ) -> list[float]:
        """Build all geometry for one pose (links + joint circles)."""
        verts: list[float] = []
        is_top = viewport_name == "top_2d"
        line_fn = self._thick_line_top if is_top else self._thick_line_side
        circle_fn = self._circle_top if is_top else self._circle_side

        # Links between consecutive joints
        for i in range(len(positions) - 1):
            color = link_colors[min(i, len(link_colors) - 1)]
            verts += line_fn(positions[i], positions[i + 1], link_width, color)

        # Joint circles
        for pos in positions:
            verts += circle_fn(pos, joint_radius, joint_color, self.CIRCLE_SEGMENTS)

        return verts

    def _build_match_rings(
        self,
        viewport_name: str,
        positions: list[tuple[float, float]],
        match_pct: dict[JointName, float],
    ) -> list[float]:
        """Colored rings around joints to indicate match quality."""
        from exca_dance.core.models import JointName as JN
        from exca_dance.rendering.theme import NeonTheme

        verts: list[float] = []
        is_top = viewport_name == "top_2d"
        circle_fn = self._circle_top if is_top else self._circle_side
        joint_map: dict[int, JN] = {
            1: JN.SWING,
            2: JN.BOOM,
            3: JN.ARM,
            4: JN.BUCKET,
        }

        for idx, jname in joint_map.items():
            if idx >= len(positions) or jname not in match_pct:
                continue
            pct = match_pct[jname]
            if pct > 0.8:
                color = NeonTheme.MATCH_GOOD.as_rgb()
            elif pct > 0.5:
                color = NeonTheme.MATCH_MEDIUM.as_rgb()
            else:
                color = NeonTheme.MATCH_BAD.as_rgb()
            verts += circle_fn(positions[idx], self.MATCH_RING_RADIUS, color, self.CIRCLE_SEGMENTS)

        return verts

    def _build_direction_arrows(
        self,
        viewport_name: str,
        current_pts: list[tuple[float, float]],
        target_pts: list[tuple[float, float]],
    ) -> list[float]:
        """Arrows at each joint endpoint pointing toward target position."""
        verts: list[float] = []
        is_top = viewport_name == "top_2d"
        arrow_fn = self._arrow_top if is_top else self._arrow_side

        # Arrows at boom(2), arm(3), bucket(4) endpoints
        for i in (2, 3, 4):
            if i >= len(current_pts) or i >= len(target_pts):
                continue
            color = _CURRENT_LINK_COLORS[min(i - 1, len(_CURRENT_LINK_COLORS) - 1)]
            bright = (
                min(1.0, color[0] * 1.3),
                min(1.0, color[1] * 1.3),
                min(1.0, color[2] * 1.3),
            )
            verts += arrow_fn(
                current_pts[i],
                target_pts[i],
                self.ARROW_SIZE,
                self.ARROW_OFFSET,
                bright,
            )

        return verts

    # ── Screen projection (for text labels) ──────────────────────────

    def _project_to_screen(
        self,
        world_pos: tuple[float, float, float],
        mvp: np.ndarray,
        vp: tuple[int, int, int, int],
    ) -> tuple[int, int] | None:
        """Project world position → pygame screen pixel coords."""
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

    @staticmethod
    def _to_world(pos: tuple[float, float], viewport_name: str) -> tuple[float, float, float]:
        """Convert 2D FK position to 3D world coord for the given view."""
        if viewport_name == "top_2d":
            return (pos[0], pos[1], 0.0)
        return (pos[0], 0.0, pos[1])

    # ── GL draw helper ───────────────────────────────────────────────

    @staticmethod
    def _draw_triangles(
        ctx: Any,
        prog: Any,
        mvp: np.ndarray,
        verts: list[float],
        alpha: float,
    ) -> None:
        """Send vertex data to GPU and render as TRIANGLES.

        Input *verts* are 6 floats/vertex (pos3 + color3).  This method
        expands them to 9 floats/vertex (pos3 + color3 + normal3) so
        ``prog_solid``'s lighting calculation receives a valid normal
        instead of undefined (0,0,0)."""
        import moderngl

        raw = np.array(verts, dtype="f4").reshape(-1, 6)
        # Add a uniform upward normal — gives ~88% lighting intensity
        normals = np.broadcast_to(
            np.array([0.0, 0.0, 1.0], dtype="f4"), (raw.shape[0], 3)
        )
        data = np.column_stack((raw[:, :3], raw[:, 3:6], normals))
        data = np.ascontiguousarray(data)
        vbo = ctx.buffer(data.tobytes())
        vao = ctx.vertex_array(
            prog, [(vbo, "3f 3f 3f", "in_position", "in_color", "in_normal")]
        )
        try:
            prog["mvp"].write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
            prog["alpha"].value = alpha
            ctx.disable_direct(moderngl.DEPTH_TEST)
            vao.render(moderngl.TRIANGLES)
        finally:
            ctx.enable_direct(moderngl.DEPTH_TEST)
            vao.release()
            vbo.release()

    # ── Public API ───────────────────────────────────────────────────

    def render(
        self,
        viewport_name: str,
        mvp: np.ndarray,
        current_angles: dict[JointName, float],
        target_angles: dict[JointName, float] | None,
        text_renderer: Any | None,
        match_pct: dict[JointName, float] | None,
    ) -> None:
        """Render high-visibility 2D schematic overlay.

        Draws the current pose as bright per-joint-colored thick line
        segments and the target pose (when provided) as a violet ghost
        schematic underneath.  Joint circles are color-coded by match
        quality (green / yellow / red).
        """
        ctx = self._renderer.ctx
        prog = self._renderer.prog_solid

        # ── FK → 2D positions ────────────────────────────────────
        if viewport_name == "top_2d":
            current_pts = self._fk.get_joint_positions_2d_top(current_angles)
        else:
            current_pts = self._fk.get_joint_positions_2d_side(current_angles)

        target_pts: list[tuple[float, float]] | None = None
        if target_angles is not None:
            full_target: dict[JointName, float] = {j: 0.0 for j in current_angles}
            full_target.update(target_angles)
            if viewport_name == "top_2d":
                target_pts = self._fk.get_joint_positions_2d_top(full_target)
            else:
                target_pts = self._fk.get_joint_positions_2d_side(full_target)

        # Capture viewport rect for text projection later
        vp = ctx.viewport

        # ── Layer 1: Target pose (behind everything) ─────────────
        if target_pts is not None:
            target_verts = self._build_pose(
                viewport_name,
                target_pts,
                _TARGET_LINK_COLORS,
                (0.8, 0.6, 1.0),
                self.TARGET_LINK_WIDTH,
                self.TARGET_JOINT_RADIUS,
            )
            if target_verts:
                self._draw_triangles(ctx, prog, mvp, target_verts, alpha=0.55)

        # ── Layer 2: Match-quality rings ─────────────────────────
        if match_pct is not None and target_pts is not None:
            ring_verts = self._build_match_rings(viewport_name, current_pts, match_pct)
            if ring_verts:
                self._draw_triangles(ctx, prog, mvp, ring_verts, alpha=0.6)

        # ── Layer 3: Current pose (on top) ───────────────────────
        current_verts = self._build_pose(
            viewport_name,
            current_pts,
            _CURRENT_LINK_COLORS,
            (1.0, 1.0, 1.0),
            self.LINK_WIDTH,
            self.JOINT_RADIUS,
        )
        if current_verts:
            self._draw_triangles(ctx, prog, mvp, current_verts, alpha=1.0)

        # ── Layer 4: Direction arrows ────────────────────────────
        if target_pts is not None:
            arrow_verts = self._build_direction_arrows(viewport_name, current_pts, target_pts)
            if arrow_verts:
                self._draw_triangles(ctx, prog, mvp, arrow_verts, alpha=0.85)

        # ── Layer 5: Text labels ─────────────────────────────────
        if text_renderer is not None and match_pct is not None and current_pts:
            ctx.viewport = (
                0,
                0,
                self._renderer.width,
                self._renderer.height,
            )
            self._render_labels(viewport_name, mvp, vp, current_pts, match_pct, text_renderer)

    def _render_labels(
        self,
        viewport_name: str,
        mvp: np.ndarray,
        vp: tuple[int, int, int, int],
        current_pts: list[tuple[float, float]],
        match_pct: dict[JointName, float],
        text_renderer: Any,
    ) -> None:
        """Render per-joint match % and name labels at screen positions."""
        from exca_dance.core.models import JointName as JN
        from exca_dance.rendering.theme import NeonTheme

        joint_map: dict[int, tuple[JN, str]] = {
            1: (JN.SWING, "SW"),
            2: (JN.BOOM, "BM"),
            3: (JN.ARM, "AR"),
            4: (JN.BUCKET, "BK"),
        }

        for idx, (jname, label) in joint_map.items():
            if idx >= len(current_pts) or jname not in match_pct:
                continue
            world = self._to_world(current_pts[idx], viewport_name)
            pos = self._project_to_screen(world, mvp, vp)
            if pos is None:
                continue
            sx, sy = pos
            pct = match_pct[jname]

            # Color based on match quality
            if pct > 0.8:
                color = NeonTheme.MATCH_GOOD.as_tuple()
            elif pct > 0.5:
                color = NeonTheme.MATCH_MEDIUM.as_tuple()
            else:
                color = NeonTheme.MATCH_BAD.as_tuple()

            text_renderer.render(
                f"{label} {int(pct * 100)}%",
                sx + 12,
                sy - 12,
                color=color,
                scale=0.65,
            )
