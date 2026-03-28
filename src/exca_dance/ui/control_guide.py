"""Control guide overlay — dual joystick-style directional arrows for gameplay.

Renders two joystick diagrams (left/right stick) with dynamic arrows that
highlight which direction the player should push based on current vs target
pose differences.

Stick mapping (ISO excavator pilot pattern):
  Left stick (WASD):  W=ARM↑  S=ARM↓  A=SWING←  D=SWING→
  Right stick (UHJK): U=BOOM↓ J=BOOM↑ H=BKT←    K=BKT→
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import moderngl
import numpy as np

from exca_dance.core.models import JointName
from exca_dance.rendering.theme import Color, NeonTheme

if TYPE_CHECKING:
    from exca_dance.rendering.renderer import GameRenderer
    from exca_dance.rendering.gl_text import GLTextRenderer

# ── Stick → Arrow mapping ────────────────────────────────────────────
# Maps (joint, sign) to (stick, arrow_direction).
# sign: +1 = positive (angle increases), -1 = negative (angle decreases).
_POSITIVE_ARROW: dict[JointName, tuple[str, str]] = {
    JointName.ARM: ("left", "up"),  # W — left stick up
    JointName.SWING: ("left", "left"),  # A — left stick left
    JointName.BOOM: ("right", "down"),  # J — right stick down (inverted!)
    JointName.BUCKET: ("right", "right"),  # K — right stick right
}

_NEGATIVE_ARROW: dict[JointName, tuple[str, str]] = {
    JointName.ARM: ("left", "down"),  # S — left stick down
    JointName.SWING: ("left", "right"),  # D — left stick right
    JointName.BOOM: ("right", "up"),  # U — right stick up (inverted!)
    JointName.BUCKET: ("right", "left"),  # H — right stick left
}

# ── Per-arrow metadata ────────────────────────────────────────────────
# (joint, action_label, key_label) for each (stick, direction) pair.
_ARROW_INFO: dict[tuple[str, str], tuple[JointName, str, str]] = {
    # Left stick (WASD)
    ("left", "up"): (JointName.ARM, "ARM↑", "W"),
    ("left", "down"): (JointName.ARM, "ARM↓", "S"),
    ("left", "left"): (JointName.SWING, "SWING←", "A"),
    ("left", "right"): (JointName.SWING, "SWING→", "D"),
    # Right stick (UHJK)
    ("right", "up"): (JointName.BOOM, "BOOM↓", "U"),  # inverted
    ("right", "down"): (JointName.BOOM, "BOOM↑", "J"),  # inverted
    ("right", "left"): (JointName.BUCKET, "BKT←", "H"),
    ("right", "right"): (JointName.BUCKET, "BKT→", "K"),
}

# Joint → Color for active arrows
_JOINT_COLORS: dict[JointName, Color] = {
    JointName.SWING: NeonTheme.JOINT_SWING,
    JointName.BOOM: NeonTheme.JOINT_BOOM,
    JointName.ARM: NeonTheme.JOINT_ARM,
    JointName.BUCKET: NeonTheme.JOINT_BUCKET,
}


class ControlGuide:
    """Renders dual joystick control guide with dynamic directional arrows."""

    # Minimum angle difference (degrees) to trigger an active arrow.
    THRESHOLD_DEG: float = 3.0
    # Panel height at 1080p reference — used by HUD for stacking.
    PANEL_HEIGHT_REF: int = 100

    def __init__(self, renderer: GameRenderer, text_renderer: GLTextRenderer) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._pulse_time: float = 0.0

    # ── Public API ────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        """Advance pulse animation timer."""
        self._pulse_time += dt

    def render(
        self,
        current_angles: dict[JointName, float],
        target_angles: dict[JointName, float] | None,
    ) -> None:
        """Draw the control guide overlay."""
        if self._text is None:
            return

        W = self._renderer.width
        H = self._renderer.height
        s = H / 1080.0

        # ── Panel geometry (full width, stacked at bottom) ─────────
        main_w = int(W * 0.55)
        guide_w = main_w - int(32 * s)
        guide_h = int(self.PANEL_HEIGHT_REF * s)
        guide_x = int(16 * s)
        main_3d_bottom = int(H * 0.72)
        guide_y = main_3d_bottom - guide_h - int(6 * s)

        # Background panel
        self._draw_rect_2d(
            guide_x,
            guide_y,
            guide_w,
            guide_h,
            NeonTheme.BG_PANEL,
            alpha=0.55,
        )
        # Top accent line
        self._draw_rect_2d(
            guide_x,
            guide_y,
            guide_w,
            max(int(2 * s), 1),
            NeonTheme.NEON_BLUE,
            alpha=0.30,
        )

        # ── Compute active arrows ─────────────────────────────────
        active = self._compute_active(current_angles, target_angles)

        # ── Left stick diagram ─────────────────────────────────────
        left_cx = guide_x + int(guide_w * 0.25)
        stick_cy = guide_y + int(guide_h * 0.55)
        self._draw_stick_diagram(left_cx, stick_cy, s, "left", active)

        # Title: 좌 (WASD)
        self._text.render(
            "좌 (WASD)",
            left_cx,
            guide_y + int(8 * s),
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=max(0.85 * s, 0.50),
            align="center",
        )

        # ── Right stick diagram ────────────────────────────────────
        right_cx = guide_x + int(guide_w * 0.75)
        self._draw_stick_diagram(right_cx, stick_cy, s, "right", active)

        # Title: 우 (UHJK)
        self._text.render(
            "우 (UHJK)",
            right_cx,
            guide_y + int(8 * s),
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=max(0.85 * s, 0.50),
            align="center",
        )

    # ── Internal: active arrow computation ────────────────────────

    def _compute_active(
        self,
        current: dict[JointName, float],
        target: dict[JointName, float] | None,
    ) -> set[tuple[str, str]]:
        """Return set of (stick, direction) pairs that should be highlighted."""
        if target is None or not target:
            return set()

        active: set[tuple[str, str]] = set()
        for joint in JointName:
            tgt = target.get(joint)
            if tgt is None:
                continue
            diff = tgt - current.get(joint, 0.0)
            if abs(diff) < self.THRESHOLD_DEG:
                continue
            if diff > 0:
                active.add(_POSITIVE_ARROW[joint])
            else:
                active.add(_NEGATIVE_ARROW[joint])
        return active

    # ── Internal: stick diagram rendering ─────────────────────────

    def _draw_stick_diagram(
        self,
        cx: int,
        cy: int,
        s: float,
        stick: str,
        active: set[tuple[str, str]],
    ) -> None:
        """Draw one joystick diagram (center dot + 4 arrows + labels)."""
        arrow_size = int(14 * s)
        arrow_dist = int(30 * s)
        dot_r = int(5 * s)

        # Center dot (small filled square ≈ circle)
        self._draw_rect_2d(
            cx - dot_r,
            cy - dot_r,
            dot_r * 2,
            dot_r * 2,
            NeonTheme.NEON_BLUE,
            alpha=0.45,
        )

        directions: list[tuple[str, int, int]] = [
            ("up", 0, -1),
            ("down", 0, 1),
            ("left", -1, 0),
            ("right", 1, 0),
        ]

        for direction, dx, dy in directions:
            key = (stick, direction)
            is_active = key in active
            joint, action_label, key_label = _ARROW_INFO[key]

            # Arrow center position
            ax = cx + dx * arrow_dist
            ay = cy + dy * arrow_dist

            if is_active:
                # Pulse effect for active arrows
                pulse = 0.7 + 0.3 * (0.5 + 0.5 * math.sin(self._pulse_time * 6.0))
                color: Color = _JOINT_COLORS[joint]
                arrow_alpha = pulse
                label_alpha = 1.0
            else:
                color = NeonTheme.TEXT_DIM
                arrow_alpha = 0.25
                label_alpha = 0.35

            # Draw triangle arrow
            self._draw_arrow_triangle(
                ax,
                ay,
                direction,
                arrow_size,
                color,
                arrow_alpha,
            )

            # Key label position (near arrow)
            kx, ky = ax, ay
            label_scale = max(0.70 * s, 0.42)
            action_scale = max(0.55 * s, 0.35)

            if direction == "up":
                ky = ay - arrow_size - int(4 * s)
                align = "center"
            elif direction == "down":
                ky = ay + arrow_size - int(2 * s)
                align = "center"
            elif direction == "left":
                kx = ax - arrow_size - int(2 * s)
                ky = ay - int(6 * s)
                align = "right"
            else:  # right
                kx = ax + arrow_size + int(2 * s)
                ky = ay - int(6 * s)
                align = "left"

            # Key letter
            key_color = color.with_alpha(label_alpha).as_tuple()
            self._text.render(
                key_label,
                kx,
                ky,
                color=key_color,
                scale=label_scale,
                align=align,
            )

            # Action label (only when active)
            if is_active:
                if direction == "up":
                    aky = ky - int(14 * s)
                elif direction == "down":
                    aky = ky + int(14 * s)
                elif direction == "left":
                    aky = ky + int(12 * s)
                else:
                    aky = ky + int(12 * s)

                self._text.render(
                    action_label,
                    kx,
                    aky,
                    color=_JOINT_COLORS[joint].as_tuple(),
                    scale=action_scale,
                    align=align,
                )

    # ── Internal: primitive drawing ───────────────────────────────

    def _draw_arrow_triangle(
        self,
        cx: int,
        cy: int,
        direction: str,
        size: int,
        color,
        alpha: float,
    ) -> None:
        """Draw a filled triangle arrow pointing in the given direction."""
        half = size / 2.0
        W = self._renderer.width
        H = self._renderer.height

        if direction == "up":
            pts = [(cx, cy - half), (cx - half, cy + half), (cx + half, cy + half)]
        elif direction == "down":
            pts = [(cx, cy + half), (cx - half, cy - half), (cx + half, cy - half)]
        elif direction == "left":
            pts = [(cx - half, cy), (cx + half, cy - half), (cx + half, cy + half)]
        else:  # right
            pts = [(cx + half, cy), (cx - half, cy - half), (cx - half, cy + half)]

        r, g, b = color.r, color.g, color.b
        verts: list[float] = []
        for px, py in pts:
            nx = (px / W) * 2.0 - 1.0
            ny = 1.0 - (py / H) * 2.0
            verts.extend([nx, ny, 0.0, r, g, b])

        data = np.array(verts, dtype="f4")
        ctx = self._renderer.ctx
        vbo = ctx.buffer(data)
        prog = self._renderer.prog_solid
        vao = ctx.vertex_array(prog, [(vbo, "3f 3f", "in_position", "in_color")])

        identity = np.eye(4, dtype="f4")
        prog["mvp"].write(np.ascontiguousarray(identity).tobytes())
        prog["alpha"].value = alpha
        ctx.disable(moderngl.DEPTH_TEST)
        vao.render(moderngl.TRIANGLES)
        vao.release()
        vbo.release()

    def _draw_rect_2d(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        color,
        *,
        alpha: float = 1.0,
    ) -> None:
        """Draw a filled 2D rectangle. Same pattern as GameplayHUD._draw_rect_2d."""
        ctx = self._renderer.ctx
        W = self._renderer.width
        H = self._renderer.height

        x0 = (x / W) * 2.0 - 1.0
        x1 = ((x + w) / W) * 2.0 - 1.0
        y0 = 1.0 - (y / H) * 2.0
        y1 = 1.0 - ((y + h) / H) * 2.0

        if hasattr(color, "r"):
            r, g, b = color.r, color.g, color.b
        else:
            r, g, b = color[0], color[1], color[2]

        verts = [
            x0,
            y1,
            0.0,
            r,
            g,
            b,
            x1,
            y1,
            0.0,
            r,
            g,
            b,
            x1,
            y0,
            0.0,
            r,
            g,
            b,
            x0,
            y1,
            0.0,
            r,
            g,
            b,
            x1,
            y0,
            0.0,
            r,
            g,
            b,
            x0,
            y0,
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
        prog["alpha"].value = alpha

        ctx.disable(moderngl.DEPTH_TEST)
        vao.render(moderngl.TRIANGLES)

        vao.release()
        vbo.release()
