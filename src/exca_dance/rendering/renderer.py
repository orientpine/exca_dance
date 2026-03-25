"""ModernGL-based game renderer using Pygame as window backend."""

from __future__ import annotations
import pygame
import moderngl
import numpy as np
from exca_dance.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT, TARGET_FPS


class GameRenderer:
    """Manages the ModernGL rendering context and window."""

    def __init__(
        self, width: int = SCREEN_WIDTH, height: int = SCREEN_HEIGHT, title: str = "Exca Dance"
    ):
        pygame.display.init()
        flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.NOFRAME
        self._surface = pygame.display.set_mode((width, height), flags)
        pygame.display.set_caption(title)
        self._ctx = moderngl.create_context()
        self._ctx.enable(moderngl.BLEND)
        self._ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self._width = width
        self._height = height
        self._clock = pygame.time.Clock()
        self._compile_shaders()

    def _compile_shaders(self) -> None:
        """Compile reusable shader programs."""
        # Solid color 3D shader (for geometry)
        self._prog_solid = self._ctx.program(
            vertex_shader="""
            #version 330
            in vec3 in_position;
            in vec3 in_color;
            in vec3 in_normal;
            out vec3 v_color;
            out vec3 v_normal;
            uniform mat4 mvp;
            void main() {
                gl_Position = mvp * vec4(in_position, 1.0);
                v_color = in_color;
                v_normal = in_normal;
            }
            """,
            fragment_shader="""
            #version 330
            in vec3 v_color;
            in vec3 v_normal;
            out vec4 f_color;
            uniform float alpha;
            void main() {
                vec3 light_dir = normalize(vec3(0.3, -0.5, 0.8));
                float diffuse = max(dot(normalize(v_normal), light_dir), 0.0);
                float ambient = 0.35;
                float lighting = ambient + (1.0 - ambient) * diffuse;
                f_color = vec4(v_color * lighting, alpha);
            }
            """,
        )
        # Textured quad shader (for GL text)
        self._prog_tex = self._ctx.program(
            vertex_shader="""
            #version 330
            in vec2 in_position;
            in vec2 in_uv;
            out vec2 v_uv;
            uniform vec2 screen_size;
            uniform vec2 pos;
            uniform vec2 size;
            void main() {
                vec2 p = pos + in_position * size;
                vec2 ndc = (p / screen_size) * 2.0 - 1.0;
                ndc.y = -ndc.y;
                gl_Position = vec4(ndc, 0.0, 1.0);
                v_uv = in_uv;
            }
            """,
            fragment_shader="""
            #version 330
            in vec2 v_uv;
            out vec4 f_color;
            uniform sampler2D tex;
            uniform vec4 color;
            void main() {
                float a = texture(tex, v_uv).r;
                f_color = vec4(color.rgb, color.a * a);
            }
            """,
        )
        # Additive blend shader (for glow / neon effects)
        self._prog_additive = self._ctx.program(
            vertex_shader="""
            #version 330
            in vec3 in_position;
            in vec4 in_color;
            out vec4 v_color;
            uniform mat4 mvp;
            void main() {
                gl_Position = mvp * vec4(in_position, 1.0);
                v_color = in_color;
            }
            """,
            fragment_shader="""
            #version 330
            in vec4 v_color;
            out vec4 f_color;
            void main() { f_color = v_color; }
            """,
        )
        # Quad VBO for textured rendering
        quad_verts = np.array(
            [
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                1.0,
                0.0,
                1.0,
                1.0,
                1.0,
                1.0,
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,
                1.0,
                1.0,
                1.0,
                0.0,
                1.0,
                0.0,
                1.0,
            ],
            dtype="f4",
        )
        self._quad_vbo = self._ctx.buffer(quad_verts)
        self._quad_vao = self._ctx.vertex_array(
            self._prog_tex, [(self._quad_vbo, "2f 2f", "in_position", "in_uv")]
        )

    @property
    def ctx(self) -> moderngl.Context:
        return self._ctx

    @property
    def prog_solid(self) -> moderngl.Program:
        return self._prog_solid

    @property
    def prog_additive(self) -> moderngl.Program:
        return self._prog_additive

    @property
    def prog_tex(self) -> moderngl.Program:
        return self._prog_tex

    @property
    def quad_vao(self) -> moderngl.VertexArray:
        return self._quad_vao

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def begin_frame(self) -> None:
        """Clear the framebuffer."""
        self._ctx.viewport = (0, 0, self._width, self._height)
        self._ctx.clear(0.04, 0.04, 0.1, 1.0)  # dark navy background

    def end_frame(self) -> float:
        """Swap buffers and return delta time in seconds."""
        pygame.display.flip()
        dt = self._clock.tick(TARGET_FPS) / 1000.0
        return dt

    def get_fps(self) -> float:
        return self._clock.get_fps()

    def destroy(self) -> None:
        self._ctx.release()
        pygame.display.quit()
