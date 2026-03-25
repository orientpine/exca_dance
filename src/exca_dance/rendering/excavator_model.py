"""3D excavator model built from geometric primitives."""

from __future__ import annotations
import math
import numpy as np
import moderngl
from exca_dance.core.kinematics import ExcavatorFK
from exca_dance.core.models import JointName


# Joint colors (R, G, B) — educational color coding
JOINT_COLORS = {
    "base": (0.23, 0.23, 0.23),  # dark gray
    "turret": (0.30, 0.30, 0.35),  # slightly lighter
    JointName.BOOM: (1.0, 0.4, 0.0),  # orange
    JointName.ARM: (1.0, 0.8, 0.0),  # yellow
    JointName.BUCKET: (0.0, 0.8, 1.0),  # cyan
}


def _make_box_verts(
    cx: float,
    cy: float,
    cz: float,
    lx: float,
    ly: float,
    lz: float,
    color: tuple[float, float, float],
) -> list[float]:
    """Generate 36 vertices (12 triangles) for an axis-aligned box."""
    hx, hy, hz = lx / 2, ly / 2, lz / 2
    faces = [
        # +Z
        ((-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)),
        # -Z
        (
            (-hx, -hy, -hz),
            (-hx, hy, -hz),
            (hx, hy, -hz),
            (-hx, -hy, -hz),
            (hx, hy, -hz),
            (hx, -hy, -hz),
        ),
        # +X
        ((hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, -hz), (hx, hy, hz), (hx, -hy, hz)),
        # -X
        (
            (-hx, -hy, -hz),
            (-hx, -hy, hz),
            (-hx, hy, hz),
            (-hx, -hy, -hz),
            (-hx, hy, hz),
            (-hx, hy, -hz),
        ),
        # +Y
        ((-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz), (-hx, hy, -hz), (hx, hy, hz), (hx, hy, -hz)),
        # -Y
        (
            (-hx, -hy, -hz),
            (hx, -hy, -hz),
            (hx, -hy, hz),
            (-hx, -hy, -hz),
            (hx, -hy, hz),
            (-hx, -hy, hz),
        ),
    ]
    r, g, b = color
    verts: list[float] = []
    for face in faces:
        for x, y, z in face:
            verts += [cx + x, cy + y, cz + z, r, g, b]
    return verts


class ExcavatorModel:
    """Renders a 3D excavator from geometric primitives using FK joint positions."""

    def __init__(self, renderer, fk: ExcavatorFK | None = None) -> None:
        self._renderer = renderer
        self._fk = fk or ExcavatorFK()
        self._current_angles: dict[JointName, float] = {j: 0.0 for j in JointName}
        self._vbo: moderngl.Buffer | None = None
        self._vao: moderngl.VertexArray | None = None
        self._vertex_count: int = 0
        self._update_geometry()

    def update(self, joint_angles: dict[JointName, float]) -> None:
        """Update joint angles and rebuild geometry."""
        self._current_angles.update(joint_angles)
        self._update_geometry()

    def _update_geometry(self) -> None:
        """Rebuild VAO/VBO from current FK positions."""
        pos = self._fk.forward_kinematics(self._current_angles)
        verts: list[float] = []

        # Base body
        verts += _make_box_verts(0, 0, 0.25, 1.5, 1.0, 0.5, JOINT_COLORS["base"])

        # Swing turret
        sp = pos["swing_pivot"]
        verts += _make_box_verts(sp[0], sp[1], sp[2], 0.8, 0.8, 0.3, JOINT_COLORS["turret"])

        # Boom link
        bp = pos["boom_pivot"]
        cx = (sp[0] + bp[0]) / 2
        cy = (sp[1] + bp[1]) / 2
        cz = (sp[2] + bp[2]) / 2
        dx, dy, dz = bp[0] - sp[0], bp[1] - sp[1], bp[2] - sp[2]
        length = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        verts += _make_box_verts(cx, cy, cz, length, 0.25, 0.25, JOINT_COLORS[JointName.BOOM])

        # Arm link
        ap = pos["arm_pivot"]
        cx2 = (bp[0] + ap[0]) / 2
        cy2 = (bp[1] + ap[1]) / 2
        cz2 = (bp[2] + ap[2]) / 2
        dx2, dy2, dz2 = ap[0] - bp[0], ap[1] - bp[1], ap[2] - bp[2]
        length2 = math.sqrt(dx2 * dx2 + dy2 * dy2 + dz2 * dz2) or 1.0
        verts += _make_box_verts(cx2, cy2, cz2, length2, 0.20, 0.20, JOINT_COLORS[JointName.ARM])

        # Bucket link
        bt = pos["bucket_tip"]
        cx3 = (ap[0] + bt[0]) / 2
        cy3 = (ap[1] + bt[1]) / 2
        cz3 = (ap[2] + bt[2]) / 2
        dx3, dy3, dz3 = bt[0] - ap[0], bt[1] - ap[1], bt[2] - ap[2]
        length3 = math.sqrt(dx3 * dx3 + dy3 * dy3 + dz3 * dz3) or 1.0
        verts += _make_box_verts(cx3, cy3, cz3, length3, 0.30, 0.25, JOINT_COLORS[JointName.BUCKET])

        data = np.array(verts, dtype="f4")
        self._vertex_count = len(data) // 6  # 3 pos + 3 color

        ctx = self._renderer.ctx
        if self._vbo is not None:
            self._vbo.release()
        if self._vao is not None:
            self._vao.release()
        self._vbo = ctx.buffer(data)
        self._vao = ctx.vertex_array(
            self._renderer.prog_solid,
            [(self._vbo, "3f 3f", "in_position", "in_color")],
        )

    def render_3d(self, mvp: np.ndarray, alpha: float = 1.0) -> None:
        """Render excavator with solid shader. mvp is a 4×4 float32 array."""
        if self._vao is None:
            return
        prog = self._renderer.prog_solid
        prog["mvp"].write(mvp.astype("f4").tobytes())
        prog["alpha"].value = alpha
        self._renderer.ctx.enable(moderngl.DEPTH_TEST)
        self._vao.render(moderngl.TRIANGLES, vertices=self._vertex_count)
        self._renderer.ctx.disable(moderngl.DEPTH_TEST)

    def render_2d_side(self, ortho: np.ndarray, alpha: float = 1.0) -> None:
        """Render in side view (XZ projection)."""
        self.render_3d(ortho, alpha)

    def render_2d_top(self, ortho: np.ndarray, alpha: float = 1.0) -> None:
        """Render in top view (XY projection)."""
        self.render_3d(ortho, alpha)

    def destroy(self) -> None:
        if self._vbo is not None:
            self._vbo.release()
        if self._vao is not None:
            self._vao.release()
