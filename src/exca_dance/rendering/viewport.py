"""Viewport manager for multi-panel rendering."""

from __future__ import annotations

import moderngl

from exca_dance.core.constants import SCREEN_HEIGHT, SCREEN_WIDTH


class ViewportManager:
    """
    Manages multiple viewport regions within a single window.

    Layout (GL bottom-left origin):
      ┌─────────────────┬───────────────────┐
      │    main_3d       │     side_2d       │  top 72%
      │   (55% width)    │  (45%, top 65%)   │
      │                  ├───────────────────┤
      │                  │     top_2d        │
      │                  │  (45%, bot 35%)   │
      ├──────────────────┴───────────────────┤
      │          timeline area               │  bottom 28%
      └─────────────────────────────────────-┘
    """

    def __init__(self, width: int = SCREEN_WIDTH, height: int = SCREEN_HEIGHT):
        self._width = width
        self._height = height

        # Vertical: main area (72%) + timeline (28%)
        timeline_h = int(height * 0.28)
        main_h = height - timeline_h

        # Horizontal: 3D view (55%) + right panels (45%)
        main_3d_w = int(width * 0.55)
        right_w = width - main_3d_w

        # Right column: side view (top 65%) + top view (bottom 35%)
        side_h = int(main_h * 0.65)
        top_h = main_h - side_h

        # GL origin is bottom-left
        self._viewports = {
            "main_3d": (0, timeline_h, main_3d_w, main_h),
            "side_2d": (main_3d_w, timeline_h + top_h, right_w, side_h),
            "top_2d": (main_3d_w, timeline_h, right_w, top_h),
        }
        self._timeline_rect = (0, 0, width, timeline_h)

    @property
    def timeline_rect(self) -> tuple[int, int, int, int]:
        """Return (x, y, width, height) for the timeline area (GL coords)."""
        return self._timeline_rect

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
