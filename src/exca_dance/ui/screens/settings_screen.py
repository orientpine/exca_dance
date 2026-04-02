from __future__ import annotations

from typing import Any, Protocol, cast

import moderngl
import numpy as np
import pygame

from exca_dance.core.camera_settings import CameraSettings
from exca_dance.core.game_settings import GameSettings
from exca_dance.core.game_state import ScreenName
from exca_dance.ros2_bridge import is_ros2_available, is_ros2_installed_but_not_sourced
from exca_dance.core.kinematics import ExcavatorFK
from exca_dance.core.models import JointName
from exca_dance.rendering.excavator_model import ExcavatorModel
from exca_dance.rendering.theme import NeonTheme


# ── Matrix helpers (same as viewport_layout / main_menu) ──────────────


def _perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / np.tan(np.radians(fov_deg) / 2.0)
    m = np.zeros((4, 4), dtype="f4")
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def _look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
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


# ── Protocols for duck-typed dependencies ─────────────────────────────


class _KeybindingLike(Protocol):
    def save(self) -> None: ...

    def get_binding(self, joint: JointName) -> tuple[int, int]: ...

    def set_binding(self, joint: JointName, positive_key: int, negative_key: int) -> None: ...


class _AudioLike(Protocol):
    def get_bgm_volume(self) -> float: ...

    def get_sfx_volume(self) -> float: ...

    def set_volume(self, volume: float) -> None: ...

    def set_sfx_volume(self, volume: float) -> None: ...

    def save_volume_settings(self, path: str) -> None: ...


# ── Settings Screen ───────────────────────────────────────────────────


class SettingsScreen:
    """Settings screen with key bindings, audio, mode, and camera preview."""

    SECTIONS: list[str] = ["KEY BINDINGS", "AUDIO", "MODE", "CAMERA"]

    def __init__(
        self,
        renderer: Any,
        text_renderer: Any,
        keybinding: _KeybindingLike,
        audio: _AudioLike,
        camera_settings: CameraSettings | None = None,
        bridge_factory: object | None = None,
        fk: ExcavatorFK | None = None,
        excavator_model_class: type[ExcavatorModel] | None = None,
        game_settings: GameSettings | None = None,
    ) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._kb: _KeybindingLike = keybinding
        self._audio: _AudioLike = audio
        self._camera: CameraSettings | None = camera_settings
        self._bridge_factory: object | None = bridge_factory
        self._game_settings: GameSettings | None = game_settings
        self._section: int = 0
        self._row: int = 0
        self._waiting_key: bool = False
        self._waiting_joint: JointName | None = None
        self._waiting_positive: bool = True
        self._volume: float = 1.0
        self._sfx_volume: float = 1.0
        self._mode: str = game_settings.mode if game_settings is not None else "virtual"
        self._ros2_status: str = "ok"

        # Camera 3D preview model
        self._preview_model: ExcavatorModel | None = None
        self._grid_vbo: moderngl.Buffer | None = None
        self._grid_vao: moderngl.VertexArray | None = None
        self._grid_line_count: int = 0

        if fk is not None and excavator_model_class is not None:
            neon_colors: dict[str | JointName, tuple[float, float, float]] = {
                "base": (0.0, 0.35, 0.45),
                "turret": (0.0, 0.45, 0.55),
                JointName.BOOM: NeonTheme.NEON_PINK.as_rgb(),
                JointName.ARM: NeonTheme.NEON_ORANGE.as_rgb(),
                JointName.BUCKET: NeonTheme.NEON_GREEN.as_rgb(),
            }
            self._preview_model = excavator_model_class(renderer, fk, joint_colors=neon_colors)
            preview_angles: dict[JointName, float] = cast(
                dict[JointName, float],
                {
                    JointName.SWING: 0.0,
                    JointName.BOOM: -20.0,
                    JointName.ARM: 80.0,
                    JointName.BUCKET: -40.0,
                },
            )
            self._preview_model.update(preview_angles)
            self._build_preview_grid()

    # ── Cached grid geometry for camera preview ───────────────────────

    def _build_preview_grid(self) -> None:
        r = NeonTheme.NEON_BLUE.r * 0.4
        g = NeonTheme.NEON_BLUE.g * 0.4
        b = NeonTheme.NEON_BLUE.b * 0.4
        verts: list[float] = []
        for i in range(-4, 10):
            x = float(i)
            verts += [x, -8.0, 0.0, r, g, b, x, 8.0, 0.0, r, g, b]
        for j in range(-8, 9):
            y = float(j)
            verts += [-4.0, y, 0.0, r, g, b, 10.0, y, 0.0, r, g, b]
        if verts:
            data = np.array(verts, dtype="f4")
            ctx = self._renderer.ctx
            self._grid_vbo = ctx.buffer(data)
            self._grid_vao = ctx.vertex_array(
                self._renderer.prog_solid,
                [(self._grid_vbo, "3f 3f", "in_position", "in_color")],
            )
            self._grid_line_count = len(data) // 6

    # ── Screen protocol ───────────────────────────────────────────────

    def on_enter(self, **_kwargs: object) -> None:
        self._section = 0
        self._row = 0
        self._waiting_key = False
        self._volume = self._audio.get_bgm_volume()
        self._sfx_volume = self._audio.get_sfx_volume()
        if self._game_settings is not None:
            self._mode = self._game_settings.mode
        self._ros2_status = self._check_ros2_status()

    def handle_event(self, event: pygame.event.Event) -> str | tuple[str, dict[str, object]] | None:
        if event.type == pygame.KEYDOWN:
            key = cast(int, event.key)

            if self._waiting_key:
                return self._capture_key(key)

            if key == pygame.K_ESCAPE:
                self._save_all()
                return ScreenName.MAIN_MENU

            # TAB: always switch section — fixes audio section trap
            if key == pygame.K_TAB:
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_SHIFT:
                    self._section = (self._section - 1) % len(self.SECTIONS)
                else:
                    self._section = (self._section + 1) % len(self.SECTIONS)
                self._row = 0
                return None

            # LEFT/RIGHT: section-specific or section navigation
            if key in (pygame.K_LEFT, pygame.K_a):
                if self._section == 1:
                    self._adjust_volume(-0.1)
                elif self._section == 3:
                    self._adjust_camera(-5.0)
                else:
                    self._section = (self._section - 1) % len(self.SECTIONS)
                    self._row = 0
            elif key in (pygame.K_RIGHT, pygame.K_d):
                if self._section == 1:
                    self._adjust_volume(0.1)
                elif self._section == 3:
                    self._adjust_camera(5.0)
                else:
                    self._section = (self._section + 1) % len(self.SECTIONS)
                    self._row = 0

            # UP/DOWN: row navigation
            elif key in (pygame.K_UP, pygame.K_w):
                self._row = max(0, self._row - 1)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self._row = min(self._max_row_for_section(), self._row + 1)

            # ENTER/SPACE: activate
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate_row()

        return None

    def _save_all(self) -> None:
        self._kb.save()
        self._audio.save_volume_settings("data/volume.json")
        if self._camera is not None:
            self._camera.save()
        if self._game_settings is not None:
            self._game_settings.save()

    def _max_row_for_section(self) -> int:
        if self._section == 0:
            return len(list(JointName)) * 2 - 1
        if self._section == 1:
            return 1
        if self._section == 2:
            return 0
        return 2  # azimuth, elevation, reset

    def _adjust_volume(self, delta: float) -> None:
        if self._row == 0:
            self._volume = max(0.0, min(1.0, self._volume + delta))
            self._audio.set_volume(self._volume)
        elif self._row == 1:
            self._sfx_volume = max(0.0, min(1.0, self._sfx_volume + delta))
            self._audio.set_sfx_volume(self._sfx_volume)

    def _adjust_camera(self, delta: float) -> None:
        if self._camera is None:
            return
        if self._row == 0:
            self._camera.azimuth += delta
        elif self._row == 1:
            self._camera.elevation += delta

    def _capture_key(self, key: int) -> None:
        if self._waiting_joint is not None:
            pk, nk = self._kb.get_binding(self._waiting_joint)
            if self._waiting_positive:
                self._kb.set_binding(self._waiting_joint, key, nk)
            else:
                self._kb.set_binding(self._waiting_joint, pk, key)
        self._waiting_key = False
        self._waiting_joint = None

    def _activate_row(self) -> None:
        if self._section == 0:
            joints = list(JointName)
            joint_idx = self._row // 2
            if joint_idx < len(joints):
                self._waiting_joint = joints[joint_idx]
                self._waiting_positive = self._row % 2 == 0
                self._waiting_key = True
        elif self._section == 1:
            pass  # volume adjusted via LEFT/RIGHT
        elif self._section == 2:
            self._mode = "real" if self._mode == "virtual" else "virtual"
            self._ros2_status = self._check_ros2_status()
            if self._game_settings is not None:
                self._game_settings.mode = self._mode
        elif self._section == 3:
            if self._row == 2 and self._camera is not None:
                self._camera.reset_to_defaults()
                self._camera.save()

    def _check_ros2_status(self) -> str:
        if self._mode != "real":
            return "ok"
        if is_ros2_available():
            return "ok"
        if is_ros2_installed_but_not_sourced():
            return "not_sourced"
        return "not_installed"

    def update(self, _dt: float) -> None:
        return None

    # ── Rendering ─────────────────────────────────────────────────────

    def render(self, renderer: Any, text_renderer: Any | None) -> None:
        if text_renderer is None:
            return
        W: int = renderer.width
        H: int = renderer.height
        s = H / 1080.0

        # Camera section: render 3D preview FIRST (behind text)
        if self._section == 3:
            self._render_camera_preview(W, H)

        # ── Title ────────────────────────────────────────────────
        text_renderer.render(  # type: ignore[union-attr]
            "SETTINGS",
            W // 2,
            int(30 * s),
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=max(0.55 * s, 0.30),
            title=True,
            align="center",
        )

        # ── Section tabs ─────────────────────────────────────────
        tab_y = int(100 * s)
        tab_positions = [0.14, 0.37, 0.60, 0.83]
        for i, sec in enumerate(self.SECTIONS):
            x = int(W * tab_positions[i])
            active = i == self._section
            color = NeonTheme.NEON_PINK if active else NeonTheme.TEXT_DIM
            text_renderer.render(  # type: ignore[union-attr]
                sec,
                x,
                tab_y,
                color=color.as_tuple(),
                scale=max(0.65 * s, 0.38),
                large=True,
                align="center",
            )
            # Underline for active tab
            if active:
                text_renderer.render(  # type: ignore[union-attr]
                    "━━━━━━━━━━━",
                    x,
                    tab_y + int(28 * s),
                    color=NeonTheme.NEON_PINK.with_alpha(0.6).as_tuple(),
                    scale=max(0.45 * s, 0.28),
                    align="center",
                )

        # ── "Press key" overlay ──────────────────────────────────
        if self._waiting_key:
            text_renderer.render(  # type: ignore[union-attr]
                "PRESS NEW KEY...",
                W // 2,
                H // 2,
                color=NeonTheme.NEON_ORANGE.as_tuple(),
                scale=max(0.55 * s, 0.30),
                title=True,
                align="center",
            )
            return

        # ── Section content ──────────────────────────────────────
        content_y = int(165 * s)
        if self._section == 0:
            self._render_keybindings(text_renderer, W, H, s, content_y)
        elif self._section == 1:
            self._render_audio(text_renderer, W, H, s, content_y)
        elif self._section == 2:
            self._render_mode(text_renderer, W, H, s, content_y)
        elif self._section == 3:
            self._render_camera_text(text_renderer, W, H, s, content_y)

    # ── Section renderers ─────────────────────────────────────────────

    def _render_keybindings(self, tr: Any, W: int, H: int, s: float, start_y: int) -> None:
        row_h = int(max(58 * s, 38))
        col_name = int(W * 0.12)
        col_pos = int(W * 0.38)
        col_neg = int(W * 0.58)
        joint_colors = {
            JointName.SWING: NeonTheme.JOINT_SWING,
            JointName.BOOM: NeonTheme.JOINT_BOOM,
            JointName.ARM: NeonTheme.JOINT_ARM,
            JointName.BUCKET: NeonTheme.JOINT_BUCKET,
        }
        y = start_y
        for i, jname in enumerate(JointName):
            pk, nk = self._kb.get_binding(jname)
            jcolor = joint_colors.get(jname, NeonTheme.TEXT_WHITE)
            tr.render(  # type: ignore[union-attr]
                cast(str, jname.value).upper(),
                col_name,
                y,
                color=jcolor.as_tuple(),
                scale=max(0.65 * s, 0.4),
                large=True,
            )
            sel_p = NeonTheme.NEON_PINK if self._row == i * 2 else NeonTheme.TEXT_WHITE
            sel_n = NeonTheme.NEON_PINK if self._row == i * 2 + 1 else NeonTheme.TEXT_WHITE
            tr.render(  # type: ignore[union-attr]
                f"+ [{pygame.key.name(pk)}]",
                col_pos,
                y,
                color=sel_p.as_tuple(),
                scale=max(0.6 * s, 0.38),
                large=True,
            )
            tr.render(  # type: ignore[union-attr]
                f"- [{pygame.key.name(nk)}]",
                col_neg,
                y,
                color=sel_n.as_tuple(),
                scale=max(0.6 * s, 0.38),
                large=True,
            )
            y += row_h

        tr.render(  # type: ignore[union-attr]
            "ENTER: Rebind  |  TAB: Switch Section  |  ESC: Save & Back",
            W // 2,
            H - int(40 * s),
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=max(0.55 * s, 0.35),
            large=True,
            align="center",
        )

    def _render_audio(self, tr: Any, W: int, H: int, s: float, start_y: int) -> None:
        # BGM Volume
        bgm_sel = self._row == 0
        bgm_color = NeonTheme.NEON_PINK if bgm_sel else NeonTheme.TEXT_WHITE
        tr.render(  # type: ignore[union-attr]
            "BGM VOLUME",
            W // 2,
            start_y,
            color=bgm_color.as_tuple(),
            scale=max(0.7 * s, 0.42),
            large=True,
            align="center",
        )
        filled = int(self._volume * 20)
        bar_text = "\u2588" * filled + "\u2591" * (20 - filled)
        tr.render(  # type: ignore[union-attr]
            f"{bar_text}  {int(self._volume * 100)}%",
            W // 2,
            start_y + int(40 * s),
            color=bgm_color.as_tuple(),
            scale=max(0.6 * s, 0.38),
            large=True,
            align="center",
        )

        # SFX Volume
        sfx_y = start_y + int(120 * s)
        sfx_sel = self._row == 1
        sfx_color = NeonTheme.NEON_PINK if sfx_sel else NeonTheme.TEXT_WHITE
        tr.render(  # type: ignore[union-attr]
            "SFX VOLUME",
            W // 2,
            sfx_y,
            color=sfx_color.as_tuple(),
            scale=max(0.7 * s, 0.42),
            large=True,
            align="center",
        )
        sfx_filled = int(self._sfx_volume * 20)
        sfx_bar = "\u2588" * sfx_filled + "\u2591" * (20 - sfx_filled)
        tr.render(  # type: ignore[union-attr]
            f"{sfx_bar}  {int(self._sfx_volume * 100)}%",
            W // 2,
            sfx_y + int(40 * s),
            color=sfx_color.as_tuple(),
            scale=max(0.6 * s, 0.38),
            large=True,
            align="center",
        )

        tr.render(  # type: ignore[union-attr]
            "\u2190/\u2192: Adjust  |  TAB: Switch Section  |  ESC: Save & Back",
            W // 2,
            H - int(40 * s),
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=max(0.55 * s, 0.35),
            large=True,
            align="center",
        )

    def _render_mode(self, tr: Any, W: int, H: int, s: float, start_y: int) -> None:
        mode_color = NeonTheme.NEON_GREEN if self._mode == "virtual" else NeonTheme.NEON_ORANGE
        tr.render(  # type: ignore[union-attr]
            f"MODE: {self._mode.upper()}",
            W // 2,
            start_y + int(60 * s),
            color=mode_color.as_tuple(),
            scale=max(0.5 * s, 0.28),
            title=True,
            align="center",
        )
        if self._ros2_status == "not_sourced":
            tr.render(  # type: ignore[union-attr]
                "ROS2 INSTALLED BUT NOT SOURCED",
                W // 2,
                start_y + int(130 * s),
                color=NeonTheme.NEON_ORANGE.as_tuple(),
                scale=max(0.45 * s, 0.26),
                large=True,
                align="center",
            )
            tr.render(  # type: ignore[union-attr]
                "Run: source /opt/ros/jazzy/setup.bash",
                W // 2,
                start_y + int(170 * s),
                color=NeonTheme.TEXT_DIM.as_tuple(),
                scale=max(0.4 * s, 0.24),
                large=True,
                align="center",
            )
        elif self._ros2_status == "not_installed":
            tr.render(  # type: ignore[union-attr]
                "ROS2 NOT INSTALLED",
                W // 2,
                start_y + int(130 * s),
                color=NeonTheme.NEON_ORANGE.as_tuple(),
                scale=max(0.45 * s, 0.26),
                large=True,
                align="center",
            )
            tr.render(  # type: ignore[union-attr]
                "Excavator will stay at default pose",
                W // 2,
                start_y + int(170 * s),
                color=NeonTheme.TEXT_DIM.as_tuple(),
                scale=max(0.4 * s, 0.24),
                large=True,
                align="center",
            )
        tr.render(  # type: ignore[union-attr]
            "ENTER: Toggle  |  TAB: Switch Section  |  ESC: Save & Back",
            W // 2,
            H - int(40 * s),
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=max(0.55 * s, 0.35),
            large=True,
            align="center",
        )

    def _render_camera_text(self, tr: Any, W: int, H: int, s: float, start_y: int) -> None:
        """Render camera parameter text (left side of screen)."""
        left_x = int(W * 0.18)
        azimuth = self._camera.azimuth if self._camera is not None else 0.0
        elevation = self._camera.elevation if self._camera is not None else 0.0

        row0_color = NeonTheme.NEON_PINK if self._row == 0 else NeonTheme.TEXT_WHITE
        row1_color = NeonTheme.NEON_PINK if self._row == 1 else NeonTheme.TEXT_WHITE
        row2_color = NeonTheme.NEON_ORANGE if self._row == 2 else NeonTheme.TEXT_DIM
        row_gap = int(max(80 * s, 50))

        # Azimuth
        tr.render(  # type: ignore[union-attr]
            "AZIMUTH",
            left_x,
            start_y,
            color=row0_color.as_tuple(),
            scale=max(0.6 * s, 0.38),
            large=True,
            align="center",
        )
        tr.render(  # type: ignore[union-attr]
            f"{azimuth:.1f}\u00b0",
            left_x,
            start_y + int(35 * s),
            color=row0_color.as_tuple(),
            scale=max(0.45 * s, 0.26),
            title=True,
            align="center",
        )

        # Elevation
        tr.render(  # type: ignore[union-attr]
            "ELEVATION",
            left_x,
            start_y + row_gap,
            color=row1_color.as_tuple(),
            scale=max(0.6 * s, 0.38),
            large=True,
            align="center",
        )
        tr.render(  # type: ignore[union-attr]
            f"{elevation:.1f}\u00b0",
            left_x,
            start_y + row_gap + int(35 * s),
            color=row1_color.as_tuple(),
            scale=max(0.45 * s, 0.26),
            title=True,
            align="center",
        )

        # Reset button
        tr.render(  # type: ignore[union-attr]
            "RESET TO DEFAULT",
            left_x,
            start_y + row_gap * 2 + int(20 * s),
            color=row2_color.as_tuple(),
            scale=max(0.55 * s, 0.35),
            large=True,
            align="center",
        )

        # Hint
        tr.render(  # type: ignore[union-attr]
            "\u2190/\u2192: Adjust  |  TAB: Section  |  ENTER: Reset  |  ESC: Back",
            W // 2,
            H - int(40 * s),
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=max(0.50 * s, 0.33),
            large=True,
            align="center",
        )

    # ── Camera 3D preview ─────────────────────────────────────────────

    def _render_camera_preview(self, W: int, H: int) -> None:
        """Render a live 3D excavator preview using current camera settings."""
        if self._preview_model is None or self._camera is None:
            return

        renderer = self._renderer
        ctx = renderer.ctx
        prog_solid = renderer.prog_solid

        # Preview viewport: right 55% of screen
        vp_x = int(W * 0.40)
        vp_y = int(H * 0.06)
        vp_w = int(W * 0.56)
        vp_h = int(H * 0.76)

        # Clear preview area
        ctx.clear(0.03, 0.03, 0.07, viewport=(vp_x, vp_y, vp_w, vp_h))
        ctx.viewport = (vp_x, vp_y, vp_w, vp_h)

        # Compute MVP from camera settings
        ex, ey, ez = self._camera.compute_eye((2.0, 0.0, 1.5))
        eye = np.array([ex, ey, ez], dtype="f4")
        target = np.array([2.0, 0.0, 1.5], dtype="f4")
        up = np.array([0.0, 0.0, 1.0], dtype="f4")
        aspect = vp_w / max(vp_h, 1)
        proj = _perspective(45.0, aspect, 0.1, 100.0)
        view = _look_at(eye, target, up)
        mvp = (proj @ view).astype("f4")
        mvp_bytes = np.ascontiguousarray(mvp.astype("f4").T).tobytes()

        # Render ground grid (no depth test — appears behind model)
        if self._grid_vao is not None:
            prog_solid["mvp"].write(mvp_bytes)
            identity = np.eye(4, dtype="f4")
            prog_solid["model"].write(np.ascontiguousarray(identity.T).tobytes())
            prog_solid["alpha"].value = 0.15
            self._grid_vao.render(moderngl.LINES, vertices=self._grid_line_count)

        # Render excavator (render_3d manages depth test internally)
        self._preview_model.render_3d(mvp, alpha=0.9)

        # Reset viewport
        ctx.viewport = (0, 0, W, H)

    # ── Cleanup ───────────────────────────────────────────────────────

    def destroy(self) -> None:
        if self._preview_model is not None:
            self._preview_model.destroy()
        if self._grid_vbo is not None:
            self._grid_vbo.release()
        if self._grid_vao is not None:
            self._grid_vao.release()
