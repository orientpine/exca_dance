/upper_controller/control_cmd 토픽 사용 매뉴얼
1. 개요
can_bridge_node는 /upper_controller/control_cmd 토픽을 구독하여, 수신된 UpperControlCmd 메시지를 CAN 프레임(0x28B 아날로그 + 0x18B 제어 비트)으로 변환해 굴삭기 상부 액추에이터(붐, 암, 버킷, 스윙)를 제어합니다.
[퍼블리셔 노드] --UpperControlCmd--> /upper_controller/control_cmd ---> [can_bridge_node] --CAN 0x28B/0x18B--> [굴삭기 하드웨어]
---
2. 메시지 정의 (UpperControlCmd.msg)
std_msgs/Header header          # ROS 표준 헤더 (타임스탬프, 프레임 ID)
float32 boom_velocity           # 붐: -1.0(하강) ~ 0.0(정지) ~ 1.0(상승)
float32 arm_velocity            # 암: -1.0(덤프) ~ 0.0(정지) ~ 1.0(크라우드)
float32 bucket_velocity         # 버킷: -1.0(덤프) ~ 0.0(정지) ~ 1.0(크라우드)
float32 swing_velocity          # 스윙: -1.0(좌회전) ~ 0.0(정지) ~ 1.0(우회전)
uint8 control_mode              # 0: 수동, 1: 자동, 2: 보조
bool emergency_stop             # 비상정지 플래그
bool safety_override            # 안전 오버라이드 플래그
필드 상세
필드	타입
boom_velocity	float32
arm_velocity	float32
bucket_velocity	float32
swing_velocity	float32
control_mode	uint8
emergency_stop	bool
safety_override	bool
> 핵심: can_bridge_node는 boom_velocity, arm_velocity, bucket_velocity, swing_velocity 4개 필드만 CAN 전송에 사용합니다.
---
3. CAN 변환 과정 (내부 처리)
3-1. float → uint8 변환
# -1.0 ~ 1.0 → 0 ~ 255 변환 공식
uint8_value = int(128 + clamp(velocity, -1.0, 1.0) * 127)
입력 (float)
-1.0
-0.5
0.0
0.5
1.0
3-2. CAN 프레임 구조
0x28B (PC Analog) — 8바이트 아날로그 제어 데이터:
바이트
0
1
2
3
4
5
6
7
> 주의: CAN 바이트 순서가 메시지 필드 순서와 다릅니다. 메시지는 boom → arm → bucket → swing이지만 CAN은 arm → swing → boom → bucket입니다.
0x18B (PC Control) — 8바이트 제어 비트:
바이트
0
1
2-6
7
제어 비트에서 각 비트는 해당 채널의 아날로그 값이 중립(128)이 아님을 표시합니다:
- bit 0: arm, bit 1: swing, bit 2: boom, bit 3: bucket, bit 4: right_track, bit 5: left_track
---
4. 토픽 발행 방법
4-1. Python 노드 (권장)
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from excavator_msgs.msg import UpperControlCmd
class UpperControlPublisher(Node):
    def __init__(self):
        super().__init__('upper_control_publisher')
        self.pub = self.create_publisher(
            UpperControlCmd,
            '/upper_controller/control_cmd',
            10
        )
        # 50ms 주기 발행 (CAN 송신 주기와 동일)
        self.timer = self.create_timer(0.05, self.publish_cmd)
    def publish_cmd(self):
        msg = UpperControlCmd()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.boom_velocity = 0.3       # 붐 30% 속도로 상승
        msg.arm_velocity = 0.0        # 암 정지
        msg.bucket_velocity = -0.5    # 버킷 50% 속도로 덤프
        msg.swing_velocity = 0.0      # 스윙 정지
        msg.control_mode = 0          # 수동 모드
        msg.emergency_stop = False
        msg.safety_override = False
        self.pub.publish(msg)
def main():
    rclpy.init()
    node = UpperControlPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
if __name__ == '__main__':
    main()
4-2. CLI (ros2 topic pub)
단발 발행 (테스트용):
ros2 topic pub --once /upper_controller/control_cmd excavator_msgs/msg/UpperControlCmd \
  "{header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, \
    boom_velocity: 0.3, arm_velocity: 0.0, \
    bucket_velocity: 0.0, swing_velocity: 0.0, \
    control_mode: 0, emergency_stop: false, safety_override: false}"
주기적 발행 (10Hz):
ros2 topic pub -r 10 /upper_controller/control_cmd excavator_msgs/msg/UpperControlCmd \
  "{boom_velocity: 0.5, arm_velocity: 0.0, \
    bucket_velocity: 0.0, swing_velocity: 0.0, \
    control_mode: 0, emergency_stop: false, safety_override: false}"
모든 축 정지 (중립 신호):
ros2 topic pub --once /upper_controller/control_cmd excavator_msgs/msg/UpperControlCmd \
  "{boom_velocity: 0.0, arm_velocity: 0.0, \
    bucket_velocity: 0.0, swing_velocity: 0.0, \
    control_mode: 0, emergency_stop: false, safety_override: false}"