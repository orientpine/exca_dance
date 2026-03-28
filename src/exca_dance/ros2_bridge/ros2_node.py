"""ROS2 excavator node — runs in a separate process.

This module is ONLY imported when ROS2 is available.
The main game process NEVER imports this directly.
"""

from __future__ import annotations
import logging
import multiprocessing as mp
import time
from queue import Empty

from exca_dance.core.models import JointName

logger = logging.getLogger(__name__)


def _ros2_process_main(
    command_queue: mp.Queue[dict[str, float]],
    state_queue: mp.Queue[dict[str, float]],
) -> None:
    """Entry point for the ROS2 subprocess."""
    try:
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node
        from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
        from sensor_msgs.msg import JointState
        from std_msgs.msg import Float32
    except ImportError as e:
        logger.error("ROS2 not available: %s", e)
        return

    try:
        from excavator_msgs.msg import ExcavatorCompleteStatus
    except ImportError:
        logger.error("excavator_msgs not available")
        return

    rclpy.init()

    real_qos = QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )

    class ExcavatorNode(Node):
        def __init__(self):
            super().__init__("exca_dance_bridge")
            self._cmd_pub = self.create_publisher(JointState, "/excavator/command", 10)
            self._swing_sub = self.create_subscription(
                Float32,
                "/excavator/sensors/swing_angle",
                self._swing_cb,
                real_qos,
            )
            self._status_sub = self.create_subscription(
                ExcavatorCompleteStatus,
                "/excavator/state/complete_status",
                self._status_cb,
                real_qos,
            )
            self._timer = self.create_timer(1.0 / 60.0, self._tick)

        def _swing_cb(self, msg: Float32) -> None:
            try:
                state_queue.put_nowait({"swing": float(msg.data)})
            except Exception:
                pass

        def _status_cb(self, msg: ExcavatorCompleteStatus) -> None:
            angles = {}
            inc = msg.inclinometer_data
            if inc.boom_sensor_valid:
                angles["boom"] = float(inc.boom_latitude)
            if inc.arm_sensor_valid:
                angles["arm"] = float(inc.arm_latitude) - float(inc.boom_latitude)
            if inc.bucket_sensor_valid:
                angles["bucket"] = float(inc.bucket_latitude) - float(inc.arm_latitude)
            if not angles:
                return
            try:
                state_queue.put_nowait(angles)
            except Exception:
                pass

        def _tick(self) -> None:
            # Drain command queue and publish latest
            latest = None
            while not command_queue.empty():
                try:
                    latest = command_queue.get_nowait()
                except Exception:
                    break
            if latest:
                msg = JointState()
                msg.header.stamp = self.get_clock().now().to_msg()
                msg.name = list(latest.keys())
                msg.position = [float(v) for v in latest.values()]
                self._cmd_pub.publish(msg)

    node = ExcavatorNode()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except Exception:
        pass
    finally:
        node.destroy_node()
        executor.shutdown()
        rclpy.shutdown()


class ROS2Bridge:
    """
    ROS2 bridge implementation using multiprocessing.
    Spawns a separate process running the ROS2 node.
    """

    def __init__(self) -> None:

        self._command_queue: mp.Queue[dict[str, float]] = mp.Queue(maxsize=10)
        self._state_queue: mp.Queue[dict[str, float]] = mp.Queue(maxsize=10)
        self._process: mp.Process | None = None
        self._latest_angles: dict[str | JointName, float] = {}
        self._connected: bool = False

    def connect(self) -> None:
        self._process = mp.Process(
            target=_ros2_process_main,
            args=(self._command_queue, self._state_queue),
            daemon=True,
        )
        self._process.start()
        time.sleep(0.5)
        if not self._process.is_alive():
            raise RuntimeError("ROS2 subprocess exited immediately (excavator_msgs unavailable?)")
        self._connected = True
        logger.info("ROS2 bridge process started (PID %d)", self._process.pid)

    def disconnect(self) -> None:
        if self._process and self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=2.0)
        self._connected = False

    def is_connected(self) -> bool:
        if self._process is None:
            return False
        return self._process.is_alive()

    def send_command(self, joint_angles: dict[JointName, float]) -> None:
        try:
            # Convert JointName enum keys to strings
            str_angles = {
                k.value if hasattr(k, "value") else str(k): v for k, v in joint_angles.items()
            }
            self._command_queue.put_nowait(str_angles)
        except Exception:
            pass

    def get_current_angles(self) -> dict[JointName, float]:
        missed = 0
        while missed < 2:
            try:
                update = self._state_queue.get(timeout=0.01)
                missed = 0
                for key, value in update.items():
                    key_name = key.value if isinstance(key, JointName) else str(key)
                    if isinstance(key, str) and any(
                        isinstance(existing, JointName) and existing.value == key
                        for existing in self._latest_angles
                    ):
                        continue
                    self._latest_angles[key_name] = float(value)
            except Empty:
                missed += 1
            except Exception:
                break

        result: dict[JointName, float] = {}
        for name, value in self._latest_angles.items():
            try:
                result[JointName(name)] = float(value)
            except (ValueError, KeyError):
                pass
        return result
