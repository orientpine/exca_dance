"""High-visibility 2D schematic overlay for top/side viewports.

Side view: Pure 2D kinematic diagram with angle arcs for boom/arm/bucket.
Top view: Overhead swing-angle visualization with per-joint coloring.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np
from exca_dance.core.constants import DEFAULT_JOINT_ANGLES

if TYPE_CHECKING:
    from exca_dance.core.kinematics import ExcavatorFK
    from exca_dance.core.models import JointName
    from exca_dance.rendering.renderer import GameRenderer

# ── Per-link colors ──────────────────────────────────────────────────
# Index 0 = base→swing, 1 = boom, 2 = arm, 3 = bucket
_CURRENT_LINK_COLORS: list[tuple[float, float, float]] = [
    (0.55, 0.55, 0.65),  # base→swing: bright steel gray
    (1.0, 0.5, 0.05),  # boom: vivid orange
    (1.0, 0.9, 0.1),  # arm: bright yellow
    (0.1, 0.9, 1.0),  # bucket: bright cyan
]

_TARGET_LINK_COLORS: list[tuple[float, float, float]] = [
    (0.0, 0.45, 0.55),  # base: teal (intro style)
    (1.0, 0.0, 0.40),  # boom: neon pink
    (0.67, 0.0, 1.0),  # arm: neon purple
    (0.0, 1.0, 0.53),  # bucket: neon green
]

_TARGET_OUTLINE_COLORS: list[tuple[float, float, float]] = [
    (0.0, 0.55, 0.65),  # base: bright teal
    (1.0, 0.25, 0.55),  # boom: bright pink
    (0.78, 0.25, 1.0),  # arm: bright purple
    (0.25, 1.0, 0.65),  # bucket: bright green
]

_CURRENT_OUTLINE_COLORS: list[tuple[float, float, float]] = [
    (0.75, 0.75, 0.85),  # base: bright silver
    (1.0, 0.70, 0.20),  # boom: bright orange
    (1.0, 1.0, 0.30),  # arm: bright yellow
    (0.30, 1.0, 1.0),  # bucket: bright cyan
]


class Overlay2DRenderer:
    """Renders high-visibility 2D schematics of current vs target pose.

    **Side view**: Pure kinematic diagram — thick link segments with
    angle arc indicators at each joint (boom/arm/bucket).  No 3D
    projection feel; shows joint mechanics directly.

    **Top view**: Overhead schematic showing swing rotation with the
    same thick-line style.
    """

    # Geometry tuning (world units)
    LINK_WIDTH: float = 0.45
    TARGET_LINK_WIDTH: float = 0.70
    JOINT_RADIUS: float = 0.32
    TARGET_JOINT_RADIUS: float = 0.40
    MATCH_RING_RADIUS: float = 0.45
    CIRCLE_SEGMENTS: int = 24
    ARROW_SIZE: float = 0.55
    ARROW_OFFSET: float = 0.80
    ARC_RADIUS: float = 0.90
    ARC_SEGMENTS: int = 28
    OUTLINE_EXTRA: float = 0.14
    JOINT_RING_WIDTH: float = 0.12
    GHOST_OUTLINE_T: float = 0.08
    GHOST_GLOW_T: float = 0.18

    def __init__(
        self,
        renderer: GameRenderer,
        fk: ExcavatorFK,
    ) -> None:
        self._renderer: GameRenderer = renderer
        self._fk: ExcavatorFK = fk
        # Pre-allocated draw buffer for _draw_triangles (avoids per-call VBO alloc)
        ctx = renderer.ctx
        self._draw_vbo: object = ctx.buffer(reserve=8192 * 9 * 4)  # ~8K vertices
        self._draw_vao: object = ctx.vertex_array(
            renderer.prog_solid,
            [(self._draw_vbo, "3f 3f 3f", "in_position", "in_color", "in_normal")],
        )
        self._z_normal: np.ndarray = np.array([0.0, 0.0, 1.0], dtype="f4")

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

    # ── Arc sector geometry (for angle indicators) ───────────────────

    @staticmethod
    def _arc_sector_side(
        center: tuple[float, float],
        radius: float,
        start_rad: float,
        end_rad: float,
        color: tuple[float, float, float],
        segments: int = 24,
    ) -> list[float]:
        """Filled arc sector (pie slice) in XZ plane (y=0)."""
        cx, cz = center
        r, g, b = color
        verts: list[float] = []
        delta = end_rad - start_rad
        if abs(delta) < 0.02:
            return verts
        for i in range(segments):
            a0 = start_rad + delta * (i / segments)
            a1 = start_rad + delta * ((i + 1) / segments)
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

    @staticmethod
    def _arc_outline_side(
        center: tuple[float, float],
        radius: float,
        start_rad: float,
        end_rad: float,
        color: tuple[float, float, float],
        width: float = 0.04,
        segments: int = 24,
    ) -> list[float]:
        """Arc outline (thick line along the arc) in XZ plane."""
        cx, cz = center
        verts: list[float] = []
        delta = end_rad - start_rad
        if abs(delta) < 0.02:
            return verts
        r_inner = radius - width / 2.0
        r_outer = radius + width / 2.0
        r, g, b = color
        for i in range(segments):
            a0 = start_rad + delta * (i / segments)
            a1 = start_rad + delta * ((i + 1) / segments)
            # Quad strip: inner → outer
            ix0 = cx + r_inner * math.cos(a0)
            iz0 = cz + r_inner * math.sin(a0)
            ox0 = cx + r_outer * math.cos(a0)
            oz0 = cz + r_outer * math.sin(a0)
            ix1 = cx + r_inner * math.cos(a1)
            iz1 = cz + r_inner * math.sin(a1)
            ox1 = cx + r_outer * math.cos(a1)
            oz1 = cz + r_outer * math.sin(a1)
            verts += [
                ix0,
                0.0,
                iz0,
                r,
                g,
                b,
                ox0,
                0.0,
                oz0,
                r,
                g,
                b,
                ox1,
                0.0,
                oz1,
                r,
                g,
                b,
                ix0,
                0.0,
                iz0,
                r,
                g,
                b,
                ox1,
                0.0,
                oz1,
                r,
                g,
                b,
                ix1,
                0.0,
                iz1,
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
        px, py = -dy * size * 0.50, dx * size * 0.50
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
        px, pz = -dz * size * 0.50, dx * size * 0.50
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
        """Build link geometry for one pose (thick lines between joints)."""
        verts: list[float] = []
        is_top = viewport_name == "top_2d"
        line_fn = self._thick_line_top if is_top else self._thick_line_side

        # Links between consecutive joints
        for i in range(len(positions) - 1):
            color = link_colors[min(i, len(link_colors) - 1)]
            verts += line_fn(positions[i], positions[i + 1], link_width, color)

        return verts

    @staticmethod
    def _ring_top(
        center: tuple[float, float],
        radius: float,
        width: float,
        color: tuple[float, float, float],
        segments: int = 20,
    ) -> list[float]:
        """Ring (hollow circle outline) in XY plane (z=0)."""
        r_in = radius - width / 2.0
        r_out = radius + width / 2.0
        r, g, b = color
        cx, cy = center
        verts: list[float] = []
        for i in range(segments):
            a0 = (i / segments) * 2.0 * math.pi
            a1 = ((i + 1) / segments) * 2.0 * math.pi
            c0, s0 = math.cos(a0), math.sin(a0)
            c1, s1 = math.cos(a1), math.sin(a1)
            verts += [
                cx + r_in * c0,
                cy + r_in * s0,
                0.0,
                r,
                g,
                b,
                cx + r_out * c0,
                cy + r_out * s0,
                0.0,
                r,
                g,
                b,
                cx + r_out * c1,
                cy + r_out * s1,
                0.0,
                r,
                g,
                b,
                cx + r_in * c0,
                cy + r_in * s0,
                0.0,
                r,
                g,
                b,
                cx + r_out * c1,
                cy + r_out * s1,
                0.0,
                r,
                g,
                b,
                cx + r_in * c1,
                cy + r_in * s1,
                0.0,
                r,
                g,
                b,
            ]
        return verts

    @staticmethod
    def _ring_side(
        center: tuple[float, float],
        radius: float,
        width: float,
        color: tuple[float, float, float],
        segments: int = 20,
    ) -> list[float]:
        """Ring (hollow circle outline) in XZ plane (y=0)."""
        r_in = radius - width / 2.0
        r_out = radius + width / 2.0
        r, g, b = color
        cx, cz = center
        verts: list[float] = []
        for i in range(segments):
            a0 = (i / segments) * 2.0 * math.pi
            a1 = ((i + 1) / segments) * 2.0 * math.pi
            c0, s0 = math.cos(a0), math.sin(a0)
            c1, s1 = math.cos(a1), math.sin(a1)
            verts += [
                cx + r_in * c0,
                0.0,
                cz + r_in * s0,
                r,
                g,
                b,
                cx + r_out * c0,
                0.0,
                cz + r_out * s0,
                r,
                g,
                b,
                cx + r_out * c1,
                0.0,
                cz + r_out * s1,
                r,
                g,
                b,
                cx + r_in * c0,
                0.0,
                cz + r_in * s0,
                r,
                g,
                b,
                cx + r_out * c1,
                0.0,
                cz + r_out * s1,
                r,
                g,
                b,
                cx + r_in * c1,
                0.0,
                cz + r_in * s1,
                r,
                g,
                b,
            ]
        return verts

    def _build_joint_markers(
        self,
        viewport_name: str,
        positions: list[tuple[float, float]],
        colors: list[tuple[float, float, float]],
        radius: float,
    ) -> list[float]:
        """Build filled circles at each joint position."""
        verts: list[float] = []
        is_top = viewport_name == "top_2d"
        circle_fn = self._circle_top if is_top else self._circle_side
        for i, pos in enumerate(positions):
            color = colors[min(i, len(colors) - 1)]
            verts += circle_fn(pos, radius, color, self.CIRCLE_SEGMENTS)
        return verts

    def _build_joint_rings(
        self,
        viewport_name: str,
        positions: list[tuple[float, float]],
        colors: list[tuple[float, float, float]],
        radius: float,
        width: float,
    ) -> list[float]:
        """Build ring outlines at each joint position."""
        verts: list[float] = []
        is_top = viewport_name == "top_2d"
        ring_fn = self._ring_top if is_top else self._ring_side
        for i, pos in enumerate(positions):
            color = colors[min(i, len(colors) - 1)]
            verts += ring_fn(pos, radius, width, color, self.CIRCLE_SEGMENTS)
        return verts

    @staticmethod
    def _link_outline_top(
        p1: tuple[float, float],
        p2: tuple[float, float],
        width: float,
        outline_t: float,
        color: tuple[float, float, float],
    ) -> list[float]:
        """Hollow rectangle outline for a link in XY plane (z=0)."""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-6:
            return []
        hw = width / 2.0
        nx = -dy / length * hw
        ny = dx / length * hw
        a = (p1[0] + nx, p1[1] + ny)
        b = (p1[0] - nx, p1[1] - ny)
        c = (p2[0] + nx, p2[1] + ny)
        d = (p2[0] - nx, p2[1] - ny)
        tl = Overlay2DRenderer._thick_line_top
        verts: list[float] = []
        verts += tl(a, c, outline_t, color)  # top edge
        verts += tl(b, d, outline_t, color)  # bottom edge
        verts += tl(a, b, outline_t, color)  # left cap
        verts += tl(c, d, outline_t, color)  # right cap
        return verts

    @staticmethod
    def _link_outline_side(
        p1: tuple[float, float],
        p2: tuple[float, float],
        width: float,
        outline_t: float,
        color: tuple[float, float, float],
    ) -> list[float]:
        """Hollow rectangle outline for a link in XZ plane (y=0)."""
        dx = p2[0] - p1[0]
        dz = p2[1] - p1[1]
        length = math.sqrt(dx * dx + dz * dz)
        if length < 1e-6:
            return []
        hw = width / 2.0
        nx = -dz / length * hw
        nz = dx / length * hw
        a = (p1[0] + nx, p1[1] + nz)
        b = (p1[0] - nx, p1[1] - nz)
        c = (p2[0] + nx, p2[1] + nz)
        d = (p2[0] - nx, p2[1] - nz)
        tl = Overlay2DRenderer._thick_line_side
        verts: list[float] = []
        verts += tl(a, c, outline_t, color)
        verts += tl(b, d, outline_t, color)
        verts += tl(a, b, outline_t, color)
        verts += tl(c, d, outline_t, color)
        return verts

    def _build_pose_outline(
        self,
        viewport_name: str,
        positions: list[tuple[float, float]],
        link_colors: list[tuple[float, float, float]],
        link_width: float,
        outline_thickness: float,
    ) -> list[float]:
        """Build hollow rectangle outlines for each link (wireframe ghost)."""
        verts: list[float] = []
        is_top = viewport_name == "top_2d"
        outline_fn = self._link_outline_top if is_top else self._link_outline_side
        for i in range(len(positions) - 1):
            color = link_colors[min(i, len(link_colors) - 1)]
            verts += outline_fn(
                positions[i],
                positions[i + 1],
                link_width,
                outline_thickness,
                color,
            )
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

        for i in (2, 3, 4):
            if i >= len(current_pts) or i >= len(target_pts):
                continue
            color = _CURRENT_LINK_COLORS[min(i - 1, len(_CURRENT_LINK_COLORS) - 1)]
            bright = (
                min(1.0, color[0] * 1.5),
                min(1.0, color[1] * 1.5),
                min(1.0, color[2] * 1.5),
            )
            verts += arrow_fn(
                current_pts[i],
                target_pts[i],
                self.ARROW_SIZE,
                self.ARROW_OFFSET,
                bright,
            )

        return verts

    # ── Side-view angle arcs ─────────────────────────────────────────

    def _build_angle_arcs(
        self,
        positions: list[tuple[float, float]],
        current_angles: dict[JointName, float],
        target_angles: dict[JointName, float] | None,
        match_pct: dict[JointName, float] | None,
    ) -> list[float]:
        """Build angle arc indicators at each joint for the side view.

        Draws:
        - Filled arc sector showing current joint angle
        - Thin arc outline in match-quality color
        - Reference direction line (where angle = 0)
        """
        from exca_dance.core.models import JointName as JN
        from exca_dance.rendering.theme import NeonTheme

        verts: list[float] = []
        if len(positions) < 5:
            return verts

        # Joint data: (pivot_index, joint_name, reference_angle_rad)
        # Reference angle = cumulative angle of the incoming link
        boom_angle_rad = math.radians(current_angles.get(JN.BOOM, 0.0))
        arm_angle_rad = math.radians(current_angles.get(JN.ARM, 0.0))

        joints_info = [
            (1, JN.BOOM, 0.0, boom_angle_rad),
            (2, JN.BOOM, boom_angle_rad, arm_angle_rad),
            (
                3,
                JN.ARM,
                boom_angle_rad + arm_angle_rad,
                math.radians(current_angles.get(JN.BUCKET, 0.0)),
            ),
        ]

        for pivot_idx, jname, ref_angle, joint_angle in joints_info:
            if pivot_idx >= len(positions):
                continue

            center = positions[pivot_idx]
            start = ref_angle
            end = ref_angle + joint_angle
            arc_radius = self.ARC_RADIUS

            # Choose color based on match quality
            if match_pct is not None and jname in match_pct:
                pct = match_pct[jname]
                if pct > 0.8:
                    arc_color = NeonTheme.MATCH_GOOD.as_rgb()
                elif pct > 0.5:
                    arc_color = NeonTheme.MATCH_MEDIUM.as_rgb()
                else:
                    arc_color = NeonTheme.MATCH_BAD.as_rgb()
            else:
                arc_color = NeonTheme.DIAGRAM_ARC_FILL.as_rgb()

            # Filled arc sector (semi-transparent)
            fill_color = (arc_color[0] * 0.5, arc_color[1] * 0.5, arc_color[2] * 0.5)
            verts += self._arc_sector_side(
                center,
                arc_radius * 0.85,
                start,
                end,
                fill_color,
                self.ARC_SEGMENTS,
            )

            # Arc outline (bright)
            verts += self._arc_outline_side(
                center,
                arc_radius,
                start,
                end,
                arc_color,
                width=0.07,
                segments=self.ARC_SEGMENTS,
            )

            # Reference direction line (thin, dim)
            ref_color = NeonTheme.DIAGRAM_REF_LINE.as_rgb()
            ref_len = arc_radius + 0.15
            ref_end = (
                center[0] + ref_len * math.cos(start),
                center[1] + ref_len * math.sin(start),
            )
            verts += self._thick_line_side(center, ref_end, 0.05, ref_color)

        return verts

    def _build_side_background(self) -> list[float]:
        """Build background geometry for the side-view kinematic diagram.

        Draws a ground reference line and subtle tick marks instead of a
        3D-style grid.  This gives a clean mechanical-diagram aesthetic.
        """
        from exca_dance.rendering.theme import NeonTheme

        verts: list[float] = []
        ground_color = NeonTheme.DIAGRAM_GROUND.as_rgb()
        grid_color = NeonTheme.DIAGRAM_GRID.as_rgb()

        # Ground line at z=0 (prominent)
        verts += self._thick_line_side((-4.0, 0.0), (10.0, 0.0), 0.08, ground_color)

        # Subtle vertical reference at x=0
        verts += self._thick_line_side((0.0, -0.3), (0.0, 7.0), 0.04, grid_color)

        # Tick marks along ground every 1 unit
        for x in range(-3, 10):
            tick_h = 0.15 if x % 2 == 0 else 0.08
            verts += self._thick_line_side(
                (float(x), -tick_h),
                (float(x), tick_h),
                0.03,
                grid_color,
            )

        # Horizontal reference lines every 2 units (subtle)
        for z in range(2, 8, 2):
            verts += self._thick_line_side((-3.0, float(z)), (9.0, float(z)), 0.025, grid_color)

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

    def _draw_triangles(
        self,
        ctx: Any,
        prog: Any,
        mvp: np.ndarray,
        verts: list[float],
        alpha: float,
    ) -> None:
        """Send vertex data to GPU and render as TRIANGLES (reusable VBO)."""
        import moderngl

        raw = np.array(verts, dtype="f4").reshape(-1, 6)
        n = raw.shape[0]
        normals = np.broadcast_to(self._z_normal, (n, 3))
        data = np.column_stack((raw[:, :3], raw[:, 3:6], normals))
        data_bytes = np.ascontiguousarray(data).tobytes()
        buf_size = len(data_bytes)

        # Grow buffer if needed; otherwise reuse
        if buf_size > self._draw_vbo.size:
            self._draw_vao.release()
            self._draw_vbo.release()
            self._draw_vbo = ctx.buffer(reserve=buf_size * 2)
            self._draw_vao = ctx.vertex_array(
                prog, [(self._draw_vbo, "3f 3f 3f", "in_position", "in_color", "in_normal")]
            )
        self._draw_vbo.write(data_bytes)

        prog["mvp"].write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
        prog["alpha"].value = alpha
        ctx.disable_direct(moderngl.DEPTH_TEST)
        try:
            self._draw_vao.render(moderngl.TRIANGLES, vertices=n)
        finally:
            ctx.enable_direct(moderngl.DEPTH_TEST)

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

        For side view: pure kinematic diagram with angle arcs.
        For top view: overhead schematic with swing visualization.
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
            full_target: dict[JointName, float] = dict(DEFAULT_JOINT_ANGLES)
            full_target.update(target_angles)
            if viewport_name == "top_2d":
                target_pts = self._fk.get_joint_positions_2d_top(full_target)
            else:
                target_pts = self._fk.get_joint_positions_2d_side(full_target)

        # ── Side view: kinematic diagram background ──────────────
        if viewport_name == "side_2d":
            bg_verts = self._build_side_background()
            if bg_verts:
                self._draw_triangles(ctx, prog, mvp, bg_verts, alpha=0.6)

        # ── Layer 1: Current outline border ─────────────────────
        current_border = self._build_pose(
            viewport_name,
            current_pts,
            _CURRENT_OUTLINE_COLORS,
            (1.0, 1.0, 1.0),
            self.LINK_WIDTH + self.OUTLINE_EXTRA,
            self.JOINT_RADIUS,
        )
        if current_border:
            self._draw_triangles(ctx, prog, mvp, current_border, alpha=0.85)

        # ── Layer 2: Current fill (fully opaque) ────────────────
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

        # ── Layer 3: Current joint dots ─────────────────────────
        joint_verts = self._build_joint_markers(
            viewport_name,
            current_pts,
            _CURRENT_OUTLINE_COLORS,
            self.JOINT_RADIUS,
        )
        if joint_verts:
            self._draw_triangles(ctx, prog, mvp, joint_verts, alpha=1.0)

        # ── Ghost target (additive blend — glows ON TOP of current) ─
        if target_pts is not None:
            import moderngl

            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
            try:
                # Layer 4: Ghost glow halo (wide, soft)
                glow_verts = self._build_pose(
                    viewport_name,
                    target_pts,
                    _TARGET_LINK_COLORS,
                    (1.0, 1.0, 1.0),
                    self.TARGET_LINK_WIDTH + self.OUTLINE_EXTRA * 2,
                    self.TARGET_JOINT_RADIUS,
                )
                if glow_verts:
                    self._draw_triangles(ctx, prog, mvp, glow_verts, alpha=0.10)

                # Layer 5: Ghost outline (precise, bright neon)
                outline_verts = self._build_pose_outline(
                    viewport_name,
                    target_pts,
                    _TARGET_OUTLINE_COLORS,
                    self.TARGET_LINK_WIDTH,
                    0.14,
                )
                if outline_verts:
                    self._draw_triangles(ctx, prog, mvp, outline_verts, alpha=0.70)

                # Layer 6: Ghost joint markers (bright glow dots)
                ghost_joints = self._build_joint_markers(
                    viewport_name,
                    target_pts,
                    _TARGET_OUTLINE_COLORS,
                    self.TARGET_JOINT_RADIUS,
                )
                if ghost_joints:
                    self._draw_triangles(ctx, prog, mvp, ghost_joints, alpha=0.60)
            finally:
                ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

        # ── Layer 7: Direction arrows ───────────────────────────────
        if target_pts is not None:
            arrow_verts = self._build_direction_arrows(viewport_name, current_pts, target_pts)
            if arrow_verts:
                self._draw_triangles(ctx, prog, mvp, arrow_verts, alpha=0.95)



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
                scale=0.85,
            )

    def _render_angle_labels(
        self,
        mvp: np.ndarray,
        vp: tuple[int, int, int, int],
        positions: list[tuple[float, float]],
        current_angles: dict[JointName, float],
        text_renderer: Any,
    ) -> None:
        """Render angle values near arc indicators (side view only)."""
        from exca_dance.core.models import JointName as JN
        from exca_dance.rendering.theme import NeonTheme

        angle_info: list[tuple[int, JN, str]] = [
            (1, JN.BOOM, "BOOM"),
            (2, JN.ARM, "ARM"),
            (3, JN.BUCKET, "BKT"),
        ]

        for pivot_idx, jname, label in angle_info:
            if pivot_idx >= len(positions):
                continue
            angle_deg = current_angles.get(jname, 0.0)
            # Project the joint position to screen
            world = self._to_world(positions[pivot_idx], "side_2d")
            pos = self._project_to_screen(world, mvp, vp)
            if pos is None:
                continue
            sx, sy = pos

            # Draw angle value offset from joint center
            color = NeonTheme.TEXT_DIM.as_tuple()
            text_renderer.render(
                f"{label} {angle_deg:+.0f}°",
                sx - 30,
                sy + 16,
                color=color,
                scale=0.75,
            )
