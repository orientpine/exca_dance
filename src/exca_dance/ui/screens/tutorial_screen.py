from __future__ import annotations

import pygame

from exca_dance.core.game_state import ScreenName
from exca_dance.rendering.theme import NeonTheme

STEPS = [
    {
        "title": "The Excavator Has 4 Joints",
        "body": (
            "SWING rotates the base.\n"
            "BOOM raises/lowers the main arm.\n"
            "ARM extends the forearm.\n"
            "BUCKET controls the shovel."
        ),
        "hint": "Watch the joints highlighted on screen",
    },
    {
        "title": "Move the Joints",
        "body": (
            "Try moving each joint:\n"
            "SWING: A / D\n"
            "BOOM: W / S\n"
            "ARM: UP / DOWN\n"
            "BUCKET: LEFT / RIGHT"
        ),
        "hint": "Hold keys to move. Press ENTER when ready.",
    },
    {
        "title": "Follow the Ghost",
        "body": (
            "A ghost (purple) shows the target pose.\n"
            "Move the excavator to match the ghost.\n"
            "The closer you match, the higher your score!"
        ),
        "hint": "Try to match 3 ghost poses. Press ENTER to continue.",
    },
    {
        "title": "Ready to Play!",
        "body": (
            "ENTER: confirm\n"
            "ESC: pause during gameplay\n"
            "Q: quit to menu from pause\n"
            "F3: toggle FPS counter"
        ),
        "hint": "Press ENTER to return to menu.",
    },
]


class TutorialScreen:
    def __init__(self, renderer, text_renderer) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._step: int = 1

    def on_enter(self, **kwargs) -> None:
        self._step = 1

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self._step < 4:
                    self._step += 1
                else:
                    return ScreenName.MAIN_MENU
            elif event.key == pygame.K_ESCAPE:
                return ScreenName.MAIN_MENU
        return None

    def update(self, dt: float):
        return None

    def render(self, renderer, text_renderer) -> None:
        if text_renderer is None:
            return

        W, H = renderer.width, renderer.height
        s = H / 1080.0
        step = STEPS[self._step - 1]

        text_renderer.render(
            f"TUTORIAL ({self._step}/4)",
            W // 2,
            int(40 * s),
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=max(0.55 * s, 0.30),
            title=True,
            align="center",
        )
        text_renderer.render(
            step["title"],
            W // 2,
            int(120 * s),
            color=NeonTheme.NEON_PINK.as_tuple(),
            scale=max(0.7 * s, 0.42),
            large=True,
            align="center",
        )

        body_start_y = int(220 * s)
        body_spacing = int(max(50 * s, 30))
        for index, line in enumerate(step["body"].split("\n")):
            text_renderer.render(
                line,
                W // 2,
                body_start_y + index * body_spacing,
                color=NeonTheme.TEXT_WHITE.as_tuple(),
                scale=max(0.6 * s, 0.38),
                large=True,
                align="center",
            )

        text_renderer.render(
            step["hint"],
            W // 2,
            H - int(80 * s),
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=max(0.55 * s, 0.35),
            large=True,
            align="center",
        )

        nav = "ENTER: Next  |  ESC: Menu" if self._step < 4 else "ENTER: Back to Menu  |  ESC: Menu"
        text_renderer.render(
            nav,
            W // 2,
            H - int(40 * s),
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=max(0.55 * s, 0.35),
            large=True,
            align="center",
        )
