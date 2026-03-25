"""GL text renderer: renders text via pygame.font → GL texture."""

from __future__ import annotations
from functools import lru_cache
import pygame
import moderngl
import numpy as np


class GLTextRenderer:
    """Renders text strings as OpenGL textured quads."""

    def __init__(self, renderer, font_path: str, font_size: int = 24):
        self._renderer = renderer
        pygame.font.init()
        self._font = pygame.font.Font(font_path, font_size)
        self._texture_cache: dict[tuple, moderngl.Texture] = {}

    def _get_or_create_texture(self, text: str, color: tuple) -> tuple[moderngl.Texture, int, int]:
        key = (text, color, id(self._font))
        if key not in self._texture_cache:
            surf = self._font.render(text, True, color[:3])
            w, h = surf.get_size()
            # Convert to grayscale alpha: use red channel as alpha
            # Use luminance-only texture for memory efficiency
            raw = pygame.surfarray.array3d(surf)  # (W, H, 3) uint8
            # Use red channel as grayscale proxy
            gray = raw[:, :, 0].T.copy()  # (H, W) uint8
            tex = self._renderer.ctx.texture((w, h), 1, gray.tobytes(), dtype="f1")
            tex.filter = moderngl.LINEAR, moderngl.LINEAR
            self._texture_cache[key] = (tex, w, h)
        return self._texture_cache[key]

    def render(
        self,
        text: str,
        x: float,
        y: float,
        color: tuple = (1.0, 1.0, 1.0, 1.0),
        scale: float = 1.0,
        align: str = "left",
    ) -> None:
        """
        Render text at screen pixel position (x, y).
        color: (r, g, b, a) as floats 0-1
        align: "left", "center", "right"
        """
        r_color = tuple(int(c * 255) for c in color[:3])
        tex, w, h = self._get_or_create_texture(text, r_color)
        rw, rh = w * scale, h * scale
        if align == "center":
            x -= rw / 2
        elif align == "right":
            x -= rw

        prog = self._renderer.prog_tex
        prog["screen_size"].value = (float(self._renderer.width), float(self._renderer.height))
        prog["pos"].value = (float(x), float(y))
        prog["size"].value = (float(rw), float(rh))
        prog["color"].value = tuple(color)
        tex.use(0)
        prog["tex"].value = 0
        self._renderer.quad_vao.render()

    def destroy(self) -> None:
        for tex, _, _ in self._texture_cache.values():
            tex.release()
        self._texture_cache.clear()
