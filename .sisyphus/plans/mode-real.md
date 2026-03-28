# mode:real — 실제 굴착기 ROS2 연동

## TL;DR

> **Quick Summary**: 실제 굴착기의 ROS2 센서 데이터(swing/boom/arm/bucket 각도)를 게임 입력으로 연동. `--mode real`로 활성화하면 키보드 대신 실제 굴착기 관절 각도로 게임 플레이.
>
> **Deliverables**:
> - `ros2_node.py` 리라이트: 실제 굴착기 토픽 구독
> - `game_loop.py` 최소 수정: real mode 입력 경로 추가
> - `__main__.py` 1줄 수정: mode 전달
> - 새 테스트 파일: real mode 동작 검증
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 -> Task 3 -> Task 5 -> Task 6 -> F1-F4

---

## Context

### Original Request
사용자가 `/home/cha/Documents/action_space_finder` 프로젝트에서 실제 굴착기 rosbag 데이터를 녹화한 경험을 바탕으로, 해당 ROS2 인터페이스를 exca_dance 게임의 `--mode real`에 연동 요청. **기존 게임 코드는 절대 수정하지 않을 것** 강조.

### Interview Summary
**Key Discussions**:
- action_space_finder의 ROS2 토픽/메시지 타입 확인 완료
- 현재 ros2_node.py가 가상 토픽(`/excavator/joint_states`)을 구독 → 실제 토픽으로 교체 필요
- GameLoop이 `get_current_angles()` 미사용 → real mode에서 호출하도록 추가
- 기존 코드 "수정 금지" → 순수 additive 변경만 허용

**Research Findings**:
- Swing: `/excavator/sensors/swing_angle` (`std_msgs/Float32`, `.data`, degrees)
- Boom/Arm/Bucket: `/excavator/state/complete_status` (`excavator_msgs/ExcavatorCompleteStatus`, `.inclinometer_data.*_latitude`, degrees)
- 유효성: `*_sensor_valid` boolean 플래그
- QoS: RELIABLE + TRANSIENT_LOCAL (실제 굴착기)
- 현재 ROS2Bridge.get_current_angles()에 JointName 키 변환 버그 존재 (dormant)

### Metis Review
**Identified Gaps** (addressed):
- Return type mismatch (`dict[str, float]` vs `dict[JointName, float]`): ros2_node 리라이트 시 수정
- `send_command()` real mode echo: mode 체크 가드 추가
- Constructor backward compat: keyword-only `mode` 파라미터 사용 → 기존 13 테스트 무변경
- Stale data: 마지막 유효값 유지 (기본값 적용)
- sensor_valid: 마지막 유효값 유지 (기본값 적용)
- JOINT_LIMITS: 실제 데이터에도 clamp 적용 (안전 우선)

---

## Work Objectives

### Core Objective
`--mode real` 실행 시 실제 굴착기 ROS2 센서 데이터가 게임 입력으로 사용되어, 운전자가 실제 굴착기를 조작하면 게임 3D 모델이 동기화되고 비트맵 타겟 대비 스코어링이 이루어지도록 한다.

### Concrete Deliverables
- `src/exca_dance/ros2_bridge/ros2_node.py` — 실제 토픽 구독으로 리라이트
- `src/exca_dance/core/game_loop.py` — `mode` kwarg 추가 + `_update_joints_from_bridge()` 메서드
- `src/exca_dance/__main__.py` — `mode=args.mode` 전달 (1줄)
- `tests/test_game_loop_real_mode.py` — real mode 전용 테스트
- `tests/test_ros2_bridge_real.py` — ROS2 노드 토픽/키 변환 테스트

### Definition of Done
- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` -> all passed, 0 failed (existing 124 + new)
- [ ] `.venv/bin/ruff check src/ tests/` → 0 errors
- [ ] `git diff --stat` → 변경 파일이 ros2_node.py, game_loop.py, __main__.py, 신규 테스트 파일뿐

### Must Have
- 실제 굴착기 ROS2 토픽 구독 (`/excavator/sensors/swing_angle`, `/excavator/state/complete_status`)
- GameLoop에서 real mode일 때 `bridge.get_current_angles()` 호출
- Virtual mode 동작 100% 동일 유지
- existing 124 tests all pass unchanged (zero test file modifications)
- `excavator_msgs` 패키지 임포트 실패 시 VirtualBridge 폴백

### Must NOT Have (Guardrails)
- ❌ 기존 게임 화면(메뉴, 곡선택, 결과, 리더보드, 설정, 에디터) 수정
- ❌ 스코어링 공식 변경
- ❌ 렌더링/3D 모델/테마 변경
- ❌ `interface.py` (ExcavatorBridgeInterface) 수정
- ❌ 기존 테스트 파일 수정
- ❌ InputSource/AngleConverter 등 새 추상화 계층 생성
- ❌ YAML/TOML 설정 파일 추가 (토픽명은 하드코딩)
- ❌ 재접속 로직, 각도 스무딩/필터링
- ❌ "Waiting for excavator" 등 새 화면 추가
- ❌ 헬스 모니터링/하트비트 시스템

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, 124 existing tests)
- **Automated tests**: TDD (RED → GREEN → REFACTOR)
- **Framework**: pytest (PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 필수)
- **If TDD**: 테스트 먼저 작성 (FAIL) → 구현 (PASS) → 리팩터

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Backend/Module**: Use Bash — pytest 실행, ruff 체크, git diff 확인

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — TDD RED phase):
├── Task 1: GameLoop real mode 테스트 작성 (RED) [quick]
├── Task 2: ROS2 노드 토픽/키변환 테스트 작성 (RED) [quick]

Wave 2 (After Wave 1 — TDD GREEN phase):
├── Task 3: GameLoop real mode 구현 (depends: 1) [quick]
├── Task 4: ros2_node.py 리라이트 (depends: 2) [deep]

Wave 3 (After Wave 2 — Wiring + Regression):
├── Task 5: __main__.py mode 전달 (depends: 3) [quick]
└── Task 6: 전체 회귀 검증 + lint + git diff (depends: 3, 4, 5) [quick]

Wave FINAL (After ALL — 4 parallel reviews, then user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|------------|--------|------|
| 1 | — | 3 | 1 |
| 2 | — | 4 | 1 |
| 3 | 1 | 5, 6 | 2 |
| 4 | 2 | 6 | 2 |
| 5 | 3 | 6 | 3 |
| 6 | 3, 4, 5 | F1-F4 | 3 |
| F1-F4 | 6 | — | FINAL |

### Agent Dispatch Summary

- **Wave 1**: **2** — T1 → `quick`, T2 → `quick`
- **Wave 2**: **2** — T3 → `quick`, T4 → `deep`
- **Wave 3**: **2** — T5 -> `quick`, T6 -> `quick`
- **FINAL**: **4** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. GameLoop real mode 테스트 작성 (TDD RED)

  **What to do**:
  - `tests/test_game_loop_real_mode.py` 파일 생성
  - 기존 `tests/test_game_loop.py`의 `_make_game_loop()` 헬퍼 패턴을 참고하여 `_make_game_loop_real()` 헬퍼 작성
  - `mode="real"` keyword-only 인자로 GameLoop 생성
  - 테스트 케이스:
    - `test_real_mode_reads_bridge_angles`: bridge.get_current_angles() 반환값이 joint_angles에 반영되는지
    - `test_real_mode_ignores_keyboard`: _held_keys에 키가 있어도 bridge 값만 사용되는지
    - `test_real_mode_skips_send_command`: real mode에서 bridge.send_command() 호출 안 되는지
    - `test_real_mode_clamps_to_joint_limits`: bridge 반환값이 JOINT_LIMITS 범위로 clamp되는지
    - `test_real_mode_handles_empty_angles`: bridge가 빈 dict 반환 시 기존 각도 유지되는지
    - `test_virtual_mode_unchanged`: mode="virtual" (기본값)이면 기존 동작 100% 동일한지
  - 이 테스트들은 아직 구현이 없으므로 FAIL해야 정상 (TDD RED phase)

  **Must NOT do**:
  - 기존 `tests/test_game_loop.py` 수정 금지
  - GameLoop 구현 코드 수정 금지 (테스트만 작성)
  - InputSource 등 추상화 계층 도입 금지

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 단일 테스트 파일 생성, 기존 패턴 복사
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: [Task 3]
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `tests/test_game_loop.py` - 기존 GameLoop 테스트 구조, `_make_game_loop()` 헬퍼 함수 패턴 (Mock 객체 구성법)

  **API/Type References**:
  - `src/exca_dance/core/game_loop.py:GameLoop.__init__()` - 현재 8개 positional args (mode는 아직 없음)
  - `src/exca_dance/core/game_loop.py:GameLoop.tick()` - 테스트 대상 메서드 (line 113)
  - `src/exca_dance/core/game_loop.py:GameLoop._update_joints()` - 키보드 입력 처리 (line 155)
  - `src/exca_dance/ros2_bridge/interface.py:ExcavatorBridgeInterface.get_current_angles()` - 반환 타입 dict[JointName, float]
  - `src/exca_dance/core/models.py:JointName` - SWING, BOOM, ARM, BUCKET enum
  - `src/exca_dance/core/constants.py:JOINT_LIMITS` - 각 관절 min/max degrees
  - `src/exca_dance/core/constants.py:DEFAULT_JOINT_ANGLES` - 초기 각도값

  **WHY Each Reference Matters**:
  - `tests/test_game_loop.py` -> Mock 구성 패턴 복사 (renderer, audio, fk, scoring, keybinding, bridge, viewport, excavator_model)
  - `GameLoop.__init__` -> keyword-only `mode` 파라미터 추가 위치 확인
  - `get_current_angles()` -> real mode에서 호출할 메서드, mock return value 설정에 필요
  - `JOINT_LIMITS` -> clamp 테스트에 필요한 경계값

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: TDD RED - 테스트 파일 존재 + 테스트 FAIL 확인
    Tool: Bash
    Preconditions: tests/test_game_loop_real_mode.py 생성 완료
    Steps:
      1. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_game_loop_real_mode.py -v
      2. 테스트가 FAIL 또는 ERROR로 종료되는지 확인 (GameLoop에 mode 파라미터 미구현)
      3. .venv/bin/ruff check tests/test_game_loop_real_mode.py
    Expected Result: pytest exit code != 0 (테스트 실패), ruff 0 errors
    Failure Indicators: 테스트가 PASS하면 구현을 미리 해버린 것 (RED phase 위반)
    Evidence: .sisyphus/evidence/task-1-tdd-red.txt

  Scenario: 기존 테스트 무영향 확인
    Tool: Bash
    Preconditions: 새 테스트 파일만 생성, 기존 파일 미수정
    Steps:
      1. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_game_loop.py -v
      2. all passed, 0 failed 확인
    Expected Result: all passed, 0 failed
    Failure Indicators: 기존 테스트 중 하나라도 FAIL
    Evidence: .sisyphus/evidence/task-1-regression.txt
  ```

  **Commit**: YES
  - Message: `test(core): add GameLoop real mode input tests (RED)`
  - Files: `tests/test_game_loop_real_mode.py`
  - Pre-commit: `ruff check tests/test_game_loop_real_mode.py`

- [x] 2. ROS2 노드 토픽 구독 및 키 변환 테스트 작성 (TDD RED)

  **What to do**:
  - `tests/test_ros2_bridge_real.py` 파일 생성
  - ros2_node.py의 실제 토픽 구독과 JointName 키 변환을 검증하는 테스트 작성
  - rclpy 없이 테스트 가능하도록 multiprocessing.Queue 기반 IPC만 테스트
  - 테스트 케이스:
    - `test_bridge_returns_jointname_keys`: ROS2Bridge.get_current_angles()가 dict[JointName, float] 반환하는지 (현재는 dict[str, float] 반환하므로 FAIL)
    - `test_bridge_merges_partial_data`: state_queue에 부분 데이터 push -> 이전 데이터와 병합되는지
    - `test_bridge_handles_sensor_invalid`: sensor_valid=False인 관절은 이전 유효값 유지하는지
    - `test_real_topics_in_source`: ros2_node.py 소스에 실제 토픽명이 포함되어 있는지 (AST/문자열 검사)
  - 이 테스트들은 FAIL해야 정상 (TDD RED phase)

  **Must NOT do**:
  - 기존 ros2 bridge 테스트 파일 수정 금지
  - ros2_node.py 수정 금지 (테스트만 작성)
  - rclpy를 테스트 의존성으로 추가 금지

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 단일 테스트 파일 생성
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: [Task 4]
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `tests/test_game_loop.py` - Mock 패턴 참고
  - `src/exca_dance/ros2_bridge/ros2_node.py:ROS2Bridge` - 현재 구현 (line 82-134), 특히 get_current_angles() (line 127-134)

  **API/Type References**:
  - `src/exca_dance/ros2_bridge/ros2_node.py:ROS2Bridge.get_current_angles()` - 현재 dict[str, float] 반환 (버그)
  - `src/exca_dance/ros2_bridge/interface.py:ExcavatorBridgeInterface` - 정의된 인터페이스 (line 15-36)
  - `src/exca_dance/core/models.py:JointName` - enum values: "swing", "boom", "arm", "bucket"

  **External References**:
  - `/home/cha/Documents/action_space_finder/src/loader.py:COLUMN_MAPPING` (line 15-26) - 실제 토픽명 확인용
  - `/home/cha/Documents/action_space_finder/raw_data/level_3pipes/metadata.yaml` - QoS 설정 확인용

  **WHY Each Reference Matters**:
  - `ros2_node.py:ROS2Bridge` -> get_current_angles()의 현재 버그 (str 키) 확인, 테스트가 이 버그를 잡아야 함
  - `JointName` -> enum values가 소문자 문자열이므로, str->JointName 변환 시 `JointName(name)` 사용

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: TDD RED - 테스트 FAIL 확인
    Tool: Bash
    Preconditions: tests/test_ros2_bridge_real.py 생성 완료
    Steps:
      1. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_ros2_bridge_real.py -v
      2. 테스트 FAIL/ERROR 확인
      3. .venv/bin/ruff check tests/test_ros2_bridge_real.py
    Expected Result: pytest exit code != 0, ruff 0 errors
    Failure Indicators: 테스트가 PASS하면 RED phase 위반
    Evidence: .sisyphus/evidence/task-2-tdd-red.txt
  ```

  **Commit**: YES
  - Message: `test(ros2): add real excavator topic subscription tests (RED)`
  - Files: `tests/test_ros2_bridge_real.py`
  - Pre-commit: `ruff check tests/test_ros2_bridge_real.py`

- [x] 3. GameLoop real mode 구현 (TDD GREEN)

  **What to do**:
  - `src/exca_dance/core/game_loop.py` 수정 (additive only)
  - `GameLoop.__init__`에 keyword-only `mode: str = "virtual"` 파라미터 추가:
    ```python
    def __init__(self, renderer, audio, fk, scoring, keybinding, bridge,
                 viewport_layout, excavator_model, *, mode: str = "virtual") -> None:
    ```
  - `self._mode = mode` 저장
  - `_update_joints_from_bridge()` 새 private 메서드 추가:
    - `self._bridge.get_current_angles()` 호출
    - 반환된 각도를 JOINT_LIMITS로 clamp
    - 빈 dict면 기존 각도 유지
  - `_update_joints()` 시작 부분에 early-return 분기 추가:
    ```python
    def _update_joints(self, dt: float) -> None:
        if self._mode == "real":
            self._update_joints_from_bridge()
            return
        # === EXISTING CODE BELOW - ZERO CHANGES ===
        for key in self._held_keys:
            ...
    ```
  - `tick()` 에서 `send_command()` 호출을 mode 가드로 보호:
    ```python
    if self._mode != "real":
        self._bridge.send_command(self._joint_angles)
    ```
  - 기존 키보드 코드는 바이트 단위 동일 유지

  **Must NOT do**:
  - 기존 `_update_joints()` 키보드 코드 변경 (새 분기 추가만 허용)
  - 새 추상화 계층 (InputSource 등) 생성 금지
  - 다른 파일 수정 금지

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 단일 파일에 ~15줄 additive 변경
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 4)
  - **Blocks**: [Task 5, Task 6]
  - **Blocked By**: [Task 1]

  **References**:

  **Pattern References**:
  - `src/exca_dance/core/game_loop.py:_update_joints()` (line 155-164) - 기존 키보드 입력 로직, early-return 전에 삽입
  - `src/exca_dance/core/game_loop.py:tick()` (line 113-130) - send_command 가드 추가 위치 (line 126)

  **API/Type References**:
  - `src/exca_dance/ros2_bridge/interface.py:get_current_angles()` - dict[JointName, float] 반환
  - `src/exca_dance/core/constants.py:JOINT_LIMITS` - clamp에 사용
  - `src/exca_dance/core/constants.py:DEFAULT_JOINT_ANGLES` - 초기값

  **WHY Each Reference Matters**:
  - `_update_joints()` -> early-return 분기를 정확히 삽입할 위치 확인
  - `tick()` -> send_command 호출 위치에 mode 가드 추가
  - `JOINT_LIMITS` -> _update_joints_from_bridge()에서 clamp 로직 구현

  **Acceptance Criteria**:
  - [ ] Task 1의 모든 테스트가 PASS (TDD GREEN)
  - [ ] 기존 13개 GameLoop 테스트 무변경 PASS
  - [ ] ruff check 클린

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: TDD GREEN - real mode 테스트 전체 PASS
    Tool: Bash
    Steps:
      1. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_game_loop_real_mode.py -v
      2. 모든 테스트 PASS 확인
    Expected Result: 6 passed, 0 failed
    Failure Indicators: 테스트 FAIL
    Evidence: .sisyphus/evidence/task-3-tdd-green.txt

  Scenario: 기존 GameLoop 테스트 회귀
    Tool: Bash
    Steps:
      1. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_game_loop.py -v
      2. all passed, 0 failed 확인
    Expected Result: all passed, 0 failed
    Evidence: .sisyphus/evidence/task-3-regression.txt

  Scenario: 변경 파일 범위 확인
    Tool: Bash
    Steps:
      1. git diff --name-only
      2. game_loop.py만 변경되었는지 확인
    Expected Result: src/exca_dance/core/game_loop.py only
    Evidence: .sisyphus/evidence/task-3-scope.txt
  ```

  **Commit**: YES
  - Message: `feat(core): support real excavator input in GameLoop`
  - Files: `src/exca_dance/core/game_loop.py`
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_game_loop.py tests/test_game_loop_real_mode.py -v && ruff check src/exca_dance/core/game_loop.py`

- [ ] 4. ros2_node.py 리라이트 - 실제 굴착기 토픽 구독 (TDD GREEN)

  **What to do**:
  - `src/exca_dance/ros2_bridge/ros2_node.py` 리라이트
  - `_ros2_process_main()` 내부 ExcavatorNode 클래스 구독 변경:
    - `/excavator/joint_states` (JointState) 제거
    - `/excavator/sensors/swing_angle` (std_msgs/Float32) 구독 추가
    - `/excavator/state/complete_status` (excavator_msgs/ExcavatorCompleteStatus) 구독 추가
    - excavator_msgs 임포트도 try/except 내부에서 처리 (rclpy와 같은 방식)
  - 콜백 구현:
    - `_swing_cb(msg: Float32)`: `{"swing": msg.data}` -> state_queue
    - `_status_cb(msg: ExcavatorCompleteStatus)` - **각도 변환 필수 (CRITICAL)**:
      - inclinometer는 절대 경사각(latitude)을 보내지만, 게임 FK는 **상대 관절각**을 사용 (kinematics.py:53 `arm_angle = boom_rad + arm_rad`)
      - 변환 공식:
        - `"boom" = inclinometer_data.boom_latitude` (boom은 시스 대비 직접 매핑)
        - `"arm" = inclinometer_data.arm_latitude - inclinometer_data.boom_latitude` (arm은 boom 대비 상대각)
        - `"bucket" = inclinometer_data.bucket_latitude - inclinometer_data.arm_latitude` (bucket은 arm 대비 상대각)
      - `*_sensor_valid` False이면 해당 관절 이전 값 유지 (dict에 미포함)
    - 두 콜백 결과를 병합하여 state_queue에 push
  - QoS 변경:
    - BEST_EFFORT -> RELIABLE
    - VOLATILE -> TRANSIENT_LOCAL
    - depth: 5 -> 10
  - `ROS2Bridge.get_current_angles()` 수정:
    - `self._latest_angles`의 string key를 JointName으로 변환하여 반환
    - `JointName(name)` 사용 (JointName은 StrEnum이므로 "swing" -> JointName.SWING)
    - JointName import를 _ros2_process_main 밖 ROS2Bridge 클래스에서 수행 (rclpy 무관)
  - `/excavator/command` 퍼블리시는 유지 (실제 모드에서는 GameLoop이 호출 안 하지만 구조는 유지)
  - **excavator_msgs 폴백 경로 명시 (CRITICAL)**:
    - `_ros2_process_main()`에서 `excavator_msgs` import 실패 시 subprocess가 즉시 return하여 종료됨
    - `ROS2Bridge.connect()`에서 subprocess 시작 후 짧은 대기 (0.5초) + `self._process.is_alive()` 체크 추가
    - subprocess가 사망했으면 `RuntimeError` raise -> `create_bridge()`의 기존 except 절이 VirtualBridge로 폴백
    - `__init__.py` 수정 불필요 — 기존 `except Exception` 절이 이미 이 케이스를 처리함

  **Must NOT do**:
  - `interface.py` 수정 금지
  - `__init__.py` (create_bridge 팩토리) 수정 금지
  - ROS2Bridge 클래스 구조 변경 (queues, subprocess, connect/disconnect 동일 유지)
  - 재접속/헬스모니터링 로직 추가 금지
  - 각도 스무딩/필터링 금지

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: ROS2 메시지 타입, QoS, 두 토픽 병합, sensor_valid 처리 등 복잡도 높음
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 3)
  - **Blocks**: [Task 6]
  - **Blocked By**: [Task 2]

  **References**:

  **Pattern References**:
  - `src/exca_dance/ros2_bridge/ros2_node.py` - 현재 전체 구조 (134 lines), 서브프로세스 패턴, IPC 큐
  - `src/exca_dance/ros2_bridge/__init__.py:create_bridge()` - 팩토리 패턴 (수정 금지, 참고만)

  **API/Type References**:
  - `src/exca_dance/ros2_bridge/interface.py:ExcavatorBridgeInterface` - 구현해야 할 인터페이스 메서드들
  - `src/exca_dance/core/models.py:JointName` - StrEnum, values: "swing", "boom", "arm", "bucket"

  **External References**:
  - `/home/cha/Documents/action_space_finder/src/loader.py:COLUMN_MAPPING` - 토픽/필드 매핑 확인:
    - `excavator/sensors/swing_angle/data` -> swing_angle
    - `excavator/state/complete_status/inclinometer_data/arm_latitude` -> arm_latitude
    - `excavator/state/complete_status/inclinometer_data/boom_latitude` -> boom_latitude
    - `excavator/state/complete_status/inclinometer_data/bucket_latitude` -> bucket_latitude
    - `*_sensor_valid` -> 유효성 플래그
  - `/home/cha/Documents/action_space_finder/raw_data/level_3pipes/metadata.yaml` - QoS 설정:
    - history: KEEP_LAST, depth: 10, reliability: RELIABLE, durability: TRANSIENT_LOCAL
  - `/home/cha/Documents/action_space_finder/src/kinematics.py` - np.radians() 사용 확인 -> raw data는 degrees

  **WHY Each Reference Matters**:
  - `ros2_node.py` -> 기존 구조를 유지하면서 내부 토픽/콜백/QoS만 교체
  - `COLUMN_MAPPING` -> 실제 토픽명과 필드 경로를 정확히 매칭
  - `metadata.yaml` -> QoS 설정이 실제 굴착기와 일치해야 함
  - `kinematics.py` -> 각도 단위가 degrees임을 확인, 변환 불필요

  **Acceptance Criteria**:
  - [ ] Task 2의 모든 테스트가 PASS (TDD GREEN)
  - [ ] 기존 전체 테스트 스위트 PASS
  - [ ] ruff check 클린

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: TDD GREEN - bridge 테스트 전체 PASS
    Tool: Bash
    Steps:
      1. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_ros2_bridge_real.py -v
      2. 모든 테스트 PASS 확인
    Expected Result: 4 passed, 0 failed
    Evidence: .sisyphus/evidence/task-4-tdd-green.txt

  Scenario: 전체 테스트 스위트 회귀
    Tool: Bash
    Steps:
      1. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v
      2. 전체 PASS 확인 (기존 124 + 신규)
    Expected Result: all passed, 0 failed
    Evidence: .sisyphus/evidence/task-4-full-regression.txt

  Scenario: ros2_node.py 소스에 실제 토픽명 포함 확인
    Tool: Bash
    Steps:
      1. grep -c '/excavator/sensors/swing_angle' src/exca_dance/ros2_bridge/ros2_node.py
      2. grep -c '/excavator/state/complete_status' src/exca_dance/ros2_bridge/ros2_node.py
      3. 각각 1 이상 확인
    Expected Result: 두 grep 모두 1 이상
    Failure Indicators: 0이면 토픽 구독 미구현
    Evidence: .sisyphus/evidence/task-4-topics.txt
  ```

  **Commit**: YES
  - Message: `feat(ros2): subscribe to real excavator sensor topics`
  - Files: `src/exca_dance/ros2_bridge/ros2_node.py`
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v && ruff check src/exca_dance/ros2_bridge/ros2_node.py`

- [x] 5. __main__.py mode 전달

  **What to do**:
  - `src/exca_dance/__main__.py` 수정 (1줄 변경)
  - GameLoop 생성자 호출에 `mode=args.mode` 추가:
    ```python
    # 기존 (line 181-183):
    game_loop = GameLoop(
        renderer, audio, fk, scoring, keybinding, bridge, viewport_layout, excavator_model
    )
    # 변경:
    game_loop = GameLoop(
        renderer, audio, fk, scoring, keybinding, bridge, viewport_layout, excavator_model,
        mode=args.mode,
    )
    ```

  **Must NOT do**:
  - __main__.py의 다른 부분 수정 금지
  - 새 import 추가 금지
  - 다른 파일 수정 금지

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 1줄 변경
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential)
  - **Blocks**: [Task 6]
  - **Blocked By**: [Task 3]

  **References**:
  - `src/exca_dance/__main__.py` line 181-183 - GameLoop 생성자 호출
  - `src/exca_dance/__main__.py` line 89-94 - args.mode 파싱

  **Acceptance Criteria**:
  - [ ] 전체 테스트 스위트 PASS
  - [ ] ruff check 클린

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: mode 전달 확인
    Tool: Bash
    Steps:
      1. grep -n 'mode=args.mode' src/exca_dance/__main__.py
      2. 결과가 1줄 이상 출력되는지 확인
    Expected Result: GameLoop 생성자에 mode=args.mode 전달 확인
    Evidence: .sisyphus/evidence/task-5-mode-wiring.txt

  Scenario: 전체 테스트 회귀
    Tool: Bash
    Steps:
      1. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v
      2. 전체 PASS 확인
    Expected Result: all passed
    Evidence: .sisyphus/evidence/task-5-regression.txt
  ```

  **Commit**: YES
  - Message: `feat(main): pass --mode flag to GameLoop constructor`
  - Files: `src/exca_dance/__main__.py`
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v && ruff check src/exca_dance/__main__.py`

- [x] 6. 전체 회귀 검증 + Lint

  **What to do**:
  - 전체 테스트 스위트 실행
  - ruff check 실행
  - git diff --stat으로 변경 파일 범위 확인
  - 기존 56개 테스트가 모두 무변경 PASS인지 최종 확인

  **Must NOT do**:
  - 코드 수정 금지 (검증만)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 검증 명령어만 실행
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (after Task 5)
  - **Blocks**: [F1-F4]
  - **Blocked By**: [Task 3, Task 4, Task 5]

  **References**:
  - AGENTS.md - 테스트 명령어: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v`
  - AGENTS.md - Lint 명령어: `.venv/bin/ruff check src/ tests/`

  **Acceptance Criteria**:
  - [ ] 전체 테스트 PASS (기존 124 + 신규)
  - [ ] ruff 0 errors
  - [ ] 변경 파일: ros2_node.py, game_loop.py, __main__.py, 2 new test files ONLY

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: 전체 테스트 스위트
    Tool: Bash
    Steps:
      1. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v
      2. 전체 PASS, 0 FAIL 확인
    Expected Result: all passed, 0 failed
    Evidence: .sisyphus/evidence/task-6-full-suite.txt

  Scenario: Lint 클린
    Tool: Bash
    Steps:
      1. .venv/bin/ruff check src/ tests/
    Expected Result: All checks passed / 0 errors
    Evidence: .sisyphus/evidence/task-6-lint.txt

  Scenario: 변경 파일 범위 최종 확인
    Tool: Bash
    Steps:
      1. git diff --stat HEAD~5..HEAD (또는 작업 시작 시점 대비)
      2. 변경된 파일이 5개(수정 3 + 신규 2)만인지 확인
    Expected Result: ros2_node.py, game_loop.py, __main__.py, test_game_loop_real_mode.py, test_ros2_bridge_real.py
    Failure Indicators: 예상치 못한 파일 변경
    Evidence: .sisyphus/evidence/task-6-scope.txt
  ```

  **Commit**: NO (검증만)

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read `.sisyphus/plans/mode-real.md` end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search for forbidden patterns.

  **QA Scenarios:**
  ```
  Scenario: Must Have 검증
    Tool: Bash
    Steps:
      1. grep -c 'get_current_angles' src/exca_dance/core/game_loop.py (결과 >= 1)
      2. grep -c '/excavator/sensors/swing_angle' src/exca_dance/ros2_bridge/ros2_node.py (결과 >= 1)
      3. grep -c '/excavator/state/complete_status' src/exca_dance/ros2_bridge/ros2_node.py (결과 >= 1)
      4. grep -c 'mode=args.mode' src/exca_dance/__main__.py (결과 >= 1)
      5. ls .sisyphus/evidence/ (파일 존재 확인)
    Expected Result: 모든 grep >= 1, evidence 파일 존재
    Evidence: .sisyphus/evidence/f1-must-have.txt

  Scenario: Must NOT Have 검증
    Tool: Bash
    Steps:
      1. git diff --name-only HEAD~5..HEAD 실행
      2. 변경 파일이 허용 목록에만 있는지 확인 (ros2_node.py, game_loop.py, __main__.py, test_*.py)
      3. grep -r 'class InputSource\|class AngleConverter\|class HealthMonitor' src/ (결과 0)
    Expected Result: 허용 파일만 변경, 금지 패턴 0건
    Evidence: .sisyphus/evidence/f1-must-not-have.txt
  ```
  Output: `Must Have [N/N] | Must NOT Have [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run lint + tests + review changed files.

  **QA Scenarios:**
  ```
  Scenario: Lint + Tests
    Tool: Bash
    Steps:
      1. .venv/bin/ruff check src/ tests/
      2. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v
      3. 모든 테스트 PASS, ruff 0 errors 확인
    Expected Result: ruff 0 errors, all tests passed
    Evidence: .sisyphus/evidence/f2-quality.txt

  Scenario: Code smell 검사
    Tool: Bash
    Steps:
      1. grep -rn 'type: ignore\|# noqa\|as any' src/exca_dance/ros2_bridge/ros2_node.py src/exca_dance/core/game_loop.py (결과 0)
      2. grep -rn 'print(' src/exca_dance/ros2_bridge/ros2_node.py src/exca_dance/core/game_loop.py (결과 0)
    Expected Result: 0건
    Evidence: .sisyphus/evidence/f2-smells.txt
  ```
  Output: `Lint [PASS/FAIL] | Tests [N pass/N fail] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Execute EVERY QA scenario from Tasks 1-6.

  **QA Scenarios:**
  ```
  Scenario: 전체 QA 시나리오 재실행
    Tool: Bash
    Steps:
      1. Tasks 1-6의 모든 QA 시나리오 단계를 순서대로 실행
      2. 각 evidence 파일 존재 확인: ls .sisyphus/evidence/task-*.txt
      3. 전체 테스트: PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v
    Expected Result: 모든 시나리오 PASS, evidence 파일 존재, all tests passed
    Evidence: .sisyphus/evidence/f3-full-qa.txt
  ```
  Output: `Scenarios [N/N pass] | Integration [N/N] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  Verify each task's deliverable matches spec exactly.

  **QA Scenarios:**
  ```
  Scenario: 변경 범위 검증
    Tool: Bash
    Steps:
      1. git diff --stat HEAD~5..HEAD
      2. 변경 파일이 5개 이하인지 확인 (ros2_node.py, game_loop.py, __main__.py, test_game_loop_real_mode.py, test_ros2_bridge_real.py)
      3. git diff HEAD~5..HEAD -- src/exca_dance/ros2_bridge/interface.py (변경 없음 확인)
      4. git diff HEAD~5..HEAD -- src/exca_dance/core/scoring.py (변경 없음 확인)
      5. git diff HEAD~5..HEAD -- src/exca_dance/ui/ (변경 없음 확인)
    Expected Result: 허용 파일만 변경, 금지 파일 무변경
    Evidence: .sisyphus/evidence/f4-scope.txt
  ```
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`

---

## Commit Strategy

| Task | Commit Message | Files | Pre-commit |
|------|---------------|-------|------------|
| 1 | `test(core): add GameLoop real mode input tests (RED)` | `tests/test_game_loop_real_mode.py` | `ruff check` |
| 2 | `test(ros2): add real excavator topic subscription tests (RED)` | `tests/test_ros2_bridge_real.py` | `ruff check` |
| 3 | `feat(core): support real excavator input in GameLoop` | `src/exca_dance/core/game_loop.py` | `pytest + ruff` |
| 4 | `feat(ros2): subscribe to real excavator sensor topics` | `src/exca_dance/ros2_bridge/ros2_node.py` | `pytest + ruff` |
| 5 | `feat(main): pass --mode flag to GameLoop constructor` | `src/exca_dance/__main__.py` | `pytest + ruff` |

---

## Success Criteria

### Verification Commands
```bash
# 전체 테스트 (기존 124 + 신규)
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v
# Expected: All passed, 0 failed

# 기존 테스트만 (회귀 확인)
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_game_loop.py -v
# Expected: all passed (existing 12 tests unchanged)

# Lint
.venv/bin/ruff check src/ tests/
# Expected: 0 errors

# 변경 파일 확인
git diff --stat HEAD~5..HEAD
# Expected: ros2_node.py, game_loop.py, __main__.py, 2 new test files ONLY
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All existing 124 tests pass unchanged
- [ ] All new tests pass
- [ ] Lint clean
- [ ] Only 5 files changed (3 modified + 2 new)
