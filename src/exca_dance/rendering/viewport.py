"""Viewport manager for multi-panel rendering."""

from __future__ import annotations
import moderngl
from exca_dance.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT


class ViewportManager:
    """
    Manages multiple viewport regions within a single window.
    Layout:
      - main_3d:  left 75%, full height (perspective 3D view)
      - top_2d:   right 25%, top 50% (orthographic top view)
      - side_2d:  right 25%, bottom 50% (orthographic side view)
    """

    def __init__(self, width: int = SCREEN_WIDTH, height: int = SCREEN_HEIGHT):
        self._width = width
        self._height = height
        main_w = int(width * 0.75)
        panel_w = width - main_w
        panel_h = height // 2
        self._viewports = {
            "main_3d": (0, 0, main_w, height),
            "top_2d": (main_w, panel_h, panel_w, panel_h),
            "side_2d": (main_w, 0, panel_w, panel_h),
        }

    def get_viewport_rect(self, name: str) -> tuple[int, int, int, int]:
        """Return (x, y, width, height) for a named viewport."""
        return self._viewports[name]

    def set_viewport(self, ctx: moderngl.Context, name: str) -> None:
        """Set the GL viewport to the named region."""
        x, y, w, h = self._viewports[name]
        ctx.viewport = (x, y, w, h)

    def get_aspect_ratio(self, name: str) -> float:
        _, _, w, h = self._viewports[name]
        return w / h if h > 0 else 1.0

    def list_viewports(self) -> list[str]:
        return list(self._viewports.keys())
