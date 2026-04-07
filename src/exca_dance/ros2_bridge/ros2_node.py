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
    import os as _os

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info(
        "ROS2 subprocess starting — DOMAIN=%s RMW=%s CYCLONE=%s",
        _os.environ.get("ROS_DOMAIN_ID", "<unset>"),
        _os.environ.get("RMW_IMPLEMENTATION", "<unset>"),
        _os.environ.get("CYCLONEDDS_URI", "<unset>")[:80],
    )

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

    try:
        from std_srvs.srv import SetBool
    except ImportError:
        SetBool = None

    try:
        rclpy.init()
    except Exception as e:
        logger.error("rclpy.init() failed: %s", e)
        return

    def call_enable_service(node, enable: bool, timeout_sec: float = 5.0) -> bool:
        """Call /upper_controller/enable to take/release control authority."""
        if SetBool is None:
            logger.warning("std_srvs not available, skipping enable service call")
            return False
        cli = node.create_client(SetBool, "/upper_controller/enable")
        if not cli.wait_for_service(timeout_sec=timeout_sec):
            logger.warning("upper_controller/enable service not available (timeout)")
            return False
        req = SetBool.Request()
        req.data = enable
        future = cli.call_async(req)
        rclpy.spin_until_future_complete(node, future, timeout_sec=timeout_sec)
        if future.result() is not None:
            logger.info("upper_controller enable=%s → success=%s", enable, future.result().success)
            return future.result().success
        logger.error("upper_controller enable=%s service call failed", enable)
        return False

    class ExcavatorNode(Node):
        def __init__(self) -> None:
            super().__init__("exca_dance_bridge")

            # Latest sensor state (updated by callbacks, pushed by timer)
            self._latest_state: dict[str, float] = {}

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

            # 100 Hz timer — velocity publish + state snapshot push
            self._timer = self.create_timer(1.0 / 100.0, self._tick)

        # ── Subscriber callbacks: store latest value (no queue) ──

        def _boom_cb(self, msg: Float32MultiArray) -> None:
            if msg.data:
                self._latest_state["boom"] = float(msg.data[0])

        def _arm_cb(self, msg: Float32MultiArray) -> None:
            if msg.data:
                self._latest_state["arm"] = float(msg.data[0])

        def _bucket_cb(self, msg: Float32MultiArray) -> None:
            if msg.data:
                self._latest_state["bucket"] = float(msg.data[0])

        def _swing_cb(self, msg: Float32) -> None:
            self._latest_state["swing"] = float(msg.data)

        # ── Timer tick: drain velocity queue → publish, push state ─

        def _tick(self) -> None:
            # --- velocity command ---
            latest: dict[str, float] | None = None
            while True:
                try:
                    latest = velocity_queue.get_nowait()
                except Empty:
                    break

            if latest is None:
                latest = {"boom": 0.0, "arm": 0.0, "bucket": 0.0, "swing": 0.0}

            msg = UpperControlCmd()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.boom_velocity = float(latest.get("boom", 0.0))
            msg.arm_velocity = float(latest.get("arm", 0.0))
            msg.bucket_velocity = float(latest.get("bucket", 0.0))
            msg.swing_velocity = float(latest.get("swing", 0.0))
            msg.control_mode = 1  # auto (matches upper_controller_node protocol)
            msg.emergency_stop = False
            msg.safety_override = False
            self._cmd_pub.publish(msg)

            # --- state snapshot (complete joint set per push) ---
            if self._latest_state:
                try:
                    state_queue.put_nowait(dict(self._latest_state))
                except Exception:
                    pass

    try:
        node = ExcavatorNode()
    except Exception as e:
        logger.error("ROS2 node creation failed (DDS domain error?): %s", e)
        try:
            rclpy.shutdown()
        except Exception:
            pass
        return

    # Disable upper_controller_node so our commands reach CAN bridge exclusively
    call_enable_service(node, enable=False)

    executor = SingleThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except Exception:
        pass
    finally:
        # Re-enable upper_controller_node before shutting down
        try:
            call_enable_service(node, enable=True, timeout_sec=2.0)
        except Exception:
            pass
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
        self._velocity_queue: mp.Queue[dict[str, float]] = mp.Queue(maxsize=50)
        self._state_queue: mp.Queue[dict[str, float]] = mp.Queue(maxsize=50)
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
            exit_code = self._process.exitcode
            raise RuntimeError(
                f"ROS2 subprocess exited immediately (exit_code={exit_code}). "
                "Check: excavator_msgs installed? DDS network interface available? "
                "CYCLONEDDS_URI config valid?"
            )
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

    _restart_count: int = 0
    _give_up_log_counter: int = 0

    def send_velocity(self, velocities: dict[JointName, float]) -> None:
        """Send velocity commands to UpperControlCmd publisher."""
        if self._process is not None and not self._process.is_alive():
            if self._restart_count < 3:
                self._restart_count += 1
                logger.error(
                    "ROS2 subprocess died (exit_code=%s), restarting (%d/3)...",
                    self._process.exitcode, self._restart_count,
                )
                # Drain stale queue before restart
                while True:
                    try:
                        self._velocity_queue.get_nowait()
                    except Exception:
                        break
                try:
                    self.connect()
                except Exception as e:
                    logger.error("ROS2 subprocess restart failed: %s", e)
                    return
            else:
                self._give_up_log_counter += 1
                if self._give_up_log_counter % 300 == 1:
                    logger.warning(
                        "ROS2 subprocess gave up after 3 restarts — velocity commands dropped"
                    )
                return
        try:
            str_vel = {k.value if hasattr(k, "value") else str(k): v for k, v in velocities.items()}
            self._velocity_queue.put_nowait(str_vel)
        except Exception:
            logger.debug("velocity_queue full — command dropped (next tick will drain)")

    def get_current_angles(self) -> dict[JointName, float]:
        """Get calibrated angles (same as raw for ROS2Bridge — calibration in game_loop)."""
        return self.get_raw_angles()

    def get_raw_angles(self) -> dict[JointName, float]:
        """Non-blocking drain of state queue. Returns latest known angles."""
        for _ in range(60):  # safety cap to prevent unbounded drain
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
