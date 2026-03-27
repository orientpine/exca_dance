"""3D excavator model built from STL meshes with URDF forward kinematics.

Architecture:  per-part static VBO + GPU-side differential transform.
Each STL mesh is uploaded to the GPU *once*.  Per-frame work is limited
to computing 25 lightweight 4×4 matrices and writing one ``model`` uniform
per draw call.
"""

from __future__ import annotations

import importlib.resources
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import moderngl

from exca_dance.core.kinematics import ExcavatorFK
from exca_dance.core.models import JointName
from exca_dance.rendering.stl_loader import load_binary_stl
from exca_dance.rendering.urdf_kin import (
    MESH_TO_LINK,
    build_link_to_color_key,
    compute_inv_zero_transforms,
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
# Per-part render data (immutable after init)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _RenderPart:
    """GPU resources + precomputed transform for one STL mesh."""

    link_name: str
    vbo: moderngl.Buffer
    vao: moderngl.VertexArray
    vertex_count: int
    inv_zero_T: np.ndarray  # 4×4 float64 — cached inv(link_T_zero)
    # CPU-side vertex data kept for ghost glow / outline extraction
    raw_vertices: np.ndarray  # (N, 3) float32


# ---------------------------------------------------------------------------
# Main model class
# ---------------------------------------------------------------------------


class ExcavatorModel:
    """Renders a 3D excavator from STL meshes using URDF FK joint transforms.

    Public API is identical to the previous implementation:

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
        joint_colors: (dict[str | JointName, tuple[float, float, float]] | None) = None,
    ) -> None:
        self._renderer = renderer  # type: ignore[assignment]
        self._fk = fk or ExcavatorFK()
        self._joint_colors: dict[str | JointName, tuple[float, float, float]] = (
            joint_colors if joint_colors is not None else JOINT_COLORS
        )
        self._current_angles: dict[JointName, float] = {j: 0.0 for j in JointName}

        # Precompute inverse zero-angle transforms (assembly→link-local)
        self._inv_zero_transforms = compute_inv_zero_transforms()
        self._link_color_map = build_link_to_color_key()

        # Current link transforms — updated each frame
        self._link_transforms: dict[str, np.ndarray] = compute_link_transforms(self._current_angles)

        # Build static per-part GPU resources
        self._parts: list[_RenderPart] = []
        self._load_and_upload_meshes()

    # ------------------------------------------------------------------
    # One-time mesh loading + GPU upload
    # ------------------------------------------------------------------

    def _load_and_upload_meshes(self) -> None:
        """Load all STL files and create one static VBO+VAO per part."""
        mesh_dir = _find_mesh_dir()
        ctx = self._renderer.ctx  # type: ignore[attr-defined]
        prog = self._renderer.prog_solid  # type: ignore[attr-defined]

        for stem, link_name in MESH_TO_LINK.items():
            stl_path = mesh_dir / f"{stem}.stl"
            if not stl_path.exists():
                continue
            vertices, normals = load_binary_stl(stl_path)
            if vertices.shape[0] == 0:
                continue

            n = vertices.shape[0]

            # Look up color for this link
            color_key = self._link_color_map.get(link_name, "base")
            r, g, b = self._joint_colors.get(color_key, (0.5, 0.5, 0.5))
            colors = np.full((n, 3), (r, g, b), dtype=np.float32)

            # Interleave: position(3f) + color(3f) + normal(3f) = 9 floats
            interleaved = np.empty((n, 9), dtype=np.float32)
            interleaved[:, :3] = vertices
            interleaved[:, 3:6] = colors
            interleaved[:, 6:9] = normals

            vbo = ctx.buffer(interleaved.ravel().tobytes())
            vao = ctx.vertex_array(
                prog,
                [
                    (
                        vbo,
                        "3f 3f 3f",
                        "in_position",
                        "in_color",
                        "in_normal",
                    )
                ],
            )

            inv_zero = self._inv_zero_transforms.get(
                link_name,
                np.eye(4, dtype=np.float64),
            )

            self._parts.append(
                _RenderPart(
                    link_name=link_name,
                    vbo=vbo,
                    vao=vao,
                    vertex_count=n,
                    inv_zero_T=inv_zero,
                    raw_vertices=vertices,
                )
            )

    # ------------------------------------------------------------------
    # Per-frame update (lightweight — matrices only)
    # ------------------------------------------------------------------

    def update(self, joint_angles: dict[JointName, float]) -> None:
        """Update joint angles — recomputes link matrices, no VBO touch."""
        self._current_angles.update(joint_angles)
        self._link_transforms = compute_link_transforms(self._current_angles)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _write_model_matrix(self, prog: moderngl.Program, mat: np.ndarray) -> None:
        """Write a 4×4 model matrix to the ``model`` uniform."""
        prog["model"].write(np.ascontiguousarray(mat.astype("f4").T).tobytes())

    def render_3d(self, mvp: np.ndarray, alpha: float = 1.0) -> None:
        """Render excavator with per-part model matrices."""
        if not self._parts:
            return

        prog = self._renderer.prog_solid  # type: ignore[attr-defined]
        ctx = self._renderer.ctx  # type: ignore[attr-defined]

        prog["mvp"].write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
        prog["alpha"].value = alpha
        ctx.enable(moderngl.DEPTH_TEST)

        for part in self._parts:
            link_T = self._link_transforms.get(part.link_name)
            if link_T is None:
                continue
            # Differential transform: link_T(current) × inv(link_T(zero))
            model = link_T @ part.inv_zero_T
            self._write_model_matrix(prog, model)
            part.vao.render(moderngl.TRIANGLES, vertices=part.vertex_count)

        # Reset model to identity so other prog_solid users are unaffected
        self._write_model_matrix(prog, np.eye(4, dtype=np.float64))
        ctx.disable(moderngl.DEPTH_TEST)

    def render_2d_side(self, ortho: np.ndarray, alpha: float = 1.0) -> None:
        """Render in side view (XZ projection)."""
        self.render_3d(ortho, alpha)

    def render_2d_top(self, ortho: np.ndarray, alpha: float = 1.0) -> None:
        """Render in top view (XY projection)."""
        self.render_3d(ortho, alpha)

    def render_glow(self, alpha: float = 0.18) -> None:
        """Re-render all parts at given alpha (glow/additive pass).

        Assumes mvp + blend state are already set by the caller.
        Model matrices are re-applied from current link transforms.
        """
        if not self._parts:
            return
        prog = self._renderer.prog_solid  # type: ignore[attr-defined]
        prog["alpha"].value = alpha
        for part in self._parts:
            link_T = self._link_transforms.get(part.link_name)
            if link_T is None:
                continue
            model = link_T @ part.inv_zero_T
            self._write_model_matrix(prog, model)
            part.vao.render(moderngl.TRIANGLES, vertices=part.vertex_count)
        self._write_model_matrix(prog, np.eye(4, dtype=np.float64))

    # ------------------------------------------------------------------
    # CPU-side data access (for ghost glow / outline — no GPU readback)
    # ------------------------------------------------------------------

    def get_transformed_vertices(self) -> np.ndarray:
        """Return all vertices transformed to current world positions.

        Returns (total_verts, 9) array: position(3) + color(3) + normal(3).
        Used by VisualCueRenderer for ghost glow/outline — avoids GPU readback.
        """
        if not self._parts:
            return np.empty((0, 9), dtype=np.float32)

        segments: list[np.ndarray] = []
        for part in self._parts:
            link_T = self._link_transforms.get(part.link_name)
            if link_T is None:
                continue
            model = link_T @ part.inv_zero_T
            rot = model[:3, :3].astype(np.float32)
            trans = model[:3, 3].astype(np.float32)

            world_pos = part.raw_vertices @ rot.T + trans

            # Color from VBO (static) — read first 3 color floats
            color_key = self._link_color_map.get(part.link_name, "base")
            r, g, b = self._joint_colors.get(color_key, (0.5, 0.5, 0.5))
            colors = np.full((part.vertex_count, 3), (r, g, b), dtype=np.float32)

            # Read normals from raw data (stored in loader output)
            # We need to get them from the interleaved VBO data, but since
            # we stored raw_vertices separately, re-derive from link_T
            normals = np.zeros_like(world_pos)  # simplified for glow use

            chunk = np.empty((part.vertex_count, 9), dtype=np.float32)
            chunk[:, :3] = world_pos
            chunk[:, 3:6] = colors
            chunk[:, 6:9] = normals
            segments.append(chunk)

        return np.vstack(segments) if segments else np.empty((0, 9), dtype=np.float32)

    def destroy(self) -> None:
        for part in self._parts:
            part.vbo.release()
            part.vao.release()
