# Error Log — 에러 발견 및 수정 기록

> **목적**: 개발 중 발견된 에러와 수정 방법을 기록하여, AI 에이전트가 동일한 실수를 반복하지 않도록 한다. 새로운 에러를 발견할 때마다 이 문서에 추가한다.
>
> **사용법**: 에러를 수정한 후, 아래 템플릿에 따라 항목을 추가한다. 모듈별로 분류하며, 최신 항목이 상단에 온다.

---

## 에러 기록 템플릿

새 에러 발견 시 아래 형식으로 추가:

```markdown
### ERR-XXX: [에러 제목 — 한 줄 요약]

- **발견일**: YYYY-MM-DD
- **모듈**: `[모듈 경로]`
- **증상**: [사용자가 관찰하는 현상 — 에러 메시지, 잘못된 동작, 크래시 등]
- **원인**: [근본 원인 — 왜 이 에러가 발생했는가]
- **수정**: [구체적인 수정 방법 — 어떤 파일의 어떤 코드를 어떻게 바꿨는가]
- **관련 파일**: `[파일1]`, `[파일2]`
- **재발 방지**: [동일 에러를 방지하기 위한 규칙 또는 체크 항목]
```

---

## 에러 이력

### rendering/

#### ERR-001: ModernGL blend_func getter 런타임 크래시

- **발견일**: 프로젝트 초기
- **모듈**: `src/exca_dance/rendering/`
- **증상**: `old = ctx.blend_func`로 현재 블렌드 모드를 백업하려 할 때 `NotImplementedError` 발생. 프로그램 크래시.
- **원인**: ModernGL 5.x에서 `blend_func`는 **쓰기 전용** 속성이다. getter가 구현되지 않았음.
- **수정**: 읽기 대신 try/finally 패턴으로 원하는 블렌드 모드 설정 후 `DEFAULT_BLENDING`으로 복원.
  ```python
  # ❌ 크래시
  old = ctx.blend_func
  ctx.blend_func = (SRC_ALPHA, ONE)
  # ... render ...
  ctx.blend_func = old

  # ✅ 수정
  ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
  try:
      # ... render ...
  finally:
      ctx.blend_func = moderngl.DEFAULT_BLENDING
  ```
- **관련 파일**: `rendering/renderer.py`, `rendering/visual_cues.py`
- **재발 방지**: `ctx.blend_func`을 읽는 코드가 있으면 즉시 삭제. `skills/anti-patterns.md` 참조.

---

#### ERR-002: NumPy 행렬 → GL 유니폼 전치 누락

- **발견일**: 프로젝트 초기
- **모듈**: `src/exca_dance/rendering/`
- **증상**: 3D 모델이 화면에 전혀 보이지 않거나, 극심하게 왜곡되어 렌더링됨. 에러 메시지 없음.
- **원인**: NumPy는 row-major, OpenGL은 column-major. `.T` (전치)를 빠뜨리면 행렬 데이터가 뒤바뀜.
- **수정**: 모든 행렬 유니폼 전송에 `.astype("f4").T` 전치를 반드시 포함.
  ```python
  # ❌ 왜곡됨
  prog["mvp"].write(mvp.tobytes())

  # ✅ 수정
  prog["mvp"].write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
  ```
- **관련 파일**: `rendering/renderer.py`, `rendering/viewport_layout.py`, `rendering/excavator_model.py`
- **재발 방지**: `render_math.validate_gl_matrix()` 사용. 행렬 전송 시 항상 `.T` 확인. `skills/rendering-pipeline.md` §행렬 컨벤션 참조.

---

#### ERR-007: URDF 소스의 boom/stick/bucket 축 (0,1,0)을 그대로 사용하면 시상면이 아닌 측면 회전 발생

- **발견일**: 2026-03-27
- **모듈**: `src/exca_dance/rendering/urdf_kin.py`
- **증상**: boom 30° 회전 시 stick이 앞뒤(Y)가 아닌 좌우(X)로 이동. 굴착기 팔이 옆으로 흔들림.
- **원인**: 소스 URDF(`ix35e.urdf`)의 boom/stick/bucket 축이 `(0,1,0)` — Y축 회전 → XZ 평면(측면). 이 게임의 Z-up 좌표계에서 boom pitch는 YZ 평면(시상면)이어야 하므로 X축 회전 `(1,0,0)`이 올바름. 소스 URDF의 레퍼런스 렌더는 zero-pose 이미지라 축 방향이 결과에 영향을 주지 않아 오류가 드러나지 않았음.
- **수정**: boom_joint, stick_joint, bucket_joint의 axis를 `(1, 0, 0)`으로 설정.
  ```python
  # ❌ 소스 URDF 값 — 측면 회전
  URDFJoint("boom_joint", ..., axis=(0, 1, 0))

  # ✅ 수정 — 시상면 회전
  URDFJoint("boom_joint", ..., axis=(1, 0, 0))
  ```
- **관련 파일**: `rendering/urdf_kin.py`, `tests/test_urdf_kin.py`
- **재발 방지**: 소스 URDF 값을 그대로 복사하지 말고, 물리 동작 테스트(`test_boom_pitch_moves_stick_in_sagittal_plane`)로 반드시 검증. zero-pose 렌더만으로는 축 방향 오류를 잡을 수 없음.
---

### audio/

#### ERR-003: pygame.mixer.music.get_pos() 타이밍 드리프트

- **발견일**: 프로젝트 초기
- **모듈**: `src/exca_dance/audio/`
- **증상**: 5분 이상 플레이하면 비트 판정이 점점 어긋남. 곡 후반에 PERFECT를 맞춰도 MISS 판정.
- **원인**: `pygame.mixer.music.get_pos()`가 MP3/OGG 디코딩에서 **300초당 ~500ms 드리프트**. 리듬 게임에 치명적.
- **수정**: `time.perf_counter()` 기반 독립 타이밍 시스템으로 교체. `AudioSystem.get_position_ms()` 메서드에 캡슐화.
  ```python
  # ❌ 드리프트
  current_ms = pygame.mixer.music.get_pos()

  # ✅ 수정
  current_ms = audio.get_position_ms()  # perf_counter 기반
  ```
- **관련 파일**: `audio/audio_system.py`, `core/game_loop.py`
- **재발 방지**: `pygame.mixer.music.get_pos()` / `get_position()` 호출 즉시 삭제. `skills/audio-timing.md` 참조.

---

### ros2_bridge/

#### ERR-004: rclpy 직접 임포트로 이벤트 루프 충돌

- **발견일**: ROS2 연동 구현 시
- **모듈**: `src/exca_dance/ros2_bridge/`
- **증상**: `--mode real`로 실행 시 pygame 윈도우가 응답하지 않거나, rclpy 초기화 실패.
- **원인**: `rclpy`가 자체 이벤트 루프를 초기화하여 pygame의 이벤트 루프와 **충돌**. 동일 프로세스에서 공존 불가.
- **수정**: `multiprocessing.Process`로 ROS2 노드를 별도 프로세스에서 실행. `Queue` IPC로 통신.
  ```python
  # ❌ 충돌
  from exca_dance.ros2_bridge.ros2_node import ROS2ExcavatorNode
  node = ROS2ExcavatorNode()

  # ✅ 수정
  from exca_dance.ros2_bridge import create_bridge
  bridge = create_bridge(mode="real")  # 서브프로세스 자동 생성
  ```
- **관련 파일**: `ros2_bridge/__init__.py`, `ros2_bridge/ros2_node.py`, `ros2_bridge/interface.py`
- **재발 방지**: 메인 프로세스에서 `ros2_node.py` 직접 임포트 절대 금지. `skills/ros2-bridge.md` 참조.

---

### core/

#### ERR-005: ROS launch pytest 플러그인 충돌

- **발견일**: CI 환경 구성 시
- **모듈**: `tests/`
- **증상**: `pytest tests/ -v` 실행 시 ROS2 관련 에러 또는 테스트 수집 실패.
- **원인**: ROS2 환경에 설치된 `launch_pytest` 플러그인이 자동 로딩되어 pytest 동작을 방해.
- **수정**: 환경변수 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 추가.
  ```bash
  # ❌ 실패
  pytest tests/ -v

  # ✅ 수정
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v
  ```
- **관련 파일**: `tests/`, `pyproject.toml`
- **재발 방지**: 테스트 실행 시 항상 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 접두사 사용. `skills/testing.md` 참조.

---

#### ERR-006: ursina 임포트로 pygame 이벤트 루프 충돌

- **발견일**: 대안 렌더링 엔진 검토 시
- **모듈**: 프로젝트 전체
- **증상**: `import ursina` 시 pygame 이벤트 루프가 정상 작동하지 않음.
- **원인**: ursina가 내부적으로 자체 윈도우 시스템을 초기화하여 pygame과 충돌.
- **수정**: ursina 의존성 완전 제거. 모든 렌더링은 ModernGL로 직접 구현.
- **관련 파일**: 없음 (임포트 자체를 금지)
- **재발 방지**: `import ursina` 금지. `skills/anti-patterns.md` 참조.

---

## 에러 추가 가이드라인

1. **에러 번호**: `ERR-XXX` 형식으로 순차 부여 (현재 마지막: ERR-006)
2. **모듈별 분류**: 해당 모듈 섹션 하단에 추가 (최신이 위)
3. **구체적 코드 포함**: 잘못된 코드와 수정된 코드를 모두 기록
4. **재발 방지 필수**: 단순 수정이 아닌, 규칙/체크 항목까지 기록
5. **관련 스킬 문서 링크**: 해당 에러와 관련된 스킬 문서를 `재발 방지`에 명시
6. **새 모듈 섹션**: 기존에 없는 모듈이면 `### [모듈명]/` 헤더를 새로 추가
