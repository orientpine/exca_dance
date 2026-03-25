# Excavator Dance — Rhythm Game for Excavator Training

## TL;DR

> **Quick Summary**: 굴착기 4관절(swing/boom/arm/bucket)을 키보드로 조작하여 BGM 비트에 맞춰 목표 자세를 따라하는 리듬 게임. 가상 모드(즉시 플레이)와 실제 굴착기 모드(ROS2 연동)를 지원하며, 인게임 자세 편집기와 영구 리더보드를 포함.
>
> **Deliverables**:
> - Pygame + ModernGL 기반 리듬 게임 (네온/사이버펑크 UI)
> - 3D 메인뷰 + 2D 탑/사이드 보조뷰 굴착기 시각화
> - 커스텀 JSON 비트맵 + 인게임 자세 편집기
> - 리더보드 (이니셜 3자, JSON 영구 저장)
> - ROS2 브릿지 (추상 인터페이스 + 멀티프로세스)
> - 샘플 BGM 2곡 + 비트맵
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 6 waves
> **Critical Path**: T1→T2→T3→T9→T10→T11→T14→T15→T16 (rendering pipeline) + T4-T8 (parallel logic)

---

## Context

### Original Request
굴착기 4관절(swing, boom, arm, bucket)을 키보드로 조작하여 Just Dance Now 스타일의 리듬 게임을 만들고 싶다. 가상 굴착기 모드와 실제 굴착기 모드(ROS2 연동) 2가지. 목표 자세 편집 가능, 리더보드(이니셜 3자, 영구 저장), BGM 포함. Ubuntu에서 실행. 굴착기 조종을 즐겁게 배우는 교육 목적.

### Interview Summary
**Key Discussions**:
- **시각화**: 3D 메인뷰(기하학 도형 굴착기) + 2D 탑뷰/사이드뷰 소형 패널
- **게임 프레임워크**: Pygame(코어) + ModernGL(3D 렌더링). ~~Ursina~~ 불가 — Pygame과 게임루프 충돌 (Metis 검증)
- **키보드**: 사용자 커스텀 키바인딩 (4관절 × 양방향 = 8키)
- **BGM**: 기본 샘플 2곡(무료 라이선스 OGG) 포함 + 추가 로드 가능
- **비트맵**: 커스텀 JSON (관절별 목표 각도 + 타이밍)
- **스코어링**: Hybrid 모델 — 연속 관절 조작 + 비트 시점에 각도 근접도×타이밍 채점
- **리더보드**: 이니셜 3자, JSON 파일 영구 저장
- **자세 편집기**: 인게임 GUI (타임라인에 이벤트 배치, BGM 재생하며 편집)
- **UI**: 네온/사이버펑크 다크 테마
- **ROS2**: 멀티프로세스 아키텍처 (multiprocessing.Queue IPC)
- **테스트**: pytest 후행 (순수 로직 모듈)

**Research Findings**:
- `pygame.mixer.music.get_pos()` — MP3에서 300초당 ~500ms 드리프트. 사용 금지. `time.perf_counter()` 수동 시계 필수.
- Pygame + ModernGL 공존 검증됨 (moderngl-window 1.2k★). 단, `Surface.blit()` 사용 불가 — 모든 렌더링 OpenGL 경유.
- ROS2 rclpy `MultiThreadedExecutor` GIL 이슈 문서화됨 → 별도 프로세스 + IPC Queue 필수.
- sensor_msgs/JointState가 관절 각도 표준 메시지 타입.
- 굴착기 관절 범위: swing(±180°), boom(-30°~+60°), arm(-50°~+90°), bucket(0°~200°).
- OGG 포맷이 최소 드리프트. WAV는 SFX용.

### Metis Review
**Identified Gaps (addressed)**:
- **3D 엔진 선택 무효화**: Ursina는 Pygame과 공존 불가 → ModernGL로 확정
- **코어 게임플레이 미정의**: Hybrid 모델 확정 (연속 조작 + 비트 시점 채점)
- **시각적 큐 시스템 미정의**: 고스트 굴착기(반투명 목표 자세) + 관절별 각도 인디케이터
- **오디오 타이밍 버그**: `get_pos()` 금지, `perf_counter()` 수동 시계 확정
- **GL 텍스트 렌더링**: pygame.font → Surface → GL 텍스처 업로드 필요
- **카메라**: 고정 각도 (게임플레이 중 회전 불가)
- **일시정지**: 오디오 정지 + 타이머 누적 + 노트 프리즈
- **8키 조작**: 교육 대상이므로 유지 (초보자 단순화 모드는 v2)
- **오디오 오프셋 캘리브레이션**: v1 범위 외

---

## Work Objectives

### Core Objective
BGM 비트에 맞춰 굴착기 4관절을 조작하는 리듬 게임을 만든다. 교육 목적으로 굴착기 움직임이 직관적으로 보이며, 가상/실제 두 모드를 지원한다.

### Concrete Deliverables
- `src/exca_dance/` — Python 게임 패키지 (Pygame + ModernGL)
- `tests/` — pytest 테스트 스위트
- `assets/music/` — 샘플 BGM 2곡 (OGG)
- `assets/beatmaps/` — 샘플 비트맵 2개 (JSON)
- `assets/sounds/` — 효과음 (WAV)
- `data/leaderboard.json` — 영구 리더보드
- `data/settings.json` — 키바인딩 + 설정

### Definition of Done
- [ ] `python -m exca_dance` 실행 → 메인 메뉴 표시 (< 5초)
- [ ] 곡 선택 → 게임플레이 → 결과 → 리더보드 풀 플로우 완료
- [ ] 게임 종료 후 재시작 → 리더보드 데이터 유지
- [ ] 자세 편집기에서 비트맵 생성 → 게임에서 플레이 가능
- [ ] `pytest tests/ -v` → 모든 테스트 통과
- [ ] 60fps 이상 안정 프레임레이트

### Must Have
- 4관절 굴착기 3D 시각화 (기하학 도형, FK 기반)
- 2D 탑뷰/사이드뷰 보조 패널
- Hybrid 채점: 비트 시점 각도 근접도 × 타이밍 윈도우
- Perfect/Great/Good/Miss 판정 + 콤보 시스템
- 리더보드 (이니셜 3자, 영구 JSON)
- 인게임 자세 편집기 (타임라인 + 이벤트 배치 + 저장/로드)
- 사용자 키바인딩 설정
- BGM OGG 재생 + perf_counter 동기화
- ROS2 추상 인터페이스 + 멀티프로세스 브릿지
- 네온/사이버펑크 UI 테마

### Must NOT Have (Guardrails)
- ❌ `pygame.mixer.music.get_pos()` 사용 금지 — 드리프트 버그
- ❌ `pygame.Surface.blit()` 게임플레이 중 사용 금지 — OpenGL 경유만
- ❌ Ursina 사용 금지 — Pygame과 루프 충돌
- ❌ MP3 포맷 지원 금지 — OGG/WAV만
- ❌ 파티클 이펙트, 그림자, 반사, 포스트프로세싱 셰이더 금지
- ❌ 네트워크/멀티플레이어/온라인 리더보드 금지
- ❌ 데이터베이스 사용 금지 — JSON 파일만
- ❌ 자세 편집기 과잉 기능 금지 (undo/redo, copy/paste, 파형 표시, snap-to-grid 금지)
- ❌ 반응형 해상도 스케일링 금지 — 1920×1080 고정
- ❌ 튜토리얼 시스템 금지 — 도움말 오버레이만
- ❌ 난이도 레벨 금지 — 비트맵당 1개 난이도
- ❌ 3곡 이상 샘플 비트맵 금지 — 정확히 2곡
- ❌ `as any`, `@ts-ignore`, 빈 catch, console.log(프로덕션), 주석 처리된 코드 금지
- ❌ ROS2 브릿지 없이 virtual mode에서 rclpy import 금지

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO (greenfield)
- **Automated tests**: YES — Tests after implementation (pytest)
- **Framework**: pytest
- **Coverage targets**: 순수 로직 모듈 (scoring, kinematics, beatmap, leaderboard, keybinding)

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Game UI/Rendering**: Playwright 불가 → `interactive_bash` (tmux)에서 게임 실행 + 스크린샷
- **Pure Logic**: `pytest` 실행 결과
- **ROS2**: `ros2 topic echo` + `ros2 topic list`로 검증
- **Audio**: 게임 실행 후 로그 확인 (타이밍 드리프트 측정)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — sequential gate + scaffolding):
├── T1: Spike validation: Pygame+ModernGL+Audio coexistence [quick]
├── T2: Project scaffolding + pyproject.toml + dependencies [quick]
└── T3: Data models + type definitions + constants [quick]

Wave 2 (Pure Logic + Renderer — 7 parallel tasks):
├── T4: Forward kinematics engine + tests [deep]
├── T5: Scoring engine + judgment + combo + tests [deep]
├── T6: Beat map JSON parser + validation + tests [deep]
├── T7: Leaderboard manager + JSON persistence + tests [quick]
├── T8: Key binding system + persistence + tests [quick]
├── T9: ModernGL renderer + GL text utility + viewport mgr [unspecified-high]
└── T12: Audio system (OGG playback + perf_counter sync) [unspecified-high]

Wave 3 (3D Visualization + Theme — 5 tasks):
├── T10: 3D excavator geometric model + FK visualization [visual-engineering]
├── T11: Multi-viewport layout (3D main + 2D top/side panels) [visual-engineering]
├── T13: Neon/cyberpunk visual theme + glow effects [visual-engineering]
├── T26: ROS2 bridge abstract interface layer [quick]
└── T29: Sample content: 2 BGMs (OGG) + beat maps (JSON) [quick]

Wave 4 (Game Core — 4 tasks):
├── T14: Game loop (input → FK → render → audio sync) [deep]
├── T15: Visual cue system (ghost excavator + beat indicators) [visual-engineering]
├── T16: Hit detection + judgment display + scoring integration [deep]
└── T17: Gameplay HUD (score, combo, judgment flash, progress) [visual-engineering]

Wave 5 (UI Screens + Editor — 8 parallel tasks):
├── T18: Main menu screen [visual-engineering]
├── T19: Song selection screen [visual-engineering]
├── T20: Score results screen [visual-engineering]
├── T21: Leaderboard screen + 3-char initials entry [visual-engineering]
├── T22: Settings screen (key bindings, volume) [visual-engineering]
├── T23: Pause/resume + game state management [quick]
├── T24: Pose editor: timeline + event placement + angle editing [deep]
└── T25: Pose editor: playback preview + save/load [deep]

Wave 6 (ROS2 + Polish — 3 tasks):
├── T27: ROS2 node process + IPC queues [unspecified-high]
├── T28: Mode switching (virtual ↔ real) + graceful fallback [deep]
└── T30: Final integration + entry point + error handling [deep]

Wave FINAL (4 parallel reviews, then user okay):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real manual QA (unspecified-high)
└── F4: Scope fidelity check (deep)
→ Present results → Get explicit user okay
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| T1 | — | T2 | 1 |
| T2 | T1 | T3-T30 | 1 |
| T3 | T2 | T4-T8, T26 | 1 |
| T4 | T3 | T10, T14, T15 | 2 |
| T5 | T3 | T16, T17, T20 | 2 |
| T6 | T3 | T15, T16, T19, T24, T29 | 2 |
| T7 | T3 | T21 | 2 |
| T8 | T3 | T14, T22 | 2 |
| T9 | T2 | T10, T11, T13, T18-T25 | 2 |
| T10 | T4, T9 | T11, T15 | 3 |
| T11 | T9, T10 | T14 | 3 |
| T12 | T2 | T14, T24, T29 | 2 |
| T13 | T9 | T18-T22 | 3 |
| T14 | T4, T8, T11, T12 | T15, T16, T17, T23, T28 | 4 |
| T15 | T6, T10, T14 | T16 | 4 |
| T16 | T5, T6, T14, T15 | T17 | 4 |
| T17 | T5, T14, T16 | T18-T22 | 4 |
| T18 | T9, T13 | T30 | 5 |
| T19 | T6, T9, T13 | T30 | 5 |
| T20 | T5, T9, T13 | T30 | 5 |
| T21 | T7, T9, T13 | T30 | 5 |
| T22 | T8, T9, T13 | T30 | 5 |
| T23 | T14 | T30 | 5 |
| T24 | T6, T9, T12 | T25 | 5 |
| T25 | T24 | T30 | 5 |
| T26 | T3 | T27 | 3 |
| T27 | T26 | T28 | 6 |
| T28 | T14, T27 | T30 | 6 |
| T29 | T6, T12 | T30 | 3 |
| T30 | T18-T25, T28, T29 | F1-F4 | 6 |

Critical Path: T1→T2→T3→T9→T10→T11→T14→T15→T16→T17→T30→F1-F4
Parallel Speedup: ~65% faster than sequential
Max Concurrent: 8 (Wave 5)

### Agent Dispatch Summary

| Wave | Tasks | Categories |
|------|-------|-----------|
| 1 | 3 | T1→`quick`, T2→`quick`, T3→`quick` |
| 2 | 7 | T4→`deep`, T5→`deep`, T6→`deep`, T7→`quick`, T8→`quick`, T9→`unspecified-high`, T12→`unspecified-high` |
| 3 | 5 | T10→`visual-engineering`, T11→`visual-engineering`, T13→`visual-engineering`, T26→`quick`, T29→`quick` |
| 4 | 4 | T14→`deep`, T15→`visual-engineering`, T16→`deep`, T17→`visual-engineering` |
| 5 | 8 | T18-T22→`visual-engineering`, T23→`quick`, T24→`deep`, T25→`deep` |
| 6 | 3 | T27→`unspecified-high`, T28→`deep`, T30→`deep` |
| FINAL | 4 | F1→`oracle`, F2→`unspecified-high`, F3→`unspecified-high`, F4→`deep` |

---

## TODOs

---

### Wave 1: Foundation (Sequential Gate)

- [x] 1. **Spike Validation: Pygame + ModernGL + Audio Coexistence**

  **What to do**:
  - Create a 30-line Python script that validates all three libraries work together:
    - Initialize Pygame display with `OPENGL | DOUBLEBUF` flags
    - Create ModernGL context from Pygame's GL context
    - Render a simple colored rotating cube using ModernGL shaders (vertex + fragment)
    - Simultaneously play an OGG audio file via `pygame.mixer.music`
    - Print FPS to console for 5 seconds, then exit cleanly
  - If this fails, STOP — the entire architecture needs rethinking
  - Place the spike script at project root as `spike.py`

  **Must NOT do**:
  - Do NOT build project structure yet (that's T2)
  - Do NOT install unnecessary dependencies
  - Do NOT spend time on visual quality — this is a pure feasibility test

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1 (sequential first)
  - **Blocks**: T2, T3 (everything depends on this gate)
  - **Blocked By**: None

  **References**:
  - ModernGL docs: https://moderngl.readthedocs.io/en/latest/
  - moderngl-window pygame backend: demonstrates Pygame+ModernGL integration pattern
  - Pygame mixer docs: https://www.pygame.org/docs/ref/mixer.html

  **Acceptance Criteria**:
  - [ ] `python spike.py` runs without error for 5+ seconds
  - [ ] Console shows FPS ≥ 55
  - [ ] Audio is audible (OGG plays)
  - [ ] GL rendered cube visible in window

  **QA Scenarios:**
  ```
  Scenario: Spike runs successfully
    Tool: Bash
    Preconditions: pygame, moderngl, PyOpenGL installed via pip
    Steps:
      1. pip install pygame moderngl PyOpenGL
      2. Download or create a short OGG file for testing (generate 1s sine wave via python)
      3. python spike.py (with DISPLAY=:0 or virtual display via xvfb-run)
      4. Capture stdout for FPS readings
    Expected Result: Exit code 0, FPS lines show values ≥ 55, no GL errors in output
    Failure Indicators: ImportError, GL context creation failure, audio device error
    Evidence: .sisyphus/evidence/task-1-spike-success.txt

  Scenario: Spike fails gracefully on missing audio device
    Tool: Bash
    Preconditions: Same as above but potentially headless
    Steps:
      1. Run spike.py with SDL_AUDIODRIVER=dummy if no audio device
      2. Check that GL rendering still works even if audio fails
    Expected Result: Script prints warning about audio but doesn't crash. GL renders.
    Evidence: .sisyphus/evidence/task-1-spike-no-audio.txt
  ```

  **Commit**: YES
  - Message: `spike: validate Pygame+ModernGL+audio coexistence`
  - Files: `spike.py`
  - Pre-commit: `python spike.py`

---

- [x] 2. **Project Scaffolding + Dependencies**

  **What to do**:
  - Create project directory structure:
    ```
    exca_dance/
    ├── pyproject.toml          # Build config, deps, entry points
    ├── README.md               # Basic usage instructions
    ├── spike.py                # (from T1)
    ├── src/
    │   └── exca_dance/
    │       ├── __init__.py
    │       ├── __main__.py      # Entry point stub
    │       ├── core/             # Game logic (scoring, FK, beatmap)
    │       ├── rendering/        # ModernGL renderer, GL text, viewport
    │       ├── ui/               # Screen classes (menu, gameplay, etc.)
    │       ├── editor/           # Pose editor
    │       ├── audio/            # Audio system
    │       ├── ros2_bridge/      # ROS2 interface (lazy import)
    │       └── utils/            # Shared utilities
    ├── tests/
    │   ├── __init__.py
    │   ├── conftest.py          # Shared fixtures
    │   └── (test files)
    ├── assets/
    │   ├── music/               # OGG files
    │   ├── beatmaps/            # JSON beat maps
    │   ├── sounds/              # WAV SFX
    │   └── fonts/               # TTF fonts for GL text
    └── data/                    # Runtime data (leaderboard, settings)
    ```
  - `pyproject.toml` with dependencies:
    - `pygame-ce>=2.4` (community edition, better maintained)
    - `moderngl>=5.10`
    - `PyOpenGL>=3.1`
    - `numpy` (for matrix math in FK)
    - Dev deps: `pytest`, `ruff`
    - Optional deps group `[ros2]`: `rclpy`, `sensor_msgs`
  - `__main__.py` stub that prints "Exca Dance starting..." and exits
  - Include a free TTF font (e.g., Orbitron from Google Fonts — fits cyberpunk theme)

  **Must NOT do**:
  - Do NOT implement any game logic
  - Do NOT set up CI/CD
  - Do NOT add unnecessary deps (no flask, no sqlalchemy, etc.)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (follows T1)
  - **Parallel Group**: Wave 1 (sequential)
  - **Blocks**: T3-T30
  - **Blocked By**: T1

  **References**:
  - Python packaging: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
  - pygame-ce: https://pypi.org/project/pygame-ce/
  - Orbitron font: https://fonts.google.com/specimen/Orbitron

  **Acceptance Criteria**:
  - [ ] `pip install -e ".[dev]"` succeeds without error
  - [ ] `python -m exca_dance` prints startup message and exits
  - [ ] All directories in structure exist
  - [ ] `pytest --collect-only` runs without error (empty collection OK)

  **QA Scenarios:**
  ```
  Scenario: Clean install and run
    Tool: Bash
    Preconditions: Python 3.10+ available
    Steps:
      1. cd /home/cha/Documents/exca_dance
      2. pip install -e ".[dev]"
      3. python -m exca_dance
      4. pytest --collect-only
    Expected Result: pip exits 0, python prints "Exca Dance starting...", pytest shows 0 items collected
    Failure Indicators: pip dependency resolution failure, ModuleNotFoundError
    Evidence: .sisyphus/evidence/task-2-install-success.txt
  ```

  **Commit**: YES (groups with T3)
  - Message: `init: project structure, dependencies, data models`
  - Files: `pyproject.toml, src/exca_dance/**, tests/**, assets/**, data/`
  - Pre-commit: `pip install -e ".[dev]"`

---

- [x] 3. **Data Models + Type Definitions + Constants**

  **What to do**:
  - Create `src/exca_dance/core/models.py` with dataclasses/TypedDicts:
    - `JointName` enum: `SWING`, `BOOM`, `ARM`, `BUCKET`
    - `JointState` dataclass: `{name: JointName, angle: float, velocity: float}`
    - `ExcavatorState` dataclass: `{joints: dict[JointName, JointState], timestamp: float}`
    - `BeatEvent` dataclass: `{time_ms: int, target_angles: dict[JointName, float], duration_ms: int}`
    - `BeatMap` dataclass: `{title: str, artist: str, bpm: float, offset_ms: int, audio_file: str, events: list[BeatEvent]}`
    - `Judgment` enum: `PERFECT`, `GREAT`, `GOOD`, `MISS`
    - `HitResult` dataclass: `{judgment: Judgment, score: int, angle_error: float, timing_error_ms: float}`
    - `LeaderboardEntry` dataclass: `{initials: str, score: int, song_title: str, timestamp: str}`
    - `KeyBinding` dataclass: `{joint: JointName, positive_key: int, negative_key: int}`
  - Create `src/exca_dance/core/constants.py`:
    - `JOINT_LIMITS`: dict mapping JointName to (min_deg, max_deg) — swing(±180), boom(-30,+60), arm(-50,+90), bucket(0,200)
    - `JUDGMENT_WINDOWS`: `{PERFECT: 35, GREAT: 70, GOOD: 120}` (ms)
    - `SCORE_VALUES`: `{PERFECT: 300, GREAT: 200, GOOD: 100, MISS: 0}`
    - `COMBO_THRESHOLDS`: `{10: 2, 25: 3, 50: 4}` (combo→multiplier)
    - `TARGET_FPS`: 60
    - `SCREEN_WIDTH`: 1920, `SCREEN_HEIGHT`: 1080
    - `JOINT_ANGULAR_VELOCITY`: degrees per second when key held
    - `DEFAULT_KEY_BINDINGS`: default 8-key mapping
  - Create `src/exca_dance/core/__init__.py` exporting all models

  **Must NOT do**:
  - Do NOT implement any logic (just data structures)
  - Do NOT add rendering or game loop code

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (follows T2, blocks T4-T8)
  - **Parallel Group**: Wave 1 (sequential)
  - **Blocks**: T4, T5, T6, T7, T8, T26
  - **Blocked By**: T2

  **References**:
  - Python dataclasses: https://docs.python.org/3/library/dataclasses.html
  - Excavator joint ranges from research: swing(±180°), boom(-30°~+60°), arm(-50°~+90°), bucket(0°~200°)
  - Scoring windows from osu!mania research: adapted to ±35/70/120ms

  **Acceptance Criteria**:
  - [ ] `python -c "from exca_dance.core.models import *; print(JointName.SWING)"` works
  - [ ] `python -c "from exca_dance.core.constants import *; print(JOINT_LIMITS)"` works
  - [ ] All dataclasses are immutable (frozen=True) where appropriate
  - [ ] Type hints on all fields

  **QA Scenarios:**
  ```
  Scenario: Import and instantiate all models
    Tool: Bash
    Preconditions: T2 installed
    Steps:
      1. python -c "from exca_dance.core.models import *; state = ExcavatorState(joints={}, timestamp=0.0); print(state)"
      2. python -c "from exca_dance.core.models import BeatEvent, JointName; e = BeatEvent(time_ms=1000, target_angles={JointName.BOOM: 45.0}, duration_ms=500); print(e)"
      3. python -c "from exca_dance.core.constants import JOINT_LIMITS, JointName; assert JointName.SWING in JOINT_LIMITS"
    Expected Result: All 3 commands exit 0, print valid repr strings
    Evidence: .sisyphus/evidence/task-3-models-import.txt
  ```

  **Commit**: YES (groups with T2)
  - Message: `init: project structure, dependencies, data models`
  - Files: `src/exca_dance/core/models.py, src/exca_dance/core/constants.py, src/exca_dance/core/__init__.py`
  - Pre-commit: `python -c "from exca_dance.core.models import *"`

### Wave 2: Core Modules + Renderer (7 Parallel Tasks)

- [x] 4. **Forward Kinematics Engine + Tests**

  **What to do**:
  - Create `src/exca_dance/core/kinematics.py`:
    - `ExcavatorFK` class with configurable link lengths (boom_L, arm_L, bucket_L in meters)
    - `forward_kinematics(joints: dict[JointName, float]) -> dict[str, tuple[float,float,float]]`
      - Input: joint angles in degrees
      - Output: 3D positions for each joint pivot + bucket tip in world frame
      - Apply DH-like chain: base(0,0,0) -> swing(yaw) -> boom_pivot -> arm_pivot -> bucket_tip
      - swing rotates around Y-axis, boom/arm/bucket rotate around Z-axis (side view plane)
    - `get_joint_positions_2d_side(joints) -> list[tuple[float,float]]` — side view projection (ignore swing)
    - `get_joint_positions_2d_top(joints) -> list[tuple[float,float]]` — top view projection (swing + horizontal reach)
    - Clamp all angles to JOINT_LIMITS from constants
  - Create `tests/test_kinematics.py` (write AFTER implementation):
    - Test zero angles → known positions
    - Test 90° boom → vertical arm
    - Test swing rotation → correct 3D rotation
    - Test angle clamping at limits
    - Test link length configuration

  **Must NOT do**:
  - Do NOT add rendering code
  - Do NOT import pygame or moderngl

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T5, T6, T7, T8, T9, T12)
  - **Blocks**: T10, T14, T15
  - **Blocked By**: T3

  **References**:
  - Excavator joint ranges: `src/exca_dance/core/constants.py` — JOINT_LIMITS
  - DH parameters for excavator: swing(yaw, Y-axis), boom/arm/bucket(pitch, Z-axis)
  - numpy for rotation matrices: `np.array([[cos, -sin], [sin, cos]])`

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_kinematics.py -v` → all pass (≥5 tests)
  - [ ] Zero angles → all joints collinear along X-axis
  - [ ] Angle clamping respects JOINT_LIMITS exactly

  **QA Scenarios:**
  ```
  Scenario: FK computes correct positions for known angles
    Tool: Bash
    Steps:
      1. python -c "
         from exca_dance.core.kinematics import ExcavatorFK
         from exca_dance.core.models import JointName
         fk = ExcavatorFK(boom_length=2.5, arm_length=2.0, bucket_length=0.8)
         pos = fk.forward_kinematics({JointName.SWING: 0, JointName.BOOM: 0, JointName.ARM: 0, JointName.BUCKET: 0})
         print(pos)
         assert abs(pos['bucket_tip'][0] - 5.3) < 0.01  # total reach = 2.5+2.0+0.8
         "
    Expected Result: Exit 0, bucket_tip x ≈ 5.3, y ≈ 0
    Evidence: .sisyphus/evidence/task-4-fk-positions.txt

  Scenario: Angles clamped to limits
    Tool: Bash
    Steps:
      1. python -c "
         from exca_dance.core.kinematics import ExcavatorFK
         from exca_dance.core.models import JointName
         fk = ExcavatorFK()
         pos = fk.forward_kinematics({JointName.BOOM: 999})  # way over limit
         # Should clamp to max boom angle (60°)
         print('Clamped successfully')
         "
    Expected Result: No error, angle clamped to 60°
    Evidence: .sisyphus/evidence/task-4-fk-clamp.txt
  ```

  **Commit**: YES
  - Message: `feat(kinematics): forward kinematics engine with tests`
  - Files: `src/exca_dance/core/kinematics.py, tests/test_kinematics.py`
  - Pre-commit: `pytest tests/test_kinematics.py`

---

- [x] 5. **Scoring Engine + Judgment Windows + Combo + Tests**

  **What to do**:
  - Create `src/exca_dance/core/scoring.py`:
    - `ScoringEngine` class:
      - `judge(angle_errors: dict[JointName, float], timing_error_ms: float) -> HitResult`
        - timing_error_ms determines judgment tier (Perfect/Great/Good/Miss)
        - angle_error is average absolute error across active joints (degrees)
        - Score = base_score(judgment) × angle_accuracy_multiplier × combo_multiplier
        - angle_accuracy_multiplier: 1.0 at 0° error, 0.5 at 15° error, linear interpolation
      - `update_combo(judgment: Judgment)` — increment on non-Miss, reset on Miss
      - `get_combo_multiplier() -> int` — based on COMBO_THRESHOLDS
      - `get_total_score() -> int`
      - `get_max_possible_score(num_events: int) -> int`
      - `get_grade(total: int, max_possible: int) -> str` — S/A/B/C/D/F
      - `reset()` — clear state for new song
  - Create `tests/test_scoring.py` (write AFTER implementation):
    - Test Perfect judgment at 0ms, 34ms
    - Test Great judgment at 36ms, 69ms
    - Test Good judgment at 71ms, 119ms
    - Test Miss at 121ms
    - Test combo increment and reset on Miss
    - Test combo multiplier thresholds (10→2x, 25→3x, 50→4x)
    - Test angle accuracy multiplier (0°→1.0, 15°→0.5)
    - Test grade calculation (S≥95%, A≥90%, etc.)

  **Must NOT do**:
  - Do NOT import game/rendering modules
  - Do NOT handle input — scoring is pure math

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T4, T6, T7, T8, T9, T12)
  - **Blocks**: T16, T17, T20
  - **Blocked By**: T3

  **References**:
  - Constants: `src/exca_dance/core/constants.py` — JUDGMENT_WINDOWS, SCORE_VALUES, COMBO_THRESHOLDS
  - Models: `src/exca_dance/core/models.py` — Judgment enum, HitResult dataclass
  - osu!mania scoring research: Perfect ±35ms, combo multiplier at thresholds

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_scoring.py -v` → all pass (≥8 tests)
  - [ ] Edge cases: timing exactly at boundary (35ms = Perfect, 36ms = Great)

  **QA Scenarios:**
  ```
  Scenario: Scoring produces correct judgments
    Tool: Bash
    Steps:
      1. python -c "
         from exca_dance.core.scoring import ScoringEngine
         from exca_dance.core.models import JointName, Judgment
         engine = ScoringEngine()
         result = engine.judge({JointName.BOOM: 5.0}, timing_error_ms=20.0)
         assert result.judgment == Judgment.PERFECT
         print(f'Score: {result.score}, Judgment: {result.judgment}')
         "
    Expected Result: Judgment.PERFECT with positive score
    Evidence: .sisyphus/evidence/task-5-scoring-perfect.txt

  Scenario: Combo resets on miss
    Tool: Bash
    Steps:
      1. python -c "
         from exca_dance.core.scoring import ScoringEngine
         from exca_dance.core.models import JointName
         engine = ScoringEngine()
         for i in range(15):
             engine.judge({JointName.BOOM: 0}, timing_error_ms=10)  # 15 perfects
         assert engine.get_combo_multiplier() == 2  # combo > 10
         engine.judge({JointName.BOOM: 0}, timing_error_ms=999)  # miss
         assert engine.get_combo_multiplier() == 1  # reset
         print('Combo reset works')
         "
    Expected Result: Combo multiplier rises to 2x at combo 10+, resets to 1x on miss
    Evidence: .sisyphus/evidence/task-5-scoring-combo.txt
  ```

  **Commit**: YES
  - Message: `feat(scoring): judgment windows, combo system with tests`
  - Files: `src/exca_dance/core/scoring.py, tests/test_scoring.py`
  - Pre-commit: `pytest tests/test_scoring.py`

---

- [x] 6. **Beat Map JSON Parser + Schema Validation + Tests**

  **What to do**:
  - Create `src/exca_dance/core/beatmap.py`:
    - `load_beatmap(path: str) -> BeatMap` — parse JSON, validate schema, sort events by time
    - `save_beatmap(beatmap: BeatMap, path: str)` — serialize to JSON
    - `validate_beatmap(data: dict) -> list[str]` — return list of validation errors
    - Validation rules:
      - `title`, `bpm`, `audio_file` required
      - `bpm` > 0
      - Each event has `time_ms` ≥ 0 and valid joint names
      - Target angles within JOINT_LIMITS
      - Events auto-sorted by `time_ms`
    - JSON schema:
      ```json
      {
        "title": "string",
        "artist": "string",
        "bpm": 120.0,
        "offset_ms": 0,
        "audio_file": "music/song.ogg",
        "events": [
          {"time_ms": 1000, "target_angles": {"BOOM": 45.0, "ARM": -20.0}, "duration_ms": 500}
        ]
      }
      ```
  - Create `tests/test_beatmap.py`:
    - Test valid JSON loads correctly
    - Test missing required fields → validation error
    - Test invalid angle (beyond limits) → validation error
    - Test events sorted by time after load
    - Test save then load roundtrip
    - Test empty events list → valid (but empty)
    - Test malformed JSON → error message, no crash

  **Must NOT do**:
  - Do NOT implement audio loading — just store `audio_file` as string path
  - Do NOT add complex schema library (no jsonschema) — manual validation

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: T15, T16, T19, T24, T29
  - **Blocked By**: T3

  **References**:
  - Models: `src/exca_dance/core/models.py` — BeatMap, BeatEvent dataclasses
  - Constants: `src/exca_dance/core/constants.py` — JOINT_LIMITS for validation

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_beatmap.py -v` → all pass (≥7 tests)
  - [ ] Malformed JSON does not crash, returns error list

  **QA Scenarios:**
  ```
  Scenario: Load valid beat map
    Tool: Bash
    Steps:
      1. Create /tmp/test_beatmap.json with valid content
      2. python -c "from exca_dance.core.beatmap import load_beatmap; bm = load_beatmap('/tmp/test_beatmap.json'); print(f'Loaded: {bm.title}, {len(bm.events)} events')"
    Expected Result: Prints title and event count matching JSON
    Evidence: .sisyphus/evidence/task-6-beatmap-load.txt

  Scenario: Reject invalid beat map
    Tool: Bash
    Steps:
      1. Create /tmp/bad_beatmap.json with missing "title" field
      2. python -c "from exca_dance.core.beatmap import validate_beatmap; import json; errors = validate_beatmap(json.load(open('/tmp/bad_beatmap.json'))); print(errors); assert len(errors) > 0"
    Expected Result: Non-empty error list mentioning 'title'
    Evidence: .sisyphus/evidence/task-6-beatmap-invalid.txt
  ```

  **Commit**: YES
  - Message: `feat(beatmap): JSON parser with schema validation and tests`
  - Files: `src/exca_dance/core/beatmap.py, tests/test_beatmap.py`
  - Pre-commit: `pytest tests/test_beatmap.py`

---

- [x] 7. **Leaderboard Manager + JSON Persistence + Tests**

  **What to do**:
  - Create `src/exca_dance/core/leaderboard.py`:
    - `LeaderboardManager` class:
      - `__init__(filepath: str = 'data/leaderboard.json')`
      - `add_entry(initials: str, score: int, song_title: str)` — validate initials (exactly 3 chars, uppercase), add with timestamp
      - `get_top_scores(limit: int = 10, song: str | None = None) -> list[LeaderboardEntry]` — sorted by score desc
      - `save()` / `load()` — JSON file I/O
      - Auto-load on init if file exists
      - Auto-save after add_entry
      - Handle corrupted JSON: reset to empty, log warning
  - Create `tests/test_leaderboard.py`:
    - Test add entry + get top scores sorted
    - Test initials validation (3 chars, uppercase)
    - Test persistence: save then load
    - Test empty leaderboard returns empty list
    - Test corrupted JSON file → reset to empty
    - Test song filter works

  **Must NOT do**:
  - Do NOT use SQLite or any database
  - Do NOT add network/sync features

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: T21
  - **Blocked By**: T3

  **References**:
  - Models: `src/exca_dance/core/models.py` — LeaderboardEntry dataclass

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_leaderboard.py -v` → all pass (≥6 tests)
  - [ ] JSON file created after first add_entry

  **QA Scenarios:**
  ```
  Scenario: Leaderboard persists across restarts
    Tool: Bash
    Steps:
      1. python -c "
         from exca_dance.core.leaderboard import LeaderboardManager
         lb = LeaderboardManager('/tmp/test_lb.json')
         lb.add_entry('AAA', 9999, 'Test Song')
         "
      2. python -c "
         from exca_dance.core.leaderboard import LeaderboardManager
         lb = LeaderboardManager('/tmp/test_lb.json')
         scores = lb.get_top_scores()
         assert scores[0].initials == 'AAA'
         assert scores[0].score == 9999
         print('Persistence works!')
         "
    Expected Result: Second script reads back the entry saved by first script
    Evidence: .sisyphus/evidence/task-7-leaderboard-persist.txt
  ```

  **Commit**: YES
  - Message: `feat(leaderboard): persistent JSON storage with tests`
  - Files: `src/exca_dance/core/leaderboard.py, tests/test_leaderboard.py`
  - Pre-commit: `pytest tests/test_leaderboard.py`

---

- [x] 8. **Key Binding System + Persistence + Tests**

  **What to do**:
  - Create `src/exca_dance/core/keybinding.py`:
    - `KeyBindingManager` class:
      - `__init__(filepath: str = 'data/settings.json')`
      - Default bindings: `{SWING: (K_a, K_d), BOOM: (K_w, K_s), ARM: (K_UP, K_DOWN), BUCKET: (K_LEFT, K_RIGHT)}`
      - `get_binding(joint: JointName) -> tuple[int, int]` — (positive_key, negative_key)
      - `set_binding(joint: JointName, positive_key: int, negative_key: int)`
      - `get_joint_for_key(key: int) -> tuple[JointName, int] | None` — returns (joint, direction +1/-1)
      - `save()` / `load()` — JSON persistence
      - Conflict detection: warn if same key mapped twice
  - Create `tests/test_keybinding.py`:
    - Test default bindings exist for all 4 joints
    - Test custom binding set/get
    - Test key lookup returns correct joint+direction
    - Test persistence save/load
    - Test unknown key returns None
    - Test conflict detection

  **Must NOT do**:
  - Do NOT import pygame in the core module (use int key codes, not pygame constants)
  - Do NOT implement the UI for key binding (that's T22)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: T14, T22
  - **Blocked By**: T3

  **References**:
  - Models: `src/exca_dance/core/models.py` — KeyBinding dataclass
  - Pygame key constants: https://www.pygame.org/docs/ref/key.html (use integer values for core module)

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_keybinding.py -v` → all pass (≥6 tests)

  **QA Scenarios:**
  ```
  Scenario: Default bindings work
    Tool: Bash
    Steps:
      1. python -c "
         from exca_dance.core.keybinding import KeyBindingManager
         from exca_dance.core.models import JointName
         kb = KeyBindingManager('/tmp/test_kb.json')
         b = kb.get_binding(JointName.SWING)
         assert b is not None
         print(f'Swing: + key={b[0]}, - key={b[1]}')
         "
    Expected Result: Prints valid key codes for swing positive/negative
    Evidence: .sisyphus/evidence/task-8-keybinding-defaults.txt
  ```

  **Commit**: YES
  - Message: `feat(keybinding): configurable key mapping with tests`
  - Files: `src/exca_dance/core/keybinding.py, tests/test_keybinding.py`
  - Pre-commit: `pytest tests/test_keybinding.py`

---

- [x] 9. **ModernGL Renderer + GL Text Utility + Viewport Manager**

  **What to do**:
  - Create `src/exca_dance/rendering/renderer.py`:
    - `GameRenderer` class:
      - `__init__(width=1920, height=1080)` — init Pygame display with OPENGL|DOUBLEBUF, create ModernGL context
      - `begin_frame()` / `end_frame()` — clear, swap buffers
      - `get_ctx() -> moderngl.Context` — expose ModernGL context
      - Compile basic shader programs: solid color, textured quad, additive blend (for glow)
      - `draw_line_3d(start, end, color, width)` — for wireframe
      - `draw_cube(position, size, color)` / `draw_cylinder(position, radius, height, color)` — for excavator parts
      - Manage projection/view matrices (perspective + orthographic)
  - Create `src/exca_dance/rendering/gl_text.py`:
    - `GLTextRenderer` class:
      - `__init__(font_path: str, font_size: int)` — load TTF via pygame.font
      - `render_text(text: str, x: int, y: int, color, scale=1.0)` — render text as GL textured quad
      - Cache rendered text surfaces as GL textures (LRU cache, max 100)
      - Support alignment (left, center, right)
  - Create `src/exca_dance/rendering/viewport.py`:
    - `ViewportManager` class:
      - Define viewport regions: main_3d (70% width), top_2d (15% width, top half), side_2d (15% width, bottom half)
      - `set_viewport(name: str)` — set GL viewport + projection matrix
      - `get_viewport_rect(name: str) -> tuple[x, y, w, h]`
  - Create `src/exca_dance/rendering/__init__.py`

  **Must NOT do**:
  - Do NOT create the excavator model (that's T10)
  - Do NOT implement game loop (that's T14)
  - Do NOT use `pygame.Surface.blit()` for any on-screen rendering
  - Do NOT use raw PyOpenGL calls — use ModernGL API only

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: OpenGL rendering pipeline design, shader setup
  - **Skills Evaluated but Omitted**:
    - `visual-engineering`: Better suited for T10/T13 where visual aesthetics matter

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T4-T8, T12)
  - **Blocks**: T10, T11, T13, T18-T25
  - **Blocked By**: T2

  **References**:
  - ModernGL documentation: https://moderngl.readthedocs.io/en/latest/
  - ModernGL context creation from Pygame: `moderngl.create_context()`
  - GLSL vertex/fragment shader basics for 3D rendering
  - pygame.font for text surface creation
  - Constants: `src/exca_dance/core/constants.py` — SCREEN_WIDTH, SCREEN_HEIGHT

  **Acceptance Criteria**:
  - [ ] `python -c "from exca_dance.rendering.renderer import GameRenderer"` imports without error
  - [ ] GameRenderer creates a visible window with GL context
  - [ ] GL text renders readable characters on screen
  - [ ] Viewport manager correctly divides screen into 3 regions

  **QA Scenarios:**
  ```
  Scenario: Renderer creates window and draws
    Tool: interactive_bash (tmux)
    Preconditions: Display available (DISPLAY=:0 or xvfb)
    Steps:
      1. Create a test script that: inits GameRenderer, draws a colored triangle, renders "Hello Exca Dance" text, runs for 3 seconds, takes screenshot via pygame.image.save, exits
      2. Run the test script
      3. Verify screenshot file exists and is non-empty (> 1KB)
    Expected Result: Screenshot shows colored triangle + text on dark background
    Evidence: .sisyphus/evidence/task-9-renderer-screenshot.png

  Scenario: Viewport regions don't overlap
    Tool: Bash
    Steps:
      1. python -c "
         from exca_dance.rendering.viewport import ViewportManager
         vm = ViewportManager(1920, 1080)
         main = vm.get_viewport_rect('main_3d')
         top = vm.get_viewport_rect('top_2d')
         side = vm.get_viewport_rect('side_2d')
         # Check no overlap
         assert main[0] + main[2] <= top[0] or top[0] + top[2] <= main[0]
         print(f'Main: {main}, Top: {top}, Side: {side}')
         "
    Expected Result: Three non-overlapping viewport rectangles
    Evidence: .sisyphus/evidence/task-9-viewport-rects.txt
  ```

  **Commit**: YES
  - Message: `feat(renderer): ModernGL setup, GL text, viewport manager`
  - Files: `src/exca_dance/rendering/*.py`
  - Pre-commit: `python -c "from exca_dance.rendering.renderer import GameRenderer"`

---

- [x] 12. **Audio System (OGG Playback + perf_counter Sync)**

  **What to do**:
  - Create `src/exca_dance/audio/audio_system.py`:
    - `AudioSystem` class:
      - `__init__()` — init pygame.mixer with buffer=512, 44100Hz, 16-bit
      - `load_music(path: str)` — load OGG via pygame.mixer.music.load. Reject non-OGG.
      - `play()` — start playback + record `time.perf_counter()` as `_start_time`
      - `pause()` / `resume()` — track accumulated pause duration
      - `stop()`
      - `get_position_ms() -> float` — calculate from perf_counter elapsed minus accumulated pauses. NEVER use `pygame.mixer.music.get_pos()`
      - `is_playing() -> bool`
      - `set_volume(volume: float)` — 0.0 to 1.0
      - `load_sfx(name: str, path: str)` — load WAV sound effect
      - `play_sfx(name: str)` — play cached SFX
    - Handle missing audio device gracefully (silent mode with warning)
  - Create `src/exca_dance/audio/__init__.py`

  **Must NOT do**:
  - Do NOT use `pygame.mixer.music.get_pos()` — FORBIDDEN (500ms drift per 5 min)
  - Do NOT support MP3 format
  - Do NOT implement beat detection or waveform analysis

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T4-T9)
  - **Blocks**: T14, T24, T29
  - **Blocked By**: T2

  **References**:
  - Pygame mixer docs: https://www.pygame.org/docs/ref/mixer.html
  - `time.perf_counter()` docs: https://docs.python.org/3/library/time.html#time.perf_counter
  - Research finding: `get_pos()` drifts ~500ms/300s with MP3, OGG is most stable
  - Buffer size 512 = ~11.6ms latency (acceptable for ±35ms Perfect window)

  **Acceptance Criteria**:
  - [ ] OGG file loads and plays
  - [ ] `get_position_ms()` returns monotonically increasing values during playback
  - [ ] Pause/resume correctly accounts for paused time
  - [ ] No calls to `pygame.mixer.music.get_pos()` in source code (grep check)

  **QA Scenarios:**
  ```
  Scenario: Audio position tracks correctly
    Tool: Bash
    Steps:
      1. Generate a 5s OGG test file: python -c "import subprocess; subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=5', '-c:a', 'libvorbis', '/tmp/test.ogg', '-y'])" OR use pygame to generate
      2. python -c "
         import time
         from exca_dance.audio.audio_system import AudioSystem
         audio = AudioSystem()
         audio.load_music('/tmp/test.ogg')
         audio.play()
         time.sleep(2.0)
         pos = audio.get_position_ms()
         assert 1900 < pos < 2100, f'Position {pos}ms should be ~2000ms'
         audio.stop()
         print(f'Position after 2s: {pos}ms — PASS')
         "
    Expected Result: Position within ±100ms of 2000ms
    Evidence: .sisyphus/evidence/task-12-audio-position.txt

  Scenario: Forbidden get_pos not used
    Tool: Bash (grep)
    Steps:
      1. grep -rn "get_pos" src/exca_dance/audio/
    Expected Result: Zero matches (no get_pos calls)
    Evidence: .sisyphus/evidence/task-12-no-getpos.txt
  ```

  **Commit**: YES
  - Message: `feat(audio): OGG playback with perf_counter sync`
  - Files: `src/exca_dance/audio/*.py`
  - Pre-commit: `python -c "from exca_dance.audio.audio_system import AudioSystem"`

---

### Wave 3: 3D Visualization + Theme + ROS2 Interface + Content (5 Tasks)

- [x] 10. **3D Excavator Geometric Model + FK Visualization**

  **What to do**:
  - Create `src/exca_dance/rendering/excavator_model.py`:
    - `ExcavatorModel` class:
      - Constructor takes `ExcavatorFK` instance and `GameRenderer` reference
      - Build excavator from geometric primitives:
        - **Base/cab**: Box (1.5×1.0×1.0) — body with tracks
        - **Swing turret**: Cylinder on top of base (rotates with swing angle)
        - **Boom**: Elongated box (L=boom_length, W=0.3, H=0.3) — pivots at turret
        - **Arm (stick)**: Elongated box (L=arm_length, W=0.25, H=0.25) — pivots at boom end
        - **Bucket**: Trapezoidal shape (wider at opening) — pivots at arm end
        - **Hydraulic cylinders**: Thin cylinders connecting joints (visual only)
      - `update(joint_angles: dict[JointName, float])` — recalculate transforms via FK
      - `render_3d(view_matrix, projection_matrix)` — draw all parts with solid color + wireframe overlay
      - `render_2d_side(view_matrix, projection_matrix)` — render side projection (boom/arm/bucket visible)
      - `render_2d_top(view_matrix, projection_matrix)` — render top projection (swing visible)
      - Each joint has distinct color for educational clarity:
        - Base: dark gray, Boom: orange, Arm: yellow, Bucket: cyan
      - Highlight active/moving joints with brighter color
  - Use numpy for transformation matrices (rotation, translation)

  **Must NOT do**:
  - Do NOT load external 3D models (OBJ, URDF, etc.)
  - Do NOT add shadows, reflections, or particle effects
  - Do NOT implement camera controls (fixed camera)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T11, T13, T26, T29 after T4+T9 complete)
  - **Parallel Group**: Wave 3
  - **Blocks**: T11, T15
  - **Blocked By**: T4 (FK engine), T9 (renderer)

  **References**:
  - FK engine: `src/exca_dance/core/kinematics.py` — use `forward_kinematics()` output for joint positions
  - Renderer: `src/exca_dance/rendering/renderer.py` — use `draw_cube()`, `draw_cylinder()` primitives
  - Constants: `src/exca_dance/core/constants.py` — JOINT_LIMITS for angle ranges
  - Color scheme: Base=dark gray(#3a3a3a), Boom=orange(#ff6600), Arm=yellow(#ffcc00), Bucket=cyan(#00ccff)

  **Acceptance Criteria**:
  - [ ] Excavator renders with all 5 parts visible (base, turret, boom, arm, bucket)
  - [ ] Changing joint angles → visual model updates correctly
  - [ ] 2D side view shows boom/arm/bucket movement clearly
  - [ ] 2D top view shows swing rotation clearly

  **QA Scenarios:**
  ```
  Scenario: Excavator renders and animates
    Tool: interactive_bash (tmux)
    Preconditions: T4, T9 complete
    Steps:
      1. Create test script: init renderer, create model, animate boom from 0° to 60° over 3 seconds, screenshot at start and end
      2. Run script, capture screenshots via pygame.image.save
      3. Compare: boom visually raised in second screenshot vs first
    Expected Result: Two distinct screenshots showing different boom angles
    Evidence: .sisyphus/evidence/task-10-excavator-start.png, .sisyphus/evidence/task-10-excavator-end.png
  ```

  **Commit**: YES (groups with T11)
  - Message: `feat(viz): 3D excavator + multi-viewport layout`
  - Files: `src/exca_dance/rendering/excavator_model.py`
  - Pre-commit: `python -c "from exca_dance.rendering.excavator_model import ExcavatorModel"`

---

- [x] 11. **Multi-Viewport Layout (3D Main + 2D Top/Side Panels)**

  **What to do**:
  - Create `src/exca_dance/rendering/viewport_layout.py`:
    - `GameViewportLayout` class that uses `ViewportManager` from T9:
      - **Main 3D view** (left 75% of screen): perspective projection, camera at 45° angle looking at excavator
      - **Top 2D view** (right 25%, top half): orthographic top-down, shows swing rotation + reach
      - **Side 2D view** (right 25%, bottom half): orthographic side view, shows boom/arm/bucket angles
      - Each panel has a thin neon border (glow effect color from theme)
      - Each panel has a label ("3D VIEW", "TOP", "SIDE") rendered via GL text
    - `render_all(excavator_model: ExcavatorModel, joint_angles: dict)` — render excavator in all 3 viewports
    - Camera position: fixed, looking at excavator center from ~45° elevation, ~30° azimuth
    - Grid/ground plane in 3D view for spatial reference

  **Must NOT do**:
  - Do NOT implement camera rotation/zoom (fixed camera)
  - Do NOT add UI elements beyond panel labels and borders

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (after T9, T10)
  - **Parallel Group**: Wave 3
  - **Blocks**: T14
  - **Blocked By**: T9 (viewport manager), T10 (excavator model)

  **References**:
  - Viewport manager: `src/exca_dance/rendering/viewport.py` — `set_viewport()`, `get_viewport_rect()`
  - Excavator model: `src/exca_dance/rendering/excavator_model.py` — `render_3d()`, `render_2d_side()`, `render_2d_top()`
  - GL text: `src/exca_dance/rendering/gl_text.py` — for panel labels

  **Acceptance Criteria**:
  - [ ] Screen divided into 3 visible panels with borders
  - [ ] 3D view shows excavator from 45° angle with ground plane
  - [ ] Top view correctly shows swing rotation
  - [ ] Side view correctly shows boom/arm/bucket angles

  **QA Scenarios:**
  ```
  Scenario: Three viewports render simultaneously
    Tool: interactive_bash (tmux)
    Steps:
      1. Create test script: init layout, set excavator to swing=45° boom=30° arm=-20°, render all views, screenshot
      2. Verify screenshot shows 3 distinct panels with different projections
    Expected Result: Screenshot with 3D, top, and side views all visible, borders clear
    Evidence: .sisyphus/evidence/task-11-viewport-layout.png
  ```

  **Commit**: YES (groups with T10)
  - Message: `feat(viz): 3D excavator + multi-viewport layout`
  - Files: `src/exca_dance/rendering/viewport_layout.py`

---

- [x] 13. **Neon/Cyberpunk Visual Theme + Glow Effects**

  **What to do**:
  - Create `src/exca_dance/rendering/theme.py`:
    - `NeonTheme` class with color constants:
      - Background: near-black (#0a0a1a)
      - Primary neon: electric blue (#00d4ff)
      - Secondary neon: hot pink (#ff0066)
      - Accent: neon green (#00ff88)
      - Warning: neon orange (#ff8800)
      - Perfect: gold (#ffd700)
      - Great: cyan (#00ccff)
      - Good: green (#00ff88)
      - Miss: red (#ff0044)
      - Panel borders: electric blue with 50% alpha
      - Text: white (#ffffff) with neon-colored shadows
    - `draw_glow_rect(x, y, w, h, color, intensity)` — additive blend rectangle (for borders, highlights)
    - `draw_glow_line(start, end, color, width, intensity)` — for wireframe glow on excavator
    - `get_judgment_color(judgment: Judgment) -> tuple` — color per judgment tier
    - Glow implementation: draw shape twice — once at full color, once slightly larger with alpha 0.3 (additive blend)
  - Apply theme to existing renderer: set clear color to background

  **Must NOT do**:
  - Do NOT implement particle systems
  - Do NOT add bloom/HDR post-processing shaders
  - Do NOT create complex shader effects beyond additive blending

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (after T9)
  - **Parallel Group**: Wave 3
  - **Blocks**: T18-T22 (all UI screens use theme)
  - **Blocked By**: T9 (renderer)

  **References**:
  - Renderer: `src/exca_dance/rendering/renderer.py` — additive blend shader
  - Models: `src/exca_dance/core/models.py` — Judgment enum for color mapping
  - Beat Saber / arcade game visual references for neon aesthetic

  **Acceptance Criteria**:
  - [ ] Dark background with neon-colored elements visible
  - [ ] Glow effect on rectangles and lines visible (additive blending)
  - [ ] All judgment tiers have distinct, readable colors

  **QA Scenarios:**
  ```
  Scenario: Neon theme renders correctly
    Tool: interactive_bash (tmux)
    Steps:
      1. Test script: render dark BG + neon-bordered panel + glow text + colored judgment labels, screenshot
    Expected Result: Screenshot shows dark background with vibrant neon elements, glow visible on borders
    Evidence: .sisyphus/evidence/task-13-neon-theme.png
  ```

  **Commit**: YES
  - Message: `style: neon/cyberpunk theme colors and glow effects`
  - Files: `src/exca_dance/rendering/theme.py`

---

- [x] 26. **ROS2 Bridge Abstract Interface Layer**

  **What to do**:
  - Create `src/exca_dance/ros2_bridge/__init__.py`
  - Create `src/exca_dance/ros2_bridge/interface.py`:
    - `ExcavatorBridgeInterface` (ABC):
      - `send_command(joint_angles: dict[JointName, float])` — abstract
      - `get_current_angles() -> dict[JointName, float]` — abstract
      - `is_connected() -> bool` — abstract
      - `connect()` / `disconnect()` — abstract
    - `VirtualBridge(ExcavatorBridgeInterface)` — implementation for virtual mode:
      - `send_command()` — stores angles directly (no-op, virtual excavator)
      - `get_current_angles()` — returns stored angles
      - Always `is_connected() = True`
    - This module MUST NOT import rclpy or any ROS2 package
  - Create `tests/test_ros2_interface.py`:
    - Test VirtualBridge stores and returns angles
    - Test interface contract (all methods exist)

  **Must NOT do**:
  - Do NOT import rclpy anywhere in this file
  - Do NOT implement the actual ROS2 node (that's T27)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: T27
  - **Blocked By**: T3

  **References**:
  - Models: `src/exca_dance/core/models.py` — JointName, ExcavatorState
  - Research: ROS2 multi-process architecture with IPC queues

  **Acceptance Criteria**:
  - [ ] `python -c "from exca_dance.ros2_bridge.interface import VirtualBridge"` works without ROS2 installed
  - [ ] VirtualBridge send/get roundtrip works
  - [ ] `pytest tests/test_ros2_interface.py -v` passes

  **QA Scenarios:**
  ```
  Scenario: VirtualBridge works standalone
    Tool: Bash
    Steps:
      1. python -c "
         from exca_dance.ros2_bridge.interface import VirtualBridge
         from exca_dance.core.models import JointName
         bridge = VirtualBridge()
         bridge.connect()
         bridge.send_command({JointName.BOOM: 30.0, JointName.ARM: -15.0})
         angles = bridge.get_current_angles()
         assert angles[JointName.BOOM] == 30.0
         print('VirtualBridge works!')
         "
    Expected Result: Exit 0, angles match what was sent
    Evidence: .sisyphus/evidence/task-26-virtual-bridge.txt

  Scenario: No ROS2 dependency
    Tool: Bash
    Steps:
      1. grep -rn "import rclpy" src/exca_dance/ros2_bridge/interface.py
    Expected Result: Zero matches
    Evidence: .sisyphus/evidence/task-26-no-rclpy.txt
  ```

  **Commit**: YES
  - Message: `feat(ros2): abstract bridge interface layer`
  - Files: `src/exca_dance/ros2_bridge/*.py, tests/test_ros2_interface.py`
  - Pre-commit: `pytest tests/test_ros2_interface.py`

---

- [x] 29. **Sample Content: 2 BGMs (WAV) + Beat Maps (JSON)**

  **What to do**:
  - Find or generate 2 free-license BGM tracks in OGG format:
    - Song 1: Medium tempo (~120 BPM), ~60-90 seconds. Beginner-friendly.
    - Song 2: Faster tempo (~140 BPM), ~60-90 seconds. More challenging.
    - Sources: freesound.org, incompetech.com (Kevin MacLeod), or generate with python (simple synthesized music)
    - Place in `assets/music/sample1.ogg` and `assets/music/sample2.ogg`
  - Create 2 beat map JSON files:
    - `assets/beatmaps/sample1.json` — matches song 1:
      - ~20-30 events, spaced evenly on beats
      - Use all 4 joints, gradually introduce complexity
      - Start with single-joint events, progress to multi-joint
    - `assets/beatmaps/sample2.json` — matches song 2:
      - ~30-40 events, faster pace
      - More multi-joint combinations
    - Both must pass `validate_beatmap()` from T6
  - Include `assets/sounds/hit_perfect.wav`, `hit_great.wav`, `hit_good.wav`, `hit_miss.wav` — short SFX

  **Must NOT do**:
  - Do NOT use copyrighted music
  - Do NOT create more than 2 sample songs

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: T30 (integration)
  - **Blocked By**: T6 (beatmap parser for validation), T12 (audio for format verification)

  **References**:
  - Beat map format: `src/exca_dance/core/beatmap.py` — `validate_beatmap()` schema
  - Audio format: OGG only (from guardrails)
  - Joint ranges: `src/exca_dance/core/constants.py` — JOINT_LIMITS

  **Acceptance Criteria**:
  - [ ] Both OGG files play without error
  - [ ] Both beat maps pass validation (`validate_beatmap()`)
  - [ ] All SFX WAV files load via `pygame.mixer.Sound()`

  **QA Scenarios:**
  ```
  Scenario: Sample content validates and plays
    Tool: Bash
    Steps:
      1. python -c "
         from exca_dance.core.beatmap import load_beatmap, validate_beatmap
         import json
         for f in ['assets/beatmaps/sample1.json', 'assets/beatmaps/sample2.json']:
             bm = load_beatmap(f)
             errors = validate_beatmap(json.load(open(f)))
             assert len(errors) == 0, f'{f}: {errors}'
             print(f'{f}: {bm.title} - {len(bm.events)} events - VALID')
         "
    Expected Result: Both beat maps load and validate with 0 errors
    Evidence: .sisyphus/evidence/task-29-content-valid.txt
  ```

  **Commit**: YES
  - Message: `content: 2 sample BGMs + beat maps`
  - Files: `assets/music/*.ogg, assets/beatmaps/*.json, assets/sounds/*.wav`

---

### Wave 4: Game Core (4 Tasks)

- [x] 14. **Game Loop Core (Input → FK → Render → Audio Sync)**

  **What to do**:
  - Create `src/exca_dance/core/game_loop.py`:
    - `GameLoop` class — the central orchestrator:
      - `__init__(renderer, audio, fk, scoring, keybinding, bridge, viewport_layout)`
      - Main loop at 60fps via `pygame.time.Clock`:
        1. **Input phase**: Process `pygame.event.get()`. Map keys via KeyBindingManager. Track held keys for continuous joint movement.
        2. **Update phase**: Apply angular velocity to joints (JOINT_ANGULAR_VELOCITY * dt) for held keys. Clamp to JOINT_LIMITS. Update bridge.
        3. **Beat check phase**: Compare current time (AudioSystem.get_position_ms()) against upcoming BeatEvents. When event time passes, evaluate hit.
        4. **Render phase**: Clear, render viewport layout with excavator, render UI overlay.
        5. **Flip**: `end_frame()`
      - `start_song(beatmap: BeatMap)` — load audio, start playback, reset scoring
      - `handle_event(event)` — delegate to current screen/state
      - Support game states: PLAYING, PAUSED, FINISHED
      - dt calculation: `clock.tick(TARGET_FPS) / 1000.0`
  - Continuous joint movement: while key is held, joint angle changes at JOINT_ANGULAR_VELOCITY deg/s
  - The game loop does NOT own screens — it provides the low-level tick. Screens are managed by a state machine (T23).

  **Must NOT do**:
  - Do NOT implement screen transitions (that's T23)
  - Do NOT implement HUD rendering (that's T17)
  - Do NOT use `pygame.mixer.music.get_pos()`

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs T4, T8, T11, T12)
  - **Parallel Group**: Wave 4 (first in wave)
  - **Blocks**: T15, T16, T17, T23, T28
  - **Blocked By**: T4, T8, T11, T12

  **References**:
  - FK: `src/exca_dance/core/kinematics.py`
  - Scoring: `src/exca_dance/core/scoring.py`
  - KeyBinding: `src/exca_dance/core/keybinding.py`
  - Audio: `src/exca_dance/audio/audio_system.py`
  - Renderer: `src/exca_dance/rendering/renderer.py`
  - Viewport: `src/exca_dance/rendering/viewport_layout.py`
  - Bridge: `src/exca_dance/ros2_bridge/interface.py`
  - Constants: `src/exca_dance/core/constants.py` — TARGET_FPS, JOINT_ANGULAR_VELOCITY

  **Acceptance Criteria**:
  - [ ] Game window opens, excavator responds to keyboard input in real-time
  - [ ] Joint angles change smoothly while key is held (not discrete jumps)
  - [ ] Angle clamping works at joint limits
  - [ ] FPS counter shows ≥55fps

  **QA Scenarios:**
  ```
  Scenario: Excavator responds to keyboard input
    Tool: interactive_bash (tmux)
    Steps:
      1. Start game loop in test mode: python -m exca_dance --test-gameplay
      2. Send key presses via tmux send-keys: press 'w' for 2 seconds (boom up)
      3. Screenshot before and after key press
      4. Verify boom angle increased in second screenshot (visual inspection) or from debug log
    Expected Result: Boom visually raised, debug log shows angle > 0
    Evidence: .sisyphus/evidence/task-14-input-response.png
  ```

  **Commit**: YES (groups with T15, T16, T17)
  - Message: `feat(core): game loop, visual cues, hit detection, HUD`
  - Files: `src/exca_dance/core/game_loop.py`

---

- [x] 15. **Visual Cue System (Ghost Excavator + Beat Indicators)**

  **What to do**:
  - Create `src/exca_dance/rendering/visual_cues.py`:
    - `VisualCueRenderer` class:
      - **Ghost excavator**: Render a semi-transparent (alpha 0.3) copy of excavator at target pose
        - Uses same ExcavatorModel but with transparency
        - Appears 2 beats before the event, fades in from alpha 0 to 0.3
      - **Joint angle indicators**: 4 arc indicators (one per joint) on the side panel:
        - Current angle shown as solid arc
        - Target angle shown as glowing outline arc
        - Color matches joint color from theme
        - When angles match closely: indicator turns green/Perfect color
      - **Beat timeline bar**: Horizontal bar at bottom of screen:
        - Shows upcoming events as markers scrolling left to right
        - Current position as vertical line
        - Color-coded by which joints are involved
      - **Approaching indicator**: As event timing approaches, ghost excavator pulses
    - `update(current_time_ms, current_angles, upcoming_events)` — update all visual cues
    - `render(renderer)` — draw all active cues

  **Must NOT do**:
  - Do NOT implement scoring or hit detection (that's T16)
  - Do NOT add particle effects

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T16, T17 after T14 starts)
  - **Parallel Group**: Wave 4
  - **Blocks**: T16
  - **Blocked By**: T6 (beat map events), T10 (excavator model), T14 (game loop)

  **References**:
  - Excavator model: `src/exca_dance/rendering/excavator_model.py` — render with transparency
  - Beat map: `src/exca_dance/core/models.py` — BeatEvent structure
  - Theme: `src/exca_dance/rendering/theme.py` — neon colors for indicators
  - FK: `src/exca_dance/core/kinematics.py` — compute ghost excavator positions

  **Acceptance Criteria**:
  - [ ] Ghost excavator visible as semi-transparent overlay at target pose
  - [ ] Joint angle indicators show both current and target angles
  - [ ] Beat timeline scrolls correctly with song position

  **QA Scenarios:**
  ```
  Scenario: Ghost excavator shows target pose
    Tool: interactive_bash (tmux)
    Steps:
      1. Load sample beat map, advance to 1 beat before first event
      2. Screenshot: should show solid excavator (current) + transparent ghost (target)
      3. Verify ghost and current excavator are in different poses
    Expected Result: Two excavators visible — solid current and transparent target
    Evidence: .sisyphus/evidence/task-15-ghost-excavator.png
  ```

  **Commit**: YES (groups with T14, T16, T17)
  - Message: `feat(core): game loop, visual cues, hit detection, HUD`
  - Files: `src/exca_dance/rendering/visual_cues.py`

---

- [x] 16. **Hit Detection + Judgment Display + Scoring Integration**

  **What to do**:
  - Create `src/exca_dance/core/hit_detection.py`:
    - `HitDetector` class:
      - `__init__(scoring_engine: ScoringEngine)`
      - `check_events(current_time_ms, current_angles, active_events) -> list[HitResult]`:
        - For each BeatEvent whose time has passed:
          - Calculate timing_error = |current_time - event_time|
          - Calculate angle_errors per joint: |current_angle - target_angle|
          - Pass to ScoringEngine.judge()
          - If event time passed by > GOOD window: auto-Miss
        - Remove processed events from active list
      - `get_pending_count() -> int` — events not yet evaluated
  - Create `src/exca_dance/rendering/judgment_display.py`:
    - `JudgmentDisplay` class:
      - Show judgment text ("PERFECT!", "GREAT!", etc.) with neon glow animation
      - Text appears large, fades and shrinks over 0.5s
      - Color from theme (gold for Perfect, cyan for Great, etc.)
      - Show combo counter below: "x15 COMBO"
      - Show score increment floating up: "+300"
    - `trigger(hit_result: HitResult, combo: int)`
    - `update(dt)` / `render(renderer, text_renderer)`

  **Must NOT do**:
  - Do NOT modify the scoring engine logic (already in T5)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T15, T17 in Wave 4)
  - **Parallel Group**: Wave 4
  - **Blocks**: T17
  - **Blocked By**: T5 (scoring), T6 (beatmap), T14 (game loop), T15 (visual cues)

  **References**:
  - Scoring: `src/exca_dance/core/scoring.py` — ScoringEngine.judge()
  - Models: `src/exca_dance/core/models.py` — BeatEvent, HitResult, Judgment
  - Theme: `src/exca_dance/rendering/theme.py` — judgment colors
  - Constants: `src/exca_dance/core/constants.py` — JUDGMENT_WINDOWS

  **Acceptance Criteria**:
  - [ ] Events trigger judgment when their time passes
  - [ ] Missed events (past GOOD window) auto-resolve as Miss
  - [ ] Judgment text appears with correct color and fades
  - [ ] Combo counter increments and resets correctly

  **QA Scenarios:**
  ```
  Scenario: Perfect hit produces correct judgment
    Tool: interactive_bash (tmux)
    Steps:
      1. Load beat map with one event at t=3000ms, target boom=30°
      2. Before t=3000ms, move boom to ~30° using keyboard
      3. Observe judgment display: should show "PERFECT!" in gold
    Expected Result: Gold "PERFECT!" text appears, score increments by 300
    Evidence: .sisyphus/evidence/task-16-perfect-hit.png
  ```

  **Commit**: YES (groups with T14, T15, T17)
  - Message: `feat(core): game loop, visual cues, hit detection, HUD`
  - Files: `src/exca_dance/core/hit_detection.py, src/exca_dance/rendering/judgment_display.py`

---

- [x] 17. **Gameplay HUD (Score, Combo, Judgment Flash, Progress)**

  **What to do**:
  - Create `src/exca_dance/ui/gameplay_hud.py`:
    - `GameplayHUD` class:
      - **Score display** (top-right): large neon text, current score with leading zeros
      - **Combo counter** (center-top): "x{N}" with size pulse on increment
      - **Judgment flash** (center): integrates JudgmentDisplay from T16
      - **Progress bar** (bottom): song progress as neon line, percentage text
      - **Joint status panel** (left side): 4 rows showing:
        - Joint name + icon
        - Current angle (numeric)
        - Target angle (if event active)
        - Angular velocity indicator (moving/still)
      - **FPS counter** (top-left, small, debug): toggle with F3 key
    - `update(game_state)` — update all HUD elements
    - `render(renderer, text_renderer)` — draw HUD overlay on top of viewport
    - All text rendered via GL text renderer (not Surface.blit)

  **Must NOT do**:
  - Do NOT implement screen transitions
  - Do NOT use Surface.blit()

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T15, T16 after T14)
  - **Parallel Group**: Wave 4
  - **Blocks**: T18-T22
  - **Blocked By**: T5 (scoring data), T14 (game loop for state)

  **References**:
  - Scoring: `src/exca_dance/core/scoring.py` — score, combo data
  - Judgment display: `src/exca_dance/rendering/judgment_display.py` — integrates into HUD
  - Theme: `src/exca_dance/rendering/theme.py` — colors
  - GL text: `src/exca_dance/rendering/gl_text.py` — text rendering
  - Audio: `src/exca_dance/audio/audio_system.py` — `get_position_ms()` for progress bar

  **Acceptance Criteria**:
  - [ ] Score displays and updates in real-time
  - [ ] Combo counter pulses on increment, resets on miss
  - [ ] Progress bar tracks song position accurately
  - [ ] Joint status shows current + target angles

  **QA Scenarios:**
  ```
  Scenario: HUD displays all elements during gameplay
    Tool: interactive_bash (tmux)
    Steps:
      1. Start gameplay with sample beat map
      2. Play for 10 seconds with some hits
      3. Screenshot: verify score (top-right), combo (top-center), progress bar (bottom), joint status (left)
    Expected Result: All HUD elements visible and correctly positioned
    Evidence: .sisyphus/evidence/task-17-hud-screenshot.png
  ```

  **Commit**: YES (groups with T14, T15, T16)
  - Message: `feat(core): game loop, visual cues, hit detection, HUD`
  - Files: `src/exca_dance/ui/gameplay_hud.py`

---

### Wave 5: UI Screens + Pose Editor (8 Parallel Tasks)

- [x] 18. **Main Menu Screen**

  **What to do**:
  - Create `src/exca_dance/ui/screens/main_menu.py`:
    - `MainMenuScreen` class:
      - Dark background with animated neon grid (subtle, cyberpunk feel)
      - Game title "EXCA DANCE" in large neon text with glow
      - Menu options (GL text, neon-highlighted on hover/select):
        1. 🎮 PLAY (-> Song Select)
        2. ✏️ EDITOR (-> Pose Editor)
        3. 🏆 LEADERBOARD (-> Leaderboard Screen)
        4. ⚙️ SETTINGS (-> Settings Screen)
        5. 🚨 QUIT
      - Keyboard navigation: Up/Down to move, Enter to select
      - Selected item has neon glow highlight + slight scale-up
      - Mode indicator: "MODE: VIRTUAL" or "MODE: REAL (ROS2)" at bottom
    - `handle_event(event) -> str | None` — return screen name to transition to, or None
    - `update(dt)` / `render(renderer, text_renderer)`

  **Must NOT do**:
  - Do NOT implement screen transition animations
  - Do NOT add background music on menu (or keep very subtle)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5 (with T19-T25)
  - **Blocks**: T30
  - **Blocked By**: T9, T13

  **References**:
  - Theme: `src/exca_dance/rendering/theme.py` — NeonTheme colors
  - GL text: `src/exca_dance/rendering/gl_text.py`
  - Renderer: `src/exca_dance/rendering/renderer.py`

  **Acceptance Criteria**:
  - [ ] Title and all 5 menu options visible
  - [ ] Keyboard Up/Down moves selection, Enter activates
  - [ ] Neon glow on selected item

  **QA Scenarios:**
  ```
  Scenario: Main menu navigation works
    Tool: interactive_bash (tmux)
    Steps:
      1. Launch game, observe main menu
      2. Press Down arrow 3 times (should highlight SETTINGS)
      3. Press Up arrow 1 time (should highlight LEADERBOARD)
      4. Screenshot
    Expected Result: LEADERBOARD option highlighted with neon glow
    Evidence: .sisyphus/evidence/task-18-main-menu.png
  ```

  **Commit**: YES (groups with T19-T22)
  - Message: `feat(ui): menu, song select, results, leaderboard, settings screens`
  - Files: `src/exca_dance/ui/screens/main_menu.py`

---

- [x] 19. **Song Selection Screen**

  **What to do**:
  - Create `src/exca_dance/ui/screens/song_select.py`:
    - `SongSelectScreen` class:
      - Scan `assets/beatmaps/` for JSON files, load metadata (title, artist, BPM, event count)
      - Display list of available songs with:
        - Title, Artist, BPM
        - Difficulty indicator (based on event density: events per minute)
        - Best score from leaderboard (if exists)
      - Keyboard: Up/Down to scroll, Enter to start, Escape to go back
      - Selected song highlighted with neon border
      - Preview: show beat count and estimated duration
    - `handle_event(event) -> tuple[str, BeatMap] | None`
    - Gracefully handle: missing audio file (gray out song), empty beatmaps folder ("No songs found")

  **Must NOT do**:
  - Do NOT play audio preview of songs
  - Do NOT implement song search/filter

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5
  - **Blocks**: T30
  - **Blocked By**: T6, T9, T13

  **References**:
  - Beatmap: `src/exca_dance/core/beatmap.py` — `load_beatmap()` for scanning
  - Leaderboard: `src/exca_dance/core/leaderboard.py` — best score lookup
  - Theme: `src/exca_dance/rendering/theme.py`

  **Acceptance Criteria**:
  - [ ] Both sample songs listed with metadata
  - [ ] Selection highlight works
  - [ ] Enter on selected song triggers gameplay transition
  - [ ] Missing audio file = grayed out song

  **QA Scenarios:**
  ```
  Scenario: Song list populates from beatmaps folder
    Tool: interactive_bash (tmux)
    Steps:
      1. Launch game, navigate to PLAY
      2. Verify song list shows 2 sample songs with title/BPM
      3. Select first song, press Enter
    Expected Result: 2 songs listed, gameplay starts on Enter
    Evidence: .sisyphus/evidence/task-19-song-select.png
  ```

  **Commit**: YES (groups with T18, T20-T22)

---

- [x] 20. **Score Results Screen**

  **What to do**:
  - Create `src/exca_dance/ui/screens/results.py`:
    - `ResultsScreen` class:
      - Display after song completes:
        - Song title + artist
        - Final score (large, neon)
        - Grade (S/A/B/C/D/F) with matching color and size
        - Judgment breakdown: N× Perfect, N× Great, N× Good, N× Miss
        - Max combo achieved
        - Accuracy percentage
      - Options: "SAVE SCORE" (-> initials entry) or "RETRY" or "BACK TO MENU"
      - Keyboard: 1/2/3 or arrow keys to select option

  **Must NOT do**:
  - Do NOT implement replay system
  - Do NOT add score sharing/export

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5
  - **Blocks**: T30
  - **Blocked By**: T5, T9, T13

  **References**:
  - Scoring: `src/exca_dance/core/scoring.py` — get_total_score(), get_grade()
  - Theme: `src/exca_dance/rendering/theme.py` — judgment colors, grade colors

  **Acceptance Criteria**:
  - [ ] All score elements display correctly
  - [ ] Grade calculation matches scoring engine
  - [ ] "SAVE SCORE" transitions to initials entry

  **QA Scenarios:**
  ```
  Scenario: Results screen shows after gameplay
    Tool: interactive_bash (tmux)
    Steps:
      1. Complete a song (let it play through)
      2. Verify results screen shows: score, grade, judgment counts, max combo
      3. Select "SAVE SCORE"
    Expected Result: Results screen with all statistics visible
    Evidence: .sisyphus/evidence/task-20-results.png
  ```

  **Commit**: YES (groups with T18-T19, T21-T22)

---

- [x] 21. **Leaderboard Screen + 3-Character Initials Entry**

  **What to do**:
  - Create `src/exca_dance/ui/screens/leaderboard_screen.py`:
    - `LeaderboardScreen` class:
      - Display top 10 scores in a neon-styled table:
        - Rank | Initials | Score | Song | Date
        - Top 3 have special neon colors (gold, silver, bronze)
      - Filter by song or show all (Tab to toggle)
    - `InitialsEntryScreen` class (sub-screen):
      - 3-character entry like arcade machines:
        - 3 slots showing current character (A-Z, 0-9)
        - Up/Down to cycle characters in current slot
        - Left/Right to move between slots
        - Enter to confirm
      - Show entered initials large with neon glow
      - Show score being saved

  **Must NOT do**:
  - Do NOT add online leaderboard
  - Do NOT allow more than 3 characters

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5
  - **Blocks**: T30
  - **Blocked By**: T7, T9, T13

  **References**:
  - Leaderboard: `src/exca_dance/core/leaderboard.py` — LeaderboardManager
  - Theme: `src/exca_dance/rendering/theme.py`

  **Acceptance Criteria**:
  - [ ] Top 10 scores displayed in table format
  - [ ] Initials entry cycles A-Z with Up/Down
  - [ ] Saved entry appears in leaderboard immediately

  **QA Scenarios:**
  ```
  Scenario: Full score save flow
    Tool: interactive_bash (tmux)
    Steps:
      1. After results screen, select "SAVE SCORE"
      2. Enter initials: Up to 'B', Right, Up to 'C', Right, Up to 'D', Enter
      3. Verify leaderboard shows "BCD" with the score
    Expected Result: "BCD" entry in leaderboard with correct score
    Evidence: .sisyphus/evidence/task-21-initials-entry.png
  ```

  **Commit**: YES (groups with T18-T20, T22)

---

- [x] 22. **Settings Screen (Key Bindings, Volume)**

  **What to do**:
  - Create `src/exca_dance/ui/screens/settings.py`:
    - `SettingsScreen` class:
      - **Key Bindings section**:
        - Show all 4 joints with current positive/negative key assignments
        - Select a binding -> "Press new key..." -> capture next key press
        - Show conflict warning if key already assigned
        - Reset to defaults button
      - **Audio section**:
        - Master volume slider (Left/Right to adjust)
        - SFX volume slider
        - Audio offset (ms) adjustment (+/- 5ms per press)
      - **Mode section**:
        - Toggle: Virtual / Real (ROS2)
        - If Real selected: show connection status
      - Save on exit (auto-save when leaving settings)

  **Must NOT do**:
  - Do NOT add visual/graphics settings
  - Do NOT implement profile/account system

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5
  - **Blocks**: T30
  - **Blocked By**: T8, T9, T13

  **References**:
  - KeyBinding: `src/exca_dance/core/keybinding.py` — get/set bindings
  - Audio: `src/exca_dance/audio/audio_system.py` — set_volume()
  - Bridge interface: `src/exca_dance/ros2_bridge/interface.py` — mode info

  **Acceptance Criteria**:
  - [ ] Key binding capture works (press new key -> updates)
  - [ ] Volume sliders adjust audio level
  - [ ] Settings persist after exiting and re-entering

  **QA Scenarios:**
  ```
  Scenario: Rebind key and verify persistence
    Tool: interactive_bash (tmux)
    Steps:
      1. Open Settings, go to Key Bindings
      2. Select Boom positive key, press 'j'
      3. Exit settings, exit game
      4. Relaunch game, check Settings -> Boom positive = 'j'
    Expected Result: Boom positive key shows 'j' after restart
    Evidence: .sisyphus/evidence/task-22-settings-persist.txt
  ```

  **Commit**: YES (groups with T18-T21)
  - Message: `feat(ui): menu, song select, results, leaderboard, settings screens`
  - Files: `src/exca_dance/ui/screens/settings.py`

---

- [x] 23. **Pause/Resume + Game State Management**

  **What to do**:
  - Create `src/exca_dance/core/game_state.py`:
    - `GameStateManager` class (state machine):
      - States: MAIN_MENU, SONG_SELECT, GAMEPLAY, PAUSED, RESULTS, LEADERBOARD, SETTINGS, EDITOR
      - `transition_to(state, **kwargs)` — switch active screen, pass data
      - `get_current_state() -> str`
      - `handle_event(event)` — delegate to current screen
      - `update(dt)` / `render(renderer, text_renderer)`
    - **Pause behavior** (ESC during GAMEPLAY):
      - AudioSystem.pause() — pause music
      - Freeze all beat event timing (pause perf_counter accumulation)
      - Show semi-transparent dark overlay with:
        - "PAUSED" in large neon text
        - "Resume" (ESC), "Restart", "Quit to Menu"
      - Resume: AudioSystem.resume(), continue timing
    - **Window focus loss**: auto-pause (SDL_WINDOWEVENT_FOCUS_LOST)
    - **Song end detection**: when all events processed + song finished -> transition to RESULTS

  **Must NOT do**:
  - Do NOT implement save/load game state
  - Do NOT add transition animations

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5
  - **Blocks**: T30
  - **Blocked By**: T14

  **References**:
  - All screens: `src/exca_dance/ui/screens/*.py`
  - Audio: `src/exca_dance/audio/audio_system.py` — pause/resume
  - Game loop: `src/exca_dance/core/game_loop.py`

  **Acceptance Criteria**:
  - [ ] ESC during gameplay shows pause overlay
  - [ ] Music stops on pause, resumes correctly
  - [ ] State machine transitions between all screens correctly
  - [ ] Window focus loss triggers auto-pause

  **QA Scenarios:**
  ```
  Scenario: Pause and resume preserves game state
    Tool: interactive_bash (tmux)
    Steps:
      1. Start gameplay, play for 5 seconds, note score
      2. Press ESC (pause)
      3. Verify music stops, overlay shows
      4. Press ESC again (resume)
      5. Verify music resumes, score unchanged
    Expected Result: Score same after unpause, timing continues correctly
    Evidence: .sisyphus/evidence/task-23-pause-resume.png
  ```

  **Commit**: YES
  - Message: `feat(flow): pause/resume + game state management`
  - Files: `src/exca_dance/core/game_state.py`

---

- [x] 24. **Pose Editor: Timeline + Event Placement + Angle Editing**

  **What to do**:
  - Create `src/exca_dance/editor/editor_screen.py`:
    - `PoseEditorScreen` class:
      - **Timeline** (bottom 30% of screen):
        - Horizontal scrollable timeline synced to audio position
        - Time markers at each beat (calculated from BPM)
        - Events shown as colored dots on timeline (color = primary joint)
        - Zoom in/out (mouse wheel or +/- keys)
        - Click on timeline to set playback position
      - **Excavator preview** (top 70%):
        - Same 3D excavator + 2D panels as gameplay
        - Shows pose at current timeline position
        - When editing an event, shows target pose as ghost + current pose
      - **Event editing**:
        - Press 'N' at current position to create new event
        - Select event on timeline (click or arrow keys)
        - Selected event: use joint control keys to adjust target angles
        - Delete selected event: 'Delete' key
        - Event duration: adjustable with '[' / ']' keys
      - **Beat map metadata**:
        - Set title, artist, BPM via text input (basic, not fancy)
        - Load audio file from file dialog or typed path

  **Must NOT do**:
  - Do NOT implement undo/redo
  - Do NOT implement copy/paste events
  - Do NOT add waveform visualization
  - Do NOT add snap-to-grid (manual placement only)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T18-T23)
  - **Parallel Group**: Wave 5
  - **Blocks**: T25
  - **Blocked By**: T6, T9, T12

  **References**:
  - Beatmap: `src/exca_dance/core/beatmap.py` — BeatMap model, save/load
  - Excavator model: `src/exca_dance/rendering/excavator_model.py`
  - Audio: `src/exca_dance/audio/audio_system.py`
  - Viewport: `src/exca_dance/rendering/viewport_layout.py`

  **Acceptance Criteria**:
  - [ ] Timeline displays with beat markers at correct BPM intervals
  - [ ] New events can be placed at timeline cursor position
  - [ ] Event angles adjustable via joint control keys
  - [ ] Events deletable with Delete key
  - [ ] Excavator preview updates in real-time as angles change

  **QA Scenarios:**
  ```
  Scenario: Create and edit a beat map event
    Tool: interactive_bash (tmux)
    Steps:
      1. Open editor, load sample OGG
      2. Navigate timeline to 2.0s mark
      3. Press 'N' to create event
      4. Adjust boom angle using keyboard
      5. Screenshot: event dot visible on timeline, ghost excavator shows target
    Expected Result: Event created at 2000ms with custom boom angle
    Evidence: .sisyphus/evidence/task-24-editor-event.png
  ```

  **Commit**: YES (groups with T25)
  - Message: `feat(editor): pose editor with timeline, preview, save/load`
  - Files: `src/exca_dance/editor/editor_screen.py`

---

- [x] 25. **Pose Editor: Playback Preview + Save/Load**

  **What to do**:
  - Extend `src/exca_dance/editor/editor_screen.py`:
    - **Playback preview**:
      - Space bar: play/pause audio from current position
      - During playback, timeline cursor advances in real-time
      - Ghost excavator shows target poses as they pass (same as gameplay visual cues)
      - No scoring during preview — just visual feedback
    - **Save**:
      - Ctrl+S: save current beat map to JSON file
      - File dialog or auto-save to `assets/beatmaps/{title}.json`
      - Validate before save (warn if invalid events)
    - **Load**:
      - Ctrl+O: load existing beat map JSON
      - Populate timeline and metadata from loaded file
      - Also load the associated audio file
    - **New**:
      - Ctrl+N: create blank beat map, prompt for audio file
  - Create `src/exca_dance/editor/__init__.py`

  **Must NOT do**:
  - Do NOT implement auto-save
  - Do NOT implement undo on save

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs T24)
  - **Parallel Group**: Wave 5 (after T24)
  - **Blocks**: T30
  - **Blocked By**: T24

  **References**:
  - Editor: `src/exca_dance/editor/editor_screen.py` — extends this file
  - Beatmap: `src/exca_dance/core/beatmap.py` — save_beatmap(), load_beatmap()
  - Audio: `src/exca_dance/audio/audio_system.py`
  - Visual cues: `src/exca_dance/rendering/visual_cues.py` — reuse for preview

  **Acceptance Criteria**:
  - [ ] Space plays/pauses audio with timeline tracking
  - [ ] Ctrl+S saves valid JSON beat map
  - [ ] Saved beat map loads in game and plays correctly
  - [ ] Ctrl+O loads existing beat map into editor

  **QA Scenarios:**
  ```
  Scenario: Full editor workflow — create, save, play
    Tool: interactive_bash (tmux)
    Steps:
      1. Open editor, create new beat map
      2. Set title='Test', BPM=120, load sample OGG
      3. Add 3 events at different times with different angles
      4. Press Space to preview (audio plays, cues animate)
      5. Ctrl+S to save
      6. Exit editor, go to PLAY, find 'Test' in song list
      7. Play the song — verify events trigger at correct times
    Expected Result: Custom beat map playable in game with 3 events
    Evidence: .sisyphus/evidence/task-25-editor-roundtrip.txt
  ```

  **Commit**: YES (groups with T24)
  - Message: `feat(editor): pose editor with timeline, preview, save/load`
  - Files: `src/exca_dance/editor/*.py`

---

### Wave 6: ROS2 Integration + Final Polish (3 Tasks)

- [ ] 27. **ROS2 Node Process + IPC Queues**

  **What to do**:
  - Create `src/exca_dance/ros2_bridge/ros2_node.py`:
    - `ROS2ExcavatorNode(Node)` class:
      - Publisher: `/excavator/command` (sensor_msgs/JointState)
      - Subscriber: `/excavator/joint_states` (sensor_msgs/JointState)
      - QoS: BEST_EFFORT + VOLATILE + KEEP_LAST(5) for state subscription
      - Store latest joint states in thread-safe buffer
    - `ROS2Bridge(ExcavatorBridgeInterface)` class:
      - Implements the abstract interface from T26
      - Uses `multiprocessing.Queue` for IPC:
        - `command_queue`: game process -> ROS2 process (joint commands)
        - `state_queue`: ROS2 process -> game process (joint states)
      - `connect()`: spawn ROS2 node in subprocess via `multiprocessing.Process`
      - `disconnect()`: terminate subprocess cleanly
      - `send_command()`: put on command_queue
      - `get_current_angles()`: get from state_queue (non-blocking, use latest)
      - `is_connected()`: check if subprocess is alive
    - ROS2 subprocess entry point: init rclpy, create node, spin
    - Graceful shutdown: handle SIGTERM, call destroy_node() -> executor.shutdown() -> rclpy.shutdown()

  **Must NOT do**:
  - Do NOT import rclpy in the main game process
  - Do NOT use threading for ROS2 (must be separate process)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs T26)
  - **Parallel Group**: Wave 6
  - **Blocks**: T28
  - **Blocked By**: T26

  **References**:
  - Interface: `src/exca_dance/ros2_bridge/interface.py` — ExcavatorBridgeInterface ABC
  - Research: sensor_msgs/JointState, QoS BEST_EFFORT, multiprocessing.Queue
  - ROS2 lifecycle: destroy_node() -> executor.shutdown() -> rclpy.shutdown()

  **Acceptance Criteria**:
  - [ ] ROS2 node starts in separate process
  - [ ] `ros2 topic list` shows `/excavator/command` and `/excavator/joint_states`
  - [ ] Joint commands sent from game appear on `/excavator/command` topic
  - [ ] Joint states published on `/excavator/joint_states` appear in game

  **QA Scenarios:**
  ```
  Scenario: ROS2 bridge sends/receives (requires ROS2 environment)
    Tool: interactive_bash (tmux)
    Steps:
      1. Source ROS2 environment: source /opt/ros/{distro}/setup.bash
      2. Start game in real mode: python -m exca_dance --mode real
      3. In another terminal: ros2 topic echo /excavator/command
      4. Press keys in game to move joints
      5. Verify JointState messages appear on topic
    Expected Result: JointState messages with correct joint names and angles
    Evidence: .sisyphus/evidence/task-27-ros2-topic.txt

  Scenario: Fallback when ROS2 not available
    Tool: Bash
    Steps:
      1. python -m exca_dance --mode real (without ROS2 sourced)
    Expected Result: Warning message "ROS2 not available, falling back to virtual mode", game runs normally
    Evidence: .sisyphus/evidence/task-27-ros2-fallback.txt
  ```

  **Commit**: YES (groups with T28)
  - Message: `feat(ros2): node process, IPC, mode switching`
  - Files: `src/exca_dance/ros2_bridge/ros2_node.py`

---

- [ ] 28. **Mode Switching (Virtual ↔ Real) + Graceful Fallback**

  **What to do**:
  - Modify `src/exca_dance/ros2_bridge/__init__.py`:
    - `create_bridge(mode: str) -> ExcavatorBridgeInterface`:
      - `mode='virtual'`: return VirtualBridge()
      - `mode='real'`: try to import and create ROS2Bridge. On ImportError or connection failure -> fallback to VirtualBridge + warning
    - Lazy import of rclpy: only when mode='real' is requested
  - Integrate with GameStateManager:
    - Mode selector in Settings (T22) calls `create_bridge()`
    - Game loop uses the bridge interface generically
    - Mode indicator on HUD: "VIRTUAL" or "REAL (ROS2)" or "REAL (DISCONNECTED)"
  - Graceful degradation:
    - ROS2 process crash -> detect via is_connected() -> switch to virtual + show warning
    - ROS2 not installed -> import error caught -> virtual mode

  **Must NOT do**:
  - Do NOT require ROS2 to be installed for virtual mode

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs T27)
  - **Parallel Group**: Wave 6
  - **Blocks**: T30
  - **Blocked By**: T14, T27

  **References**:
  - Bridge interface: `src/exca_dance/ros2_bridge/interface.py`
  - ROS2 node: `src/exca_dance/ros2_bridge/ros2_node.py`
  - Game state: `src/exca_dance/core/game_state.py`
  - Settings: `src/exca_dance/ui/screens/settings.py` — mode toggle

  **Acceptance Criteria**:
  - [ ] `--mode virtual` works without ROS2
  - [ ] `--mode real` falls back gracefully if ROS2 unavailable
  - [ ] Mode indicator displays correctly on HUD
  - [ ] Mid-game ROS2 disconnect -> auto-fallback + warning

  **QA Scenarios:**
  ```
  Scenario: Graceful fallback
    Tool: Bash
    Steps:
      1. python -m exca_dance --mode real (no ROS2)
      2. Verify output contains "falling back to virtual"
      3. Verify game runs normally in virtual mode
    Expected Result: Game starts in virtual mode with warning, no crash
    Evidence: .sisyphus/evidence/task-28-graceful-fallback.txt
  ```

  **Commit**: YES (groups with T27)
  - Message: `feat(ros2): node process, IPC, mode switching`
  - Files: `src/exca_dance/ros2_bridge/__init__.py`

---

- [ ] 30. **Final Integration + Entry Point + Error Handling**

  **What to do**:
  - Complete `src/exca_dance/__main__.py`:
    - Parse CLI args: `--mode {virtual,real}`, `--fullscreen`, `--windowed`, `--debug`
    - Initialize all subsystems in order:
      1. Pygame + ModernGL (renderer)
      2. Audio system
      3. FK engine + excavator model
      4. Scoring, leaderboard, keybinding managers
      5. Bridge (based on mode)
      6. Game state manager with all screens
    - Start game loop
    - Clean shutdown on exit (save settings, close audio, terminate ROS2 process)
  - Global error handling:
    - Catch unhandled exceptions -> show error dialog -> clean exit
    - Log errors to `data/error.log`
  - Create `src/exca_dance/ui/__init__.py` and `src/exca_dance/ui/screens/__init__.py`
  - Verify full flow: Main Menu -> Song Select -> Gameplay -> Results -> Leaderboard -> Editor -> Settings
  - Run full pytest suite, fix any integration issues

  **Must NOT do**:
  - Do NOT add features not in the plan
  - Do NOT optimize prematurely (if >55fps, it's fine)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (final integration)
  - **Parallel Group**: Wave 6 (last task)
  - **Blocks**: F1-F4
  - **Blocked By**: T18-T25, T28, T29

  **References**:
  - All modules in `src/exca_dance/`
  - All test files in `tests/`
  - Constants: `src/exca_dance/core/constants.py` — SCREEN_WIDTH, SCREEN_HEIGHT, TARGET_FPS

  **Acceptance Criteria**:
  - [ ] `python -m exca_dance` launches to main menu in < 5 seconds
  - [ ] Full gameplay flow works end-to-end
  - [ ] `pytest tests/ -v` all pass
  - [ ] Clean exit on Ctrl+C
  - [ ] Error log written on crash

  **QA Scenarios:**
  ```
  Scenario: Full end-to-end flow
    Tool: interactive_bash (tmux)
    Steps:
      1. python -m exca_dance
      2. Main Menu -> PLAY -> Select song 1 -> Play through (30 seconds)
      3. Results screen -> SAVE SCORE -> Enter "AAA"
      4. Back to Menu -> LEADERBOARD -> Verify "AAA" appears
      5. SETTINGS -> Change boom key -> Back
      6. EDITOR -> Load sample -> Add event -> Save -> Back
      7. QUIT
    Expected Result: All transitions work, no crashes, data persists
    Evidence: .sisyphus/evidence/task-30-full-flow.txt

  Scenario: Clean exit on error
    Tool: Bash
    Steps:
      1. Delete assets/music/ directory
      2. python -m exca_dance
      3. Navigate to PLAY -> Select song
    Expected Result: Error message about missing audio, no crash, error logged
    Evidence: .sisyphus/evidence/task-30-error-handling.txt
  ```

  **Commit**: YES
  - Message: `feat: final integration, entry point, error handling`
  - Files: `src/exca_dance/__main__.py, src/exca_dance/ui/__init__.py, src/exca_dance/ui/screens/__init__.py`
  - Pre-commit: `python -m exca_dance --help`
## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns (e.g., `get_pos()`, `.blit(`, `import ursina`) — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `python -m py_compile` on all source files + `pytest tests/ -v` + `ruff check src/`. Review all files for: empty except blocks, print() in production, unused imports, hardcoded paths. Check for AI slop: excessive docstrings, over-abstraction, generic variable names.
  Output: `Build [PASS/FAIL] | Tests [N pass/N fail] | Lint [N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start game from clean state. Execute EVERY QA scenario from EVERY task. Test full flow: Main Menu → Song Select → Gameplay → Results → Leaderboard → Editor. Test edge cases: pause during gameplay, empty beat map, corrupted leaderboard JSON, missing audio file. Save evidence to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read spec, read actual code. Verify 1:1 match. Check "Must NOT Have" compliance — search for forbidden patterns. Detect scope creep: features not in plan. Flag unaccounted files/modules.
  Output: `Tasks [N/N compliant] | Forbidden [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Wave | Commit | Message | Files | Pre-commit |
|------|--------|---------|-------|------------|
| 1 | T1 | `spike: validate Pygame+ModernGL+audio coexistence` | spike.py | python spike.py |
| 1 | T2+T3 | `init: project structure, deps, data models` | pyproject.toml, src/exca_dance/**, tests/ | pip install -e . |
| 2 | T4 | `feat(kinematics): forward kinematics engine with tests` | kinematics.py, test_kinematics.py | pytest tests/test_kinematics.py |
| 2 | T5 | `feat(scoring): judgment windows, combo system with tests` | scoring.py, test_scoring.py | pytest tests/test_scoring.py |
| 2 | T6 | `feat(beatmap): JSON parser with schema validation and tests` | beatmap.py, test_beatmap.py | pytest tests/test_beatmap.py |
| 2 | T7 | `feat(leaderboard): persistent JSON storage with tests` | leaderboard.py, test_leaderboard.py | pytest tests/test_leaderboard.py |
| 2 | T8 | `feat(keybinding): configurable key mapping with tests` | keybinding.py, test_keybinding.py | pytest tests/test_keybinding.py |
| 2 | T9 | `feat(renderer): ModernGL setup, GL text, viewport manager` | renderer.py, gl_text.py, viewport.py | python -c "from exca_dance.renderer import *" |
| 2 | T12 | `feat(audio): OGG playback with perf_counter sync` | audio.py | python -c "from exca_dance.audio import *" |
| 3 | T10+T11 | `feat(viz): 3D excavator + multi-viewport layout` | excavator_model.py, viewport_layout.py | python -c "from exca_dance.excavator_model import *" |
| 3 | T13 | `style: neon/cyberpunk theme colors and glow` | theme.py | — |
| 3 | T26 | `feat(ros2): abstract bridge interface layer` | ros2_interface.py | pytest tests/test_ros2_interface.py |
| 3 | T29 | `content: 2 sample BGMs + beat maps` | assets/music/**, assets/beatmaps/** | python -c "from exca_dance.beatmap import load; load('assets/beatmaps/sample1.json')" |
| 4 | T14-T17 | `feat(core): game loop, visual cues, hit detection, HUD` | game_loop.py, visual_cues.py, hit_detection.py, hud.py | python -m exca_dance --test-gameplay |
| 5 | T18-T22 | `feat(ui): menu, song select, results, leaderboard, settings screens` | screens/*.py | python -m exca_dance |
| 5 | T23 | `feat(flow): pause/resume + game state management` | game_state.py | — |
| 5 | T24+T25 | `feat(editor): pose editor with timeline, preview, save/load` | editor/*.py | — |
| 6 | T27+T28 | `feat(ros2): node process, IPC, mode switching` | ros2_node.py, ros2_bridge.py | — |
| 6 | T30 | `feat: final integration, entry point, error handling` | __main__.py | python -m exca_dance |

---

## Success Criteria

### Verification Commands
```bash
# 의존성 설치
pip install -e ".[dev]"

# 테스트 스위트
pytest tests/ -v  # Expected: all pass

# 린트
ruff check src/  # Expected: 0 errors

# 게임 실행
python -m exca_dance  # Expected: 메인 메뉴 표시 < 5초

# ROS2 모드 (ROS2 환경에서만)
python -m exca_dance --mode real  # Expected: ROS2 노드 시작 또는 graceful fallback
```

### Final Checklist
- [ ] 모든 "Must Have" 구현됨
- [ ] 모든 "Must NOT Have" 위반 없음
- [ ] `pytest tests/ -v` 전체 통과
- [ ] 메인 메뉴 → 곡 선택 → 게임플레이 → 결과 → 리더보드 풀 플로우
- [ ] 리더보드 영구 저장 검증 (재시작 후 데이터 유지)
- [ ] 자세 편집기 → 비트맵 생성 → 게임 플레이 가능
- [ ] 60fps 이상 안정 프레임레이트
- [ ] ROS2 없이 가상 모드 정상 동작
