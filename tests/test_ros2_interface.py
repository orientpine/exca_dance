from exca_dance.core.models import JointName
from exca_dance.ros2_bridge.interface import ExcavatorBridgeInterface, VirtualBridge


def test_virtual_bridge_connect_disconnect():
    b = VirtualBridge()
    assert not b.is_connected()
    b.connect()
    assert b.is_connected()
    b.disconnect()
    assert not b.is_connected()


def test_virtual_bridge_send_and_get():
    b = VirtualBridge()
    b.connect()
    b.send_command({JointName.BOOM: 30.0, JointName.ARM: -15.0})
    angles = b.get_current_angles()
    assert angles[JointName.BOOM] == 30.0
    assert angles[JointName.ARM] == -15.0


def test_virtual_bridge_implements_interface():
    assert issubclass(VirtualBridge, ExcavatorBridgeInterface)


def test_no_rclpy_import():
    import ast
    from pathlib import Path

    source = Path(
        "/home/cha/Documents/exca_dance/src/exca_dance/ros2_bridge/interface.py"
    ).read_text()
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "rclpy" not in imported_modules
