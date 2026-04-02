"""ModernGL-based game renderer using Pygame as window backend."""

from __future__ import annotations
import os
from typing import Any, cast
import pygame
import moderngl
import numpy as np
from exca_dance.core.constants import SCREEN_WIDTH, SCREEN_HEIGHT, TARGET_FPS


class GameRenderer:
    """Manages the ModernGL rendering context and window."""

    def __init__(
        self,
        width: int = SCREEN_WIDTH,
        height: int = SCREEN_HEIGHT,
        title: str = "Exca Dance",
        fullscreen: bool = False,
    ):
        pygame.display.init()
        flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.NOFRAME
        if fullscreen:
            os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
        self._surface = pygame.display.set_mode((width, height), flags)
        pygame.display.set_caption(title)
        self._ctx = moderngl.create_context()
        self._ctx.enable(moderngl.BLEND)
        self._ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self._width = width
        self._height = height
        self._clock = pygame.time.Clock()
        self._bloom_enabled = False
        self._scene_tex: moderngl.Texture | None = None
        self._scene_fbo: moderngl.Framebuffer | None = None
        self._bloom_tex: moderngl.Texture | None = None
        self._bloom_fbo: moderngl.Framebuffer | None = None
        self._bloom_tmp_tex: moderngl.Texture | None = None
        self._bloom_tmp_fbo: moderngl.Framebuffer | None = None
        self._compile_shaders()

    @staticmethod
    def _set_uniform(program: moderngl.Program, name: str, value: Any) -> None:
        cast(Any, program[name]).value = value

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
            uniform mat4 model;
            void main() {
                vec4 world_pos = model * vec4(in_position, 1.0);
                gl_Position = mvp * world_pos;
                v_color = in_color;
                v_normal = mat3(model) * in_normal;
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
                float nl = length(v_normal);
                float diffuse = nl > 0.001
                    ? max(dot(v_normal / nl, light_dir), 0.0) : 0.0;
                float ambient = 0.35;
                float lighting = ambient + (1.0 - ambient) * diffuse;
                f_color = vec4(v_color * lighting, alpha);
            }
            """,
        )
        # Set model uniform to identity by default
        _id4 = np.eye(4, dtype="f4")
        self._prog_solid["model"].write(np.ascontiguousarray(_id4.T).tobytes())
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
            uniform float alpha_mult;
            void main() { f_color = vec4(v_color.rgb, v_color.a * alpha_mult); }
            """,
        )
        self._set_uniform(self._prog_additive, "alpha_mult", 1.0)
        self._prog_bloom_extract = self._ctx.program(
            vertex_shader="""
            #version 330
            in vec2 in_position;
            in vec2 in_uv;
            out vec2 v_uv;
            void main() {
                gl_Position = vec4(in_position, 0.0, 1.0);
                v_uv = in_uv;
            }
            """,
            fragment_shader="""
            #version 330
            in vec2 v_uv;
            out vec4 f_color;
            uniform sampler2D tex;
            uniform float threshold;
            void main() {
                vec4 c = texture(tex, v_uv);
                float luminance = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
                f_color = luminance > threshold ? c : vec4(0.0, 0.0, 0.0, 1.0);
            }
            """,
        )
        self._prog_bloom_blit = self._ctx.program(
            vertex_shader="""
            #version 330
            in vec2 in_position;
            in vec2 in_uv;
            out vec2 v_uv;
            void main() {
                gl_Position = vec4(in_position, 0.0, 1.0);
                v_uv = in_uv;
            }
            """,
            fragment_shader="""
            #version 330
            in vec2 v_uv;
            out vec4 f_color;
            uniform sampler2D tex;
            uniform sampler2D bloom_tex;
            uniform vec2 texel_size;
            uniform bool horizontal;
            uniform bool do_blur;
            uniform bool do_composite;
            void main() {
                if (do_composite) {
                    vec4 base = texture(tex, v_uv);
                    vec4 bloom = texture(bloom_tex, v_uv);
                    f_color = vec4(base.rgb + bloom.rgb, 1.0);
                    return;
                }

                if (do_blur) {
                    vec2 axis = horizontal ? vec2(texel_size.x, 0.0) : vec2(0.0, texel_size.y);
                    vec3 result = texture(tex, v_uv).rgb * 0.227027;
                    result += texture(tex, v_uv + axis * 1.384615).rgb * 0.316216;
                    result += texture(tex, v_uv - axis * 1.384615).rgb * 0.316216;
                    result += texture(tex, v_uv + axis * 3.230769).rgb * 0.070270;
                    result += texture(tex, v_uv - axis * 3.230769).rgb * 0.070270;
                    f_color = vec4(result, 1.0);
                    return;
                }

                f_color = texture(tex, v_uv);
            }
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

        bloom_quad_verts = np.array(
            [
                -1.0,
                -1.0,
                0.0,
                0.0,
                1.0,
                -1.0,
                1.0,
                0.0,
                1.0,
                1.0,
                1.0,
                1.0,
                -1.0,
                -1.0,
                0.0,
                0.0,
                1.0,
                1.0,
                1.0,
                1.0,
                -1.0,
                1.0,
                0.0,
                1.0,
            ],
            dtype="f4",
        )
        self._bloom_quad_vbo = self._ctx.buffer(bloom_quad_verts)
        self._bloom_extract_vao = self._ctx.vertex_array(
            self._prog_bloom_extract,
            [(self._bloom_quad_vbo, "2f 2f", "in_position", "in_uv")],
        )
        self._bloom_blit_vao = self._ctx.vertex_array(
            self._prog_bloom_blit,
            [(self._bloom_quad_vbo, "2f 2f", "in_position", "in_uv")],
        )

        self._set_uniform(self._prog_bloom_extract, "tex", 0)
        self._set_uniform(self._prog_bloom_extract, "threshold", 0.7)
        self._set_uniform(self._prog_bloom_blit, "tex", 0)
        self._set_uniform(self._prog_bloom_blit, "bloom_tex", 1)
        self._set_uniform(self._prog_bloom_blit, "do_blur", False)
        self._set_uniform(self._prog_bloom_blit, "do_composite", False)

    def _setup_bloom(self) -> None:
        w, h = self._width, self._height
        self._scene_tex = self._ctx.texture((w, h), 4)
        self._scene_fbo = self._ctx.framebuffer([self._scene_tex])

        bw, bh = max(1, w // 2), max(1, h // 2)
        self._bloom_tex = self._ctx.texture((bw, bh), 4)
        self._bloom_fbo = self._ctx.framebuffer([self._bloom_tex])
        self._bloom_tmp_tex = self._ctx.texture((bw, bh), 4)
        self._bloom_tmp_fbo = self._ctx.framebuffer([self._bloom_tmp_tex])

        for tex in (self._scene_tex, self._bloom_tex, self._bloom_tmp_tex):
            tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

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
    def bloom_enabled(self) -> bool:
        return self._bloom_enabled

    @bloom_enabled.setter
    def bloom_enabled(self, value: bool) -> None:
        self._bloom_enabled = value
        if self._bloom_enabled and self._scene_fbo is None:
            self._setup_bloom()

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def begin_frame(self) -> None:
        """Clear the framebuffer."""
        if self._bloom_enabled and self._scene_fbo:
            self._scene_fbo.use()
            self._ctx.viewport = (0, 0, self._width, self._height)
            self._scene_fbo.clear(0.04, 0.04, 0.1, 1.0)
        else:
            self._ctx.screen.use()
            self._ctx.viewport = (0, 0, self._width, self._height)
            self._ctx.clear(0.04, 0.04, 0.1, 1.0)  # dark navy background

    def _apply_bloom(self) -> None:
        if (
            self._scene_tex is None
            or self._scene_fbo is None
            or self._bloom_tex is None
            or self._bloom_fbo is None
            or self._bloom_tmp_tex is None
            or self._bloom_tmp_fbo is None
        ):
            return

        ctx = self._ctx
        bw, bh = cast(tuple[int, int], self._bloom_tex.size)

        ctx.disable(moderngl.BLEND)

        self._bloom_fbo.use()
        ctx.viewport = (0, 0, bw, bh)
        self._bloom_fbo.clear(0.0, 0.0, 0.0, 1.0)
        self._scene_tex.use(location=0)
        self._bloom_extract_vao.render(moderngl.TRIANGLES)

        self._bloom_tmp_fbo.use()
        ctx.viewport = (0, 0, bw, bh)
        self._bloom_tmp_fbo.clear(0.0, 0.0, 0.0, 1.0)
        self._set_uniform(self._prog_bloom_blit, "do_blur", True)
        self._set_uniform(self._prog_bloom_blit, "do_composite", False)
        self._set_uniform(self._prog_bloom_blit, "horizontal", True)
        self._set_uniform(self._prog_bloom_blit, "texel_size", (1.0 / bw, 1.0 / bh))
        self._bloom_tex.use(location=0)
        self._bloom_blit_vao.render(moderngl.TRIANGLES)

        self._bloom_fbo.use()
        ctx.viewport = (0, 0, bw, bh)
        self._bloom_fbo.clear(0.0, 0.0, 0.0, 1.0)
        self._set_uniform(self._prog_bloom_blit, "horizontal", False)
        self._bloom_tmp_tex.use(location=0)
        self._bloom_blit_vao.render(moderngl.TRIANGLES)

        ctx.screen.use()
        ctx.viewport = (0, 0, self._width, self._height)
        self._set_uniform(self._prog_bloom_blit, "do_blur", False)
        self._set_uniform(self._prog_bloom_blit, "do_composite", True)
        self._scene_tex.use(location=0)
        self._bloom_tex.use(location=1)
        self._bloom_blit_vao.render(moderngl.TRIANGLES)
        self._set_uniform(self._prog_bloom_blit, "do_composite", False)
        ctx.enable(moderngl.BLEND)

    def end_frame(self) -> float:
        """Swap buffers and return delta time in seconds."""
        if self._bloom_enabled and self._scene_fbo:
            self._apply_bloom()
        pygame.display.flip()
        dt = self._clock.tick(TARGET_FPS) / 1000.0
        return dt

    def get_fps(self) -> float:
        return self._clock.get_fps()

    def destroy(self) -> None:
        for resource in (
            self._bloom_extract_vao,
            self._bloom_blit_vao,
            self._bloom_quad_vbo,
            self._bloom_tmp_fbo,
            self._bloom_tmp_tex,
            self._bloom_fbo,
            self._bloom_tex,
            self._scene_fbo,
            self._scene_tex,
            self._quad_vao,
            self._quad_vbo,
        ):
            if resource is not None:
                resource.release()
        self._ctx.release()
        pygame.display.quit()
