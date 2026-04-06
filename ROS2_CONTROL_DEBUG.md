# ROS2 Xbox Controller → Excavator Control 디버깅 기록

## 날짜: 2026-04-06

---

## 1. 네트워크 설정 (해결됨)

### 문제
- 192.168.0.21 (로컬, WiFi) ↔ 192.168.0.8 (orin1, 유선) 간 ping은 되지만 ROS2 토픽이 안 보임

### 원인
- 로컬에 네트워크 인터페이스가 3개 (wlp2s0, enx3610bec68041, docker0)
- CycloneDDS가 멀티캐스트를 `enx3610bec68041` (172.20.10.2)로 보내고 있었음
- 원격도 eno1 + docker0 두 개 인터페이스

### 해결
- **로컬** `~/.bashrc`에 추가:
  ```bash
  export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="wlp2s0"/></Interfaces></General></Domain></CycloneDDS>'
  ```
- **원격** `~/.bashrc`에 추가:
  ```bash
  export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="eno1"/></Interfaces></General></Domain></CycloneDDS>'
  ```
- 원격에서 `ros2 daemon stop && ros2 daemon start` 필요했음 (daemon이 옛 설정으로 캐시)

---

## 2. Xbox 조이스틱 3-5초 후 먹통 문제 (미해결)

### 증상
- 조종권한 스위치를 주면 3-5초간 작동 후 완전 먹통
- 스위치를 껐다 키면 아주 잠깐 작동 후 다시 먹통 반복
- upper_controller_node 단독 자동제어는 잘 됨
- 물리 조종기로 되돌리면 정상 작동

### 조사한 원인들과 결과

#### (A) 화면 전환 시 velocity 전송 중단 → 수정함 (근본 원인 아님)
- `game_loop.tick()`이 `GameplayScreen`에서만 호출됨
- 노래 끝나면 (`_check_song_end()` 3000ms) RESULTS 화면 전환 → tick() 중단 → velocity 중단
- **수정**: `game_loop.update_bridge()`를 `__main__.py` 메인 루프에서 매 프레임 호출
- **파일**: `game_loop.py`, `__main__.py`

#### (B) state_queue 오버플로우 (자세 갱신 느림) → 수정함
- 4개 센서 subscriber가 개별 joint를 `state_queue(maxsize=10)`에 각각 `put_nowait()`
- 큐가 즉시 가득 차서 대부분 데이터 유실
- **수정**: subscriber 콜백은 노드 내부 dict에 저장, 타이머가 50Hz로 전체 스냅샷 push
- 큐 크기 10 → 50, 타이머 20Hz → 50Hz
- **파일**: `ros2_node.py`

#### (C) `velocity_queue.empty()` 신뢰성 문제 → 수정함
- Python multiprocessing Queue의 `empty()`는 unreliable
- `while not queue.empty()` → `while True` / `except Empty: break`로 변경
- **파일**: `ros2_node.py` `_tick()` 메서드

#### (D) upper_controller_node가 같은 토픽에 publish → 수정함 (근본 원인 아님)
- `upper_controller_node`가 `/upper_controller/control_cmd`에 20Hz로 publish
- 우리 게임도 같은 토픽에 publish → 메시지 충돌
- **수정**: 게임 시작 시 `/upper_controller/enable` 서비스로 `False` 호출하여 비활성화, 종료 시 `True` 복원
- **파일**: `ros2_node.py` `call_enable_service()` 함수

#### (E) control_mode 불일치 → 수정함 (근본 원인 아님)
- upper_controller_node는 `control_mode=1` (자동), 우리는 `control_mode=0` (수동)
- `control_mode=1`로 변경
- **파일**: `ros2_node.py` `_tick()` 메서드

#### (F) Gamepad 끊김 / subprocess 크래시 → 수정함 (발생하지 않음)
- Gamepad는 연결 유지됨 (로그 확인)
- subprocess 크래시 시 자동 재시작 (최대 3회)
- 재시작 시 큐 drain 추가
- **파일**: `ros2_node.py`, `gamepad.py`, `game_loop.py`

### 현재 상태 (확인된 사실)

| 항목 | 상태 |
|------|------|
| 게임 → velocity_queue → ROS2 subprocess | 정상 (로그 확인) |
| ROS2 subprocess → `/upper_controller/control_cmd` publish | 정상 50Hz |
| 원격에서 `ros2 topic hz` | 42-53Hz 도착 확인 |
| Gamepad 연결 | 유지됨 |
| emergency_stop | 발생 안 함 |
| upper_controller_node 단독 제어 | 잘 됨 |
| 물리 조종기 | 정상 작동 |

### 미해결 핵심 의심점

#### **★ tmux 노드들의 CYCLONEDDS_URI 문제 (가장 유력)**
- 원격의 ROS2 노드들 (can_bridge_node 등)이 tmux 안에서 실행됨
- tmux는 **CYCLONEDDS_URI 설정 전에** 시작되었을 가능성
- `ros2 topic hz` (새 SSH 세션, CYCLONEDDS_URI 있음)에서는 메시지가 보임
- 하지만 **can_bridge_node** (옛 tmux 세션)는 CYCLONEDDS_URI가 없어서 우리 메시지를 못 받을 수 있음
- 마지막 확인 시 can_bridge_node 프로세스에 CYCLONEDDS_URI가 **있었음** → 추가 검증 필요
- **확인 방법**: tmux 세션을 모두 죽이고 재시작하여 새 CYCLONEDDS_URI 적용 후 테스트

#### 하드웨어 레벨 워치독
- CAN bridge (`can_bridge_node.py`)는 단순히 `self.upper_control_cmd = msg`로 저장 후 CAN 전송
- `_send_control_can()`: 0x28B (아날로그) + 0x18B (컨트롤 비트) 두 개 CAN 메시지 전송
- 컨트롤 메시지 byte 7 = 0x20 (PC 제어 활성 플래그?)
- 하드웨어 ECU가 자체 워치독으로 PC 제어를 3-5초 후 차단할 가능성

#### DDS QoS / WiFi 안정성
- WiFi 경유 DDS 통신에서 jitter 발생 (min: 0.001s, max: 0.210s)
- DDS RELIABLE QoS에서 패킷 손실 시 재전송 백프레셔 가능성
- can_bridge_node subscriber QoS: RELIABLE, KEEP_LAST(10)

---

## 3. 파일 변경 요약

### `src/exca_dance/ros2_bridge/ros2_node.py`
- `_tick()`: `while not queue.empty()` → `while True` / `except Empty`
- subscriber 콜백: 큐 직접 push → 노드 내부 dict 저장
- `_tick()`: 50Hz 타이머, 아날로그 스냅샷 push + velocity drain
- `control_mode`: 0 → 1
- 큐 크기: 10 → 50
- `call_enable_service()`: 시작 시 upper_controller disable, 종료 시 re-enable
- `send_velocity()`: subprocess 생존 확인 + 자동 재시작 (최대 3회)
- drain safety cap: 20 → 60

### `src/exca_dance/core/game_loop.py`
- `update_bridge()` 메서드 추가: real 모드에서 매 프레임 bridge I/O
- `tick()`: real 모드일 때 bridge I/O 분리 (update_bridge에서 처리)
- `_send_velocity_to_bridge()`: 5초마다 진단 로그 출력
- gamepad 연결 상태 로그 추가

### `src/exca_dance/__main__.py`
- 메인 루프에 `game_loop.update_bridge()` 호출 추가

### `src/exca_dance/core/gamepad.py`
- `JOYDEVICEREMOVED` 시 즉시 재연결 시도
- 로그 레벨 강화

### `~/.bashrc` (로컬)
- `CYCLONEDDS_URI` 추가 (wlp2s0 인터페이스)

### `~/.bashrc` (원격 kimm@192.168.0.8)
- `CYCLONEDDS_URI` 추가 (eno1 인터페이스)

---

## 4. 내일 할 일

1. **tmux 세션 재시작 테스트** (최우선)
   - 원격에서 tmux kill 후 재시작 → 모든 노드가 새 CYCLONEDDS_URI로 시작
   - 이후 게임 실행하여 3-5초 타임아웃 재현 여부 확인

2. **can_bridge_node가 실제로 우리 메시지를 받는지 확인**
   - `can_bridge_node.py`에 임시 로그 추가하거나
   - CAN bus 모니터링: `candump can2` 또는 `candump can3`으로 실제 CAN 프레임 확인

3. **DDS 통신 직접 검증**
   - 원격 tmux 안에서 `ros2 topic echo /upper_controller/control_cmd` 실행
   - 게임 실행 → 메시지가 보이는지 확인 (tmux 환경에서)

4. **하드웨어 워치독 확인**
   - 위 테스트에서 CAN 메시지가 정상 전달되는데도 3-5초 후 먹통이면 하드웨어 문제
   - 하드웨어 프로토콜 문서 확인 필요

---

## 5. 참고: 원격 SSH 접속 정보
- Host: 192.168.0.8
- User: kimm
- Password: kimm
- ROS2 workspace: ~/robot_ws
- CAN bridge 소스: ~/robot_ws/src/excavator_signal_manager/excavator_signal_manager/can_bridge_node.py
- Upper controller 소스: ~/robot_ws/src/excavator_control/excavator_control/upper_controller_node.py
