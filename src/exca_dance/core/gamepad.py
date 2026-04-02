"""Xbox gamepad input — on-demand stick read + hot-plug + menu helpers."""

from __future__ import annotations

import logging

import pygame

from exca_dance.core.constants import (
    GAMEPAD_AXIS_DEADZONE,
    GAMEPAD_AXIS_MAP,
    GAMEPAD_BUTTON_A,
    GAMEPAD_BUTTON_B,
    GAMEPAD_BUTTON_START,
)
from exca_dance.core.models import JointName

logger = logging.getLogger(__name__)


class GamepadManager:

    def __init__(self) -> None:
        self._joystick: pygame.joystick.JoystickType | None = None
        self._try_connect()

    # ------------------------------------------------------------------ #
    # Connection management
    # ------------------------------------------------------------------ #

    def _try_connect(self) -> None:
        if pygame.joystick.get_count() > 0:
            self._joystick = pygame.joystick.Joystick(0)
            self._joystick.init()
            logger.info(
                "Gamepad connected: %s (axes=%d, buttons=%d)",
                self._joystick.get_name(),
                self._joystick.get_numaxes(),
                self._joystick.get_numbuttons(),
            )
        else:
            self._joystick = None

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.JOYDEVICEADDED:
            if self._joystick is None:
                self._try_connect()
        elif event.type == pygame.JOYDEVICEREMOVED:
            if self._joystick is not None:
                try:
                    instance_id = self._joystick.get_instance_id()
                except pygame.error:
                    instance_id = -1
                removed_id = getattr(event, "instance_id", -2)
                if instance_id == removed_id or instance_id == -1:
                    logger.info("Gamepad disconnected")
                    self._joystick = None

    # ------------------------------------------------------------------ #
    # Stick → joint mapping (analog)
    # ------------------------------------------------------------------ #

    @property
    def connected(self) -> bool:
        return self._joystick is not None

    def get_joint_input(self, joint: JointName) -> float:
        """Return ``[-1.0, 1.0]``; positive = keyboard positive-key direction."""
        if self._joystick is None:
            return 0.0

        mapping = GAMEPAD_AXIS_MAP.get(joint)
        if mapping is None:
            return 0.0

        axis_index, invert = mapping
        if axis_index >= self._joystick.get_numaxes():
            return 0.0

        raw = self._joystick.get_axis(axis_index)
        if abs(raw) < GAMEPAD_AXIS_DEADZONE:
            return 0.0

        # Deadzone rescale: ramp from 0.0 at edge of deadzone to 1.0 at full tilt
        sign = 1.0 if raw > 0 else -1.0
        scaled = (abs(raw) - GAMEPAD_AXIS_DEADZONE) / (1.0 - GAMEPAD_AXIS_DEADZONE)
        value = sign * scaled

        if invert:
            value = -value

        return value

    # ------------------------------------------------------------------ #
    # Button helpers (for menus / pause)
    # ------------------------------------------------------------------ #

    def is_button_pressed(self, event: pygame.event.Event, button_id: int) -> bool:
        return event.type == pygame.JOYBUTTONDOWN and event.button == button_id

    def is_confirm(self, event: pygame.event.Event) -> bool:
        return self.is_button_pressed(event, GAMEPAD_BUTTON_A)

    def is_back(self, event: pygame.event.Event) -> bool:
        return self.is_button_pressed(event, GAMEPAD_BUTTON_B)

    def is_start(self, event: pygame.event.Event) -> bool:
        return self.is_button_pressed(event, GAMEPAD_BUTTON_START)

    def get_dpad(self, event: pygame.event.Event) -> tuple[int, int] | None:
        if event.type == pygame.JOYHATMOTION:
            return (event.value[0], event.value[1])
        return None

    def get_menu_direction(self, event: pygame.event.Event) -> int:
        dpad = self.get_dpad(event)
        if dpad is not None:
            # D-pad hat_y +1 = physical up → menu index -1
            if dpad[1] > 0:
                return -1
            if dpad[1] < 0:
                return 1

        if event.type == pygame.JOYAXISMOTION and event.axis == 1:
            if event.value < -0.5:
                return -1
            if event.value > 0.5:
                return 1

        return 0
