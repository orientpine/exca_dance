# AGENTS.md — ros2_bridge/

ROS2 interface for real excavator control. **Subprocess isolation is mandatory.**

---

## STRUCTURE

```
ros2_bridge/
├── __init__.py     # create_bridge() factory — use this, not direct imports
├── interface.py    # ROS2BridgeInterface — abstract protocol (virtual + real modes)
└── ros2_node.py    # ROS2ExcavatorNode — NEVER import from main game process
```

---

## CRITICAL CONSTRAINT

```python
# FORBIDDEN — ros2_node.py imports rclpy which conflicts with pygame event loop
from exca_dance.ros2_bridge.ros2_node import ROS2ExcavatorNode

# CORRECT — use the factory, which handles subprocess isolation
from exca_dance.ros2_bridge import create_bridge
bridge = create_bridge(mode="virtual")   # or "real"
```

`ros2_node.py` is **only** imported inside the subprocess entry point. The main game process communicates via the bridge interface, not directly.

---

## FACTORY USAGE

```python
from exca_dance.ros2_bridge import create_bridge

bridge = create_bridge(mode="virtual")  # no ROS2 needed
bridge = create_bridge(mode="real")     # requires ROS2 environment

bridge.send_command(joint_angles: dict[JointName, float]) -> None
bridge.get_feedback() -> dict[JointName, float] | None
bridge.shutdown() -> None
```

`create_bridge()` falls back to virtual mode if ROS2 is unavailable.

---

## MODES

| Mode | Behavior |
|------|----------|
| `virtual` | No-op send, returns None feedback |
| `real` | Publishes to ROS2 topics via subprocess |

---

## NOTES

- `GameLoop.tick()` always calls `bridge.send_command(joint_angles)` regardless of game state
- ROS2 optional dependency — install separately via ROS2 environment, not pip
- `pyproject.toml` has `[project.optional-dependencies] ros2 = []` (empty — rclpy installed via ROS2)
