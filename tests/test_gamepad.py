from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame

from exca_dance.core.constants import (
    GAMEPAD_AXIS_DEADZONE,
    GAMEPAD_BUTTON_A,
    GAMEPAD_BUTTON_B,
    GAMEPAD_BUTTON_START,
)
import pytest

from exca_dance.core.gamepad import GamepadManager
from exca_dance.core.models import JointName


def _make_manager_no_joystick() -> GamepadManager:
    with patch("pygame.joystick.get_count", return_value=0):
        return GamepadManager()


def _make_manager_with_joystick() -> tuple[GamepadManager, MagicMock]:
    mock_js = MagicMock()
    mock_js.get_name.return_value = "Xbox Controller"
    mock_js.get_numaxes.return_value = 6
    mock_js.get_numbuttons.return_value = 11
    mock_js.get_instance_id.return_value = 0

    with (
        patch("pygame.joystick.get_count", return_value=1),
        patch("pygame.joystick.Joystick", return_value=mock_js),
    ):
        mgr = GamepadManager()
    return mgr, mock_js


def test_no_joystick_connected_returns_zero() -> None:
    mgr = _make_manager_no_joystick()
    assert mgr.connected is False
    assert mgr.get_joint_input(JointName.SWING) == 0.0
    assert mgr.get_joint_input(JointName.BOOM) == 0.0


def test_connected_property_true_when_joystick_present() -> None:
    mgr, _ = _make_manager_with_joystick()
    assert mgr.connected is True


def test_deadzone_filters_small_values() -> None:
    mgr, mock_js = _make_manager_with_joystick()
    mock_js.get_axis.return_value = GAMEPAD_AXIS_DEADZONE * 0.5
    assert mgr.get_joint_input(JointName.SWING) == 0.0


def test_left_stick_x_negative_maps_to_swing_positive() -> None:
    mgr, mock_js = _make_manager_with_joystick()
    mock_js.get_axis.return_value = -1.0
    result = mgr.get_joint_input(JointName.SWING)
    assert result > 0.0


def test_left_stick_y_negative_maps_to_arm_positive() -> None:
    mgr, mock_js = _make_manager_with_joystick()
    mock_js.get_axis.return_value = -1.0
    result = mgr.get_joint_input(JointName.ARM)
    assert result > 0.0


def test_right_stick_y_positive_maps_to_boom_positive() -> None:
    mgr, mock_js = _make_manager_with_joystick()
    mock_js.get_axis.return_value = 1.0
    result = mgr.get_joint_input(JointName.BOOM)
    assert result > 0.0


def test_right_stick_x_positive_maps_to_bucket_positive() -> None:
    mgr, mock_js = _make_manager_with_joystick()
    mock_js.get_axis.return_value = 1.0
    result = mgr.get_joint_input(JointName.BUCKET)
    assert result > 0.0


def test_full_tilt_returns_magnitude_one() -> None:
    mgr, mock_js = _make_manager_with_joystick()
    mock_js.get_axis.return_value = 1.0
    result = mgr.get_joint_input(JointName.BOOM)
    assert abs(result) == pytest.approx(1.0, abs=0.01)


def test_hotplug_add_connects_joystick() -> None:
    mgr = _make_manager_no_joystick()
    assert mgr.connected is False

    mock_js = MagicMock()
    mock_js.get_name.return_value = "Xbox Controller"
    mock_js.get_numaxes.return_value = 6
    mock_js.get_numbuttons.return_value = 11

    event = pygame.event.Event(pygame.JOYDEVICEADDED)
    with (
        patch("pygame.joystick.get_count", return_value=1),
        patch("pygame.joystick.Joystick", return_value=mock_js),
    ):
        mgr.handle_event(event)

    assert mgr.connected is True


def test_hotplug_remove_disconnects_joystick() -> None:
    mgr, mock_js = _make_manager_with_joystick()
    assert mgr.connected is True

    event = pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=0)
    mgr.handle_event(event)
    assert mgr.connected is False


def test_is_confirm_matches_button_a() -> None:
    mgr = _make_manager_no_joystick()
    event = pygame.event.Event(pygame.JOYBUTTONDOWN, button=GAMEPAD_BUTTON_A)
    assert mgr.is_confirm(event) is True


def test_is_back_matches_button_b() -> None:
    mgr = _make_manager_no_joystick()
    event = pygame.event.Event(pygame.JOYBUTTONDOWN, button=GAMEPAD_BUTTON_B)
    assert mgr.is_back(event) is True


def test_is_start_matches_start_button() -> None:
    mgr = _make_manager_no_joystick()
    event = pygame.event.Event(pygame.JOYBUTTONDOWN, button=GAMEPAD_BUTTON_START)
    assert mgr.is_start(event) is True


def test_dpad_up_returns_menu_direction_negative_one() -> None:
    mgr = _make_manager_no_joystick()
    event = pygame.event.Event(pygame.JOYHATMOTION, value=(0, 1))
    assert mgr.get_menu_direction(event) == -1


def test_dpad_down_returns_menu_direction_positive_one() -> None:
    mgr = _make_manager_no_joystick()
    event = pygame.event.Event(pygame.JOYHATMOTION, value=(0, -1))
    assert mgr.get_menu_direction(event) == 1


def test_stick_flick_up_returns_menu_direction_negative_one() -> None:
    mgr = _make_manager_no_joystick()
    event = pygame.event.Event(pygame.JOYAXISMOTION, axis=1, value=-0.8)
    assert mgr.get_menu_direction(event) == -1


def test_stick_flick_down_returns_menu_direction_positive_one() -> None:
    mgr = _make_manager_no_joystick()
    event = pygame.event.Event(pygame.JOYAXISMOTION, axis=1, value=0.8)
    assert mgr.get_menu_direction(event) == 1


def test_unrelated_event_returns_menu_direction_zero() -> None:
    mgr = _make_manager_no_joystick()
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)
    assert mgr.get_menu_direction(event) == 0
