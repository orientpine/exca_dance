"""ROS2 excavator node — runs in a separate process.

This module is ONLY imported when ROS2 is available.
The main game process NEVER imports this directly.
"""

from __future__ import annotations
import logging
import multiprocessing as mp
import time

logger = logging.getLogger(__name__)


def _ros2_process_main(command_queue: mp.Queue, state_queue: mp.Queue) -> None:
    """Entry point for the ROS2 subprocess."""
    try:
        import rclpy
        from rclpy.node import Node
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
        from sensor_msgs.msg import JointState
    except ImportError as e:
        logger.error("ROS2 not available: %s", e)
        return

    rclpy.init()

    low_latency_qos = QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        history=HistoryPolicy.KEEP_LAST,
        depth=5,
        durability=DurabilityPolicy.VOLATILE,
    )

    class ExcavatorNode(Node):
        def __init__(self):
            super().__init__("exca_dance_bridge")
            self._cmd_pub = self.create_publisher(JointState, "/excavator/command", 10)
            self._state_sub = self.create_subscription(
                JointState, "/excavator/joint_states", self._state_cb, low_latency_qos
            )
            self._timer = self.create_timer(1.0 / 60.0, self._tick)

        def _state_cb(self, msg: JointState) -> None:
            angles = {}
            for i, name in enumerate(msg.name):
                if i < len(msg.position):
                    angles[name] = float(msg.position[i])
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
        from exca_dance.ros2_bridge.interface import ExcavatorBridgeInterface

        self._command_queue: mp.Queue = mp.Queue(maxsize=10)
        self._state_queue: mp.Queue = mp.Queue(maxsize=10)
        self._process: mp.Process | None = None
        self._latest_angles: dict = {}
        self._connected = False

    def connect(self) -> None:
        self._process = mp.Process(
            target=_ros2_process_main,
            args=(self._command_queue, self._state_queue),
            daemon=True,
        )
        self._process.start()
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

    def send_command(self, joint_angles: dict) -> None:
        try:
            # Convert JointName enum keys to strings
            str_angles = {
                k.value if hasattr(k, "value") else str(k): v for k, v in joint_angles.items()
            }
            self._command_queue.put_nowait(str_angles)
        except Exception:
            pass

    def get_current_angles(self) -> dict:
        # Drain state queue, keep latest
        while not self._state_queue.empty():
            try:
                self._latest_angles = self._state_queue.get_nowait()
            except Exception:
                break
        return dict(self._latest_angles)
