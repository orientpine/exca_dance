"""Settings screen: key bindings, volume, mode."""

from __future__ import annotations
import pygame
from exca_dance.core.models import JointName
from exca_dance.rendering.theme import NeonTheme
from exca_dance.core.game_state import ScreenName


class SettingsScreen:
    SECTIONS = ["KEY BINDINGS", "AUDIO", "MODE"]

    def __init__(self, renderer, text_renderer, keybinding, audio, bridge_factory=None) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._kb = keybinding
        self._audio = audio
        self._bridge_factory = bridge_factory
        self._section = 0
        self._row = 0
        self._waiting_key = False
        self._waiting_joint: JointName | None = None
        self._waiting_positive: bool = True
        self._volume = 1.0
        self._mode = "virtual"

    def on_enter(self, **kwargs) -> None:
        self._section = 0
        self._row = 0
        self._waiting_key = False

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if self._waiting_key:
                return self._capture_key(event.key)
            if event.key == pygame.K_ESCAPE:
                self._kb.save()
                return ScreenName.MAIN_MENU
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._section = (self._section - 1) % len(self.SECTIONS)
                self._row = 0
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._section = (self._section + 1) % len(self.SECTIONS)
                self._row = 0
            elif event.key in (pygame.K_UP, pygame.K_w):
                self._row = max(0, self._row - 1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._row += 1
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate_row()
        return None

    def _capture_key(self, key: int):
        if self._waiting_joint is not None:
            pk, nk = self._kb.get_binding(self._waiting_joint)
            if self._waiting_positive:
                self._kb.set_binding(self._waiting_joint, key, nk)
            else:
                self._kb.set_binding(self._waiting_joint, pk, key)
        self._waiting_key = False
        self._waiting_joint = None
        return None

    def _activate_row(self) -> None:
        if self._section == 0:  # Key bindings
            joints = list(JointName)
            joint_idx = self._row // 2
            if joint_idx < len(joints):
                self._waiting_joint = joints[joint_idx]
                self._waiting_positive = self._row % 2 == 0
                self._waiting_key = True
        elif self._section == 1:  # Audio
            pass  # handled by left/right
        elif self._section == 2:  # Mode
            self._mode = "real" if self._mode == "virtual" else "virtual"

    def update(self, dt: float):
        return None

    def render(self, renderer, text_renderer) -> None:
        if text_renderer is None:
            return
        W, H = renderer.width, renderer.height

        text_renderer.render(
            "SETTINGS", W // 2, 30, color=NeonTheme.NEON_BLUE.as_tuple(), scale=2.0, align="center"
        )

        # Section tabs
        for i, sec in enumerate(self.SECTIONS):
            x = W // 4 * (i + 1)
            color = NeonTheme.NEON_PINK if i == self._section else NeonTheme.TEXT_DIM
            text_renderer.render(sec, x, 80, color=color.as_tuple(), scale=1.1, align="center")

        if self._waiting_key:
            text_renderer.render(
                "PRESS NEW KEY...",
                W // 2,
                H // 2,
                color=NeonTheme.NEON_ORANGE.as_tuple(),
                scale=2.0,
                align="center",
            )
            return

        y = 140
        if self._section == 0:
            for i, jname in enumerate(JointName):
                pk, nk = self._kb.get_binding(jname)
                color = NeonTheme.JOINT_BOOM if jname == JointName.BOOM else NeonTheme.TEXT_WHITE
                text_renderer.render(
                    f"{jname.value.upper()}", 200, y, color=color.as_tuple(), scale=1.0
                )
                sel_p = NeonTheme.NEON_PINK if self._row == i * 2 else NeonTheme.TEXT_WHITE
                sel_n = NeonTheme.NEON_PINK if self._row == i * 2 + 1 else NeonTheme.TEXT_WHITE
                text_renderer.render(
                    f"+ [{pygame.key.name(pk)}]", 400, y, color=sel_p.as_tuple(), scale=1.0
                )
                text_renderer.render(
                    f"- [{pygame.key.name(nk)}]", 600, y, color=sel_n.as_tuple(), scale=1.0
                )
                y += 50
            text_renderer.render(
                "ENTER to rebind  |  ESC Save & Back",
                W // 2,
                H - 40,
                color=NeonTheme.TEXT_DIM.as_tuple(),
                scale=0.9,
                align="center",
            )

        elif self._section == 1:
            text_renderer.render(
                f"Volume: {int(self._volume * 100)}%",
                W // 2,
                y,
                color=NeonTheme.TEXT_WHITE.as_tuple(),
                scale=1.2,
                align="center",
            )
            text_renderer.render(
                "ESC Save & Back",
                W // 2,
                H - 40,
                color=NeonTheme.TEXT_DIM.as_tuple(),
                scale=0.9,
                align="center",
            )

        elif self._section == 2:
            mode_color = NeonTheme.NEON_GREEN if self._mode == "virtual" else NeonTheme.NEON_ORANGE
            text_renderer.render(
                f"Mode: {self._mode.upper()}",
                W // 2,
                y,
                color=mode_color.as_tuple(),
                scale=1.5,
                align="center",
            )
            text_renderer.render(
                "ENTER to toggle  |  ESC Save & Back",
                W // 2,
                H - 40,
                color=NeonTheme.TEXT_DIM.as_tuple(),
                scale=0.9,
                align="center",
            )
