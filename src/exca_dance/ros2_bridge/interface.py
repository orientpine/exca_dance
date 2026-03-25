"""ROS2 bridge abstract interface.
CRITICAL: This module MUST NOT import rclpy or any ROS2 packages.
Virtual mode works standalone without ROS2 installed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import override

from exca_dance.core.models import JointName


class ExcavatorBridgeInterface(ABC):
    """Abstract interface for excavator communication."""

    @abstractmethod
    def send_command(self, joint_angles: dict[JointName, float]) -> None:
        """Send joint angle commands to the excavator."""

    @abstractmethod
    def get_current_angles(self) -> dict[JointName, float]:
        """Get current joint angles from excavator."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if bridge is connected."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection."""


class VirtualBridge(ExcavatorBridgeInterface):
    """Virtual excavator bridge — angles stored internally, no hardware."""

    def __init__(self):
        self._angles: dict[JointName, float] = {j: 0.0 for j in JointName}
        self._connected: bool = False

    @override
    def connect(self) -> None:
        self._connected = True

    @override
    def disconnect(self) -> None:
        self._connected = False

    @override
    def is_connected(self) -> bool:
        return self._connected

    @override
    def send_command(self, joint_angles: dict[JointName, float]) -> None:
        self._angles.update(joint_angles)

    @override
    def get_current_angles(self) -> dict[JointName, float]:
        return dict(self._angles)
