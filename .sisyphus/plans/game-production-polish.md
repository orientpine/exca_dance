# Game Production Polish — 굴착기 댄스 게임 프로덕션 레벨 개선

## TL;DR

> **Quick Summary**: 굴착기 댄스 게임의 3D 렌더링 품질을 프로덕션 수준으로 끌어올리고(목표/현재 자세의 명확한 시각적 구분, 모든 뷰포트에서 양쪽 자세 표시), 게임 종료·점수·조작 등 핵심 게임 로직 버그 7건을 수정하며, UI 흐름을 완전하게 폴리시합니다.
> 
> **Deliverables**:
> - 모든 3개 뷰포트(3D, Top, Side)에서 목표 자세(ghost)와 현재 자세가 시각적으로 명확히 구분되는 렌더링
> - 3D 굴착기 박스가 링크 방향을 따라 올바르게 회전하는 수정된 모델
> - 뷰포트 테두리, 라벨, 참조 그리드가 포함된 아름다운 2D 뷰
> - 간단한 디렉셔널 라이팅으로 깊이감 있는 3D 모델
> - 노래 종료 시 자동으로 결과 화면 전환되는 정상 게임 플로우
> - Q키 일시정지 종료, ESC 일관성, RETRY 직접 재시작 등 완성된 UI 흐름
> - 정확한 점수 계산 및 프로그레스 바 표시
> - 비트 타임라인 시각화
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 4 waves
> **Critical Path**: T1 → T8 → T10 → T15/T16 → FINAL

> **NOTE**: 이 플랜은 기존 `fix-excavator-rendering.md`의 미완성 작업을 포함하고 확장합니다. 해당 플랜은 이 플랜으로 대체됩니다.

---

## Context

### Original Request
사용자가 3가지 영역의 개선을 요청:
1. **3D 굴착기 시각화 개선**: 2D 뷰에서 보기 불편한 3D 굴착기를 심미적으로 아름답게, 목표 자세와 현재 자세가 모든 화면에서 명확히 구분되도록
2. **게임 인터페이스 수정**: 게임이 종료되지 않음, Q로 종료 불가, 점수 계산이 임의적, 모든 문제 제시 후 미종료
3. **기타 게임플레이 기능 수정**: 프로덕션 레벨 품질

### Interview Summary
**Key Discussions**:
- 프로덕션 레벨 품질 요구 — 모든 기능이 완전하고 버그 없이 작동해야 함
- 기존 사이버펑크/네온 테마 유지하면서 시각 품질 향상

**Research Findings**:
- **렌더링 12건 이슈**: Ghost가 3D 뷰에서만 렌더링, 동일 색상에 30% 알파만 다름, 뷰포트 테두리/라벨 없음, 2D 뷰에 참조 그리드 없음, 박스가 링크 방향으로 회전하지 않음 (축 정렬된 채), 사이드 뷰 행렬에 _look_at 누락, 프로그레스 바 _draw_rect_2d 미구현, additive 셰이더 미사용, 라이팅 없음 등
- **게임 로직 7건 버그**: AudioSystem.is_playing()이 False를 반환하지 않아 게임 미종료 (CRITICAL), Q키 메인메뉴에서만 작동, 콤보 배율 1회 지연, 비트 판정이 프레임 시점 기준, 곡 길이 추정치 부정확, HitDetector 죽은 코드, _draw_rect_2d no-op
- **UI 8건 이슈**: 일시정지에서 메뉴 복귀 불가, RETRY가 곡 선택으로 이동, 리더보드 진입 후 결과 복귀 불가, 결과 화면 ESC 미지원, ScreenName.PAUSED 미사용 상수
- **기존 fix-excavator-rendering.md 플랜**: 8개 미완 태스크 — 박스 회전, 사이드 뷰 행렬, 행렬 컨벤션, 뷰포트 테두리 등

### Metis Review
**Identified Gaps** (addressed):
- 행렬 컨벤션(numpy row-major vs GL column-major) 검증 필요 → T1에 포함
- 무음 모드(음악 파일 없이 실행)에서의 종료 로직 → T2에 폴백 포함
- 셰이더 수정 시 기존 렌더링 파이프라인 호환성 → T15에 가드레일 설정
- FK kinematics.py는 테스트 커버리지 있으므로 수정 금지 → 가드레일에 명시
- 에디터 화면의 LEFT/RIGHT 키 충돌 → T12에 포함

---

## Work Objectives

### Core Objective
굴착기 댄스 게임을 프로덕션 수준으로 끌어올린다: 아름답고 읽기 쉬운 3D/2D 시각화, 완전하고 버그 없는 게임 플로우, 직관적인 UI 인터랙션.

### Concrete Deliverables
- `rendering/render_math.py` — 방향 벡터, 회전 행렬 유틸리티
- `rendering/excavator_model.py` — 링크 방향 따라 회전하는 박스 렌더링
- `rendering/visual_cues.py` — 모든 뷰포트에서 distinct color ghost 렌더링
- `rendering/viewport_layout.py` — 테두리, 라벨, 그리드가 포함된 뷰포트
- `rendering/renderer.py` — 디렉셔널 라이팅 셰이더
- `rendering/theme.py` — ghost 전용 색상 팔레트
- `audio/audio_system.py` — 곡 종료 감지 로직
- `core/game_loop.py` — 정상 종료 + 폴백 타이머
- `core/scoring.py` — 정확한 점수 계산
- `ui/gameplay_hud.py` — 동작하는 프로그레스 바 + 비트 타임라인
- `ui/screens/gameplay_screen.py` — Q키 종료, 전체 뷰포트 ghost
- `ui/screens/results.py` — ESC 지원, beatmap 참조 보존
- `ui/screens/leaderboard_screen.py` — 결과 복귀 플로우

### Definition of Done
- [ ] 모든 3개 뷰포트에서 목표/현재 자세가 색상으로 명확히 구분됨
- [ ] 3D 박스가 링크 방향을 따라 정확히 회전함
- [ ] 곡 재생 완료 후 3초 이내 결과 화면으로 자동 전환
- [ ] Q키로 일시정지 상태에서 메뉴 복귀 가능
- [ ] 점수가 정확한 공식으로 계산됨 (42개 기존 테스트 통과)
- [ ] 프로그레스 바가 정확한 시간으로 시각적으로 표시됨
- [ ] RETRY가 동일 곡으로 즉시 재시작
- [ ] `bun test` / `pytest` 전체 통과

### Must Have
- 모든 뷰포트에서 목표 자세와 현재 자세의 시각적 구분
- 게임 종료 후 결과 화면 자동 전환
- Q키 일시정지 종료
- 정확한 점수 계산
- 프로그레스 바 렌더링
- 2D 뷰의 참조 그리드

### Must NOT Have (Guardrails)
- `core/kinematics.py` 수정 금지 — FK 로직은 테스트 커버리지가 있으며, 렌더링 레이어에서 결과만 소비
- 새로운 외부 의존성 추가 금지 — pygame-ce, moderngl, PyOpenGL, numpy 범위 내에서 해결
- 비트맵 JSON 스키마 변경 금지 — 기존 sample1.json, sample2.json 호환 유지
- ROS2 bridge 코드 수정 금지 — 게임 핵심 로직과 분리된 모듈
- 에디터 기능 확장 금지 — 에디터의 기존 키 충돌만 수정, 새 기능 추가 안함
- 과도한 주석/JSDoc 추가 금지 — 코드 자체가 문서
- 기존 테마 색상 대폭 변경 금지 — 사이버펑크/네온 테마 유지, ghost 색상만 추가

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, 42 tests across 6 files)
- **Automated tests**: YES (Tests-after for new rendering math; existing tests must pass)
- **Framework**: pytest
- **Approach**: 새 render_math.py에 대한 단위 테스트 추가, 기존 42개 테스트 전체 통과 확인

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Rendering/Visual**: Use interactive_bash (tmux) — Launch game with `xvfb-run`, capture screenshot via capture_screenshot.py, visually verify
- **Game Logic**: Use Bash — Run pytest, verify specific test assertions
- **UI Flow**: Use interactive_bash (tmux) — Launch game, send keypresses, verify screen transitions
- **Audio**: Use Bash — Run with `SDL_AUDIODRIVER=dummy`, verify state transitions

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation, 7 tasks parallel):
├── T1: Rendering math utilities (render_math.py) [deep]
├── T2: Fix AudioSystem end-of-song + game termination [deep]
├── T3: Ghost distinct color scheme in theme.py [quick]
├── T4: Fix Q quit during pause + ESC consistency [quick]
├── T5: Fix scoring formula (angle multiplier + combo) [quick]
├── T6: Fix progress bar (_draw_rect_2d + song duration) [quick]
├── T7: Remove dead code + unused constants [quick]

Wave 2 (After Wave 1 — core visual + UI flow, 6 tasks):
├── T8: Fix excavator box rotation along link directions [deep] (depends: T1)
├── T9: Fix side view matrix + top view validation [unspecified-high] (depends: T1)
├── T10: Ghost rendering in ALL viewports [unspecified-high] (depends: T3, T8)
├── T11: Viewport borders + labels + panel separation [visual-engineering]
├── T12: Fix screen flow (RETRY, Results ESC, leaderboard, editor keys) [quick]

Wave 3 (After Wave 2 — polish + effects, 6 tasks):
├── T13: Grid/reference lines in 2D views [visual-engineering] (depends: T9, T11)
├── T14: Tighten ortho projection bounds [quick] (depends: T9, T13)
├── T15: Directional lighting in solid shader [unspecified-high] (depends: T8)
├── T16: Neon glow effects on ghost (additive shader) [visual-engineering] (depends: T10, T11)
├── T17: Beat timeline visualization [visual-engineering] (depends: T11)
├── T18: Ghost geometry optimization (VBO cache) [quick] (depends: T10)

Wave FINAL (After ALL — 4 parallel reviews, then user okay):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real manual QA (unspecified-high)
└── F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: T1 → T8 → T10 → T15/T16 → F1-F4 → user okay
Parallel Speedup: ~65% faster than sequential
Max Concurrent: 7 (Wave 1)
```

### Dependency Matrix

| Task | Blocked By | Blocks |
|------|-----------|--------|
| T1 | — | T8, T9 |
| T2 | — | — |
| T3 | — | T10, T16 |
| T4 | — | — |
| T5 | — | — |
| T6 | — | T17 |
| T7 | — | — |
| T8 | T1 | T10, T15 |
| T9 | T1 | T13, T14 |
| T10 | T3, T8 | T16, T18 |
| T11 | — | T13, T16, T17 |
| T12 | — | — |
| T13 | T9, T11 | T14 |
| T14 | T9, T13 | — |
| T15 | T8 | — |
| T16 | T10, T11 | — |
| T17 | T11 | — |
| T18 | T10 | — |

### Agent Dispatch Summary

- **Wave 1**: **7** — T1 → `deep`, T2 → `deep`, T3 → `quick`, T4 → `quick`, T5 → `quick`, T6 → `quick`, T7 → `quick`
- **Wave 2**: **5** — T8 → `deep`, T9 → `unspecified-high`, T10 → `unspecified-high`, T11 → `visual-engineering`, T12 → `quick`
- **Wave 3**: **6** — T13 → `visual-engineering`, T14 → `quick`, T15 → `unspecified-high`, T16 → `visual-engineering`, T17 → `visual-engineering`, T18 → `quick`
- **FINAL**: **4** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

> Implementation + Test = ONE Task. EVERY task has QA Scenarios.


### Wave 1 — Foundation (7 tasks, all independent)

- [x] 1. Rendering Math Utilities — 방향 벡터·회전 행렬 유틸리티 모듈 신규 생성

  **What to do**:
  - `src/exca_dance/rendering/render_math.py` 신규 생성:
    - `direction_vector(p1: np.ndarray, p2: np.ndarray) -> np.ndarray` — 두 3D 점 사이의 단위 방향 벡터 계산
    - `rotation_matrix_from_direction(direction: np.ndarray, up: np.ndarray = Z_UP) -> np.ndarray` — 방향 벡터를 따라 정렬하는 4x4 회전 행렬 (GL column-major 호환)
    - `make_oriented_box(p1, p2, width, height) -> np.ndarray` — 두 점 사이를 잇는 회전된 박스 정점 생성 (현재 `_make_box_verts`의 축 정렬 문제 해결)
    - `validate_matrix_convention(mat: np.ndarray) -> bool` — numpy 행렬이 GL column-major로 올바르게 전달되는지 검증 유틸
  - `tests/test_render_math.py` 신규 생성:
    - `test_direction_vector_unit_length` — 결과가 단위 벡터인지
    - `test_direction_vector_axis_aligned` — X/Y/Z 축 정렬 케이스
    - `test_rotation_identity_for_default_direction` — 기본 방향(Z-up)일 때 단위 행렬
    - `test_oriented_box_endpoints` — 박스 끝점이 p1, p2 근처인지
    - `test_oriented_box_face_count` — 36개 정점 (6면 × 2삼각형 × 3정점)
    - `test_matrix_convention_gl_compatible` — bytes() 전달 시 GL이 올바르게 해석
    - `test_degenerate_zero_length` — p1==p2일 때 NaN/crash 방지 (안전한 폴백)

  **Must NOT do**:
  - kinematics.py 수정 금지 — FK 출력을 소비만 할 것
  - 기존 ExcavatorModel API 변경 금지 — 이 태스크는 유틸만 생성

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 3D 수학(방향 벡터, 회전 행렬, GL 행렬 컨벤션)의 정확한 구현 필요
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: 3D 수학 로직이라 UI 스킬 불필요

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T2, T3, T4, T5, T6, T7)
  - **Blocks**: T8 (box rotation), T9 (side view matrix)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/excavator_model.py:_make_box_verts()` (line ~68-100) — 현재 축 정렬 박스 생성 로직. 이 함수가 `make_oriented_box`로 대체될 예정이므로 입력/출력 형식 참고
  - `src/exca_dance/core/kinematics.py:ExcavatorFK.compute()` — FK가 반환하는 joint_positions 딕셔너리 구조 (joint_name → np.ndarray 3D point). 이 출력이 render_math의 입력이 됨
  - `src/exca_dance/rendering/viewport_layout.py:_look_at()`, `_ortho()`, `_perspective()` — 기존 행렬 생성 패턴. numpy row-major → GL bytes 전달 방식 참고

  **API/Type References**:
  - `src/exca_dance/core/constants.py:LINK_WIDTHS` — 각 링크의 폭/높이 상수
  - `src/exca_dance/core/models.py:JointName` — SWING, BOOM, ARM, BUCKET enum

  **Test References**:
  - `tests/test_kinematics.py` — numpy 기반 3D 수학 테스트 패턴 참고 (assert_allclose 사용)

  **External References**:
  - OpenGL 행렬 컨벤션: column-major order, numpy는 row-major → `.T.tobytes()` 또는 `order='F'` 필요

  **Acceptance Criteria**:
  - [ ] `tests/test_render_math.py` 생성 완료, pytest 통과 (7+ tests, 0 failures)
  - [ ] `render_math.py` 모든 함수가 docstring 포함
  - [ ] 기존 42개 테스트 전체 통과: `pytest` → 0 failures

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Direction vector computation is correct
    Tool: Bash
    Preconditions: render_math.py and test file created
    Steps:
      1. Run: pytest tests/test_render_math.py -v
      2. Verify all 7+ tests pass
      3. Run: python -c "from exca_dance.rendering.render_math import direction_vector; import numpy as np; v = direction_vector(np.array([0,0,0]), np.array([1,0,0])); print(v); assert abs(np.linalg.norm(v) - 1.0) < 1e-6"
    Expected Result: All tests PASS; direction vector is [1, 0, 0] with unit length
    Failure Indicators: Any test failure; ImportError; norm != 1.0
    Evidence: .sisyphus/evidence/task-1-render-math-tests.txt

  Scenario: Degenerate case (zero-length link) handled safely
    Tool: Bash
    Preconditions: render_math.py created with degenerate handling
    Steps:
      1. Run: python -c "from exca_dance.rendering.render_math import make_oriented_box; import numpy as np; p = np.array([1.0, 2.0, 3.0]); verts = make_oriented_box(p, p, 0.5, 0.5); print('Shape:', verts.shape); assert not np.any(np.isnan(verts))"
    Expected Result: Returns valid vertices (no NaN), shape contains 36 rows
    Failure Indicators: NaN values; crash; ZeroDivisionError
    Evidence: .sisyphus/evidence/task-1-degenerate-case.txt
  ```

  **Commit**: YES (group 1)
  - Message: `feat(rendering): add render_math utilities for oriented box geometry`
  - Files: `src/exca_dance/rendering/render_math.py`, `tests/test_render_math.py`
  - Pre-commit: `pytest tests/test_render_math.py`

---

- [x] 2. Fix AudioSystem End-of-Song Detection + Game Termination

  **What to do**:
  - `src/exca_dance/audio/audio_system.py` 수정:
    - `is_playing()` 메서드에 `pygame.mixer.music.get_busy()` 체크 추가: `self._is_playing` 플래그가 True여도 실제 음악이 끝났으면 `_is_playing = False` 설정 후 False 반환
    - 무음 모드(silent mode) 폴백: `self._silent_mode`일 때는 곡 길이 기반으로 판단 (`self._song_duration_ms` 추적, `get_position_ms() >= _song_duration_ms`이면 종료)
    - `play()` 메서드에서 `_song_duration_ms` 설정 (pygame.mixer.Sound로 길이 확인하거나, beatmap의 마지막 이벤트 시간 + duration + 버퍼 사용)
  - `src/exca_dance/core/game_loop.py` 수정:
    - `_check_song_end()` 메서드에 그레이스 피리어드 폴백 추가: 모든 이벤트 소진 후 3초(3000ms) 경과 시 `is_playing()`와 무관하게 FINISHED 상태로 전환
    - `_all_events_consumed_at_ms` 타임스탬프 추적 필드 추가
  - `src/exca_dance/ui/screens/gameplay_screen.py` 수정:
    - `_on_song_end` 콜백에서 `game_loop.stop()` 호출하여 오디오 정리

  **Must NOT do**:
  - `pygame.mixer.music.set_endevent()` 사용 금지 — 이벤트 루프에 의존하면 타이밍이 불안정
  - `time.sleep()` 사용 금지 — 게임 루프 블로킹 불가

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 오디오 상태 머신과 게임 루프 타이밍의 정확한 통합 필요
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T3, T4, T5, T6, T7)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/exca_dance/audio/audio_system.py:play()` (line ~70-85) — _is_playing = True 설정 위치. 여기에 _song_duration_ms 설정 추가
  - `src/exca_dance/audio/audio_system.py:is_playing()` (line ~108-109) — 현재 `return self._is_playing and not self._is_paused`. get_busy() 체크 추가 위치
  - `src/exca_dance/audio/audio_system.py:stop()` (line ~88-95) — _is_playing = False 설정하는 유일한 위치. 참고용
  - `src/exca_dance/core/game_loop.py:_check_song_end()` (line ~190-197) — 현재 종료 조건: `not _pending_events and not audio.is_playing()`. 그레이스 피리어드 폴백 추가 위치

  **API/Type References**:
  - `src/exca_dance/core/game_loop.py:GameState` — WAITING, PLAYING, PAUSED, FINISHED enum
  - `src/exca_dance/core/models.py:BeatEvent` — time_ms, duration_ms 필드

  **External References**:
  - `pygame.mixer.music.get_busy()` — 음악이 실제로 재생 중인지 확인 (bool 반환)
  - 프로젝트 learnings: `pygame.mixer.music.get_pos()` 사용 금지 (드리프트 버그)

  **Acceptance Criteria**:
  - [ ] 곡 재생 후 모든 이벤트 소진 시 3초 이내 GameState.FINISHED 전환
  - [ ] `is_playing()`이 음악 종료 후 False 반환
  - [ ] 무음 모드에서도 게임 종료 정상 동작
  - [ ] 기존 42개 테스트 전체 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Game terminates after all events processed
    Tool: Bash
    Preconditions: Game can run with SDL_AUDIODRIVER=dummy
    Steps:
      1. Run: SDL_AUDIODRIVER=dummy DISPLAY=:99 timeout 60 python -c "
         from exca_dance.audio.audio_system import AudioSystem
         a = AudioSystem()
         a._is_playing = True
         a._silent_mode = True
         a._song_duration_ms = 1000
         a._start_time = __import__('time').perf_counter() - 2.0
         print('is_playing:', a.is_playing())
         assert a.is_playing() == False, 'Should detect song ended'
         print('PASS')"
    Expected Result: prints 'is_playing: False' and 'PASS'
    Failure Indicators: is_playing returns True; assertion error
    Evidence: .sisyphus/evidence/task-2-song-end-detection.txt

  Scenario: Grace period fallback works
    Tool: Bash
    Preconditions: game_loop.py updated with grace period
    Steps:
      1. Run: pytest tests/ -v -k 'not ros2'
      2. Verify all existing tests still pass
    Expected Result: 42+ tests PASS
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-2-existing-tests.txt
  ```

  **Commit**: YES (group 2)
  - Message: `fix(audio): detect end-of-song and trigger game termination`
  - Files: `src/exca_dance/audio/audio_system.py`, `src/exca_dance/core/game_loop.py`, `src/exca_dance/ui/screens/gameplay_screen.py`
  - Pre-commit: `pytest`

---

- [x] 3. Ghost Distinct Color Scheme — 목표 자세 전용 색상 팔레트

  **What to do**:
  - `src/exca_dance/rendering/theme.py` 수정:
    - `NeonTheme` 클래스에 ghost 전용 색상 상수 추가:
      - `GHOST_BASE = (0.2, 0.1, 0.4)` — 어두운 보라 (기존 dark gray 대체)
      - `GHOST_TURRET = (0.3, 0.15, 0.5)` — 보라 (기존 lighter gray 대체)
      - `GHOST_BOOM = (0.4, 0.2, 1.0)` — 밝은 보라-파랑 (기존 orange 대체)
      - `GHOST_ARM = (0.6, 0.3, 1.0)` — 라벤더 (기존 yellow 대체)
      - `GHOST_BUCKET = (0.8, 0.4, 1.0)` — 밝은 보라 (기존 cyan 대체)
    - `GHOST_JOINT_COLORS` 딕셔너리 추가 (JointName → color tuple 매핑)
    - `GHOST_ALPHA = 0.5` 상수 추가 (기존 0.3에서 상향 — 더 잘 보이도록)
    - `GHOST_OUTLINE_COLOR = (0.8, 0.4, 1.0, 0.8)` — ghost 외곽선용 밝은 보라
  - 기존 `JOINT_COLORS`는 변경하지 않음 (현재 자세 색상 유지)

  **Must NOT do**:
  - 기존 JOINT_COLORS 딕셔너리 수정 금지
  - 기존 NeonTheme의 다른 색상 상수 변경 금지

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: theme.py에 상수 몇 개 추가하는 단순 작업
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T2, T4, T5, T6, T7)
  - **Blocks**: T10 (ghost in all viewports), T16 (neon glow)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/theme.py:NeonTheme` — 기존 JOINT_COLORS 딕셔너리 구조 참고. 같은 패턴으로 GHOST_JOINT_COLORS 추가
  - `src/exca_dance/rendering/visual_cues.py:GHOST_ALPHA = 0.30` (line ~12) — 현재 ghost 알파 상수 위치. theme.py로 이동 권장

  **API/Type References**:
  - `src/exca_dance/core/models.py:JointName` — SWING, BOOM, ARM, BUCKET enum keys

  **WHY Each Reference Matters**:
  - JOINT_COLORS 구조를 동일하게 따라야 ExcavatorModel이 ghost 렌더링 시 색상 교체가 간단함
  - GHOST_ALPHA를 theme.py로 이동하면 visual_cues.py가 theme에서 모든 스타일 정보를 가져올 수 있음

  **Acceptance Criteria**:
  - [ ] `NeonTheme.GHOST_JOINT_COLORS` 딕셔너리가 4개 관절 모두 포함
  - [ ] `NeonTheme.GHOST_ALPHA` 가 0.5로 설정
  - [ ] 기존 `JOINT_COLORS` 값 변경 없음
  - [ ] `python -c "from exca_dance.rendering.theme import NeonTheme; print(NeonTheme.GHOST_JOINT_COLORS)"` 정상 출력
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Ghost colors are importable and distinct from current pose colors
    Tool: Bash
    Steps:
      1. Run: python -c "
         from exca_dance.rendering.theme import NeonTheme
         assert hasattr(NeonTheme, 'GHOST_JOINT_COLORS'), 'Missing GHOST_JOINT_COLORS'
         assert hasattr(NeonTheme, 'GHOST_ALPHA'), 'Missing GHOST_ALPHA'
         assert NeonTheme.GHOST_ALPHA >= 0.4, 'Alpha too low'
         for joint in ['SWING', 'BOOM', 'ARM', 'BUCKET']:
           gc = NeonTheme.GHOST_JOINT_COLORS[joint]
           cc = NeonTheme.JOINT_COLORS[joint]
           assert gc != cc, f'Ghost color same as current for {joint}'
         print('All ghost colors distinct. PASS')"
    Expected Result: Prints 'All ghost colors distinct. PASS'
    Failure Indicators: AssertionError; ImportError; missing keys
    Evidence: .sisyphus/evidence/task-3-ghost-colors.txt

  Scenario: Existing tests unaffected
    Tool: Bash
    Steps:
      1. Run: pytest tests/ -v -k 'not ros2'
    Expected Result: 42+ tests PASS, 0 failures
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-3-existing-tests.txt
  ```

  **Commit**: YES (group 3)
  - Message: `feat(theme): add distinct ghost color palette for target pose`
  - Files: `src/exca_dance/rendering/theme.py`
  - Pre-commit: `pytest`

---

- [x] 4. Fix Q Quit During Pause + ESC Consistency

  **What to do**:
  - `src/exca_dance/ui/screens/gameplay_screen.py` 수정:
    - `handle_event()`에 일시정지 상태에서 Q키 처리 추가: `game_loop.state == LoopState.PAUSED`이고 `event.key == pygame.K_q`일 때 `game_loop.stop()` 호출 후 `ScreenName.MAIN_MENU` 반환
    - 일시정지 오버레이 텍스트 업데이트: "ESC Resume | Q Main Menu" (기존 "Q Quit"을 더 명확하게)
  - `src/exca_dance/__main__.py` 수정:
    - Q키 핸들러를 확장: 현재 스크린이 `GAMEPLAY`이고 game_loop이 paused상태일 때도 Q키로 종료 허용 (또는 gameplay_screen의 handle_event에서 직접 처리하여 중복 회피)

  **Must NOT do**:
  - 플레이 중(paused 아닐 때) Q키로 종료되는 것 금지 — 일시정지 상태에서만
  - 다른 화면(Results, Settings 등)의 Q키 동작 변경 금지

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 조건분기 2-3개 추가하는 단순 작업
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `src/exca_dance/ui/screens/gameplay_screen.py:handle_event()` (line ~34-39) — 현재 이벤트 처리. F3 키만 직접 처리, 나머지는 game_loop으로 위임
  - `src/exca_dance/ui/screens/gameplay_screen.py:render()` (line ~95-100) — 일시정지 오버레이 텍스트 "ESC Resume | Q Quit" 위치
  - `src/exca_dance/core/game_loop.py:LoopState` — WAITING, PLAYING, PAUSED, FINISHED enum
  - `src/exca_dance/core/game_loop.py:handle_event()` (line ~127-144) — ESC로 일시정지/재개 처리
  - `src/exca_dance/__main__.py` (line ~116-119) — 현재 Q키 핸들러 (MAIN_MENU에서만 동작)

  **Acceptance Criteria**:
  - [ ] 일시정지 상태에서 Q키 누르면 메인 메뉴로 전환
  - [ ] 플레이 중(paused 아닐 때) Q키는 무시됨
  - [ ] 일시정지 오버레이에 "Q Main Menu" 표시
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Q key exits to main menu from paused state
    Tool: Bash
    Steps:
      1. Run: python -c "
         import pygame; pygame.init()
         from exca_dance.ui.screens.gameplay_screen import GameplayScreen
         # Verify Q key handling exists in handle_event by inspecting code
         import inspect
         src = inspect.getsource(GameplayScreen.handle_event)
         assert 'K_q' in src, 'Q key not handled in gameplay_screen'
         print('Q key handler found. PASS')"
    Expected Result: 'Q key handler found. PASS'
    Failure Indicators: assertion error; K_q not found in source
    Evidence: .sisyphus/evidence/task-4-q-quit-handler.txt

  Scenario: Pause overlay text updated
    Tool: Bash
    Steps:
      1. Run: grep -n 'Main Menu' src/exca_dance/ui/screens/gameplay_screen.py
    Expected Result: Line containing 'Q Main Menu' found
    Failure Indicators: No match; still says 'Q Quit'
    Evidence: .sisyphus/evidence/task-4-pause-text.txt
  ```

  **Commit**: YES (group 4, with T5)
  - Message: `fix(gameplay): wire Q-quit during pause and fix scoring formula`
  - Files: `src/exca_dance/ui/screens/gameplay_screen.py`, `src/exca_dance/__main__.py`
  - Pre-commit: `pytest`

---

- [x] 5. Fix Scoring Formula — 각도 배율 곡선 + 콤보 순서 조정

  **What to do**:
  - `src/exca_dance/core/scoring.py` 수정:
    - `angle_mult` 계산식 강화: `max(0.1, 1.0 - (avg_err / 20.0))` (기존: `max(0.5, 1.0 - (avg_err / 30.0))`)
      - 20도 이상 오차에서 최소 0.1x (기존 0.5x → 너무 관대했음)
      - 10도 오차에서 0.5x (기존 0.67x → 더 엄격한 차별화)
    - 콤보 배율 순서: `update_combo(judgment)` 호출을 `get_combo_multiplier()` 앞으로 이동
      - 이유: 현재 히트가 콤보에 포함된 후 배율이 적용되어야 직관적
  - `tests/test_scoring.py` 수정:
    - `test_angle_accuracy_scaling` 테스트 업데이트: 새 곡선에 맞게 (15도에서 0.25x, 0도에서 1.0x)
    - 콤보 순서 테스트 추가: 10번째 히트에서 2x 배율 적용 확인
    - `test_max_score_calculation` 업데이트: 새 공식에 맞는 최대 점수 재계산

  **Must NOT do**:
  - JUDGMENT_WINDOWS 변경 금지 (PERFECT 35ms, GREAT 70ms, GOOD 120ms 유지)
  - SCORE_VALUES 변경 금지 (300, 200, 100 유지)
  - COMBO_THRESHOLDS 변경 금지 (10, 25, 50 유지)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 수식 2줄 변경 + 테스트 업데이트
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `src/exca_dance/core/scoring.py:judge()` (line ~30-40) — 현재 angle_mult, combo_mult 계산 순서
  - `src/exca_dance/core/scoring.py:get_combo_multiplier()` — COMBO_THRESHOLDS 기반 배율 계산
  - `src/exca_dance/core/scoring.py:update_combo()` — 판정에 따른 콤보 증가/리셋
  - `src/exca_dance/core/constants.py:COMBO_THRESHOLDS` — {10: 2, 25: 3, 50: 4}
  - `tests/test_scoring.py` — 전체 10개 테스트 참고, 수정 필요한 테스트 식별

  **Acceptance Criteria**:
  - [ ] `angle_mult`가 20도 오차에서 0.1, 10도에서 0.5, 0도에서 1.0
  - [ ] 콤보 10번째 히트에서 2x 배율 적용 (이전: 11번째에서 적용)
  - [ ] `pytest tests/test_scoring.py` → 모든 테스트 PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Angle multiplier curve is stricter
    Tool: Bash
    Steps:
      1. Run: python -c "
         from exca_dance.core.scoring import ScoringEngine
         from exca_dance.core.models import Judgment
         s = ScoringEngine()
         # 0 degree error = 1.0x
         s.judge(Judgment.PERFECT, [0.0])
         print('Score at 0 err:', s.total_score)
         s2 = ScoringEngine()
         # 20 degree error = 0.1x (minimum)
         s2.judge(Judgment.PERFECT, [20.0])
         print('Score at 20 err:', s2.total_score)
         assert s.total_score > s2.total_score * 5, 'Curve not strict enough'
         print('PASS')"
    Expected Result: Score at 0 err >> Score at 20 err; PASS printed
    Failure Indicators: assertion error; scores too similar
    Evidence: .sisyphus/evidence/task-5-scoring-curve.txt

  Scenario: All scoring tests pass
    Tool: Bash
    Steps:
      1. Run: pytest tests/test_scoring.py -v
    Expected Result: 10+ tests PASS, 0 failures
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-5-scoring-tests.txt
  ```

  **Commit**: YES (group 4, with T4)
  - Message: `fix(gameplay): wire Q-quit during pause and fix scoring formula`
  - Files: `src/exca_dance/core/scoring.py`, `tests/test_scoring.py`
  - Pre-commit: `pytest tests/test_scoring.py`

---

- [x] 6. Fix Progress Bar Rendering + Song Duration

  **What to do**:
  - `src/exca_dance/ui/gameplay_hud.py` 수정:
    - `_draw_rect_2d()` 스텀 구현: ModernGL로 색상 사각형 렌더링
      - renderer.prog_solid를 사용하여 NDC 좌표계에서 2D 사각형 그리기
      - 또는 1x1 흰색 텍스처 + prog_tex로 색상 사각형 (프로그레스 바 배경 + 색상 채우기)
    - 프로그레스 바 스타일: 하단 전체 너비, 높이 8px, 배경 NeonTheme.PANEL_BG, 채우기 NeonTheme.NEON_BLUE
  - `src/exca_dance/ui/screens/gameplay_screen.py` 수정:
    - 곡 길이 계산 수정: `beatmap.events[-1].time_ms + beatmap.events[-1].duration_ms + 3000` (기존: `len(events) * 2000`)
    - 이벤트 없는 비트맵 폴백: `60000.0` 그대로 유지

  **Must NOT do**:
  - HUD의 다른 요소(score, combo, judgment flash) 변경 금지
  - prog_solid/prog_tex 셈이더 코드 수정 금지

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 스텀 구현 + 1줄 수정
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: T17 (beat timeline)
  - **Blocked By**: None

  **References**:
  - `src/exca_dance/ui/gameplay_hud.py:_draw_rect_2d()` (line ~170-175) — 현재 `pass` 스텀. x, y, w, h, color 파라미터 수신
  - `src/exca_dance/ui/gameplay_hud.py:_render_progress_bar()` (line ~155-168) — _draw_rect_2d 호출 위치 + NDC 좌표 계산 로직
  - `src/exca_dance/rendering/renderer.py:prog_solid` — MVP + 색상 셈이더, 2D에서는 MVP=identity로 사용 가능
  - `src/exca_dance/ui/screens/gameplay_screen.py:on_enter()` (line ~27) — `set_song_duration(len(events) * 2000.0)` 수정 위치

  **Acceptance Criteria**:
  - [ ] `_draw_rect_2d()`가 실제로 색상 사각형을 그림 (no-op 아님)
  - [ ] 곡 길이가 마지막 이벤트 기반으로 계산됨
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Progress bar rect rendering is implemented
    Tool: Bash
    Steps:
      1. Run: python -c "
         import inspect
         from exca_dance.ui.gameplay_hud import GameplayHUD
         src = inspect.getsource(GameplayHUD._draw_rect_2d)
         assert 'pass' not in src or len(src.strip().split('\n')) > 3, '_draw_rect_2d is still a stub'
         print('_draw_rect_2d implemented. PASS')"
    Expected Result: Prints 'PASS'
    Failure Indicators: assertion error — still a stub
    Evidence: .sisyphus/evidence/task-6-progress-bar.txt

  Scenario: Song duration calculated from events
    Tool: Bash
    Steps:
      1. Run: grep -n 'set_song_duration' src/exca_dance/ui/screens/gameplay_screen.py
    Expected Result: Line using events[-1].time_ms, NOT len(events) * 2000
    Failure Indicators: Still using len(events) * 2000
    Evidence: .sisyphus/evidence/task-6-song-duration.txt
  ```

  **Commit**: YES (group 6, with T7)
  - Message: `fix(hud): implement progress bar rendering and remove dead code`
  - Files: `src/exca_dance/ui/gameplay_hud.py`, `src/exca_dance/ui/screens/gameplay_screen.py`
  - Pre-commit: `pytest`

---

- [x] 7. Remove Dead Code + Unused Constants

  **What to do**:
  - `src/exca_dance/core/hit_detection.py` 수정:
    - `HitDetector` 클래스 전체 삭제 (죽은 코드 — GameLoop._check_beats()와 중복)
    - `JudgmentDisplay` 클래스는 유지 (실제 사용 중)
    - 파일명은 유지 (JudgmentDisplay 그대로 사용 중이므로)
  - `src/exca_dance/core/game_state.py` 수정:
    - `ScreenName.PAUSED = "paused"` 상수 삭제 (등록된 적 없는 미사용 상수)
  - 삭제된 코드의 임포트가 다른 파일에 있는지 확인 (lsp_find_references 사용)

  **Must NOT do**:
  - JudgmentDisplay 클래스 삭제 금지 (실제 사용 중)
  - 다른 ScreenName 상수 삭제 금지

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 클래스 1개 삭제 + 상수 1개 삭제
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `src/exca_dance/core/hit_detection.py:HitDetector` (line ~10-48) — 삭제 대상. GameLoop._check_beats()와 동일 로직 중복
  - `src/exca_dance/core/hit_detection.py:JudgmentDisplay` (line ~50+) — 유지 대상. 삭제 금지
  - `src/exca_dance/core/game_state.py:ScreenName` — PAUSED 상수 위치 확인
  - `src/exca_dance/core/game_loop.py:_check_beats()` — HitDetector와 중복되는 실제 사용 코드

  **Acceptance Criteria**:
  - [ ] HitDetector 클래스가 hit_detection.py에서 삭제됨
  - [ ] JudgmentDisplay는 그대로 유지
  - [ ] ScreenName.PAUSED 제거됨
  - [ ] 기존 42개 테스트 통과 (삭제된 코드를 참조하는 테스트 없음 확인)

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: HitDetector removed, JudgmentDisplay preserved
    Tool: Bash
    Steps:
      1. Run: python -c "
         from exca_dance.core.hit_detection import JudgmentDisplay
         print('JudgmentDisplay imported OK')
         try:
           from exca_dance.core.hit_detection import HitDetector
           print('FAIL: HitDetector still exists')
         except ImportError:
           print('HitDetector removed. PASS')"
    Expected Result: JudgmentDisplay imports; HitDetector raises ImportError
    Failure Indicators: HitDetector still importable
    Evidence: .sisyphus/evidence/task-7-dead-code.txt

  Scenario: ScreenName.PAUSED removed
    Tool: Bash
    Steps:
      1. Run: python -c "
         from exca_dance.core.game_state import ScreenName
         assert not hasattr(ScreenName, 'PAUSED'), 'PAUSED still exists'
         print('PAUSED removed. PASS')"
    Expected Result: 'PAUSED removed. PASS'
    Failure Indicators: PAUSED attribute still exists
    Evidence: .sisyphus/evidence/task-7-paused-removed.txt
  ```

  **Commit**: YES (group 6, with T6)
  - Message: `fix(hud): implement progress bar rendering and remove dead code`
  - Files: `src/exca_dance/core/hit_detection.py`, `src/exca_dance/core/game_state.py`
  - Pre-commit: `pytest`

---

### Wave 2 — Core Visual + UI Flow (5 tasks)

---

- [x] 8. Fix Excavator Box Rotation Along Link Directions

  **What to do**:
  - `src/exca_dance/rendering/excavator_model.py` 수정:
    - `_make_box_verts()` 리팩터링: `render_math.make_oriented_box(p1, p2, width, height)` 사용
    - 현재 패턴: midpoint = (p1+p2)/2에서 축 정렬 박스 생성 → 두 점 사이를 잇는 회전된 박스로 교체
    - `_update_geometry()` 메서드에서 FK joint_positions를 순회하며 각 링크별로 `make_oriented_box()` 호출
    - 각 링크의 색상은 기존 JOINT_COLORS 딕셔너리에서 가져오기 (변경 없음)
    - GL column-major 행렬 컨벤션 적용: 정점 변환 시 render_math의 회전 행렬 사용
  - 기존 `_make_box_verts` 시그니처는 유지하되 내부 구현만 변경 (API 호환성)

  **Must NOT do**:
  - kinematics.py 수정 금지
  - ExcavatorModel의 공개 API (update, render_3d, render_2d_top, render_2d_side) 시그니처 변경 금지
  - JOINT_COLORS 변경 금지

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 3D 기하학 변환의 정확성이 중요 — 잘못된 회전은 시각적 버그 유발
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2 내에서 T9, T11, T12와 병렬)
  - **Parallel Group**: Wave 2
  - **Blocks**: T10 (ghost in all viewports), T15 (directional lighting)
  - **Blocked By**: T1 (render_math.py)

  **References**:
  - `src/exca_dance/rendering/render_math.py` (T1에서 생성) — `make_oriented_box()`, `rotation_matrix_from_direction()` 사용
  - `src/exca_dance/rendering/excavator_model.py:_make_box_verts()` (line ~68-100) — 현재 축 정렬 박스 생성. 이 함수의 호출부와 반환값 형식 파악
  - `src/exca_dance/rendering/excavator_model.py:_update_geometry()` — FK 결과를 정점 데이터로 변환하는 메서드
  - `src/exca_dance/core/kinematics.py:ExcavatorFK.compute()` — 반환하는 joint_positions 구조 (READ ONLY)
  - `src/exca_dance/core/constants.py:LINK_WIDTHS` — 각 링크의 폭/높이

  **Acceptance Criteria**:
  - [ ] 박스가 링크 방향을 따라 회전됨 (축 정렬 아님)
  - [ ] 모든 4개 링크 (boom, arm, bucket, 기초)가 올바르게 렌더링
  - [ ] 기존 render_3d/render_2d_top/render_2d_side API 동작 유지
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Excavator model renders without errors
    Tool: Bash
    Preconditions: xvfb-run available, render_math.py from T1 exists
    Steps:
      1. Run: xvfb-run -a python -c "
         import os; os.environ['SDL_AUDIODRIVER'] = 'dummy'
         import pygame; pygame.init()
         screen = pygame.display.set_mode((800, 600), pygame.OPENGL | pygame.DOUBLEBUF)
         from exca_dance.rendering.renderer import GameRenderer
         from exca_dance.rendering.excavator_model import ExcavatorModel
         r = GameRenderer(800, 600)
         m = ExcavatorModel(r)
         m.update({'SWING': 45, 'BOOM': 30, 'ARM': -20, 'BUCKET': 10})
         import numpy as np
         mvp = np.eye(4, dtype='f4')
         m.render_3d(mvp)
         print('Render OK. PASS')"
    Expected Result: 'Render OK. PASS' without GL errors or crashes
    Failure Indicators: GL error; crash; NaN in geometry
    Evidence: .sisyphus/evidence/task-8-box-rotation.txt

  Scenario: Existing tests still pass
    Tool: Bash
    Steps:
      1. Run: pytest tests/ -v -k 'not ros2'
    Expected Result: 42+ tests PASS
    Evidence: .sisyphus/evidence/task-8-existing-tests.txt
  ```

  **Commit**: YES (group 8)
  - Message: `fix(rendering): rotate excavator boxes along link direction vectors`
  - Files: `src/exca_dance/rendering/excavator_model.py`
  - Pre-commit: `pytest`

---

- [x] 9. Fix Side View Matrix + Top View Validation

  **What to do**:
  - `src/exca_dance/rendering/viewport_layout.py` 수정:
    - `_mvp_side` 재계산: `_look_at()` 사용하여 XZ 평면 투영 (eye=(0,10,3), center=(0,0,3), up=(0,0,1))
    - `_mvp_top` 검증: 현재 `_ortho(-8,8,-6,6)` — XY 평면 투영이 맞는지 확인. 필요시 `_look_at(eye=(0,0,15), center=(0,0,0), up=(0,1,0))` 추가
    - 행렬 컨벤션 일관성 확인: 모든 MVP 행렬이 GL column-major로 전달되는지 검증 (render_math.validate_matrix_convention 사용)
  - `src/exca_dance/rendering/viewport.py` 수정:
    - 필요시 viewport 영역의 종횡비 조정 (2D 패널 영역이 정사각형이 아니면 왜곡 발생)

  **Must NOT do**:
  - main_3d 뷰포트 메트릭스 변경 금지 (3D 퍼스펙티브 뷰 유지)
  - kinematics.py 수정 금지

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 3D 행렬 수학 + 시각적 검증 필요
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2 내에서 T8, T11, T12와 병렬)
  - **Parallel Group**: Wave 2
  - **Blocks**: T13 (grid lines), T14 (ortho bounds)
  - **Blocked By**: T1 (render_math.py)

  **References**:
  - `src/exca_dance/rendering/viewport_layout.py:_build_matrices()` — 현재 MVP 행렬 생성 위치. _mvp_side에 _look_at 추가 필요
  - `src/exca_dance/rendering/viewport_layout.py:_look_at()` — 기존 look-at 구현 (이미 사용 중 for 3D view)
  - `src/exca_dance/rendering/viewport_layout.py:_ortho()` — 기존 직교 투영 구현
  - `src/exca_dance/rendering/viewport.py:ViewportManager` — 뷰포트 영역 정의 (top_2d, side_2d 각각 480x540)
  - `.sisyphus/plans/fix-excavator-rendering.md` Task 3 — 사이드 뷰 문제 분석 참고

  **Acceptance Criteria**:
  - [ ] 사이드 뷰가 XZ 평면을 올바르게 투영 (굴착기 측면에서 보는 시점)
  - [ ] 탑 뷰가 XY 평면을 올바르게 투영 (위에서 내려다보는 시점)
  - [ ] 두 뷰에서 굴착기 링크가 올바른 위치/방향으로 표시
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Side view shows XZ plane correctly
    Tool: Bash
    Preconditions: xvfb-run available
    Steps:
      1. Run: xvfb-run -a python capture_screenshot.py --output .sisyphus/evidence/task-9-side-view.png
      2. Verify screenshot saved successfully
    Expected Result: Screenshot captured, side view shows excavator from the side (XZ plane)
    Failure Indicators: Screenshot empty or GL error
    Evidence: .sisyphus/evidence/task-9-side-view.png

  Scenario: Top view shows XY plane correctly
    Tool: Bash
    Steps:
      1. Run: xvfb-run -a python capture_screenshot.py --output .sisyphus/evidence/task-9-top-view.png
    Expected Result: Screenshot shows excavator from above (XY plane)
    Evidence: .sisyphus/evidence/task-9-top-view.png
  ```

  **Commit**: YES (group 9)
  - Message: `fix(rendering): correct side view matrix with proper look-at transform`
  - Files: `src/exca_dance/rendering/viewport_layout.py`, `src/exca_dance/rendering/viewport.py`
  - Pre-commit: `pytest`

---

- [x] 10. Ghost Rendering in ALL 3 Viewports with Distinct Colors

  **What to do**:
  - `src/exca_dance/rendering/visual_cues.py` 수정:
    - `_ghost_model` 생성 시 ghost 전용 색상 적용: `NeonTheme.GHOST_JOINT_COLORS`를 ExcavatorModel에 전달
    - ExcavatorModel에 `joint_colors` 파라미터 추가 필요: 기본값 = NeonTheme.JOINT_COLORS, ghost는 GHOST_JOINT_COLORS 전달
    - `render_ghost()` 메서드 확장: 복수 MVP 행렬 수신 또는 3회 호출 지원
    - GHOST_ALPHA를 NeonTheme.GHOST_ALPHA에서 가져오기 (기존 로컬 상수 제거)
  - `src/exca_dance/rendering/excavator_model.py` 수정:
    - `__init__`에 `joint_colors: dict = None` 파라미터 추가 (기본값: NeonTheme.JOINT_COLORS)
    - `_update_geometry()`에서 self._joint_colors 사용
  - `src/exca_dance/ui/screens/gameplay_screen.py` 수정:
    - `render()` 메서드에서 ghost를 3개 뷰포트 모두에서 렌더링:
      ```python
      self._visual_cues.render_ghost(self._layout.mvp_3d)  # 기존
      self._visual_cues.render_ghost(self._layout.mvp_top)  # 추가
      self._visual_cues.render_ghost(self._layout.mvp_side) # 추가
      ```
    - 각 뷰포트 활성화 후 ghost 렌더링 (글리실에 클리핑 적용)

  **Must NOT do**:
  - 현재 자세 렌더링 색상/로직 변경 금지
  - ghost와 현재 자세가 동일한 색상을 사용하는 것 금지

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 여러 파일 걸친 렌더링 파이프라인 통합
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2 내에서 T8 완료 후)
  - **Parallel Group**: Wave 2 (T8 후 시작)
  - **Blocks**: T16 (neon glow), T18 (VBO cache)
  - **Blocked By**: T3 (ghost colors), T8 (box rotation)

  **References**:
  - `src/exca_dance/rendering/visual_cues.py:VisualCueRenderer` — 전체 클래스. _ghost_model 생성, render_ghost() 메서드
  - `src/exca_dance/rendering/visual_cues.py:GHOST_ALPHA = 0.30` (line ~12) — NeonTheme.GHOST_ALPHA로 교체
  - `src/exca_dance/rendering/excavator_model.py:__init__` — joint_colors 파라미터 추가 위치
  - `src/exca_dance/rendering/theme.py:NeonTheme.GHOST_JOINT_COLORS` (T3에서 생성)
  - `src/exca_dance/ui/screens/gameplay_screen.py:render()` (line ~75-90) — 뷰포트별 렌더링 순서. ghost render_ghost 호출 위치 (line ~83 만 main_3d)

  **Acceptance Criteria**:
  - [ ] 3D 뷰에서 ghost가 보라 계열 색상으로 렌더링
  - [ ] Top 2D 뷰에서 ghost가 보라 계열 색상으로 렌더링
  - [ ] Side 2D 뷰에서 ghost가 보라 계열 색상으로 렌더링
  - [ ] 현재 자세와 ghost가 시각적으로 명확히 구분됨
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Ghost renders in all 3 viewports
    Tool: Bash
    Preconditions: xvfb-run available, T3 and T8 complete
    Steps:
      1. Run: xvfb-run -a python capture_screenshot.py --output .sisyphus/evidence/task-10-all-viewports.png
      2. Verify screenshot shows ghost in all 3 panels
    Expected Result: Screenshot captured with visible ghost (purple/violet color) in 3D, Top, and Side views
    Failure Indicators: Ghost missing from any viewport; same color as current pose
    Evidence: .sisyphus/evidence/task-10-all-viewports.png

  Scenario: Ghost uses distinct colors from current pose
    Tool: Bash
    Steps:
      1. Run: python -c "
         from exca_dance.rendering.visual_cues import VisualCueRenderer
         from exca_dance.rendering.theme import NeonTheme
         import inspect
         src = inspect.getsource(VisualCueRenderer)
         assert 'GHOST_JOINT_COLORS' in src, 'Not using ghost-specific colors'
         assert 'GHOST_ALPHA' in src, 'Not using theme ghost alpha'
         print('Distinct ghost colors. PASS')"
    Expected Result: 'PASS'
    Failure Indicators: assertion errors
    Evidence: .sisyphus/evidence/task-10-ghost-colors.txt
  ```

  **Commit**: YES (group 10)
  - Message: `feat(rendering): render ghost pose in all 3 viewports with distinct colors`
  - Files: `src/exca_dance/rendering/visual_cues.py`, `src/exca_dance/rendering/excavator_model.py`, `src/exca_dance/ui/screens/gameplay_screen.py`
  - Pre-commit: `pytest`

---

- [x] 11. Viewport Borders + Labels + Panel Separation

  **What to do**:
  - `src/exca_dance/rendering/viewport_layout.py` 수정:
    - `render_viewport_decorations()` 메서드 추가:
      - 각 뷰포트 테두리: NeonTheme.BORDER 색상 (electric blue 60% alpha)으로 1px 라인
      - 뷰포트 라벨: "3D VIEW", "TOP", "SIDE" 텍스트 (각 패널 상단 좌측)
      - 패널 배경: NeonTheme.PANEL_BG로 반투명 구분 (이미 적용되어 있다면 검증만)
    - 라인 렌더링: GL_LINES 또는 thin quad로 테두리 그리기
    - 라벨 렌더링: 기존 GLTextRenderer 사용
  - `src/exca_dance/ui/screens/gameplay_screen.py`에서 `render_viewport_decorations()` 호출 추가

  **Must NOT do**:
  - 뷰포트 영역 크기/위치 변경 금지 (데코레이션만 추가)
  - 3D 뷰 레이블이 뷰포트 내부 3D 렌더링을 가리는 것 금지

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 시각적 UI 요소 추가 (테두리, 라벨, 패널 분리)
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: T13 (grid), T16 (neon glow), T17 (timeline)
  - **Blocked By**: None (viewport decorations are independent of model fixes)

  **References**:
  - `src/exca_dance/rendering/viewport_layout.py` — 전체 파일. 렌더링 파이프라인에 데코레이션 추가
  - `src/exca_dance/rendering/viewport.py:ViewportManager` — viewport 영역 좌표 (main_3d, top_2d, side_2d)
  - `src/exca_dance/rendering/theme.py:NeonTheme.BORDER` — 테두리 색상 상수 (정의됨 but 미사용)
  - `src/exca_dance/rendering/gl_text.py:GLTextRenderer` — 텍스트 렌더링 API
  - `src/exca_dance/rendering/renderer.py:prog_solid` — 라인/사각형 렌더링용 셈이더

  **Acceptance Criteria**:
  - [ ] 3개 뷰포트 모두 테두리 라인 표시
  - [ ] 각 뷰포트에 "3D VIEW", "TOP", "SIDE" 라벨 표시
  - [ ] 라벨이 렌더링 콘텐츠를 가리지 않음
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Viewport decorations render without errors
    Tool: Bash
    Steps:
      1. Run: xvfb-run -a python capture_screenshot.py --output .sisyphus/evidence/task-11-borders.png
    Expected Result: Screenshot shows borders around all 3 viewports and labels visible
    Failure Indicators: No borders; labels missing; GL errors
    Evidence: .sisyphus/evidence/task-11-borders.png

  Scenario: Decorations method exists and is called
    Tool: Bash
    Steps:
      1. Run: python -c "
         from exca_dance.rendering.viewport_layout import GameViewportLayout
         assert hasattr(GameViewportLayout, 'render_viewport_decorations')
         print('Method exists. PASS')"
      2. Run: grep -n 'render_viewport_decorations' src/exca_dance/ui/screens/gameplay_screen.py
    Expected Result: Method exists; called in gameplay_screen.py
    Evidence: .sisyphus/evidence/task-11-decorations-check.txt
  ```

  **Commit**: YES (group 11)
  - Message: `feat(rendering): add viewport borders labels and panel separation`
  - Files: `src/exca_dance/rendering/viewport_layout.py`, `src/exca_dance/ui/screens/gameplay_screen.py`
  - Pre-commit: `pytest`

---

- [x] 12. Fix Screen Flow — RETRY, Results ESC, Leaderboard Return, Editor Keys

  **What to do**:
  - `src/exca_dance/ui/screens/results.py` 수정:
    - `on_enter()`에서 `beatmap` 참조 저장 (기존 kwargs에서)
    - "RETRY" 선택 시 `(ScreenName.GAMEPLAY, {"beatmap": self._beatmap})` 반환 (동일 곡 직접 재시작)
    - ESC 키 처리 추가: `return ScreenName.MAIN_MENU`
  - `src/exca_dance/ui/screens/gameplay_screen.py` 수정:
    - `_on_song_end` 콜백에서 results로 beatmap도 전달: `{"scoring": scoring, "song_title": title, "beatmap": self._beatmap}`
  - `src/exca_dance/ui/screens/leaderboard_screen.py` 수정:
    - 이니셜 입력 후 확인 시: `view` 모드로 전환 대신 `ScreenName.MAIN_MENU` 반환 (또는 "MAIN MENU" 버튼 추가)
  - `src/exca_dance/editor/editor_screen.py` 수정:
    - LEFT/RIGHT 키 충돌 해결: 타임라인 스크러빙에는 handle_event에서 처리, 관절 조작에는 update에서 처리 — 관절 조작 키를 Shift+LEFT/RIGHT로 변경

  **Must NOT do**:
  - 다른 화면 전환 로직 변경 금지 (여기 명시된 것만 수정)
  - 화면 시각적 요소 변경 금지 (로직만 수정)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 각 파일에 조건분기 몇 개 추가
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `src/exca_dance/ui/screens/results.py:handle_event()` (line ~35-45) — "RETRY" 선택 시 SONG_SELECT 반환하는 위치. GAMEPLAY으로 변경
  - `src/exca_dance/ui/screens/results.py:on_enter()` — scoring, song_title 받는 위치. beatmap 추가 필요
  - `src/exca_dance/ui/screens/gameplay_screen.py:_on_song_end` 콜백 — results로 데이터 전달 위치
  - `src/exca_dance/ui/screens/leaderboard_screen.py:handle_event()` — 이니셜 입력 후 처리 로직
  - `src/exca_dance/editor/editor_screen.py:handle_event()` + `update()` — LEFT/RIGHT 중복 처리 위치

  **Acceptance Criteria**:
  - [ ] Results에서 RETRY 선택 시 동일 곡으로 GAMEPLAY 직접 전환
  - [ ] Results에서 ESC 시 MAIN_MENU 전환
  - [ ] 리더보드 이니셜 입력 후 메인 메뉴로 복귀 가능
  - [ ] 에디터에서 LEFT/RIGHT가 타임라인만, Shift+LEFT/RIGHT가 관절
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: RETRY passes beatmap to gameplay screen
    Tool: Bash
    Steps:
      1. Run: python -c "
         import inspect
         from exca_dance.ui.screens.results import ResultsScreen
         src = inspect.getsource(ResultsScreen.handle_event)
         assert 'GAMEPLAY' in src or 'gameplay' in src, 'RETRY does not go to GAMEPLAY'
         assert 'beatmap' in src, 'beatmap not passed in RETRY'
         print('RETRY flow correct. PASS')"
    Expected Result: 'PASS'
    Failure Indicators: RETRY still goes to SONG_SELECT; no beatmap
    Evidence: .sisyphus/evidence/task-12-retry-flow.txt

  Scenario: Results screen handles ESC
    Tool: Bash
    Steps:
      1. Run: python -c "
         import inspect
         from exca_dance.ui.screens.results import ResultsScreen
         src = inspect.getsource(ResultsScreen.handle_event)
         assert 'K_ESCAPE' in src or 'ESCAPE' in src, 'ESC not handled'
         print('ESC handled in Results. PASS')"
    Expected Result: 'PASS'
    Evidence: .sisyphus/evidence/task-12-results-esc.txt
  ```

  **Commit**: YES (group 12)
  - Message: `fix(ui): fix RETRY flow, Results ESC, leaderboard return, editor keys`
  - Files: `src/exca_dance/ui/screens/results.py`, `src/exca_dance/ui/screens/gameplay_screen.py`, `src/exca_dance/ui/screens/leaderboard_screen.py`, `src/exca_dance/editor/editor_screen.py`
  - Pre-commit: `pytest`

---

### Wave 3 — Polish + Effects (6 tasks)

---

- [x] 13. Grid/Reference Lines in 2D Orthographic Views

  **What to do**:
  - `src/exca_dance/rendering/viewport_layout.py` 수정:
    - `render_2d_grid()` 메서드 추가:
      - Top 뷰: XY 평면 그리드 (1m 간격 주요 라인, 0.5m 간격 보조 라인)
      - Side 뷰: XZ 평면 그리드 (1m 간격)
      - 그리드 색상: NeonTheme.DIM_TEXT (0.6, 0.6, 0.7) at 15% alpha
      - 원점 축: X축 빨간, Y축 초록, Z축 파랑 (20% alpha)
      - 지면 라인 (Z=0 또는 Y=0): NeonTheme.NEON_GREEN at 30% alpha
    - GL_LINES로 그리드 렌더링 (prog_solid 사용, MVP = 해당 뷰포트 MVP)
  - `src/exca_dance/ui/screens/gameplay_screen.py`에서 각 2D 뷰포트 렌더링 전에 `render_2d_grid()` 호출

  **Must NOT do**:
  - 그리드가 굴착기 모델을 시각적으로 가리는 것 금지 (낮은 알파)
  - 3D 뷰에 그리드 추가 금지 (2D 뷰만)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 시각적 참조 요소 디자인 + GL 라인 렌더링
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 3 내)
  - **Parallel Group**: Wave 3
  - **Blocks**: T14 (ortho bounds)
  - **Blocked By**: T9 (side view matrix), T11 (viewport decorations)

  **References**:
  - `src/exca_dance/rendering/viewport_layout.py` — MVP 행렬 + 뷰포트 렌더링 파이프라인
  - `src/exca_dance/rendering/renderer.py:prog_solid` — GL_LINES 렌더링용 셈이더
  - `src/exca_dance/rendering/theme.py:NeonTheme` — DIM_TEXT, NEON_GREEN 색상
  - `src/exca_dance/rendering/viewport.py:ViewportManager` — 뷰포트 영역 (그리드 범위 결정에 필요)

  **Acceptance Criteria**:
  - [ ] Top 뷰에 XY 그리드 라인 표시
  - [ ] Side 뷰에 XZ 그리드 라인 표시
  - [ ] 지면 라인이 초록으로 강조
  - [ ] 그리드가 굴착기보다 낮은 알파로 배경에 어우러짐
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Grid lines visible in 2D views
    Tool: Bash
    Steps:
      1. Run: xvfb-run -a python capture_screenshot.py --output .sisyphus/evidence/task-13-grid.png
    Expected Result: 2D panels show grid lines behind excavator model
    Failure Indicators: No grid visible; grid obscures model
    Evidence: .sisyphus/evidence/task-13-grid.png

  Scenario: Grid method exists and is callable
    Tool: Bash
    Steps:
      1. Run: python -c "
         from exca_dance.rendering.viewport_layout import GameViewportLayout
         assert hasattr(GameViewportLayout, 'render_2d_grid')
         print('Grid method exists. PASS')"
    Expected Result: 'PASS'
    Evidence: .sisyphus/evidence/task-13-grid-method.txt
  ```

  **Commit**: YES (group 13, with T14)
  - Message: `feat(rendering): add reference grid in 2D views and tighten ortho bounds`
  - Files: `src/exca_dance/rendering/viewport_layout.py`, `src/exca_dance/ui/screens/gameplay_screen.py`
  - Pre-commit: `pytest`

---

- [x] 14. Tighten Ortho Projection Bounds for 2D Views

  **What to do**:
  - `src/exca_dance/rendering/viewport.py` 또는 `viewport_layout.py` 수정:
    - Top 뷰 직교 범위 조정: `ortho(-8, 8, -6, 6)` → `ortho(-5, 7, -4, 4)` (굴착기 작업 반경 ~5.3m에 맞추어 중앙 배치)
    - Side 뷰 직교 범위 조정: `ortho(-2, 10, -1, 7)` → `ortho(-1, 7, -1, 7)` (더 대칭적, 굴착기 중앙 배치)
    - 뷰포트 종횡비에 맞게 aspect ratio 보정 (각 480x540 = 8:9 비율)
  - 조정 후 T13의 그리드가 올바르게 표시되는지 검증

  **Must NOT do**:
  - 3D 뷰 퍼스펙티브 설정 변경 금지

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 수치 4개 조정
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (T13 후)
  - **Parallel Group**: Wave 3 (T13 완료 후)
  - **Blocks**: None
  - **Blocked By**: T9 (side view matrix), T13 (grid)

  **References**:
  - `src/exca_dance/rendering/viewport_layout.py:_build_matrices()` — 현재 ortho 범위 설정 위치
  - `src/exca_dance/core/constants.py:LINK_LENGTHS` — boom 2.5m + arm 2.0m + bucket 0.8m = 최대 도달거리 ~5.3m
  - `src/exca_dance/rendering/viewport.py:ViewportManager` — 뷰포트 크기 480x540

  **Acceptance Criteria**:
  - [ ] Top 뷰에서 굴착기가 화면 중앙에 적절한 크기로 표시 (화면의 40-60% 차지)
  - [ ] Side 뷰에서 굴착기가 화면 중앙에 적절한 크기로 표시
  - [ ] 웠곡 없이 정상 비율 유지

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Excavator properly framed in 2D views
    Tool: Bash
    Steps:
      1. Run: xvfb-run -a python capture_screenshot.py --output .sisyphus/evidence/task-14-framing.png
    Expected Result: Excavator well-centered in both 2D panels, not too small or cropped
    Evidence: .sisyphus/evidence/task-14-framing.png
  ```

  **Commit**: YES (group 13, with T13)
  - Message: `feat(rendering): add reference grid in 2D views and tighten ortho bounds`
  - Files: `src/exca_dance/rendering/viewport_layout.py`, `src/exca_dance/rendering/viewport.py`
  - Pre-commit: `pytest`

---

- [x] 15. Directional Lighting in Solid Shader

  **What to do**:
  - `src/exca_dance/rendering/renderer.py` 수정:
    - `prog_solid` 버텍스 셈이더에 normal 속성 추가: `in vec3 in_normal`
    - 프래그먼트 셈이더에 간단한 디렉셔널 라이트 추가:
      ```glsl
      // 방향: 위에서 약간 앞쪽 (카메라 다운 라이트)
      vec3 light_dir = normalize(vec3(0.3, -0.5, 0.8));
      float diffuse = max(dot(normalize(v_normal), light_dir), 0.0);
      float ambient = 0.3;
      float lighting = ambient + (1.0 - ambient) * diffuse;
      fragColor = vec4(v_color.rgb * lighting, v_color.a * u_alpha);
      ```
    - 셈이더 변경은 기존 기능과 호환 (normal이 없으면 ambient만 적용 또는 fallback)
  - `src/exca_dance/rendering/excavator_model.py` 수정:
    - 정점 데이터에 face normal 추가 (각 면의 법선 벡터 계산)
    - VBO 레이아웃: position(3) + color(3) + normal(3) = 9 floats per vertex
    - VAO 업데이트: normal 속성 바인딩 추가

  **Must NOT do**:
  - prog_tex/prog_additive 셈이더 변경 금지
  - 복잡한 라이팅 모델 추가 금지 (specular, ambient occlusion 등) — 간단한 diffuse만
  - HUD 렌더링에 영향 금지 (HUD는 prog_tex 사용)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: GLSL 셈이더 수정 + 정점 레이아웃 변경의 정확성 필요
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 3 내)
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: T8 (box rotation — 정점 데이터 형식이 T8에서 결정됨)

  **References**:
  - `src/exca_dance/rendering/renderer.py:prog_solid` — 현재 셈이더 코드 (버텍스 + 프래그먼트)
  - `src/exca_dance/rendering/excavator_model.py:_update_geometry()` — VBO 데이터 생성 (현재: position + color = 6 floats)
  - `src/exca_dance/rendering/excavator_model.py:render_3d()` — VAO 바인딩 + 렌더 호출

  **Acceptance Criteria**:
  - [ ] 3D 뷰에서 굴착기 면이 음영 차이로 구분됨 (flat 색상 아님)
  - [ ] 2D 뷰에서도 라이팅 적용됨
  - [ ] HUD 렌더링에 영향 없음
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Lighting renders without GL errors
    Tool: Bash
    Steps:
      1. Run: xvfb-run -a python -c "
         import os; os.environ['SDL_AUDIODRIVER'] = 'dummy'
         import pygame; pygame.init()
         screen = pygame.display.set_mode((800, 600), pygame.OPENGL | pygame.DOUBLEBUF)
         from exca_dance.rendering.renderer import GameRenderer
         from exca_dance.rendering.excavator_model import ExcavatorModel
         r = GameRenderer(800, 600)
         m = ExcavatorModel(r)
         m.update({'SWING': 45, 'BOOM': 30, 'ARM': -20, 'BUCKET': 10})
         import numpy as np; mvp = np.eye(4, dtype='f4')
         m.render_3d(mvp)
         print('Lighting render OK. PASS')"
    Expected Result: 'PASS'
    Evidence: .sisyphus/evidence/task-15-lighting.txt
  ```

  **Commit**: YES (group 15)
  - Message: `feat(rendering): add directional lighting to solid shader`
  - Files: `src/exca_dance/rendering/renderer.py`, `src/exca_dance/rendering/excavator_model.py`
  - Pre-commit: `pytest`

---

- [x] 16. Neon Glow Effects on Ghost Using Additive Shader

  **What to do**:
  - `src/exca_dance/rendering/visual_cues.py` 수정:
    - ghost 렌더링 후 additive 블렌드 패스로 발광 효과 추가:
      - ghost 모델을 약간 확대한 버전으로 한번 더 렌더링 (scale 1.05x, 낮은 알파 0.15)
      - `renderer.prog_additive` 사용 (이미 컴파일되어 있지만 미사용)
      - additive blending: `glBlendFunc(GL_SRC_ALPHA, GL_ONE)` → 네온 발광 효과
    - 발광 색상: NeonTheme.GHOST_OUTLINE_COLOR (밝은 보라)
    - 펃드인 애니메이션과 동기화: ghost alpha가 높을 때 발광도 강해짐

  **Must NOT do**:
  - 현재 자세 모델에 발광 효과 추가 금지 (ghost에만)
  - prog_additive 셈이더 코드 변경 금지 (이미 정의된 대로 사용)
  - 과도한 발광으로 가독성 해치는 것 금지

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 시각적 효과 + 블렌드 모드 통합
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 3 내)
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: T10 (ghost in all viewports), T11 (viewport decorations)

  **References**:
  - `src/exca_dance/rendering/renderer.py:prog_additive` — 이미 컴파일된 additive 셈이더 (미사용)
  - `src/exca_dance/rendering/visual_cues.py:render_ghost()` — ghost 렌더링 로직 (여기에 glow 패스 추가)
  - `src/exca_dance/rendering/theme.py:NeonTheme.GHOST_OUTLINE_COLOR` (T3에서 생성)

  **Acceptance Criteria**:
  - [ ] ghost 주변에 보라 발광 효과 표시
  - [ ] 현재 자세에는 발광 효과 없음
  - [ ] 발광 알파가 ghost 페이드인과 동기화
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Additive shader is used for ghost glow
    Tool: Bash
    Steps:
      1. Run: python -c "
         import inspect
         from exca_dance.rendering.visual_cues import VisualCueRenderer
         src = inspect.getsource(VisualCueRenderer)
         assert 'prog_additive' in src or 'additive' in src, 'Additive shader not used'
         print('Additive glow effect found. PASS')"
    Expected Result: 'PASS'
    Evidence: .sisyphus/evidence/task-16-neon-glow.txt
  ```

  **Commit**: YES (group 16)
  - Message: `feat(rendering): add neon glow effects on ghost using additive shader`
  - Files: `src/exca_dance/rendering/visual_cues.py`
  - Pre-commit: `pytest`

---

- [x] 17. Beat Timeline Visualization

  **What to do**:
  - `src/exca_dance/rendering/visual_cues.py` 수정:
    - `render_timeline()` 스텀 구현:
      - 하단이나 상단에 스크롤링 비트 타임라인 표시
      - 현재 시간 위치에 수직 라인 (NeonTheme.NEON_PINK)
      - 다가오는 이벤트: 주황 또는 색상 점 표시 (3초 앞 이벤트까지 표시)
      - 지난 이벤트: 판정에 따른 색상 (PERFECT=금, GREAT=청록, GOOD=초록, MISS=빨간)
      - 뷰 너비: main_3d 뷰포트 하단 ~50px 영역
  - `src/exca_dance/ui/gameplay_hud.py` 또는 `gameplay_screen.py`에서 호출 위치 결정

  **Must NOT do**:
  - 타임라인이 다른 HUD 요소와 겹치는 것 금지
  - 복잡한 애니메이션 추가 금지 (간단한 스크롤 + 색상 점)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 시각적 UI 요소 디자인 + 타이밍 동기화
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 3 내)
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: T11 (viewport decorations)

  **References**:
  - `src/exca_dance/rendering/visual_cues.py:render_timeline()` (line ~65-69) — 현재 `pass` 스텀
  - `src/exca_dance/core/game_loop.py` — 현재 시간, _pending_events, _past_events 접근
  - `src/exca_dance/rendering/theme.py:NeonTheme` — 판정별 색상 (JUDGMENT_COLORS)
  - `src/exca_dance/ui/gameplay_hud.py:_render_progress_bar()` — 유사한 UI 요소 패턴 참고

  **Acceptance Criteria**:
  - [ ] render_timeline()이 실제로 비트 타임라인을 렌더링 (스텀 아님)
  - [ ] 현재 시간 표시기 표시
  - [ ] 다가오는 이벤트 점 표시
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Timeline is no longer a stub
    Tool: Bash
    Steps:
      1. Run: python -c "
         import inspect
         from exca_dance.rendering.visual_cues import VisualCueRenderer
         src = inspect.getsource(VisualCueRenderer.render_timeline)
         lines = [l.strip() for l in src.strip().split('\n') if l.strip() and not l.strip().startswith('#')]
         assert len(lines) > 3, 'render_timeline is still a stub'
         assert 'pass' not in src or len(lines) > 5, 'Likely still a stub'
         print('Timeline implemented. PASS')"
    Expected Result: 'PASS'
    Evidence: .sisyphus/evidence/task-17-timeline.txt
  ```

  **Commit**: YES (group 17)
  - Message: `feat(hud): implement scrolling beat timeline visualization`
  - Files: `src/exca_dance/rendering/visual_cues.py`
  - Pre-commit: `pytest`

---

- [x] 18. Ghost Geometry Optimization (VBO Cache)

  **What to do**:
  - `src/exca_dance/rendering/visual_cues.py` 수정:
    - `_prev_ghost_angles` 필드 추가하여 이전 프레임의 목표 각도 저장
    - `update()` 메서드에서 각도가 변경되었을 때만 `_ghost_model.update()` 호출
    - 비교 로직: `all(abs(new[k] - old[k]) < 0.01 for k in angles)` — 미세한 변화 무시
    - 효과: 같은 목표 각도가 유지되는 동안 VBO/VAO 재생성 생략

  **Must NOT do**:
  - 현재 자세 모델의 업데이트 로직 변경 금지 (현재 자세는 매 프레임 변함)
  - 캠싱 로직이 시각적 아티팩트를 유발하는 것 금지 (임계값 적절하게)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 비교 + 조건분기 단순 추가
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 3 내)
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: T10 (ghost in all viewports)

  **References**:
  - `src/exca_dance/rendering/visual_cues.py:update()` — 현재 매 프레임 _ghost_model.update() 호출 위치
  - `src/exca_dance/rendering/excavator_model.py:update()` — _update_geometry() 호출하여 VBO/VAO 재생성

  **Acceptance Criteria**:
  - [ ] 목표 각도 변경 없을 때 ghost geometry 재생성 생략됨
  - [ ] 각도 변경 시 정상적으로 업데이트됨
  - [ ] 기존 42개 테스트 통과

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Ghost caching logic exists
    Tool: Bash
    Steps:
      1. Run: python -c "
         import inspect
         from exca_dance.rendering.visual_cues import VisualCueRenderer
         src = inspect.getsource(VisualCueRenderer.update)
         assert '_prev_ghost_angles' in src or 'cached' in src or 'changed' in src, 'No caching logic found'
         print('Ghost caching implemented. PASS')"
    Expected Result: 'PASS'
    Evidence: .sisyphus/evidence/task-18-ghost-cache.txt
  ```

  **Commit**: YES (group 18)
  - Message: `perf(rendering): cache ghost VBO and only rebuild on angle change`
  - Files: `src/exca_dance/rendering/visual_cues.py`
  - Pre-commit: `pytest`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay".

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `pytest` + linter (ruff). Review all changed files for: unused imports, empty catches, debug prints, commented-out code. Check AI slop: excessive comments, over-abstraction, generic names. Verify no modifications to kinematics.py, no new dependencies in pyproject.toml, no beatmap schema changes.
  Output: `Tests [N pass/N fail] | Lint [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start game with `xvfb-run python -m exca_dance`. Use capture_screenshot.py to verify: (1) all 3 viewports show ghost and current pose, (2) ghost color is visually distinct, (3) viewport borders and labels visible, (4) grid lines in 2D views. Test gameplay flow: start song → play → verify game ends → results screen shows → RETRY works → Q quits from pause. Save all screenshots to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check kinematics.py is untouched. Check no new dependencies. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Group | Commit Message | Files | Pre-commit |
|-------|---------------|-------|------------|
| T1 | `feat(rendering): add render_math utilities for oriented box geometry` | rendering/render_math.py, tests/test_render_math.py | pytest tests/test_render_math.py |
| T2 | `fix(audio): detect end-of-song and trigger game termination` | audio/audio_system.py, core/game_loop.py | pytest |
| T3 | `feat(theme): add distinct ghost color palette for target pose` | rendering/theme.py | pytest |
| T4+T5 | `fix(gameplay): wire Q-quit during pause and fix scoring formula` | ui/screens/gameplay_screen.py, core/scoring.py | pytest tests/test_scoring.py |
| T6+T7 | `fix(hud): implement progress bar rendering and remove dead code` | ui/gameplay_hud.py, core/hit_detection.py, core/game_state.py | pytest |
| T8 | `fix(rendering): rotate excavator boxes along link direction vectors` | rendering/excavator_model.py | pytest |
| T9 | `fix(rendering): correct side view matrix with proper look-at transform` | rendering/viewport_layout.py, rendering/viewport.py | pytest |
| T10 | `feat(rendering): render ghost pose in all 3 viewports with distinct colors` | rendering/visual_cues.py, ui/screens/gameplay_screen.py | pytest |
| T11 | `feat(rendering): add viewport borders labels and panel separation` | rendering/viewport_layout.py | pytest |
| T12 | `fix(ui): fix RETRY flow, Results ESC, leaderboard return, editor keys` | ui/screens/results.py, ui/screens/leaderboard_screen.py, editor/editor_screen.py | pytest |
| T13+T14 | `feat(rendering): add reference grid in 2D views and tighten ortho bounds` | rendering/viewport_layout.py, rendering/viewport.py | pytest |
| T15 | `feat(rendering): add directional lighting to solid shader` | rendering/renderer.py, rendering/excavator_model.py | pytest |
| T16 | `feat(rendering): add neon glow effects on ghost using additive shader` | rendering/visual_cues.py | pytest |
| T17 | `feat(hud): implement scrolling beat timeline visualization` | rendering/visual_cues.py, ui/gameplay_hud.py | pytest |
| T18 | `perf(rendering): cache ghost VBO and only rebuild on angle change` | rendering/visual_cues.py | pytest |

---

## Success Criteria

### Verification Commands
```bash
pytest                                    # Expected: 42+ tests PASS, 0 failures
ruff check src/                           # Expected: 0 errors
python -c "from exca_dance.rendering.render_math import direction_vector, rotation_matrix_from_direction; print('OK')"  # Expected: OK
python -c "from exca_dance.core.scoring import ScoringEngine; s = ScoringEngine(); print(s.get_grade())"  # Expected: F (no hits)
```

### Final Checklist
- [ ] All "Must Have" present (6 items)
- [ ] All "Must NOT Have" absent (7 guardrails)
- [ ] All 42+ tests pass
- [ ] All 3 viewports show both ghost and current pose
- [ ] Game auto-terminates after song ends
- [ ] Q key works during pause
- [ ] Progress bar visually renders
- [ ] 2D views have borders, labels, grid
