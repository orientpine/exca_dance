# ROS2 Bridge — 실제 굴착기 연동

> **목적**: exca_dance의 ROS2 통합 — 서브프로세스 격리, IPC 메커니즘, 메시지 포맷, 모드 전환을 정의한다.
>
> **대상 파일**: `src/exca_dance/ros2_bridge/`

---

## 아키텍처: 서브프로세스 격리

```
┌─────────────────────┐     ┌─────────────────────┐
│   메인 게임 프로세스  │     │  ROS2 서브프로세스    │
│                     │     │                     │
│  create_bridge()   │────▶│  _ros2_process_main │
│  (Queue IPC)       │     │  rclpy 초기화        │
│  send_command()    │────▶│  /excavator/command │
│  get_current_angles│◀────│  /excavator/joint_states
└─────────────────────┘     └─────────────────────┘
```

**왜 서브프로세스인가?**
- `rclpy`는 자체 이벤트 루프를 초기화하여 pygame 이벤트 루프와 **충돌**
- 메인 프로세스에서 `ros2_node.py` 직접 임포트 **금지**

---

## IPC: `multiprocessing.Queue`

| 큐 | 방향 | 용도 |
|----|------|------|
| `command_queue` | 메인 → 서브 | 관절 각도 명령 전송 |
| `state_queue` | 서브 → 메인 | 관절 상태 피드백 수신 |

- `maxsize=10` (메모리 누수 방지)
- 메인: 매 `get_current_angles()` 호출 시 큐 드레인, 최신 상태만 유지
- 서브: 매 틱마다 명령 큐 드레인, 최신 명령만 퍼블리시

---

## 메시지 포맷

ROS2 메시지 타입: `sensor_msgs.msg.JointState`

```python
msg.name = ["swing", "boom", "arm", "bucket"]   # 소문자 관절명
msg.position = [45.0, -20.0, 30.0, 10.0]         # 각도 (도)
```

---

## 두 가지 모드

| 모드 | 클래스 | 활성화 | 동작 |
|------|--------|--------|------|
| `virtual` | `VirtualBridge` | 기본값 | No-op send, 내부 각도 저장 |
| `real` | `ROS2Bridge` | `--mode real` | 서브프로세스 생성, ROS2 토픽 퍼블리시 |

폴백: ROS2 임포트 또는 서브프로세스 실패 시 자동으로 `VirtualBridge`로 전환

---

## 팩토리 사용법

```python
# ✅ 올바른 방법
from exca_dance.ros2_bridge import create_bridge
bridge = create_bridge(mode="virtual")  # 또는 "real"

# ❌ 절대 금지
from exca_dance.ros2_bridge.ros2_node import ROS2ExcavatorNode
```

---

## QoS 설정

```python
QoSProfile(
    reliability=BEST_EFFORT,   # 재전송 없음, 저지연
    history=KEEP_LAST, depth=5,
    durability=VOLATILE,       # 영속성 없음
)
```

타이머 빈도: 60Hz (`1.0/60.0`)
