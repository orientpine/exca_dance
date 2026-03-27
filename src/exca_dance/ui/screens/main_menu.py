"""Main menu screen with animated 3D excavator and neon cyberpunk effects."""

from __future__ import annotations

# pyright: reportPrivateUsage=false
import math
import random

import moderngl
import numpy as np
import pygame

from exca_dance.core.game_state import ScreenName
from exca_dance.core.kinematics import ExcavatorFK
from exca_dance.core.models import JointName
from exca_dance.rendering.excavator_model import ExcavatorModel
from exca_dance.rendering.renderer import GameRenderer
from exca_dance.rendering.gl_text import GLTextRenderer
from exca_dance.rendering.theme import NeonTheme

MENU_ITEMS = [
    ("PLAY", ScreenName.SONG_SELECT),
    ("HOW TO PLAY", ScreenName.TUTORIAL),
    ("EDITOR", ScreenName.EDITOR),
    ("LEADERBOARD", ScreenName.LEADERBOARD),
    ("SETTINGS", ScreenName.SETTINGS),
    ("QUIT", "quit"),
]

_NUM_PARTICLES = 50


def _perspective(
    fov_deg: float,
    aspect: float,
    near: float,
    far: float,
) -> np.ndarray:
    """Build a perspective projection matrix."""
    f = 1.0 / np.tan(np.radians(fov_deg) / 2.0)
    m = np.zeros((4, 4), dtype="f4")
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def _look_at(
    eye: np.ndarray,
    target: np.ndarray,
    up: np.ndarray,
) -> np.ndarray:
    """Build a look-at view matrix."""
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


class MainMenuScreen:
    """Animated main menu with 3D excavator and neon cyberpunk effects."""

    def __init__(
        self,
        renderer: GameRenderer,
        text_renderer: GLTextRenderer,
        mode_label: str,
        fk: ExcavatorFK,
        excavator_model_class: type[ExcavatorModel],
    ) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._selected = 0
        self._mode_label = mode_label
        self._time: float = 0.0

        # Neon-colored excavator for menu background
        neon_colors: dict[str | JointName, tuple[float, float, float]] = {
            "base": (0.0, 0.35, 0.45),
            "turret": (0.0, 0.45, 0.55),
            JointName.BOOM: NeonTheme.NEON_PINK.as_rgb(),
            JointName.ARM: NeonTheme.NEON_ORANGE.as_rgb(),
            JointName.BUCKET: NeonTheme.NEON_GREEN.as_rgb(),
        }
        self._menu_model = excavator_model_class(
            renderer,
            fk,
            joint_colors=neon_colors,
        )

        # Camera: cinematic angle, excavator on the left
        W, H = renderer.width, renderer.height
        aspect = W / H
        eye = np.array([8.0, -10.0, 5.0], dtype="f4")
        target = np.array([1.0, 0.0, 1.8], dtype="f4")
        up = np.array([0.0, 0.0, 1.0], dtype="f4")
        proj = _perspective(40.0, aspect, 0.1, 100.0)
        view = _look_at(eye, target, up)
        self._mvp: np.ndarray = (proj @ view).astype("f4")

        # Background particles
        self._particles: list[dict[str, float]] = []
        self._init_particles()

        # Pre-build ground grid VBO (static geometry)
        self._grid_vbo: moderngl.Buffer | None = None
        self._grid_vao: moderngl.VertexArray | None = None
        self._grid_line_count = 0
        self._build_grid()

    # ── Initialization helpers ───────────────────────────────────

    def _init_particles(self) -> None:
        """Initialize floating neon particle field."""
        self._particles.clear()
        for _ in range(_NUM_PARTICLES):
            self._particles.append(
                {
                    "x": random.uniform(-1.0, 1.0),
                    "y": random.uniform(-1.0, 1.0),
                    "speed": random.uniform(0.03, 0.10),
                    "size": random.uniform(0.002, 0.005),
                    "phase": random.uniform(0.0, math.tau),
                    "color": float(random.randint(0, 3)),
                }
            )

    def _build_grid(self) -> None:
        """Build a perspective ground-plane grid (Z=0)."""
        r = NeonTheme.NEON_BLUE.r * 0.4
        g = NeonTheme.NEON_BLUE.g * 0.4
        b = NeonTheme.NEON_BLUE.b * 0.4
        verts: list[float] = []
        for i in range(-6, 14):
            x = float(i)
            verts += [
                x,
                -12.0,
                0.0,
                r,
                g,
                b,
                x,
                12.0,
                0.0,
                r,
                g,
                b,
            ]
        for j in range(-12, 13):
            y = float(j)
            verts += [
                -6.0,
                y,
                0.0,
                r,
                g,
                b,
                14.0,
                y,
                0.0,
                r,
                g,
                b,
            ]
        if verts:
            data = np.array(verts, dtype="f4")
            ctx = self._renderer.ctx
            self._grid_vbo = ctx.buffer(data)
            self._grid_vao = ctx.vertex_array(
                self._renderer.prog_solid,
                [(self._grid_vbo, "3f 3f", "in_position", "in_color")],
            )
            self._grid_line_count = len(data) // 6

    # ── Screen protocol ──────────────────────────────────────────

    def on_enter(self, **kwargs) -> None:
        self._selected = 0

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self._selected = (self._selected - 1) % len(MENU_ITEMS)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._selected = (self._selected + 1) % len(MENU_ITEMS)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                _, target = MENU_ITEMS[self._selected]
                return target
        return None

    def update(self, dt: float):
        self._time += dt
        t = self._time

        # Animate excavator joints with layered sine waves
        angles: dict[JointName, float] = {
            JointName.SWING: 20.0 * math.sin(t * 0.25),
            JointName.BOOM: 15.0 + 18.0 * math.sin(t * 0.4),
            JointName.ARM: (-5.0 + 25.0 * math.sin(t * 0.55 + 1.2)),
            JointName.BUCKET: (80.0 + 35.0 * math.sin(t * 0.35 + 2.5)),
        }
        self._menu_model.update(angles)

        # Drift particles upward
        for p in self._particles:
            p["y"] += p["speed"] * dt
            if p["y"] > 1.15:
                p["y"] = -1.15
                p["x"] = random.uniform(-1.0, 1.0)

        return None

    def render(self, renderer, text_renderer) -> None:
        if text_renderer is None:
            return
        W, H = renderer.width, renderer.height
        ctx = renderer.ctx

        # Layer 1: Ground grid
        self._render_grid(ctx)

        # Layer 2: 3D excavator (solid)
        self._menu_model.render_3d(self._mvp, alpha=0.9)

        # Layer 3: Excavator additive glow overlay
        # render_3d left DEPTH_TEST disabled, reuse same VAO
        self._render_excavator_glow(ctx)

        # Layer 4: Dim overlay on right half for text readability
        self._render_overlay(ctx, W, H)

        # Layer 5: Floating neon particles
        self._render_particles(ctx)

        # Layer 6: Horizontal accent lines
        self._render_accent_lines(ctx)

        # Layer 7: Title with glow
        self._render_title(text_renderer, W, H)

        # Layer 8: Menu items
        self._render_menu(text_renderer, W, H)

        # Layer 9: Footer (resolution-aware)
        s = H / 1080.0
        text_renderer.render(
            f"MODE: {self._mode_label}",
            W // 2,
            H - int(30 * s),
            color=NeonTheme.TEXT_DIM.with_alpha(0.5).as_tuple(),
            scale=max(0.9 * s, 0.6),
            align="center",
        )
        text_renderer.render(
            "\u2191\u2193 SELECT   ENTER CONFIRM   Q QUIT",
            W // 2,
            H - int(60 * s),
            color=NeonTheme.TEXT_DIM.with_alpha(0.3).as_tuple(),
            scale=max(0.8 * s, 0.55),
            align="center",
        )

    # ── Render helpers ───────────────────────────────────────────

    def _render_grid(self, ctx: moderngl.Context) -> None:
        """Render pulsing ground grid."""
        if self._grid_vao is None:
            return
        prog = self._renderer.prog_solid
        prog["mvp"].write(
            np.ascontiguousarray(
                self._mvp.astype("f4").T,
            ).tobytes()
        )
        pulse = 0.15 + 0.08 * math.sin(self._time * 0.6)
        prog["alpha"].value = pulse
        ctx.disable(moderngl.DEPTH_TEST)
        self._grid_vao.render(
            moderngl.LINES,
            vertices=self._grid_line_count,
        )

    def _render_excavator_glow(
        self,
        ctx: moderngl.Context,
    ) -> None:
        """Additive glow pass on excavator geometry."""
        model = self._menu_model
        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
        # prog_solid MVP already set by render_3d; just update alpha
        model.render_glow(alpha=0.18)
        ctx.blend_func = moderngl.DEFAULT_BLENDING
        ctx.blend_func = moderngl.DEFAULT_BLENDING

    def _render_overlay(
        self,
        ctx: moderngl.Context,
        W: int,
        H: int,
    ) -> None:
        """Semi-transparent dark overlay on right half."""
        prog = self._renderer.prog_solid
        identity = np.eye(4, dtype="f4")
        prog["mvp"].write(
            np.ascontiguousarray(identity).tobytes(),
        )
        prog["alpha"].value = 0.55

        bg = NeonTheme.BG
        r, g, b = bg.r, bg.g, bg.b
        x0 = 0.05  # NDC: just right of center
        verts = np.array(
            [
                x0,
                -1.0,
                0.0,
                r,
                g,
                b,
                1.0,
                -1.0,
                0.0,
                r,
                g,
                b,
                1.0,
                1.0,
                0.0,
                r,
                g,
                b,
                x0,
                -1.0,
                0.0,
                r,
                g,
                b,
                1.0,
                1.0,
                0.0,
                r,
                g,
                b,
                x0,
                1.0,
                0.0,
                r,
                g,
                b,
            ],
            dtype="f4",
        )
        vbo = ctx.buffer(verts)
        vao = ctx.vertex_array(
            prog,
            [(vbo, "3f 3f", "in_position", "in_color")],
        )
        vao.render(moderngl.TRIANGLES)
        vao.release()
        vbo.release()

    def _render_particles(
        self,
        ctx: moderngl.Context,
    ) -> None:
        """Render floating neon particles with additive blending."""
        palette = [
            NeonTheme.NEON_BLUE.as_rgb(),
            NeonTheme.NEON_PINK.as_rgb(),
            NeonTheme.NEON_GREEN.as_rgb(),
            NeonTheme.NEON_PURPLE.as_rgb(),
        ]
        t = self._time
        verts: list[float] = []
        for p in self._particles:
            x, y = p["x"], p["y"]
            s = p["size"]
            cr, cg, cb = palette[int(p["color"])]
            twinkle = 0.3 + 0.7 * abs(math.sin(t * 2.5 + p["phase"]))
            a = twinkle * 0.5
            # Quad: 2 triangles
            verts += [
                x - s,
                y - s,
                0.0,
                cr,
                cg,
                cb,
                a,
                x + s,
                y - s,
                0.0,
                cr,
                cg,
                cb,
                a,
                x + s,
                y + s,
                0.0,
                cr,
                cg,
                cb,
                a,
                x - s,
                y - s,
                0.0,
                cr,
                cg,
                cb,
                a,
                x + s,
                y + s,
                0.0,
                cr,
                cg,
                cb,
                a,
                x - s,
                y + s,
                0.0,
                cr,
                cg,
                cb,
                a,
            ]

        if not verts:
            return

        data = np.array(verts, dtype="f4")
        vbo = ctx.buffer(data)
        prog = self._renderer.prog_additive
        vao = ctx.vertex_array(
            prog,
            [(vbo, "3f 4f", "in_position", "in_color")],
        )

        identity = np.eye(4, dtype="f4")
        prog["mvp"].write(
            np.ascontiguousarray(
                identity.astype("f4").T,
            ).tobytes()
        )

        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
        vao.render(moderngl.TRIANGLES)
        ctx.blend_func = moderngl.DEFAULT_BLENDING

        vao.release()
        vbo.release()

    def _render_accent_lines(
        self,
        ctx: moderngl.Context,
    ) -> None:
        """Render slow-moving horizontal neon accent lines."""
        t = self._time
        prog = self._renderer.prog_additive
        identity = np.eye(4, dtype="f4")
        prog["mvp"].write(
            np.ascontiguousarray(
                identity.astype("f4").T,
            ).tobytes()
        )

        line_configs = [
            (0.8, 0.12, NeonTheme.NEON_BLUE),
            (0.5, 0.08, NeonTheme.NEON_PINK),
            (0.3, 0.15, NeonTheme.NEON_PURPLE),
        ]
        verts: list[float] = []
        for speed, base_alpha, color in line_configs:
            y = ((t * speed) % 2.2) - 1.1
            lh = 0.001
            a = base_alpha * (1.0 - abs(y) * 0.5)
            cr, cg, cb = color.r, color.g, color.b
            verts += [
                -1.0,
                y - lh,
                0.0,
                cr,
                cg,
                cb,
                a,
                1.0,
                y - lh,
                0.0,
                cr,
                cg,
                cb,
                a,
                1.0,
                y + lh,
                0.0,
                cr,
                cg,
                cb,
                a,
                -1.0,
                y - lh,
                0.0,
                cr,
                cg,
                cb,
                a,
                1.0,
                y + lh,
                0.0,
                cr,
                cg,
                cb,
                a,
                -1.0,
                y + lh,
                0.0,
                cr,
                cg,
                cb,
                a,
            ]

        if not verts:
            return

        data = np.array(verts, dtype="f4")
        vbo = ctx.buffer(data)
        vao = ctx.vertex_array(
            prog,
            [(vbo, "3f 4f", "in_position", "in_color")],
        )

        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
        vao.render(moderngl.TRIANGLES)
        ctx.blend_func = moderngl.DEFAULT_BLENDING

        vao.release()
        vbo.release()

    def _draw_highlight_bar(
        self,
        ctx: moderngl.Context,
        renderer: GameRenderer,
        cx: int,
        y: int,
        w: int,
        h: int,
        color,
        alpha: float,
    ) -> None:
        """Draw a centered semi-transparent highlight bar behind selected item."""
        W, H = renderer.width, renderer.height
        x0_px = cx - w // 2
        x0 = (x0_px / W) * 2 - 1
        x1 = ((x0_px + w) / W) * 2 - 1
        y0 = 1 - (y / H) * 2
        y1 = 1 - ((y + h) / H) * 2
        r, g, b = color.r, color.g, color.b
        verts = np.array(
            [
                x0, y1, 0, r, g, b,
                x1, y1, 0, r, g, b,
                x1, y0, 0, r, g, b,
                x0, y1, 0, r, g, b,
                x1, y0, 0, r, g, b,
                x0, y0, 0, r, g, b,
            ],
            dtype="f4",
        )
        vbo = ctx.buffer(verts)
        prog = renderer.prog_solid
        vao = ctx.vertex_array(
            prog,
            [(vbo, "3f 3f", "in_position", "in_color")],
        )
        identity = np.eye(4, dtype="f4")
        prog["mvp"].write(np.ascontiguousarray(identity).tobytes())
        prog["alpha"].value = alpha
        ctx.disable(moderngl.DEPTH_TEST)
        vao.render(moderngl.TRIANGLES)
        vao.release()
        vbo.release()

    def _render_title(
        self,
        text_renderer: GLTextRenderer,
        W: int,
        H: int,
    ) -> None:
        """Render pulsing neon title with glow layer — resolution-aware."""
        t = self._time
        s = H / 1080.0
        cx = W // 2
        title_y = int(H * 0.18)

        # Glow layer (title=True → 128px base for high-res rendering)
        glow_s = max((0.9 + 0.056 * math.sin(t * 1.5)) * s, 0.45)
        glow_a = 0.18 + 0.10 * math.sin(t * 2.0)
        text_renderer.render(
            "EXCA DANCE",
            cx,
            title_y - 3,
            color=NeonTheme.NEON_BLUE.with_alpha(glow_a).as_tuple(),
            scale=glow_s,
            align="center",
            title=True,
        )

        # Main title
        title_a = 0.85 + 0.15 * math.sin(t * 1.0)
        title_s = max(0.825 * s, 0.45)
        text_renderer.render(
            "EXCA DANCE",
            cx,
            title_y,
            color=NeonTheme.NEON_BLUE.with_alpha(title_a).as_tuple(),
            scale=title_s,
            align="center",
            title=True,
        )

        # Subtitle (neon pink accent)
        sub_y = title_y + int(80 * s)
        sub_a = 0.4 + 0.15 * math.sin(t * 0.8 + 1.0)
        sub_s = max(1.4 * s, 0.75)
        text_renderer.render(
            "EXCAVATOR  RHYTHM  TRAINING",
            cx,
            sub_y,
            color=NeonTheme.NEON_PINK.with_alpha(sub_a).as_tuple(),
            scale=sub_s,
            align="center",
        )

    def _render_menu(
        self,
        text_renderer: GLTextRenderer,
        W: int,
        H: int,
    ) -> None:
        """Render animated menu items with highlight bar — resolution-aware."""
        t = self._time
        s = H / 1080.0
        cx = W // 2
        start_y = int(H * 0.44)
        spacing = int(max(62 * s, 36))
        ctx = self._renderer.ctx

        for i, (label, _) in enumerate(MENU_ITEMS):
            y = start_y + i * spacing

            if i == self._selected:
                # Neon highlight bar behind selected item
                bar_h = int(max(38 * s, 25))
                bar_w = int(max(360 * s, 220))
                self._draw_highlight_bar(
                    ctx,
                    self._renderer,
                    cx,
                    y - int(4 * s),
                    bar_w,
                    bar_h,
                    NeonTheme.NEON_PINK,
                    0.08 + 0.04 * math.sin(t * 3.0),
                )

                # Selected: pulsing neon pink
                pulse = 0.85 + 0.15 * math.sin(t * 3.5)
                color = NeonTheme.NEON_PINK.with_alpha(
                    pulse,
                ).as_tuple()
                scale = max(
                    (2.2 + 0.06 * math.sin(t * 2.5)) * s, 1.15
                )

                # Glow behind selected text
                glow_c = NeonTheme.NEON_PINK.with_alpha(
                    0.12,
                ).as_tuple()
                text_renderer.render(
                    label,
                    cx,
                    y - 2,
                    color=glow_c,
                    scale=scale + max(0.3 * s, 0.15),
                    align="center",
                )

                # Animated arrow indicators
                arrow_off = int(5.0 * math.sin(t * 4.0))
                arrow_x = int(max(150 * s, 85))
                arrow_s = max(1.5 * s, 0.85)
                text_renderer.render(
                    "\u25b6",
                    cx - arrow_x - arrow_off,
                    y + int(2 * s),
                    color=color,
                    scale=arrow_s,
                    align="center",
                )
                text_renderer.render(
                    "\u25c0",
                    cx + arrow_x + arrow_off,
                    y + int(2 * s),
                    color=color,
                    scale=arrow_s,
                    align="center",
                )
            else:
                color = NeonTheme.TEXT_WHITE.with_alpha(
                    0.55,
                ).as_tuple()
                scale = max(1.6 * s, 0.9)

            text_renderer.render(
                label,
                cx,
                y,
                color=color,
                scale=scale,
                align="center",
            )

    def destroy(self) -> None:
        """Release GL resources."""
        self._menu_model.destroy()
        if self._grid_vbo is not None:
            self._grid_vbo.release()
        if self._grid_vao is not None:
            self._grid_vao.release()
