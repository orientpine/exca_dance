"""GL text renderer: renders text via pygame.font → GL texture."""

from __future__ import annotations
import pygame
import moderngl


class GLTextRenderer:
    """Renders text strings as OpenGL textured quads."""

    def __init__(
        self,
        renderer,
        font_path: str | None,
        font_size: int = 24,
    ):
        self._renderer = renderer
        pygame.font.init()
        self._font = pygame.font.Font(font_path, font_size)
        self._judgment_font = pygame.font.Font(font_path, 48)
        self._texture_cache: dict[tuple[str, int], tuple[moderngl.Texture, int, int]] = {}

    def _get_or_create_texture(
        self,
        text: str,
        font: pygame.font.Font | None = None,
    ) -> tuple[moderngl.Texture, int, int]:
        """Create or retrieve a cached GL texture for the given text.
        Renders in white, uses the surface's per-pixel alpha as glyph mask.
        Color is applied by the shader uniform.
        """
        active_font = self._font if font is None else font
        key = (text, id(active_font))
        if key not in self._texture_cache:
            # Render white text with antialiasing — pygame creates per-pixel alpha
            surf = active_font.render(text, True, (255, 255, 255))
            surf = surf.convert_alpha()
            w, h = surf.get_size()
            if w == 0 or h == 0:
                w, h = max(w, 1), max(h, 1)
            # Extract the ACTUAL alpha channel — this is the glyph mask
            alpha_arr = pygame.surfarray.pixels_alpha(surf)  # (W, H) uint8
            alpha_mask = alpha_arr.T.copy()  # transpose to (H, W) for row-major GL
            tex = self._renderer.ctx.texture((w, h), 1, alpha_mask.tobytes(), dtype="f1")
            tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
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
        *,
        large: bool = False,
    ) -> None:
        """
        Render text at screen pixel position (x, y).
        color: (r, g, b, a) as floats 0-1
        align: "left", "center", "right"
        large: use 48px judgment font for crisp large text
        """
        if not text:
            return
        font = self._judgment_font if large else None
        tex, w, h = self._get_or_create_texture(text, font=font)
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

    def render_judgment(
        self,
        text: str,
        x: float,
        y: float,
        color: tuple = (1.0, 1.0, 1.0, 1.0),
        scale: float = 1.0,
        align: str = "left",
    ) -> None:
        if not text:
            return
        tex, w, h = self._get_or_create_texture(text, font=self._judgment_font)
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
