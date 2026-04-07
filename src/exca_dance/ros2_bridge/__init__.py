"""ROS2 bridge package for Exca Dance.

Provides create_bridge() factory that returns the appropriate bridge
based on mode and ROS2 availability.
"""

from __future__ import annotations
import logging
import os
from exca_dance.ros2_bridge.interface import ExcavatorBridgeInterface, VirtualBridge

logger = logging.getLogger(__name__)

# Expected ROS2 environment for cross-machine communication
_EXPECTED_DOMAIN_ID = "7"
_EXPECTED_RMW = "rmw_cyclonedds_cpp"


def is_ros2_available() -> bool:
    try:
        import rclpy  # noqa: F401
        return True
    except ImportError:
        return False


def is_ros2_installed_but_not_sourced() -> bool:
    if is_ros2_available():
        return False
    from pathlib import Path
    return Path("/opt/ros").is_dir() or bool(os.environ.get("ROS_DISTRO"))


def get_ros2_distro() -> str:
    """Detect installed ROS2 distro name. Falls back to 'humble'."""
    distro = os.environ.get("ROS_DISTRO")
    if distro:
        return distro
    from pathlib import Path
    ros_path = Path("/opt/ros")
    if ros_path.is_dir():
        distros = [d.name for d in ros_path.iterdir() if d.is_dir()]
        if distros:
            return distros[0]
    return "humble"


def _validate_ros2_env() -> list[str]:
    warnings: list[str] = []

    domain_id = os.environ.get("ROS_DOMAIN_ID", "")
    if not domain_id:
        warnings.append(
            f"ROS_DOMAIN_ID not set (excavator nodes use {_EXPECTED_DOMAIN_ID}). "
            f"Set: export ROS_DOMAIN_ID={_EXPECTED_DOMAIN_ID}"
        )
    elif domain_id != _EXPECTED_DOMAIN_ID:
        warnings.append(
            f"ROS_DOMAIN_ID={domain_id} but excavator nodes use {_EXPECTED_DOMAIN_ID}"
        )

    rmw = os.environ.get("RMW_IMPLEMENTATION", "")
    if rmw and rmw != _EXPECTED_RMW:
        warnings.append(
            f"RMW_IMPLEMENTATION={rmw} but excavator nodes use {_EXPECTED_RMW}"
        )

    cyclone_uri = os.environ.get("CYCLONEDDS_URI", "")
    if not cyclone_uri:
        warnings.append(
            "CYCLONEDDS_URI not set — DDS may bind to wrong network interface"
        )

    return warnings


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
    env_warnings = _validate_ros2_env()
    for w in env_warnings:
        logger.warning("ROS2 env: %s", w)

    try:
        from exca_dance.ros2_bridge.ros2_node import ROS2Bridge

        bridge = ROS2Bridge()
        bridge.connect()
        logger.info("ROS2 bridge connected (DOMAIN=%s, RMW=%s)",
                     os.environ.get("ROS_DOMAIN_ID", "0"),
                     os.environ.get("RMW_IMPLEMENTATION", "default"))
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
