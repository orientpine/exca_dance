"""Multi-viewport layout for Exca Dance gameplay screen."""

from __future__ import annotations
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

        # Top-down orthographic (XY plane, camera looks down -Z — default)
        self._mvp_top: np.ndarray = _ortho(-8.0, 8.0, -6.0, 6.0).astype("f4")

        # Side orthographic (XZ plane, looking along +Y)
        # Rotation swaps axes: view_X = world_X, view_Y = world_Z, depth = -world_Y
        side_view = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, -1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype="f4")
        self._mvp_side: np.ndarray = (_ortho(-2.0, 10.0, -1.0, 7.0) @ side_view).astype("f4")

    def render_all(self, excavator_model, joint_angles: dict) -> None:
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
