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
    """Generate 36 vertices (12 triangles) for an axis-aligned box with per-face normals."""
    hx, hy, hz = lx / 2, ly / 2, lz / 2
    faces_with_normals = [
        # +Z face, normal = (0, 0, 1)
        (
            [
                (-hx, -hy, hz),
                (hx, -hy, hz),
                (hx, hy, hz),
                (-hx, -hy, hz),
                (hx, hy, hz),
                (-hx, hy, hz),
            ],
            (0, 0, 1),
        ),
        # -Z face, normal = (0, 0, -1)
        (
            [
                (-hx, -hy, -hz),
                (-hx, hy, -hz),
                (hx, hy, -hz),
                (-hx, -hy, -hz),
                (hx, hy, -hz),
                (hx, -hy, -hz),
            ],
            (0, 0, -1),
        ),
        # +X face, normal = (1, 0, 0)
        (
            [
                (hx, -hy, -hz),
                (hx, hy, -hz),
                (hx, hy, hz),
                (hx, -hy, -hz),
                (hx, hy, hz),
                (hx, -hy, hz),
            ],
            (1, 0, 0),
        ),
        # -X face, normal = (-1, 0, 0)
        (
            [
                (-hx, -hy, -hz),
                (-hx, -hy, hz),
                (-hx, hy, hz),
                (-hx, -hy, -hz),
                (-hx, hy, hz),
                (-hx, hy, -hz),
            ],
            (-1, 0, 0),
        ),
        # +Y face, normal = (0, 1, 0)
        (
            [
                (-hx, hy, -hz),
                (-hx, hy, hz),
                (hx, hy, hz),
                (-hx, hy, -hz),
                (hx, hy, hz),
                (hx, hy, -hz),
            ],
            (0, 1, 0),
        ),
        # -Y face, normal = (0, -1, 0)
        (
            [
                (-hx, -hy, -hz),
                (hx, -hy, -hz),
                (hx, -hy, hz),
                (-hx, -hy, -hz),
                (hx, -hy, hz),
                (-hx, -hy, hz),
            ],
            (0, -1, 0),
        ),
    ]
    r, g, b = color
    verts: list[float] = []
    for face_verts, (nx, ny, nz) in faces_with_normals:
        for x, y, z in face_verts:
            verts += [cx + x, cy + y, cz + z, r, g, b, nx, ny, nz]
    return verts


def _make_link_verts(
    p1: tuple[float, float, float],
    p2: tuple[float, float, float],
    thickness_y: float,
    thickness_z: float,
    color: tuple[float, float, float],
) -> list[float]:
    """Generate 36 vertices for a box oriented along the vector from *p1* to *p2*, with normals."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dz = p2[2] - p1[2]
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-6:
        return []

    # Build an orthonormal basis: x_axis along link direction
    x_ax = np.array([dx / length, dy / length, dz / length], dtype="f4")
    ref = (
        np.array([0.0, 0.0, 1.0], dtype="f4")
        if abs(x_ax[2]) < 0.95
        else np.array([0.0, 1.0, 0.0], dtype="f4")
    )
    y_ax = np.cross(ref, x_ax)
    y_ax /= float(np.linalg.norm(y_ax))
    z_ax = np.cross(x_ax, y_ax)

    rot = np.column_stack([x_ax, y_ax, z_ax])  # 3×3 rotation
    mid = np.array([(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, (p1[2] + p2[2]) / 2], dtype="f4")

    hx, hy, hz = length / 2, thickness_y / 2, thickness_z / 2
    faces_with_normals = [
        # +Z face
        (
            [
                (-hx, -hy, hz),
                (hx, -hy, hz),
                (hx, hy, hz),
                (-hx, -hy, hz),
                (hx, hy, hz),
                (-hx, hy, hz),
            ],
            (0, 0, 1),
        ),
        # -Z face
        (
            [
                (-hx, -hy, -hz),
                (-hx, hy, -hz),
                (hx, hy, -hz),
                (-hx, -hy, -hz),
                (hx, hy, -hz),
                (hx, -hy, -hz),
            ],
            (0, 0, -1),
        ),
        # +X face
        (
            [
                (hx, -hy, -hz),
                (hx, hy, -hz),
                (hx, hy, hz),
                (hx, -hy, -hz),
                (hx, hy, hz),
                (hx, -hy, hz),
            ],
            (1, 0, 0),
        ),
        # -X face
        (
            [
                (-hx, -hy, -hz),
                (-hx, -hy, hz),
                (-hx, hy, hz),
                (-hx, -hy, -hz),
                (-hx, hy, hz),
                (-hx, hy, -hz),
            ],
            (-1, 0, 0),
        ),
        # +Y face
        (
            [
                (-hx, hy, -hz),
                (-hx, hy, hz),
                (hx, hy, hz),
                (-hx, hy, -hz),
                (hx, hy, hz),
                (hx, hy, -hz),
            ],
            (0, 1, 0),
        ),
        # -Y face
        (
            [
                (-hx, -hy, -hz),
                (hx, -hy, -hz),
                (hx, -hy, hz),
                (-hx, -hy, -hz),
                (hx, -hy, hz),
                (-hx, -hy, hz),
            ],
            (0, -1, 0),
        ),
    ]
    r, g, b = color
    verts: list[float] = []
    for face_verts, local_normal in faces_with_normals:
        world_normal = rot @ np.array(local_normal, dtype="f4")
        nx, ny, nz = float(world_normal[0]), float(world_normal[1]), float(world_normal[2])
        for lx, ly, lz in face_verts:
            w = rot @ np.array([lx, ly, lz], dtype="f4") + mid
            verts += [float(w[0]), float(w[1]), float(w[2]), r, g, b, nx, ny, nz]
    return verts


def _make_octagonal_prism_verts(
    p1: tuple[float, float, float],
    p2: tuple[float, float, float],
    radius: float,
    color: tuple[float, float, float],
    sides: int = 8,
) -> list[float]:
    if sides < 3:
        return []

    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dz = p2[2] - p1[2]
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-6:
        return []

    x_ax = np.array([dx / length, dy / length, dz / length], dtype="f4")
    ref = (
        np.array([0.0, 0.0, 1.0], dtype="f4")
        if abs(x_ax[2]) < 0.95
        else np.array([0.0, 1.0, 0.0], dtype="f4")
    )
    y_ax = np.cross(ref, x_ax)
    y_ax /= float(np.linalg.norm(y_ax))
    z_ax = np.cross(x_ax, y_ax)

    p1v = np.array(p1, dtype="f4")
    p2v = np.array(p2, dtype="f4")

    r, g, b = color
    verts: list[float] = []
    two_pi = 2.0 * math.pi

    def _append_vertex(point: np.ndarray, normal: np.ndarray) -> None:
        verts.extend(
            [
                float(point[0]),
                float(point[1]),
                float(point[2]),
                r,
                g,
                b,
                float(normal[0]),
                float(normal[1]),
                float(normal[2]),
            ]
        )

    for i in range(sides):
        angle0 = two_pi * i / sides
        angle1 = two_pi * (i + 1) / sides
        c0, s0 = math.cos(angle0), math.sin(angle0)
        c1, s1 = math.cos(angle1), math.sin(angle1)

        radial0 = c0 * y_ax + s0 * z_ax
        radial1 = c1 * y_ax + s1 * z_ax
        p1_a = p1v + radius * radial0
        p1_b = p1v + radius * radial1
        p2_a = p2v + radius * radial0
        p2_b = p2v + radius * radial1

        mid_angle = 0.5 * (angle0 + angle1)
        side_normal = math.cos(mid_angle) * y_ax + math.sin(mid_angle) * z_ax
        side_normal /= float(np.linalg.norm(side_normal))

        _append_vertex(p1_a, side_normal)
        _append_vertex(p2_a, side_normal)
        _append_vertex(p2_b, side_normal)
        _append_vertex(p1_a, side_normal)
        _append_vertex(p2_b, side_normal)
        _append_vertex(p1_b, side_normal)

        _append_vertex(p1v, -x_ax)
        _append_vertex(p1_b, -x_ax)
        _append_vertex(p1_a, -x_ax)

        _append_vertex(p2v, x_ax)
        _append_vertex(p2_a, x_ax)
        _append_vertex(p2_b, x_ax)

    return verts


class ExcavatorModel:
    """Renders a 3D excavator from geometric primitives using FK joint positions."""

    def __init__(
        self,
        renderer,
        fk: ExcavatorFK | None = None,
        joint_colors: dict[str | JointName, tuple[float, float, float]] | None = None,
    ) -> None:
        self._renderer = renderer
        self._fk = fk or ExcavatorFK()
        self._joint_colors: dict[str | JointName, tuple[float, float, float]] = (
            joint_colors if joint_colors is not None else JOINT_COLORS
        )
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

        # Base body (axis-aligned — stationary)
        verts += _make_box_verts(0, 0, 0.25, 1.5, 1.0, 0.5, self._joint_colors["base"])

        verts += _make_box_verts(0.0, 0.6, 0.08, 2.0, 0.35, 0.18, self._joint_colors["base"])
        verts += _make_box_verts(0.0, -0.6, 0.08, 2.0, 0.35, 0.18, self._joint_colors["base"])

        # Swing turret (axis-aligned at pivot)
        sp = pos["swing_pivot"]
        verts += _make_box_verts(sp[0], sp[1], sp[2], 0.8, 0.8, 0.3, self._joint_colors["turret"])

        verts += _make_box_verts(sp[0] - 0.1, sp[1], sp[2] + 0.3, 0.4, 0.5, 0.3, (0.20, 0.22, 0.28))

        # Boom link — oriented from swing_pivot → boom_pivot
        bp = pos["boom_pivot"]
        verts += _make_octagonal_prism_verts(sp, bp, 0.12, self._joint_colors[JointName.BOOM])

        # Arm link — oriented from boom_pivot → arm_pivot
        ap = pos["arm_pivot"]
        verts += _make_octagonal_prism_verts(bp, ap, 0.10, self._joint_colors[JointName.ARM])

        # Bucket link — oriented from arm_pivot → bucket_tip
        bt = pos["bucket_tip"]
        verts += _make_octagonal_prism_verts(ap, bt, 0.14, self._joint_colors[JointName.BUCKET])


        data = np.array(verts, dtype="f4")
        self._vertex_count = len(data) // 9  # 3 pos + 3 color + 3 normal

        ctx = self._renderer.ctx
        if self._vbo is not None:
            self._vbo.release()
        if self._vao is not None:
            self._vao.release()
        self._vbo = ctx.buffer(data)
        self._vao = ctx.vertex_array(
            self._renderer.prog_solid,
            [(self._vbo, "3f 3f 3f", "in_position", "in_color", "in_normal")],
        )

    def render_3d(self, mvp: np.ndarray, alpha: float = 1.0) -> None:
        """Render excavator with solid shader. mvp is a 4×4 float32 array."""
        if self._vao is None:
            return
        prog = self._renderer.prog_solid
        prog["mvp"].write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
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
