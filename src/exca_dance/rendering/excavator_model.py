"""3D excavator model built from STL meshes with URDF forward kinematics."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import numpy as np
import moderngl

from exca_dance.core.kinematics import ExcavatorFK
from exca_dance.core.models import JointName
from exca_dance.rendering.stl_loader import load_binary_stl
from exca_dance.rendering.urdf_kin import (
    MESH_TO_LINK,
    build_link_to_color_key,
    compute_link_transforms,
)


# Default joint colors (R, G, B) — educational neon color coding
JOINT_COLORS: dict[str | JointName, tuple[float, float, float]] = {
    "base": (0.23, 0.23, 0.23),  # dark gray
    "turret": (0.30, 0.30, 0.35),  # slightly lighter
    JointName.BOOM: (1.0, 0.4, 0.0),  # orange
    JointName.ARM: (1.0, 0.8, 0.0),  # yellow
    JointName.BUCKET: (0.0, 0.8, 1.0),  # cyan
}


# ---------------------------------------------------------------------------
# Mesh asset resolution
# ---------------------------------------------------------------------------


def _find_mesh_dir() -> Path:
    """Locate the ``assets/meshes/collision/`` directory.

    Works both from a source checkout and from an installed package.
    """
    # Walk up from this file to find the project root containing assets/
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "assets" / "meshes" / "collision"
        if candidate.is_dir():
            return candidate
    # Fallback: importlib.resources (Python 3.9+)
    try:
        ref = (
            importlib.resources.files("exca_dance")
            / ".."
            / ".."
            / "assets"
            / "meshes"
            / "collision"
        )
        p = Path(str(ref))
        if p.is_dir():
            return p
    except Exception:
        pass
    raise FileNotFoundError(
        "Cannot find assets/meshes/collision/ directory. Make sure STL mesh files are present."
    )


# ---------------------------------------------------------------------------
# Mesh data container
# ---------------------------------------------------------------------------


class _MeshPart:
    """Pre-loaded STL mesh data for one link."""

    __slots__ = ("link_name", "vertices", "normals", "vertex_count")

    def __init__(self, link_name: str, vertices: np.ndarray, normals: np.ndarray) -> None:
        self.link_name = link_name
        self.vertices = vertices  # (N, 3) float32
        self.normals = normals  # (N, 3) float32
        self.vertex_count = vertices.shape[0]


# ---------------------------------------------------------------------------
# Main model class
# ---------------------------------------------------------------------------


class ExcavatorModel:
    """Renders a 3D excavator from STL meshes using URDF FK joint transforms.

    Public API is identical to the previous primitive-based implementation:

    * ``__init__(renderer, fk=None, joint_colors=None)``
    * ``update(joint_angles)``
    * ``render_3d(mvp, alpha)``
    * ``render_2d_side(ortho, alpha)``
    * ``render_2d_top(ortho, alpha)``
    * ``destroy()``
    """

    def __init__(
        self,
        renderer: object,
        fk: ExcavatorFK | None = None,
        joint_colors: dict[str | JointName, tuple[float, float, float]] | None = None,
    ) -> None:
        self._renderer = renderer  # type: ignore[assignment]
        self._fk = fk or ExcavatorFK()
        self._joint_colors: dict[str | JointName, tuple[float, float, float]] = (
            joint_colors if joint_colors is not None else JOINT_COLORS
        )
        self._current_angles: dict[JointName, float] = {j: 0.0 for j in JointName}
        self._vbo: moderngl.Buffer | None = None
        self._vao: moderngl.VertexArray | None = None
        self._vertex_count: int = 0

        # Pre-load mesh data
        self._mesh_parts: list[_MeshPart] = []
        self._link_color_map: dict[str, str | JointName] = build_link_to_color_key()
        self._total_raw_verts: int = 0
        self._load_meshes()
        self._update_geometry()

    # ------------------------------------------------------------------
    # Mesh loading (once at init)
    # ------------------------------------------------------------------

    def _load_meshes(self) -> None:
        """Load all STL files and store as _MeshPart instances."""
        mesh_dir = _find_mesh_dir()
        for stem, link_name in MESH_TO_LINK.items():
            stl_path = mesh_dir / f"{stem}.stl"
            if not stl_path.exists():
                continue
            vertices, normals = load_binary_stl(stl_path)
            if vertices.shape[0] == 0:
                continue
            self._mesh_parts.append(_MeshPart(link_name, vertices, normals))
            self._total_raw_verts += vertices.shape[0]

    # ------------------------------------------------------------------
    # Geometry update (per-frame when angles change)
    # ------------------------------------------------------------------

    def update(self, joint_angles: dict[JointName, float]) -> None:
        """Update joint angles and rebuild geometry."""
        self._current_angles.update(joint_angles)
        self._update_geometry()

    def _update_geometry(self) -> None:
        """Rebuild VAO/VBO from current FK positions using URDF transforms."""
        if not self._mesh_parts:
            return

        # Compute world transform for every link
        link_transforms = compute_link_transforms(self._current_angles)

        # Pre-allocate output: 9 floats per vertex (pos3 + color3 + normal3)
        out = np.empty((self._total_raw_verts, 9), dtype=np.float32)
        write_idx = 0

        for part in self._mesh_parts:
            T = link_transforms.get(part.link_name)
            if T is None:
                continue

            n = part.vertex_count
            rot = T[:3, :3].astype(np.float32)
            trans = T[:3, 3].astype(np.float32)

            # Transform positions: v_world = rot @ v_local + trans
            world_pos = part.vertices @ rot.T + trans

            # Transform normals: n_world = rot @ n_local (no translation)
            world_norm = part.normals @ rot.T
            # Re-normalize (rotation preserves length, but fp precision)
            norms_len = np.linalg.norm(world_norm, axis=1, keepdims=True)
            norms_len = np.where(norms_len < 1e-8, 1.0, norms_len)
            world_norm = world_norm / norms_len

            # Look up color for this link
            color_key = self._link_color_map.get(part.link_name, "base")
            r, g, b = self._joint_colors.get(color_key, (0.5, 0.5, 0.5))
            color_col = np.full((n, 3), (r, g, b), dtype=np.float32)

            out[write_idx : write_idx + n, :3] = world_pos
            out[write_idx : write_idx + n, 3:6] = color_col
            out[write_idx : write_idx + n, 6:9] = world_norm
            write_idx += n

        # Trim if some parts were skipped (missing transforms)
        data = out[:write_idx].ravel()
        self._vertex_count = write_idx

        ctx = self._renderer.ctx  # type: ignore[attr-defined]
        if self._vbo is not None:
            self._vbo.release()
        if self._vao is not None:
            self._vao.release()
        self._vbo = ctx.buffer(data)
        self._vao = ctx.vertex_array(
            self._renderer.prog_solid,  # type: ignore[attr-defined]
            [(self._vbo, "3f 3f 3f", "in_position", "in_color", "in_normal")],
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_3d(self, mvp: np.ndarray, alpha: float = 1.0) -> None:
        """Render excavator with solid shader. *mvp* is a 4×4 float32 array."""
        if self._vao is None:
            return
        prog = self._renderer.prog_solid  # type: ignore[attr-defined]
        prog["mvp"].write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
        prog["alpha"].value = alpha
        self._renderer.ctx.enable(moderngl.DEPTH_TEST)  # type: ignore[attr-defined]
        self._vao.render(moderngl.TRIANGLES, vertices=self._vertex_count)
        self._renderer.ctx.disable(moderngl.DEPTH_TEST)  # type: ignore[attr-defined]

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
