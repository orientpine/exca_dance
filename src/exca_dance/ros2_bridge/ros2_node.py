"""ROS2 excavator node — runs in a separate process.

This module is ONLY imported when ROS2 is available.
The main game process NEVER imports this directly.

Publishes: /upper_controller/control_cmd (UpperControlCmd)
Subscribes: /excavator/sensors/joint_boom, joint_arm, joint_bucket (Float32MultiArray)
            /excavator/sensors/swing_angle (Float32)
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import time
from queue import Empty

from exca_dance.core.models import JointName

logger = logging.getLogger(__name__)

# Queue message types (str literal keys for cross-process pickling)
_MSG_TYPE_VELOCITY = "velocity"
_MSG_TYPE_ANGLES = "angles"


def _ros2_process_main(
    velocity_queue: mp.Queue[dict[str, float]],
    state_queue: mp.Queue[dict[str, float]],
) -> None:
    """Entry point for the ROS2 subprocess."""
    try:
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node
        from std_msgs.msg import Float32, Float32MultiArray
    except ImportError as e:
        logger.error("ROS2 not available: %s", e)
        return

    try:
        from excavator_msgs.msg import UpperControlCmd
    except ImportError:
        logger.error("excavator_msgs not available (UpperControlCmd)")
        return

    rclpy.init()

    class ExcavatorNode(Node):
        def __init__(self) -> None:
            super().__init__("exca_dance_bridge")

            # Publisher: velocity commands → CAN bridge
            self._cmd_pub = self.create_publisher(
                UpperControlCmd, "/upper_controller/control_cmd", 10
            )

            # Subscribers: joint angles from inclinometer → kine_publisher
            self._boom_sub = self.create_subscription(
                Float32MultiArray,
                "/excavator/sensors/joint_boom",
                self._boom_cb,
                10,
            )
            self._arm_sub = self.create_subscription(
                Float32MultiArray,
                "/excavator/sensors/joint_arm",
                self._arm_cb,
                10,
            )
            self._bucket_sub = self.create_subscription(
                Float32MultiArray,
                "/excavator/sensors/joint_bucket",
                self._bucket_cb,
                10,
            )
            self._swing_sub = self.create_subscription(
                Float32,
                "/excavator/sensors/swing_angle",
                self._swing_cb,
                10,
            )

            # 20 Hz publish timer — matches CAN bridge 50ms cycle
            self._timer = self.create_timer(1.0 / 20.0, self._tick)

        # ── Subscriber callbacks ─────────────────────────────────

        def _boom_cb(self, msg: Float32MultiArray) -> None:
            if msg.data:
                try:
                    state_queue.put_nowait({"boom": float(msg.data[0])})
                except Exception:
                    pass

        def _arm_cb(self, msg: Float32MultiArray) -> None:
            if msg.data:
                try:
                    state_queue.put_nowait({"arm": float(msg.data[0])})
                except Exception:
                    pass

        def _bucket_cb(self, msg: Float32MultiArray) -> None:
            if msg.data:
                try:
                    state_queue.put_nowait({"bucket": float(msg.data[0])})
                except Exception:
                    pass

        def _swing_cb(self, msg: Float32) -> None:
            try:
                state_queue.put_nowait({"swing": float(msg.data)})
            except Exception:
                pass

        # ── Timer tick: drain velocity queue → publish ────────────

        def _tick(self) -> None:
            latest: dict[str, float] | None = None
            while not velocity_queue.empty():
                try:
                    latest = velocity_queue.get_nowait()
                except Exception:
                    break

            if latest is None:
                # No new command: publish zero velocities (hold still)
                latest = {"boom": 0.0, "arm": 0.0, "bucket": 0.0, "swing": 0.0}

            msg = UpperControlCmd()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.boom_velocity = float(latest.get("boom", 0.0))
            msg.arm_velocity = float(latest.get("arm", 0.0))
            msg.bucket_velocity = float(latest.get("bucket", 0.0))
            msg.swing_velocity = float(latest.get("swing", 0.0))
            msg.control_mode = 0  # manual
            msg.emergency_stop = False
            msg.safety_override = False
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
        try:
            rclpy.shutdown()
        except Exception:
            pass  # SIGTERM signal handler may have already called shutdown


class ROS2Bridge:
    """
    ROS2 bridge implementation using multiprocessing.
    Spawns a separate process running the ROS2 node.
    """

    def __init__(self) -> None:
        self._velocity_queue: mp.Queue[dict[str, float]] = mp.Queue(maxsize=10)
        self._state_queue: mp.Queue[dict[str, float]] = mp.Queue(maxsize=10)
        self._process: mp.Process | None = None
        self._latest_angles: dict[str, float] = {}
        self._connected: bool = False

    def connect(self) -> None:
        self._process = mp.Process(
            target=_ros2_process_main,
            args=(self._velocity_queue, self._state_queue),
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
        """Legacy: send joint angles (kept for virtual-mode compatibility)."""
        pass  # real mode no longer sends angle commands

    def send_velocity(self, velocities: dict[JointName, float]) -> None:
        """Send velocity commands to UpperControlCmd publisher."""
        try:
            str_vel = {k.value if hasattr(k, "value") else str(k): v for k, v in velocities.items()}
            self._velocity_queue.put_nowait(str_vel)
        except Exception:
            pass

    def get_current_angles(self) -> dict[JointName, float]:
        """Get calibrated angles (same as raw for ROS2Bridge — calibration in game_loop)."""
        return self.get_raw_angles()

    def get_raw_angles(self) -> dict[JointName, float]:
        """Non-blocking drain of state queue. Returns latest known angles."""
        for _ in range(20):  # safety cap to prevent unbounded drain
            try:
                update = self._state_queue.get_nowait()
                for key, value in update.items():
                    key_name = key.value if isinstance(key, JointName) else str(key)
                    self._latest_angles[key_name] = float(value)
            except Empty:
                break
            except Exception:
                break

        result: dict[JointName, float] = {}
        for name, value in self._latest_angles.items():
            try:
                result[JointName(name)] = float(value)
            except (ValueError, KeyError):
                pass
        return result
