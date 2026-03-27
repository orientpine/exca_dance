# 아키텍처 — 시스템 와이어링

> **목적**: exca_dance 프로젝트의 전체 아키텍처, 서브시스템 생성 순서, 메인 루프, 핵심 설계 원칙을 기술한다.

---

## 프로젝트 개요

**exca_dance**는 DDR 스타일 리듬 게임으로, 플레이어가 3D 굴착기의 4개 관절(swing/boom/arm/bucket)을 BGM 비트에 맞춰 조작하여 목표 자세를 맞추는 교육용 시뮬레이터이다.

### 기술 스택

| 영역 | 기술 | 버전 |
|------|------|------|
| 언어 | Python | 3.10+ |
| 윈도우/입력 | pygame-ce | ≥2.4 |
| 3D 렌더링 | ModernGL | ≥5.10 |
| GL 바인딩 | PyOpenGL | ≥3.1 |
| 수학/행렬 | NumPy | ≥1.24 |
| ROS2 (옵션) | rclpy + sensor_msgs | ROS2 환경별 |

---

## 디렉토리 구조

```
src/exca_dance/
├── __main__.py          # 진입점: 모든 서브시스템 생성 + pygame 루프 실행
├── core/                # 게임 로직, 데이터 모델, 상수
├── rendering/           # ModernGL 셰이더, 3D 모델, 뷰포트, 테마
├── ui/
│   ├── gameplay_hud.py  # 점수/콤보/진행바 오버레이
│   └── screens/         # 8개 스크린 (duck-typed)
├── audio/               # perf_counter 기반 타이밍
├── editor/              # 포즈 에디터 스크린
├── ros2_bridge/         # ROS2 인터페이스 (서브프로세스 전용)
└── utils/               # (비어 있음)
tests/                   # 56개 테스트
assets/beatmaps/         # JSON 비트맵 파일
```

---

## 서브시스템 생성 순서 (`__main__.py:main()`)

모든 서브시스템은 `main()` 함수에서 수동 생성되며, DI 컨테이너나 레지스트리 없이 직접 와이어링된다.

```
1.  pygame.init()
2.  GameRenderer(W, H)           → renderer
3.  GLTextRenderer(renderer)     → text_renderer
4.  AudioSystem()                → audio
5.  Sound 파일 로딩              → hit_sounds
6.  ExcavatorFK()                → fk
7.  ScoringEngine()              → scoring
8.  KeyBindingManager()          → keybinding
9.  LeaderboardManager()         → leaderboard
10. create_bridge(mode)          → bridge
11. ExcavatorModel(renderer, fk) → excavator_model
12. GameViewportLayout(renderer) → viewport_layout
13. GameLoop(renderer, audio, fk, scoring, keybinding, bridge, viewport_layout, excavator_model)
14. VisualCueRenderer(renderer, ExcavatorModel, fk)    → visual_cues
15. Overlay2DRenderer(renderer, fk)                    → overlay_2d
16. GameplayHUD(renderer, text_renderer, audio, scoring, visual_cues) → hud
17. 8개 스크린 등록 → GameStateManager
18. 메인 루프 시작
```

---

## 메인 루프

```python
while running:
    # 1. 이벤트 처리
    for event in pygame.event.get():
        state_mgr.handle_event(event)

    # 2. 업데이트
    dt = clock.tick(TARGET_FPS) / 1000.0
    result = state_mgr.update(dt)

    # 3. 렌더
    renderer.begin_frame()
    state_mgr.render(renderer, text_renderer)
    if state_mgr.is_transitioning:
        _draw_fade_overlay(renderer, state_mgr.fade_alpha)
    renderer.end_frame()
```

---

## 서브시스템 관계도

```
┌──────────────────────────────────────────────────────────────┐
│                       __main__.py                             │
│  (모든 서브시스템 생성 + pygame 메인 루프)                        │
└───────────────────────┬──────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
  GameStateManager   GameRenderer    AudioSystem
   (스크린 전환)      (GL 컨텍스트)   (perf_counter)
        │               │               │
        ▼               ▼               ▼
  8개 Screen  ←→  ViewportLayout   GameLoop
  (duck-typed)    ExcavatorModel   (tick→비트체크→스코어링)
        │          VisualCues          │
        │          GLTextRenderer      │
        ▼               │              ▼
   GameplayHUD  ←───────┘     ScoringEngine
   (2D 오버레이)                ExcavatorFK
                               KeyBindingManager
                               ROS2 Bridge
```

---

## 핵심 설계 원칙

- **No DI Container**: 모든 와이어링은 `__main__.py:main()`에서 수동으로 이루어짐
- **GameLoop는 서비스**: 스크린이 아닌 서비스 객체 — `GameplayScreen`만이 `tick(dt)` 호출
- **스크린은 Duck-typed**: 기반 클래스 없음, 4개 메서드 프로토콜만 충족하면 됨
- **렌더링은 전부 OpenGL**: `surface.blit()` 등 pygame 2D 렌더링 금지
- **새 서브시스템 추가 시**: `__main__.py:main()`에서 생성 순서에 맞게 삽입

---

## 관련 스킬 문서

| 스킬 | 파일 | 관련 내용 |
|------|------|-----------|
| Python 컨벤션 | `skills/python-conventions.md` | 임포트, 타입, 코드 스타일 |
| Core 게임 로직 | `skills/core-game-logic.md` | 모델, 상수, 스코어링, FK |
| 렌더링 파이프라인 | `skills/rendering-pipeline.md` | ModernGL, 셰이더, VBO |
| 오디오 타이밍 | `skills/audio-timing.md` | perf_counter, 비트 체크 |
| UI 스크린 | `skills/ui-screens.md` | 스크린 프로토콜, HUD |
| ROS2 브릿지 | `skills/ros2-bridge.md` | 서브프로세스 격리 |
