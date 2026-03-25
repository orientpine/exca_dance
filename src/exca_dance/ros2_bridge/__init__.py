"""ROS2 bridge package for Exca Dance.

Provides create_bridge() factory that returns the appropriate bridge
based on mode and ROS2 availability.
"""

from __future__ import annotations
import logging
from exca_dance.ros2_bridge.interface import ExcavatorBridgeInterface, VirtualBridge

logger = logging.getLogger(__name__)


def create_bridge(mode: str = "virtual") -> ExcavatorBridgeInterface:
    """
    Factory function for excavator bridge.

    mode='virtual': Returns VirtualBridge (no ROS2 required)
    mode='real':    Tries ROS2Bridge, falls back to VirtualBridge on failure
    """
    if mode == "virtual":
        bridge = VirtualBridge()
        bridge.connect()
        return bridge

    # mode == 'real'
    try:
        from exca_dance.ros2_bridge.ros2_node import ROS2Bridge

        bridge = ROS2Bridge()
        bridge.connect()
        logger.info("ROS2 bridge connected")
        return bridge
    except ImportError:
        logger.warning("ROS2 not available \u2014 falling back to virtual mode")
        bridge = VirtualBridge()
        bridge.connect()
        return bridge
    except Exception as exc:
        logger.warning("ROS2 bridge failed (%s) \u2014 falling back to virtual mode", exc)
        bridge = VirtualBridge()
        bridge.connect()
        return bridge
