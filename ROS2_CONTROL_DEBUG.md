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
- `send_velocity()`: 재시작 drain 패턴을 `while True` / `except Empty`로 통일
- `send_velocity()`: 큐 오버플로 시 경고 로그 추가 (기존 무음 → `logger.debug`)
- `send_velocity()`: 3회 재시작 실패 후 매 프레임 경고 로그 (기존 무음 → `logger.warning`)

### `src/exca_dance/core/game_loop.py`
- `update_bridge()` 메서드 추가: real 모드에서 매 프레임 bridge I/O
- `tick()`: real 모드일 때 bridge I/O 분리 (update_bridge에서 처리)
- `_send_velocity_to_bridge()`: 5초마다 진단 로그 출력
- gamepad 연결 상태 로그 추가
- `_send_velocity_to_bridge()`: `_vel_log_counter` 이중 증가 버그 수정

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

## 4. 해결된 문제 (2026-04-07)

### ★★★ 근본 원인: 멀티캐스트 라우팅 오류 (해결됨)

kbj_machine의 DDS 멀티캐스트가 `enx3610bec68041` (USB 이더넷, 172.20.10.x)으로 나가고 있었음.
`wlp2s0` (192.168.0.21, WiFi)로 바인드했지만 커널 멀티캐스트 라우팅이 metric이 낮은 USB 이더넷을 선택.

```bash
# 수정 전
ip route get 239.255.0.1
# → multicast 239.255.0.1 dev enx3610bec68041 src 172.20.10.2  ← 잘못된 인터페이스!

# 수정 후
ip route get 239.255.0.1
# → multicast 239.255.0.1 dev wlp2s0 src 192.168.0.21  ← 올바른 인터페이스
```

#### 수정 사항

**1. 멀티캐스트 라우트 즉시 수정 + 영구 설정:**
```bash
sudo ip route add 239.255.0.0/16 dev wlp2s0
```
영구 스크립트: `/etc/networkd-dispatcher/routable.d/50-multicast-wlp2s0.sh`

**2. CycloneDDS 유니캐스트 피어 추가 (양쪽 .bashrc):**
- kbj_machine: `<Peer address="192.168.0.8"/>` 추가 (멀티캐스트 유지 + 유니캐스트 보조)
- inner_orin1: `<Peer address="192.168.0.21"/>` 추가 (기존 멀티캐스트 유지)

**3. 게임 코드 환경 검증 추가:**
- `ros2_bridge/__init__.py`: `_validate_ros2_env()` — ROS_DOMAIN_ID, RMW, CYCLONEDDS_URI 체크
- `ros2_bridge/ros2_node.py`: subprocess 시작 시 환경변수 로깅

### 검증 결과

| 테스트 | 결과 |
|--------|------|
| kbj → orin1 토픽 디스커버리 | ✅ 37+ 토픽, 14 노드 |
| kbj → orin1 센서 데이터 수신 (boom/arm) | ✅ 정상 |
| kbj → orin1 velocity 커맨드 발행 | ✅ 720개/8초 |
| 양방향 통신 | ✅ COMMUNICATION_OK |

### WiFi 품질 (잔존 이슈)

| 지표 | 값 | 평가 |
|------|-----|------|
| 대역 | 2.4GHz | ⚠️ 5GHz 전환 권장 |
| 신호 | -58dBm (52/70) | 보통 |
| Ping 패킷 손실 | 13.3% | ❌ 나쁨 |
| Ping 평균/최대 | 95ms / 228ms | ⚠️ 높음 |
| DDS 메시지 jitter | 64.8ms | ⚠️ 높음 |
| DDS 간격 >100ms | 7.8% | ⚠️ 간헐적 스파이크 |

게임 FPS에는 영향 없음 (ROS2는 별도 subprocess). 굴착기 하드웨어 응답 지연에만 영향.

**개선 방안:**
- 5GHz WiFi 사용 (현재 2.4GHz)
- 또는 kbj_machine에 유선 이더넷 연결 (USB 어댑터를 192.168.0.x 서브넷에 연결)

---

## 5. 남은 확인 사항

1. **3-5초 먹통 문제 재현 테스트**
   - 통신이 정상화된 지금, 게임 실행 후 조종 테스트
   - 먹통 재현 시 → 하드웨어 ECU 워치독 문제 확정
   - 정상 작동 시 → 멀티캐스트 라우팅이 근본 원인이었음

2. **can_bridge_node 실제 수신 확인**
   - `candump can2` 또는 `candump can3`으로 CAN 프레임 확인
   - 게임에서 보낸 velocity → CAN 메시지로 변환되는지

3. **upper_controller_node vs 게임 메시지 필드 비교**
   - 하드웨어 워치독 의심 시, 두 메시지 필드 차이가 ECU 동작에 영향 가능

---

## 6. 코드 분석 결과 (2026-04-06)

### 수정 사항 (A-F) 코드 검증

| 수정 항목 | 상태 | 검증 위치 |
|---|---|---|
| (A) 화면 전환 시 velocity 중단 | ✅ 적용됨 | `__main__.py:313` — `game_loop.update_bridge()` 매 프레임 호출 |
| (B) state_queue 오버플로우 | ✅ 적용됨 | `ros2_node.py:82,120-133` — 콜백→dict, 50Hz 타이머 push |
| (C) `queue.empty()` 신뢰성 | ✅ 적용됨 | `ros2_node.py:140-144` — `while True` / `except Empty` |
| (D) upper_controller_node 충돌 | ✅ 적용됨 | `ros2_node.py:178` — `call_enable_service(False)` |
| (E) control_mode 불일치 | ✅ 적용됨 | `ros2_node.py:155` — `msg.control_mode = 1` |
| (F) subprocess 자동 재시작 | ✅ 적용됨 | `ros2_node.py:250-269` — 최대 3회 재시작 |

### 전체 데이터 흐름 (정상 동작 확인)

```
__main__.py:313  game_loop.update_bridge()          ← 매 프레임 (~60Hz) ✅
  → game_loop.py:152  _send_velocity_to_bridge()     ← real 모드면 항상 실행 ✅
    → game_loop.py:258  bridge.send_velocity()         ← calibrated velocity 전송 ✅
      → ros2_node.py:272  velocity_queue.put_nowait()   ← IPC 큐에 삽입 ✅
        → ros2_node.py:142  velocity_queue.get_nowait()  ← 50Hz 타이머 drain ✅
          → ros2_node.py:158  cmd_pub.publish(msg)       ← ROS2 토픽 발행 ✅
```

real 모드에서 정상 동작 중 velocity가 중단될 코드 경로는 없음.

### 발견된 부수적 문제점 (수정 완료)

| # | 문제 | 위치 | 영향 | 수정 |
|---|---|---|---|---|
| 1 | restart drain에 unreliable `while not empty()` 패턴 | `ros2_node.py:258` | 재시작 시 큐 drain 불완전 가능 | `while True` / `except Empty`로 통일 |
| 2 | `put_nowait()` 실패 시 무음 처리 | `ros2_node.py:272-274` | 큐 오버플로 디버깅 불가 | `logger.debug` 추가 |
| 3 | 3회 재시작 실패 후 조용히 포기 | `ros2_node.py:268-269` | 사용자에게 피드백 없음 | 매 프레임 `logger.warning` (300프레임 스로틀) |
| 4 | `_vel_log_counter` 이중 증가 | `game_loop.py:235,248` | gamepad 미연결 시 진단 로그 주기 왜곡 | 중복 증가 제거 |

### 결론: 코드베이스 내 근본 원인 없음

전체 코드 추적 결과, real 모드에서 velocity 전송이 중단되는 코드 버그는 없다.
원격 42-53Hz 수신 확인과 일치하며, 근본 원인은 코드 밖에 있다.

| 우선순위 | 의심점 | 근거 |
|---|---|---|
| ★★★ | tmux CYCLONEDDS_URI 미적용 | `ros2 topic hz`(새 SSH)에선 보이나 can_bridge_node(옛 tmux)의 실제 수신 미확인 |
| ★★☆ | 하드웨어 ECU 워치독 | CAN byte 7=0x20, upper_controller_node만 작동 → ECU 기대 패턴 불일치 가능 |
| ★☆☆ | UpperControlCmd 필드 차이 | 우리 메시지에 누락된 필드가 CAN bridge/ECU 동작에 영향 가능 |

---

## 7. ★★★ 1초 후 멈춤 현상 — 진짜 근본 원인 (2026-04-07 해결)

### 증상 (재확인)

- 게임에서 패드로 굴착기 명령 → 약 0.8~1초 움직이고 완전히 멈춤
- upper_controller_node가 켜져 있든 꺼져 있든 동일한 증상
- 물리 조종기와 upper_controller_node 단독 자동제어는 정상 작동

### 진단 과정 요약

1. **DDS 통신 검증** — `ros2 topic hz /upper_controller/control_cmd` → ~100Hz 안정 수신 확인 ✅
2. **간섭 검증** — `ros2 topic info /upper_controller/control_cmd -v` → Publisher 1개 (`exca_dance_bridge`)뿐, 간섭 없음 ✅
3. **게임 로그 검증** — `bridge vel: ... | gamepad=True | input=True | arm: -1.0` 정상 입력 확인 ✅
4. **Topic echo** — boom 스틱 누를 때 0.83~0.94 값 정상 도착, **단 0.0이 ~37% 비율로 교차 출현**
5. **candump 결정타** — `0x28B`/`0x18B` 프레임이 50ms마다 **활성 ↔ 중립 토글**

### 핵심 CAN 패턴 (decoded)

```
28B  80 80 80 80 80 80 80 00   ← 모두 중립
18B  00 00 00 00 00 00 00 20   ← control_bits=0x00 ("PC가 손 뗐음")
↓ 50ms 후
28B  FF 64 80 80 80 80 80 00   ← arm=+1.0, swing=-0.22 (활성)
18B  03 03 00 00 00 00 00 20   ← control_bits=0x03 (arm+swing 활성)
↓ 50ms 후
28B  80 80 80 80 80 80 80 00   ← 다시 중립
18B  00 00 00 00 00 00 00 20   ← 다시 0x00 (해제)
...
```

ECU는 50ms마다 "PC 명령 받음 → 손 뗐음 → 명령 받음 → 손 뗐음"을 반복적으로 보고, 약 1초 후 PC 컨트롤을 안전 차단함 (워치독 동작).

### 근본 원인: Rate Mismatch 버그

| | 빈도 | 행동 |
|---|---|---|
| 게임 main loop | **60Hz** (16.7ms) | velocity_queue에 push (1개씩) |
| Subprocess `_tick` | **100Hz** (10ms) | 큐 drain 후 즉시 발행 |

10ms 주기 tick의 약 40%는 큐가 비어있음 → 기존 코드는 이때 `{0,0,0,0}` (중립) 발행 → can_bridge_node가 신성하게 0x80(중립) CAN 프레임 전송 → ECU 토글 → 워치독 차단.

### 수정 (`src/exca_dance/ros2_bridge/ros2_node.py`)

- `ExcavatorNode.__init__`에 `self._last_velocity` 필드 추가 (마지막 발행값 캐시)
- `_tick()`에서 큐가 비었을 때 `{0,0,0,0}` 대신 **`self._last_velocity` 재사용**
- 큐에서 새 값을 받으면 `self._last_velocity` 갱신

이렇게 하면:
- 패드를 꾹 누르고 있을 때: CAN 프레임이 일관되게 같은 명령 유지 → ECU 만족 → 워치독 차단 안 됨
- 패드를 놓으면: 게임이 60Hz로 0을 push → 약 16ms 내에 즉시 0으로 전환 → 응답성 양호 (지연 < 17ms)
- 게임이 정상 종료/크래시되면: subprocess 자체가 종료되므로 마지막 값이 무한히 전송될 위험 없음

### 재발 방지 규칙

- **subprocess timer 주기를 게임 frame rate(60Hz)와 일치시키지 말 것** — IPC 큐 기반 통신에서 consumer가 producer보다 빠르면 항상 빈 tick이 발생함. 이 경우 "최신 값 캐싱" 패턴이 필수.
- **CAN/ECU에 명령을 발행하는 모든 경로**에서 "데이터 없음 = 중립값"으로 fallback하는 코드는 금지. 반드시 마지막 유효값 유지해야 함.

---

## 8. 참고: 원격 SSH 접속 정보

### inner_orin1
- Host: 192.168.0.8
- User: kimm
- Password: kimm
- ROS2 workspace: ~/robot_ws
- CAN bridge 소스: ~/robot_ws/src/excavator_signal_manager/excavator_signal_manager/can_bridge_node.py
- Upper controller 소스: ~/robot_ws/src/excavator_control/excavator_control/upper_controller_node.py
### kbj_machine
- Host: 192.168.0.21
- User: kbj
- Password: 200314
- exca_dance workspace: ~/Documents/exca_dance