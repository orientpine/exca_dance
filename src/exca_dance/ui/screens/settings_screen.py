from __future__ import annotations

from typing import Protocol, cast

import pygame
from exca_dance.core.camera_settings import CameraSettings
from exca_dance.core.game_state import ScreenName
from exca_dance.core.models import JointName
from exca_dance.rendering.theme import NeonTheme


class _RendererLike(Protocol):
    width: int
    height: int


class _TextRendererLike(Protocol):
    def render(
        self,
        text: str,
        x: int,
        y: int,
        *,
        color: tuple[float, float, float, float] | tuple[int, int, int, int],
        scale: float = 1.0,
        align: str = "left",
    ) -> None: ...


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


class SettingsScreen:
    SECTIONS: list[str] = ["KEY BINDINGS", "AUDIO", "MODE", "CAMERA"]

    def __init__(
        self,
        renderer: _RendererLike,
        text_renderer: _TextRendererLike,
        keybinding: _KeybindingLike,
        audio: _AudioLike,
        camera_settings: CameraSettings | None = None,
        bridge_factory: object | None = None,
    ) -> None:
        self._renderer: _RendererLike = renderer
        self._text: _TextRendererLike = text_renderer
        self._kb: _KeybindingLike = keybinding
        self._audio: _AudioLike = audio
        self._camera: CameraSettings | None = camera_settings
        self._bridge_factory: object | None = bridge_factory
        self._section: int = 0
        self._row: int = 0
        self._waiting_key: bool = False
        self._waiting_joint: JointName | None = None
        self._waiting_positive: bool = True
        self._volume: float = 1.0
        self._sfx_volume: float = 1.0
        self._mode: str = "virtual"

    def on_enter(self, **_kwargs: object) -> None:
        self._section = 0
        self._row = 0
        self._waiting_key = False
        self._volume = self._audio.get_bgm_volume()
        self._sfx_volume = self._audio.get_sfx_volume()

    def handle_event(self, event: pygame.event.Event) -> str | tuple[str, dict[str, object]] | None:
        if event.type == pygame.KEYDOWN:
            key = cast(int, event.key)
            if self._waiting_key:
                return self._capture_key(key)
            if key == pygame.K_ESCAPE:
                self._kb.save()
                self._audio.save_volume_settings("data/volume.json")
                if self._camera is not None:
                    self._camera.save()
                return ScreenName.MAIN_MENU
            if key in (pygame.K_LEFT, pygame.K_a):
                if self._section == 1:
                    self._adjust_volume(-0.1)
                else:
                    self._section = (self._section - 1) % len(self.SECTIONS)
                    self._row = 0
            elif key in (pygame.K_RIGHT, pygame.K_d):
                if self._section == 1:
                    self._adjust_volume(0.1)
                else:
                    self._section = (self._section + 1) % len(self.SECTIONS)
                    self._row = 0
            elif key in (pygame.K_UP, pygame.K_w):
                self._row = max(0, self._row - 1)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self._row = min(self._max_row_for_section(), self._row + 1)
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate_row()
        return None

    def _max_row_for_section(self) -> int:
        if self._section == 0:
            return len(list(JointName)) * 2 - 1
        if self._section == 1:
            return 1
        if self._section == 2:
            return 0
        return 2

    def _adjust_volume(self, delta: float) -> None:
        if self._row == 0:
            self._volume = max(0.0, min(1.0, self._volume + delta))
            self._audio.set_volume(self._volume)
        elif self._row == 1:
            self._sfx_volume = max(0.0, min(1.0, self._sfx_volume + delta))
            self._audio.set_sfx_volume(self._sfx_volume)

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
            if self._row == 0:
                self._volume = max(0.0, min(1.0, self._volume))
            elif self._row == 1:
                self._sfx_volume = max(0.0, min(1.0, self._sfx_volume))
        elif self._section == 2:
            self._mode = "real" if self._mode == "virtual" else "virtual"
        elif self._section == 3:
            if self._row == 2 and self._camera is not None:
                self._camera.reset_to_defaults()
                self._camera.save()

    def update(self, _dt: float) -> None:
        return None

    def render(self, renderer: _RendererLike, text_renderer: _TextRendererLike | None) -> None:
        if text_renderer is None:
            return
        W, H = renderer.width, renderer.height
        s = H / 1080.0

        text_renderer.render(
            "SETTINGS",
            W // 2,
            int(30 * s),
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=max(1.1 * s, 0.6),
            large=True,
            align="center",
        )

        for i, sec in enumerate(self.SECTIONS):
            x = W // 4 * (i + 1)
            color = NeonTheme.NEON_PINK if i == self._section else NeonTheme.TEXT_DIM
            text_renderer.render(
                sec,
                x,
                int(80 * s),
                color=color.as_tuple(),
                scale=max(1.2 * s, 0.7),
                align="center",
            )

        if self._waiting_key:
            text_renderer.render(
                "PRESS NEW KEY...",
                W // 2,
                H // 2,
                color=NeonTheme.NEON_ORANGE.as_tuple(),
                scale=max(1.1 * s, 0.6),
                large=True,
                align="center",
            )
            return

        content_y = int(140 * s)
        row_spacing = int(max(50 * s, 32))
        if self._section == 0:
            col_name = int(W * 0.15)
            col_pos = int(W * 0.40)
            col_neg = int(W * 0.60)
            for i, jname in enumerate(JointName):
                pk, nk = self._kb.get_binding(jname)
                color = NeonTheme.JOINT_BOOM if jname == JointName.BOOM else NeonTheme.TEXT_WHITE
                text_renderer.render(
                    f"{cast(str, jname.value).upper()}",
                    col_name,
                    content_y,
                    color=color.as_tuple(),
                    scale=max(1.1 * s, 0.65),
                )
                sel_p = NeonTheme.NEON_PINK if self._row == i * 2 else NeonTheme.TEXT_WHITE
                sel_n = NeonTheme.NEON_PINK if self._row == i * 2 + 1 else NeonTheme.TEXT_WHITE
                text_renderer.render(
                    f"+ [{pygame.key.name(pk)}]",
                    col_pos,
                    content_y,
                    color=sel_p.as_tuple(),
                    scale=max(1.1 * s, 0.65),
                )
                text_renderer.render(
                    f"- [{pygame.key.name(nk)}]",
                    col_neg,
                    content_y,
                    color=sel_n.as_tuple(),
                    scale=max(1.1 * s, 0.65),
                )
                content_y += row_spacing
            text_renderer.render(
                "ENTER to rebind  |  ESC Save & Back",
                W // 2,
                H - int(40 * s),
                color=NeonTheme.TEXT_DIM.as_tuple(),
                scale=max(0.95 * s, 0.6),
                align="center",
            )

        elif self._section == 1:
            bgm_color = NeonTheme.NEON_PINK if self._row == 0 else NeonTheme.TEXT_WHITE
            sfx_color = NeonTheme.NEON_PINK if self._row == 1 else NeonTheme.TEXT_WHITE
            text_renderer.render(
                f"BGM Volume: {int(self._volume * 100)}%",
                W // 2,
                content_y,
                color=bgm_color.as_tuple(),
                scale=max(1.3 * s, 0.75),
                align="center",
            )
            text_renderer.render(
                f"SFX Volume: {int(self._sfx_volume * 100)}%",
                W // 2,
                content_y + row_spacing,
                color=sfx_color.as_tuple(),
                scale=max(1.3 * s, 0.75),
                align="center",
            )
            text_renderer.render(
                "LEFT/RIGHT adjust  |  ESC Save & Back",
                W // 2,
                H - int(40 * s),
                color=NeonTheme.TEXT_DIM.as_tuple(),
                scale=max(0.95 * s, 0.6),
                align="center",
            )

        elif self._section == 2:
            mode_color = NeonTheme.NEON_GREEN if self._mode == "virtual" else NeonTheme.NEON_ORANGE
            text_renderer.render(
                f"Mode: {self._mode.upper()}",
                W // 2,
                content_y,
                color=mode_color.as_tuple(),
                scale=max(0.8 * s, 0.45),
                large=True,
                align="center",
            )
            text_renderer.render(
                "ENTER to toggle  |  ESC Save & Back",
                W // 2,
                H - int(40 * s),
                color=NeonTheme.TEXT_DIM.as_tuple(),
                scale=max(0.95 * s, 0.6),
                align="center",
            )
        elif self._section == 3:
            azimuth = self._camera.azimuth if self._camera is not None else 0.0
            elevation = self._camera.elevation if self._camera is not None else 0.0
            row0_color = NeonTheme.NEON_PINK if self._row == 0 else NeonTheme.TEXT_WHITE
            row1_color = NeonTheme.NEON_PINK if self._row == 1 else NeonTheme.TEXT_WHITE
            row2_color = NeonTheme.NEON_ORANGE if self._row == 2 else NeonTheme.TEXT_DIM
            text_renderer.render(
                f"Azimuth: {azimuth:.1f} deg",
                W // 2,
                content_y,
                color=row0_color.as_tuple(),
                scale=max(1.3 * s, 0.75),
                align="center",
            )
            text_renderer.render(
                f"Elevation: {elevation:.1f} deg",
                W // 2,
                content_y + row_spacing,
                color=row1_color.as_tuple(),
                scale=max(1.3 * s, 0.75),
                align="center",
            )
            text_renderer.render(
                "RESET CAMERA TO DEFAULT",
                W // 2,
                content_y + row_spacing * 2,
                color=row2_color.as_tuple(),
                scale=max(1.15 * s, 0.7),
                align="center",
            )
            text_renderer.render(
                "UP/DOWN select  |  ENTER reset  |  ESC Save & Back",
                W // 2,
                H - int(40 * s),
                color=NeonTheme.TEXT_DIM.as_tuple(),
                scale=max(0.95 * s, 0.6),
                align="center",
            )
