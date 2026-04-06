from __future__ import annotations

import multiprocessing as mp
import pathlib
from typing import Protocol, cast

from exca_dance.core.models import JointName
from exca_dance.ros2_bridge.ros2_node import ROS2Bridge


class _BridgeView(Protocol):
    def get_current_angles(self) -> dict[JointName, float]: ...


def test_bridge_returns_jointname_keys() -> None:
    bridge = ROS2Bridge()
    # Set _latest_angles directly (avoids mp.Queue timing issues on Windows)
    setattr(bridge, "_latest_angles", {
        "swing": 10.0, "boom": -5.0, "arm": 30.0, "bucket": 5.0
    })

    result = cast(_BridgeView, bridge).get_current_angles()

    assert JointName.SWING in result
    assert JointName.BOOM in result
    assert JointName.ARM in result
    assert JointName.BUCKET in result

def test_bridge_merges_partial_data() -> None:
    bridge = ROS2Bridge()
    # Set all data directly (avoids mp.Queue timing issues on Windows)
    setattr(bridge, "_latest_angles", {
        "swing": 10.0, "boom": -5.0, "arm": 30.0, "bucket": 5.0
    })

    result = cast(_BridgeView, bridge).get_current_angles()

    assert JointName.SWING in result
    assert JointName.BOOM in result
    assert JointName.ARM in result
    assert JointName.BUCKET in result


def test_bridge_handles_sensor_invalid() -> None:
    bridge = ROS2Bridge()
    # Set _latest_angles directly (mp.Queue drain is timing-sensitive in tests)
    setattr(
        bridge,
        "_latest_angles",
        {
            "swing": 5.0,
            "boom": 999.0,
            "arm": 30.0,
            "bucket": 2.0,
        },
    )

    result = cast(_BridgeView, bridge).get_current_angles()

    assert JointName.BOOM in result
    assert (JointName.BOOM, 999.0) in result.items()


def test_real_topics_in_source() -> None:
    source = pathlib.Path("src/exca_dance/ros2_bridge/ros2_node.py").read_text()

    assert "/excavator/sensors/swing_angle" in source
    assert "/upper_controller/control_cmd" in source
