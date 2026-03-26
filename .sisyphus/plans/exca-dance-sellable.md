# Exca Dance — 판매 가능 수준 개발 계획

> **목표**: DDR-style 굴착기 리듬 게임을 판매 가능한 수준의 게임성·그래픽·안정성으로 끌어올린다.
> **방법**: Impact-Effort 기반 5-Phase 반복 개발 루프
> **예상 기간**: 2–3주 (프롬프트 ~13개, overhaul에서 2개 제거)
> **ROS2 호환성**: 검토 완료 — Task 2-3(이징) 제거됨 (§8 참조)
> **중복 제거**: gameplay-screen-overhaul.md와 대조 완료 — Task 1-1, 1-2 제거됨

---

## 1. 현황 진단 (Sellability Audit)

### 1.1 점수표

| 영역 | 현재 | 목표 | 갭 요약 |
|------|:----:|:----:|---------|
| 기능 완성도 | 8/10 | 9/10 | 튜토리얼·난이도 시스템 부재 |
| 그래픽 | 5/10 | 7.5/10 | 박스 프리미티브, 포스트프로세싱 無, 게임플레이 배경 없음 |
| 오디오 | 4/10 | 7/10 | SFX 4개 파일 존재하나 연결 안 됨 (무음 게임플레이), 곡 2개뿐 |
| 게임성 | 7/10 | 8/10 | 스코어링 견고, 노트 하이웨이·비주얼 피드백 부재 |
| UI/UX 폴리시 | 5/10 | 8/10 | 메인메뉴만 화려, 나머지는 텍스트 나열 |
| 버그 | 9/10 | 9.5/10 | ghost glow VBO 포맷 불일치, TOCTOU 경쟁 상태 1건 |
| 테스트 | 6/10 | 7/10 | 코어 로직만 56건, 렌더링/UI/오디오 0건 |

### 1.2 핵심 발견

- **SFX 미연결**: `assets/sounds/`에 `hit_perfect.wav` 등 4개 파일 존재. `AudioSystem`에 `load_sfx()`/`play_sfx()` 메서드도 구현됨. **하지만 코드 어디에서도 호출하지 않음** → 완전 무음 게임플레이.
- **굴착기 3D 모델**: 박스 5개 = 총 ~180 vertices, 60 triangles. 단일 디렉셔널 라이트(Lambert diffuse, ambient=0.35). 스페큘러·쉐도우 없음.
- **메인메뉴 vs 게임플레이 격차**: 메인메뉴는 9-layer 렌더 파이프라인(파티클, 글로우, 어센트 라인, 펄싱 타이틀). 게임플레이는 어두운 공허에 박스만 보임.
- **화면 전환 없음**: 모든 화면이 즉시 컷(instant cut).
- **콘텐츠 부족**: 곡 2개(각 ~40초), 난이도 선택 없음.
- **ghost glow 버그**: `visual_cues.py:72`에서 VBO를 `reshape(-1, 6)`으로 읽지만 실제 모델은 9 floats/vertex → glow가 렌더링되지 않음.
- **TOCTOU 경쟁 상태**: `gameplay_screen.py:66-68`에서 `get_upcoming_events(500)`을 두 번 호출 → 사이에 리스트 비어질 수 있음.

### 1.3 이미 갖추어진 것 (판매 가능 기반)

- 완전한 게임 플로우: Menu → Song Select → Gameplay → Results → Leaderboard
- 견고한 스코어링/콤보 (PERFECT/GREAT/GOOD/MISS, 콤보 배율, S~F 등급)
- 3-패널 뷰포트 (3D 투시 + 탑다운 + 사이드)
- 영구 리더보드 + 키 바인딩 저장
- 사이버펑크 네온 테마 (일관된 색상 팔레트)
- 포즈 에디터 (사용자 비트맵 제작)
- ROS2 브릿지 (교육용 실제 굴착기 연결)
- 깨끗한 코드베이스 (TODO/FIXME 0건, 테스트 전부 통과)

---

## 2. 기술 컨텍스트 (프롬프트 작성 시 참조)

### 2.1 아키텍처 요약

```
src/exca_dance/
├── __main__.py           # 유일한 와이어링 포인트 (DI 없음, 수동 조립)
├── core/                 # 게임 로직, 데이터 모델, 상수
│   ├── game_loop.py      # GameLoop — tick(), 비트 체크, 곡 종료
│   ├── scoring.py        # ScoringEngine — 판정, 콤보, 등급
│   ├── kinematics.py     # ExcavatorFK — 4관절 순운동학
│   ├── beatmap.py        # BeatMap JSON 로드/저장/검증
│   ├── game_state.py     # GameStateManager + ScreenName enum
│   ├── hit_detection.py  # JudgmentDisplay — 애니메이션 텍스트
│   ├── leaderboard.py    # 영구 저장 (JSON)
│   └── keybinding.py     # 키 바인딩 매니저
├── rendering/
│   ├── renderer.py       # GameRenderer — ModernGL 컨텍스트, 3개 셰이더
│   ├── excavator_model.py# ExcavatorModel — FK로부터 3D 지오메트리
│   ├── viewport_layout.py# 3-패널 MVP 매트릭스, 데코레이션, 그리드
│   ├── visual_cues.py    # VisualCueRenderer — 고스트, 타임라인
│   ├── theme.py          # NeonTheme — 색상 상수 (팔레트 전용)
│   ├── gl_text.py        # GLTextRenderer — pygame.font → GL 텍스처
│   └── render_math.py    # 수학 유틸리티
├── ui/
│   ├── gameplay_hud.py   # 스코어/콤보/진행바/조인트 상태
│   └── screens/          # Duck-typed 스크린 (7개)
├── audio/
│   └── audio_system.py   # BGM + SFX (perf_counter 타이밍)
└── editor/
    └── editor_screen.py  # 포즈 에디터
```

### 2.2 셰이더 프로그램

| 프로그램 | VBO 레이아웃 | 유니폼 | 용도 |
|---------|-------------|--------|------|
| `prog_solid` | `3f 3f 3f` (pos, color, normal) | `mvp: mat4`, `alpha: float` | 3D 지오메트리, 그리드, HUD 사각형 |
| `prog_tex` | `2f 2f` (pos, uv) | `screen_size`, `pos`, `size`, `tex`, `color` | GL 텍스트 |
| `prog_additive` | `3f 4f` (pos, color) | `mvp: mat4` | 글로우/네온 (additive blend) |

### 2.3 스크린 프로토콜

```python
class MyScreen:
    def on_enter(self, **kwargs) -> None: ...
    def handle_event(self, event) -> str | tuple | None: ...
    def update(self, dt: float) -> str | tuple | None: ...
    def render(self, renderer, text_renderer) -> None: ...
```

전환: `"screen_name"` 또는 `("screen_name", {"key": value})` 반환. `"quit"`은 메인 루프 종료.

### 2.4 절대 규칙 (Anti-Patterns)

```python
# 금지 — 타이밍 드리프트
pygame.mixer.music.get_pos()

# 금지 — pygame 이벤트 루프 충돌
import ursina

# 금지 — 모든 렌더링은 OpenGL
surface.blit(...)

# 금지 — 타입 에러 억제 (코드베이스에 0건, 유지할 것)
# type: ignore / # noqa

# 금지 — ROS2 노드 메인 프로세스 임포트
from exca_dance.ros2_bridge.ros2_node import ROS2ExcavatorNode
```

### 2.5 컨벤션

- `from __future__ import annotations` — 모든 파일 최상단
- 완전한 도티드 임포트: `from exca_dance.rendering.renderer import GameRenderer`
- `time.perf_counter()` — 모든 타이밍 (pygame clock은 게임 로직에 사용 금지)
- 각도는 **degrees** (radians는 `kinematics.py` 내부만)
- Numpy → GL: `np.ascontiguousarray(mat.astype("f4").T).tobytes()`
- 라인 길이: 100자 (ruff 강제)

### 2.6 명령어

```bash
# 테스트 (플러그인 플래그 필수)
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v

# 린트
.venv/bin/ruff check src/ tests/
.venv/bin/ruff format src/ tests/

# 실행
python -m exca_dance              # 풀스크린
python -m exca_dance --windowed   # 창모드
```

---

## 3. Phase 별 작업 계획

### Phase 1 — Critical Fixes (Wave 1)

> **목적**: 게임이 "제대로 작동"하는 상태로 만든다.
> **예상 기간**: 0.5일 (overhaul에서 2개 제거, TOCTOU만 남음)
> **선행 조건**: 없음

#### ~~Task 1-1: SFX 연결~~ — gameplay-screen-overhaul T4에서 수행됨

> **제거 사유**: `gameplay-screen-overhaul.md` T4 (Wire hit sound effects on judgment)이
> 동일한 작업을 수행함. pygame.mixer.Sound로 히트 사운드를 연결하고
> GameplayScreen에서 판정 시 재생하는 것까지 포함.

#### ~~Task 1-2: Ghost Glow VBO 포맷 버그 수정~~ — gameplay-screen-overhaul T1에서 수행됨

> **제거 사유**: `gameplay-screen-overhaul.md` T1 (Fix VBO stride bug in ghost glow rebuild)이
> 동일한 버그를 수정함. reshape(-1, 9) + downstream glow_data 구성 수정 포함.

#### Task 1-3: TOCTOU 경쟁 상태 수정

- **파일**: `ui/screens/gameplay_screen.py`
- **내용**: 라인 66-68에서 `get_upcoming_events(500)`을 **한 번만** 호출 → 변수에 저장 → 재사용
- **제약**: 스코어링 로직 변경 금지.
- **TDD**: `tests/test_gameplay_screen.py` 작성 — `get_upcoming_events()`가 빈 리스트 반환할 때 `update(dt)` 호출 시 예외 없음을 assert
- **검증**:
  1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` → 전부 통과
  2. 수동: 빈 비트맵(events=[])으로 게임플레이 진입 → 크래시 없음

---

### Phase 2 — Game Feel (Wave 2)

> **목적**: 게임이 "플레이하면 재미있는" 상태로 만든다.
> **예상 기간**: 2–3일
> **선행 조건**: Phase 1 완료

#### Task 2-1: 판정 시각 피드백 강화

- **파일**: `ui/gameplay_hud.py`, `core/hit_detection.py`
- **내용**:
  1. PERFECT 판정 시 화면 전체 짧은 flash (50ms, 흰색 alpha 0.15)
  2. 판정 텍스트에 scale 애니메이션 (1.5→1.0, 0.3초 ease-out)
  3. 콤보 10/25/50 달성 시 특별 시각 효과 (색상 변경 + 스케일 펌프)
  4. MISS 시 화면 살짝 빨간색 flash (30ms, red alpha 0.08)
- **제약**: 기존 `prog_solid`, `prog_additive` 셸이더만 사용. 새 셸이더 추가 금지.
- **TDD**: `tests/test_hit_detection.py` 작성 — `JudgmentDisplay.trigger(PERFECT, combo=1)` 후 `flash_alpha > 0` assert; `trigger(MISS, combo=0)` 후 `flash_color == RED` assert
- **검증**:
  1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` → 전부 통과
  2. `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed` → exit 0
  3. 수동: 게임 실행 → PERFECT/MISS 시 화면 flash 확인

#### Task 2-2: 화면 전환 시스템

- **파일**: `core/game_state.py`, `__main__.py`
- **내용**:
  1. `GameStateManager`에 fade-to-black 전환 (0.3초 out → 0.3초 in)
  2. `transition_to()` 내에서 페이드 상태 관리
  3. 렌더링: 현재 화면 위에 검은 오버레이를 alpha 0→1→0
  4. `prog_solid` + identity MVP 전체 화면 쿼드
- **제약**: Screen protocol (duck-typed 4-method) 변경 금지. `__main__.py` 메인 루프의 `state_mgr.render()` 호출 부분만 수정.
- **TDD**: `tests/test_game_state.py` 작성 — `GameStateManager.transition_to()` 호출 후 `is_transitioning == True` assert; 0.6초 경과 후 `is_transitioning == False` assert
- **검증**:
  1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` → 전부 통과
  2. `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed` → exit 0
  3. 수동: 메뉴 → 곡 선택 → 게임플레이 전환 시 페이드 확인

#### ~~Task 2-3: 조인트 움직임 이징~~ — ROS2 호환성 사유로 제거

> **제거 사유**: 실제 굴착기 연동 시 `self._joint_angles`는 `bridge.get_current_angles()`
> (실제 센서 데이터)에서 와야 한다. `_update_joints()`에 이징(가속/감속)을 주입하면:
> 1. 실제 모드에서 센서 데이터와 소프트웨어 이징이 충돌
> 2. virtual/real 모드 간 조작 체감이 달라져 학습 전이 효과 저해
> 3. 실제 굴착기 유압 시스템이 자체적으로 물리적 가감속을 제공 — 소프트웨어 이징 불필요
> 4. 현재의 60deg/s 선형 움직임이 오히려 실제 조이스틱 응답에 더 가까움
#### Task 2-4: 비트 타임라인 개선 (노트 하이웨이)

> **참고**: `gameplay-screen-overhaul.md` T3이 기존 `render_timeline()`을 `gameplay_screen.py`에
> 연결(wiring)하는 작업을 완료함. 본 태스크는 텍스트 도트 방식을 **시각적 노트 하이웨이로 재설계**하는 것.

- **파일**: `rendering/visual_cues.py`
- **내용**:
  1. 화면 하단 수평 바 (높이 60px, 화면 폭 75%)
  2. 다가오는 이벤트 → 네온 컬러 사각형, 우→좌 스크롤
  3. 현재 타이밍 위치에 밝은 수직선 (히트 라인)
  4. 이벤트가 히트 라인에 가까울수록 밝아지는 효과
  5. `target_angles` 포함 조인트 수에 따라 사각형 크기 변경
- **제약**: `prog_solid` + `prog_additive`만 사용. 매 프레임 VBO 생성/파괴 기존 패턴 준수.
- **TDD**: `tests/test_visual_cues.py`에 추가 — `render_timeline()` 호출 시 예외 없음 assert; upcoming_events=[] 일 때도 크래시 없음 assert
- **검증**:
  1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` → 전부 통과
  2. `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed` → exit 0
  3. 수동: 게임 실행 → 하단 노트 하이웨이 스크롤 확인

---

### Phase 3 — Visual Polish (Wave 3)

> **목적**: 게임이 "보기에 예쁜" 상태로 만든다.
> **예상 기간**: 4–5일
> **선행 조건**: Phase 2 완료

#### Task 3-1: 굴착기 지오메트리 개선

- **파일**: `rendering/excavator_model.py`, `rendering/render_math.py`
- **내용**:
  1. 붐/암/버킷 링크 → 팔각기둥(octagonal prism)으로 교체
  2. 베이스에 트랙(궤도) 형상 추가 (낮은 직육면체 2개)
  3. 터렛에 캡(운전실) 형상 추가 (작은 직육면체)
  4. 각 조인트 연결부에 원통형 관절 표시
  5. `_make_link_verts()`에 옆면 수 파라미터 추가
- **제약**: VBO 레이아웃 `pos(3)+color(3)+normal(3)` = 9 floats/vertex 유지. 기존 셸이더 호환 필수.
- **TDD**: `tests/test_render_math.py`에 추가 — 팔각기둥 생성 함수의 vertex 수 = `sides * 12` assert; 보문 생성 후 `ExcavatorModel._vertex_count > 180` assert (180 = 기존 박스 모델)
- **검증**:
  1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` → 전부 통과
  2. `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed` → exit 0
  3. 수동: 게임 실행 → 굴착기 둥글어진 모양 확인

#### Task 3-2: 게임플레이 배경 및 환경

- **파일**: `rendering/viewport_layout.py`, `ui/screens/gameplay_screen.py`
- **내용**:
  1. 3D 뷰포트에 Z=0 지면 그리드 (`main_menu.py`의 `_build_grid`와 유사, neon blue)
  2. 비트에 맞춰 그리드 라인 펄스 (BPM 동기화)
  3. 3D 뷰포트 배경에 장식적 네온 링/원
  4. `viewport_layout.py`에 gameplay 전용 배경 렌더 메서드 추가
- **제약**: `gameplay_screen.py`의 `render()`에서 excavator 렌더 전에 호출. 카메라 위치 변경 금지.
- **TDD**: `tests/test_viewport_layout.py` 작성 — `render_gameplay_background()` 메서드 존재 확인; mock renderer로 호출 시 예외 없음 assert
- **검증**:
  1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` → 전부 통과
  2. `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed` → exit 0
  3. 수동: 게임 실행 → 3D 뷰에 지면 그리드 + 비트 동기 펄스 확인

#### Task 3-3: 포스트프로세싱 블룸

- **파일**: `rendering/renderer.py` (새 FBO/셰이더 추가)
- **내용**:
  1. 메인 렌더를 FBO에 먼저 렌더
  2. 밝은 픽셀 추출 threshold pass (brightness > 0.7)
  3. 2-pass Gaussian blur (가로→세로), 다운샘플
  4. 원본 + 블러 밝은 부분 additive 합성 → 최종 출력
  5. on/off 토글 (Settings에서 조정 가능)
- **제약**: 기존 3개 셸이더 프로그램은 수정 금지 (새 프로그램 추가). `renderer.py`의 `begin_frame()`/`end_frame()` 시그니처 변경 최소화.
- **TDD**: `tests/test_bloom.py` 작성 — bloom on/off 토글 시 `renderer.bloom_enabled` 상태 변경 assert; FBO 생성 확인 (headless에서 `ctx.framebuffer()` 반환값 존재 assert)
- **검증**:
  1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` → 전부 통과
  2. `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed` → exit 0
  3. 수동: 블룸 on → 네온 요소 빛 번짐 확인. off 시 기존과 동일. FPS 60 유지 확인.

---

### Phase 4 — Content & Features (Wave 4)

> **목적**: 게임이 "콘텐츠가 충분한" 상태로 만든다.
> **예상 기간**: 3–4일
> **선행 조건**: Phase 3 완료 (독립 작업 가능한 태스크 있음)

#### Task 4-1: 튜토리얼 화면

- **파일**: 신규 `ui/screens/tutorial_screen.py`, `core/game_state.py`, `__main__.py`, `ui/screens/main_menu.py`
- **내용**:
  1. `ScreenName.TUTORIAL` 추가
  2. 4단계 인터랙티브 튜토리얼:
     - Step 1: "굴착기에는 4개의 관절이 있습니다" + 각 관절 하이라이트
     - Step 2: 키 입력으로 각 관절 직접 움직여보기
     - Step 3: "유령을 따라하세요" + 연습 이벤트 3개
     - Step 4: "준비 완료!" + 메뉴 복귀
  3. 메인메뉴에 "HOW TO PLAY" 항목 추가 (PLAY 아래)
- **제약**: Screen protocol (duck-typed 4-method) 준수. 기존 `ExcavatorModel`, `ExcavatorFK` 재사용.
- **TDD**: `tests/test_tutorial.py` 작성 — `TutorialScreen`이 4-method protocol 준수 assert; `on_enter()` 후 step=1 assert; 각 step에서 handle_event으로 다음 단계 이동 가능 assert
- **검증**:
  1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` → 전부 통과
  2. `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed` → exit 0
  3. 수동: 메뉴 → HOW TO PLAY → 4단계 진행 → 메뉴 복귀 확인

#### Task 4-2: 난이도 시스템

- **파일**: `core/models.py`, `core/scoring.py`, `core/beatmap.py`, `ui/screens/song_select.py`
- **내용**:
  1. `BeatMap`에 `difficulty: str` 필드 추가 (기본값 "NORMAL")
  2. `ScoringEngine`에 난이도별 판정 윈도우:
     - EASY: PERFECT ±50ms, GREAT ±100ms, GOOD ±170ms
     - NORMAL: 현재값 유지 (35/70/120)
     - HARD: PERFECT ±25ms, GREAT ±50ms, GOOD ±90ms
  3. Song Select에서 같은 곡의 난이도별 비트맵 그룹 표시
  4. 기존 `sample1.json`, `sample2.json`에 `"difficulty": "NORMAL"` 추가
- **제약**: 기존 점수 계산 공식 (base_score × accuracy × combo_mult) 변경 금지. 판정 윈도우만 조정.
- **TDD**: `tests/test_scoring.py`에 추가 — `ScoringEngine(difficulty="EASY")` 생성 후 timing_error=45ms에서 PERFECT 판정 assert (NORMAL은 GREAT); `difficulty="HARD"` 생성 후 timing_error=30ms에서 GREAT 판정 assert (NORMAL은 PERFECT)
- **검증**:
  1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` → 전부 통과 (신규 + 기존 scoring 테스트 모두)
  2. 수동: EASY/NORMAL/HARD 각각 플레이 → 판정 난이도 체감 확인

#### Task 4-3: Settings 볼륨 기능 구현

- **파일**: `ui/screens/settings_screen.py`, `audio/audio_system.py`
- **내용**:
  1. 좌/우 키로 볼륨 조절 (10% 단위)
  2. `AudioSystem`에 `set_bgm_volume()`, `set_sfx_volume()` 메서드 추가/활용
  3. 변경 즉시 반영
  4. 볼륨 설정 영구 저장 (keybinding과 유사한 JSON)
- **TDD**: `tests/test_volume.py` 작성 — `AudioSystem.set_bgm_volume(0.5)` 후 `get_bgm_volume() == 0.5` assert; 저장/로드 후 값 유지 assert
- **검증**:
  1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` → 전부 통과
  2. 수동: Settings → 볼륨 조절 → 게임 종료 → 재시작 → 볼륨 유지 확인

#### Task 4-4: Pause 메뉴 개선

- **파일**: `ui/screens/gameplay_screen.py`
- **내용**:
  1. ESC 시 현재 텍스트 2줄 → 정식 오버레이 패널
  2. 배경 어둡게 (반투명 검정 오버레이)
  3. 메뉴 항목: RESUME / RESTART / SETTINGS / QUIT TO MENU
  4. 상/하 키로 선택, Enter로 확인
- **제약**: `LoopState.PAUSED` 기존 상태 활용. 별도 스크린으로 분리하지 않음 (게임플레이 스크린 내부에서 처리).
- **TDD**: `tests/test_gameplay_screen.py`에 추가 — paused 상태에서 `_pause_selected` 초기값=0 assert; UP/DOWN 이벤트 시 선택 인덱스 변경 assert
- **검증**:
  1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` → 전부 통과
  2. `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed` → exit 0
  3. 수동: 게임 중 ESC → 정식 메뉴 표시 → 각 옵션 동작 확인

---

### Phase 5 — Distribution Ready (Wave 5)

> **목적**: 게임이 "배포·판매 가능한" 상태로 만든다.
> **예상 기간**: 2–3일
> **선행 조건**: Phase 1–4 완료

#### Task 5-1: 오디오 최적화

- **파일**: `assets/music/`, `assets/sounds/`, `audio/audio_system.py`
- **내용**:
  1. WAV → OGG 변환 (ffmpeg 사용)
  2. `AudioSystem`에서 OGG 포맷 지원 확인
  3. 비트맵 JSON의 `audio_file` 경로 업데이트
- **효과**: ~11MB → ~1.5MB 예상 (오디오 파일 크기 90% 감소)
- **검증**:
  1. `ffprobe assets/music/sample1.ogg` → 코덱 vorbis, 샘플레이트 44100 확인
  2. `du -sh assets/music/` → 2MB 미만
  3. `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 10 python -m exca_dance --windowed` → exit 0 (오디오 로드 크래시 없음)
  4. 수동: 게임 실행 → 재생 품질 동일 + 타이밍 드리프트 없음 확인

#### Task 5-2: PyInstaller 패키징

- **파일**: 신규 `exca_dance.spec`, `pyproject.toml` 수정
- **내용**:
  1. Windows + Linux 빌드용 PyInstaller spec 파일
  2. `assets/` 폴더 전체 번들링
  3. 아이콘 파일 포함
  4. 원클릭 실행 파일 생성
- **검증**:
  1. `pyinstaller exca_dance.spec` → exit 0
  2. `ls -lh dist/exca_dance` → 실행 파일 존재
  3. `dist/exca_dance --windowed` → 게임 실행 확인 (assets 번들링 포함)

#### Task 5-3: 최종 QA 및 폴리시

- **내용**:
  1. 전체 게임 플로우 End-to-End 테스트
  2. 모든 화면 전환 확인
  3. 메모리 누수 체크 (VBO 생성/파괴 패턴)
  4. 60fps 안정성 확인
  5. 에지 케이스: 빈 비트맵, 오디오 없는 비트맵, 0점 결과, 리더보드 만석
- **검증**:
  1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` → 전부 통과 (최종)
  2. `.venv/bin/ruff check src/ tests/` → 린트 클린
  3. `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 30 python -m exca_dance --windowed` → 30초간 크래시 없음
  4. 수동: 전체 플로우 3회 반복 → 크래시/글리치 0건

---

## 4. 의존성 그래프

```
Phase 1 ─────────────────────────────────┐
  ~~Task 1-1 (SFX)~~       ─ overhaul T4  │
  ~~Task 1-2 (Ghost)~~     ─ overhaul T1  │
  Task 1-3 (TOCTOU 수정)    ─ 독립     │
                                         ▼
Phase 2 ─────────────────────────────────┐
  Task 2-1 (판정 피드백)  ─ 독립         │
  Task 2-2 (화면 전환)    ─ 독립         │
  Task 2-4 (노트 하이웨이) ─ 독립        │
                                         ▼
  Phase 3 ─────────────────────────────────┐
  Task 3-1 (지오메트리)   ─ 독립         │
  Task 3-2 (배경)         ─ 독립         │
  Task 3-3 (블룸)         ─ 독립         │
                                         ▼
  Phase 4 ─────────────────────────────────┐
  Task 4-1 (튜토리얼)     ─ 독립         │
  Task 4-2 (난이도)        ─ 독립         │
  Task 4-3 (볼륨)          ─ 독립         │
  Task 4-4 (Pause)         ─ 독립         │
                                         ▼
  Phase 5 ─────────────────────────────────
  Task 5-1 (오디오 최적화) ─ 독립
  Task 5-2 (패키징)        ← 모든 Phase 완료
  Task 5-3 (최종 QA)       ← Task 5-2

> **병렬 실행 가능**: 같은 Phase 내 "독립" 태스크는 동시 작업 가능.

---

## 5. 프롬프트 작성 원칙

### 5.1 필수 포함 요소

| 요소 | 이유 | 예시 |
|------|------|------|
| **수정 파일 명시** | 엉뚱한 파일 수정 방지 | `"excavator_model.py에 구현"` |
| **기존 패턴 참조** | 코드 스타일 일관성 | `"main_menu.py의 _build_grid()와 유사하게"` |
| **금지 사항** | AI 흔한 실수 차단 | `"새 셰이더 추가 금지"` |
| **기술 제약** | 아키텍처 보호 | `"VBO 레이아웃 9 floats/vertex 유지"` |
| **검증 방법** | 완료 기준 명확화 | `"테스트 실행하여 56개 통과 확인"` |
| **하나의 관심사** | 원자적 작업 = 리뷰 용이 | SFX만, 또는 버그만 |

### 5.2 매 프롬프트 검증 블록 (복사하여 사용)

```
완료 후 검증:
1. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v → 전부 통과
2. .venv/bin/ruff check src/ tests/ → 린트 통과
3. .venv/bin/ruff format src/ tests/ → 포맷 적용
4. 변경 사항 git commit (feat/fix/refactor 컨벤션)
5. 게임 실행하여 수동 확인 (해당 기능 동작 검증)
```

### 5.3 커밋 컨벤션

```bash
git commit -m "<type>(<scope>): <description>"
# type: feat, fix, refactor, test, docs, chore, perf
# scope: rendering, audio, core, ui, ros2, editor
```

---

## 6. 병목 및 리스크

| 리스크 | 심각도 | 대응 |
|--------|--------|------|
| **곡 부족** (2곡) | 🔴 높음 | 프롬프트로 해결 불가. 음악 파일 직접 제작 또는 라이선스 필요. |
| 블룸 성능 저하 | 🟡 중간 | 다운샘플 비율 조절, on/off 토글 필수 |
| VBO 매 프레임 재생성 | 🟡 중간 | 현재 180 vertices로 문제없으나, 지오메트리 확대 시 프로파일링 필요 |
| PyInstaller + ModernGL 호환 | 🟡 중간 | hidden imports 이슈 가능. 클린 환경 테스트 필수 |
| 폰트 미번들 | 🟢 낮음 | `assets/fonts/` 비어있음. 시스템 기본 폰트 사용 중. 배포 시 번들링 필요 |

---

## 7. 판매 가능 기준 체크리스트

- [x] ~~모든 판정에 사운드 피드백~~ (gameplay-screen-overhaul T4에서 수행)
- [x] 시각적 판정 피드백 (flash, scale)
- [x] 화면 전환 애니메이션
- [ ] ~~부드러운 조인트 움직임~~ (ROS2 호환성 사유로 제거)
- [x] 노트 하이웨이 시각화
- [x] 개선된 굴착기 3D 모델
- [x] 게임플레이 배경/환경
- [x] 블룸 포스트프로세싱
- [x] 튜토리얼 화면
- [x] 난이도 시스템 (EASY/NORMAL/HARD)
- [x] Settings 볼륨 실제 동작
- [x] 정식 Pause 메뉴
- [ ] 최소 5곡 이상 (음악 파일 필요, 코드 외 항목)
- [x] 단일 실행 파일 패키징 (Task 5-2 — WAV 파일로 패키징, onedir 모드)
- [x] End-to-End QA 통과

---

## 8. ROS2 실제 굴착기 호환성 노트

### 8.1 현재 아키텍처 데이터 플로우

```
Virtual Mode (현재):
  Keyboard → _update_joints() → self._joint_angles ─┬→ bridge.send_command()  (게임 → 굴착기)
                                                     ├→ excavator_model.update() (화면 표시)
                                                     └→ _check_beats()  (스코어링)

Real Mode (최종 목표):
  키보드 → bridge.send_command() → 실제 굴착기 조작 명령
  실제 센서 → /excavator/joint_states → bridge.get_current_angles() → self._joint_angles
                                                                     ├→ 화면 표시
                                                                     └→ 스코어링
```

### 8.2 주요 갭

- `bridge.get_current_angles()`는 인터페이스에 정의되어 있으나 **`GameLoop`에서 호출하지 않음**
- `_update_joints()`는 키보드 입력만 처리 — real 모드에서는 센서 데이터로 교체 필요
- 이 갭은 본 계획의 스코프 밖이며, ROS2 통합 Phase에서 별도로 다룰 것

### 8.3 ROS2 호환성 검토 결과

| Task | 호환 | 비고 |
|------|:----:|------|
| 1-1 SFX | ✅ | HitResult 기반 — 입력 소스 무관 |
| 1-2 Ghost Glow | ✅ | 렌더링 전용 |
| 1-3 TOCTOU | ✅ | 로직 버그 수정 |
| 2-1 판정 피드백 | ✅ | 시각 효과 — 입력 소스 무관 |
| 2-2 화면 전환 | ✅ | UI 전용 |
| ~~2-3 이징~~ | ❌ | **제거됨** — 센서 데이터와 충돌, 학습 전이 저해 |
| 2-4 노트 하이웨이 | ✅ | 타이밍 시각화 — 입력 소스 무관 |
| 3-1~3-3 | ✅ | 렌더링 전용 |
| 4-1 튜토리얼 | ✅ | virtual 모드용 — real 모드 튜토리얼은 별도 |
| 4-2 난이도 | ✅ | 판정 윈도우 — 입력 소스 무관 |
| 4-3~4-4 | ✅ | UI/오디오 전용 |
| 5-* | ✅ | 배포/QA |
