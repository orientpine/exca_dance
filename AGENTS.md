# AGENTS.md — exca_dance

**Branch:** main | **Stack:** Python 3.12, pygame-ce 2.5.7, ModernGL 5.x, numpy

DDR-style rhythm game where the player controls a 3D excavator's 4 joints (swing/boom/arm/bucket) to match target poses on beat. Educational excavator operation simulator.

---

## LANGUAGE

모든 응답은 **한국어**로 작성한다. 코드, 커밋 메시지, 변수명은 영어 유지.

---

## REQUIRED SKILLS

> 이 프로젝트 작업 전 반드시 읽어야 할 스킬 문서. 각 AGENTS.md는 해당 모듈에 필요한 스킬만 인용한다.

| 스킬 | 파일 | 핵심 내용 |
|------|------|-----------|
| Python 컨벤션 | `skills/python-conventions.md` | 임포트 규칙, 타입, 코드 스타일, 데이터 단위 |
| 아키텍처 | `skills/architecture.md` | 서브시스템 와이어링, 메인 루프, 설계 원칙 |
| Core 게임 로직 | `skills/core-game-logic.md` | 모델, 상수, 스코어링, FK, GameLoop, 비트맵 |
| 렌더링 파이프라인 | `skills/rendering-pipeline.md` | ModernGL, 셰이더, VBO/VAO, 뷰포트, 테마 |
| 오디오 타이밍 | `skills/audio-timing.md` | perf_counter, 비트 동기화, 사일런트 모드 |
| UI 스크린 | `skills/ui-screens.md` | 스크린 프로토콜, 전환 맵, HUD |
| ROS2 브릿지 | `skills/ros2-bridge.md` | 서브프로세스 격리, IPC, 메시지 포맷 |
| 테스팅 | `skills/testing.md` | 테스트 실행, 작성 규칙, 단언 스타일 |
| 안티패턴 | `skills/anti-patterns.md` | 금지 패턴, 명령어, 작업별 참조 테이블 |
| 에러 로그 | `skills/error-log.md` | 발견된 에러와 수정 이력, 재발 방지 규칙 |

---

## STRUCTURE

```
src/exca_dance/
├── __main__.py          # God-wiring: constructs ALL subsystems + runs pygame loop
├── core/                # Game logic, data models, constants — AGENTS.md inside
├── rendering/           # ModernGL shaders, 3D model, viewport — AGENTS.md inside
├── ui/
│   ├── gameplay_hud.py  # Score/combo/progress overlay (not a screen)
│   └── screens/         # Duck-typed screen implementations — AGENTS.md inside
├── audio/               # AudioSystem with perf_counter timing — AGENTS.md inside
├── editor/              # Pose editor screen (standalone)
├── ros2_bridge/         # ROS2 interface — subprocess only — AGENTS.md inside
└── utils/               # Empty
tests/                   # 56 tests, no GL coverage — AGENTS.md inside
assets/beatmaps/         # JSON beatmaps (sample1.json, sample2.json)
```

---

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add a new screen | `ui/screens/` + register in `__main__.py` + add `ScreenName` constant |
| Change scoring formula | `core/scoring.py` + update `tests/test_scoring.py` |
| Modify 3D model geometry | `rendering/excavator_model.py` |
| Change joint limits / link lengths | `core/constants.py` |
| Add beatmap events | `assets/beatmaps/*.json` (lowercase joint keys) |
| Change ghost/current pose colors | `rendering/theme.py:NeonTheme` |
| Fix audio timing | `audio/audio_system.py` — read AGENTS.md there first |
| Add viewport / camera | `rendering/viewport_layout.py:_build_matrices()` |
| Wire new subsystem | `__main__.py:main()` — no DI container, all manual |
| ROS2 integration | `ros2_bridge/` — read AGENTS.md there first |

---

## COMMANDS

```bash
# Run tests (PLUGIN FLAG IS MANDATORY — ROS launch plugin conflicts otherwise)
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v

# Lint / format
.venv/bin/ruff check src/ tests/
.venv/bin/ruff format src/ tests/

# Run game (desktop)
python -m exca_dance

# Run game (windowed)
python -m exca_dance --windowed

# Run headless (CI / no display)
xvfb-run -a SDL_AUDIODRIVER=dummy python -m exca_dance
```

---

## WORKFLOW

**Every task must be committed when complete.**

```bash
git add -A
git commit -m "<type>(<scope>): <description>"
```

Commit types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`  
Scope examples: `rendering`, `audio`, `core`, `ui`, `ros2`

Do not accumulate uncommitted changes across tasks. One logical change = one commit.

---

## ANTI-PATTERNS (THIS PROJECT)

```python
# FORBIDDEN — drifts ~500ms/300s
pygame.mixer.music.get_pos()
pygame.mixer.music.get_position()

# FORBIDDEN — conflicts with pygame event loop
import ursina

# FORBIDDEN — all rendering is OpenGL
surface.blit(...)

# FORBIDDEN — import from main game process
from exca_dance.ros2_bridge.ros2_node import ROS2ExcavatorNode  # subprocess only

# FORBIDDEN — suppressing type errors (zero in codebase, keep it that way)
# type: ignore
# noqa

# FORBIDDEN — blend_func is WRITE-ONLY in ModernGL 5.x (getter raises NotImplementedError)
old = ctx.blend_func              # crashes at runtime
# Use: set desired blend, restore with moderngl.DEFAULT_BLENDING in finally block
```

---

## CONVENTIONS

- `from __future__ import annotations` at top of every file
- Full dotted imports: `from exca_dance.rendering.renderer import GameRenderer` (not `from exca_dance.rendering import ...`)
- Exception: `from exca_dance.core import JointName` works (core re-exports via `__all__`)
- `time.perf_counter()` for all timing — never pygame clock for game logic
- Angles in **degrees** throughout game logic; radians only inside `kinematics.py`
- Numpy matrices to GL: `np.ascontiguousarray(mat.astype("f4").T).tobytes()`
- Line length: 100 chars (ruff enforced)

---

## SCREEN PROTOCOL (duck-typed, no base class)

```python
class MyScreen:
    def on_enter(self, **kwargs) -> None: ...          # setup, receives transition data
    def handle_event(self, event) -> str | tuple | None: ...  # return transition or None
    def update(self, dt: float) -> str | tuple | None: ...    # return transition or None
    def render(self, renderer, text_renderer) -> None: ...    # side-effects only
```

Transition return: `"screen_name"` or `("screen_name", {"key": value})`.  
Special: `"quit"` exits the main loop.  
Register: `state_mgr.register(ScreenName.X, MyScreen(...))` in `__main__.py`.

---

## NOTES

- `__main__.py` is the only wiring point — no DI container, no registry
- `GameLoop` is a service, not a screen — only `GameplayScreen` calls `tick(dt)`
- `TARGET_FPS = 60` but `GameRenderer` has a second internal clock (cosmetic FPS counter only)
- Mesa llvmpipe (software GL 4.5) confirmed working; `xvfb-run -a` for headless
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` is not optional — ROS launch plugin breaks pytest without it
- Beatmap joint keys are **lowercase** (`"boom"`, not `"BOOM"`)
