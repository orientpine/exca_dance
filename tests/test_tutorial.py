from __future__ import annotations

from importlib import import_module
from unittest.mock import MagicMock


def test_tutorial_screen_implements_protocol() -> None:
    module = import_module("exca_dance.ui.screens.tutorial_screen")
    tutorial_screen_class = module.TutorialScreen

    screen = tutorial_screen_class(MagicMock(), MagicMock())
    assert hasattr(screen, "on_enter")
    assert hasattr(screen, "handle_event")
    assert hasattr(screen, "update")
    assert hasattr(screen, "render")


def test_tutorial_step_starts_at_1() -> None:
    module = import_module("exca_dance.ui.screens.tutorial_screen")
    tutorial_screen_class = module.TutorialScreen

    screen = tutorial_screen_class(MagicMock(), MagicMock())
    screen.on_enter()
    assert screen._step == 1


def test_tutorial_step_advances_on_enter() -> None:
    import pygame

    module = import_module("exca_dance.ui.screens.tutorial_screen")
    tutorial_screen_class = module.TutorialScreen

    screen = tutorial_screen_class(MagicMock(), MagicMock())
    screen.on_enter()
    event = MagicMock()
    event.type = pygame.KEYDOWN
    event.key = pygame.K_RETURN
    screen.handle_event(event)
    assert screen._step == 2
