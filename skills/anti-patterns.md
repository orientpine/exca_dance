# 안티패턴, 명령어, 작업별 참조

> **목적**: exca_dance에서 절대 금지되는 코드 패턴, 올바른 대안, 개발 명령어, 작업별 수정 파일 가이드를 종합한다. 모든 모듈에 공통 적용된다.

---

## 절대 금지 (Forbidden)

```python
# ❌ 타이밍 — 500ms/300s 드리프트
pygame.mixer.music.get_pos()
pygame.mixer.music.get_position()

# ❌ 이벤트 루프 충돌
import ursina

# ❌ 렌더링 — 모든 렌더링은 OpenGL
surface.blit(...)
pygame.draw.line(...)
pygame.draw.rect(...)

# ❌ ROS2 — 메인 프로세스에서 직접 임포트 금지
from exca_dance.ros2_bridge.ros2_node import ROS2ExcavatorNode

# ❌ 타입 에러 억제 — 코드베이스에 0건
# type: ignore
# noqa
as any

# ❌ ModernGL 5.x — blend_func getter (런타임 NotImplementedError)
old = ctx.blend_func              # 런타임 크래시

# ❌ 행렬 전치 누락
prog["mvp"].write(mvp.tobytes())  # row-major → GL column-major 불일치
```

---

## 올바른 대안

| 잘못된 코드 | 올바른 코드 |
|------------|------------|
| `pygame.mixer.music.get_pos()` | `audio.get_position_ms()` (perf_counter) |
| `surface.blit(text_surface, pos)` | `gl_text.render("text", x, y, color)` |
| `old = ctx.blend_func` | `try/finally`로 원하는 모드 설정 후 복원 |
| `mvp.tobytes()` | `np.ascontiguousarray(mvp.astype("f4").T).tobytes()` |
| `from ros2_node import ...` | `create_bridge(mode)` 팩토리 사용 |

---

## 설계 안티패턴

| 안티패턴 | 이유 |
|---------|------|
| GameLoop를 스크린으로 사용 | GameLoop는 서비스 — GameplayScreen만 tick() 호출 |
| 셰이더 매 프레임 컴파일 | 시작 시 한 번만 컴파일, 기존 프로그램 사용 |
| DI 컨테이너/레지스트리 추가 | `__main__.py`에서 수동 와이어링이 프로젝트 컨벤션 |
| 상대 임포트 | 전체 도트 경로 사용 (`from exca_dance.xxx import yyy`) |
| 테스트에서 모킹 | 실제 로직 직접 테스트 |

---

## 개발 명령어

```bash
# 테스트 실행 (플러그인 플래그 필수)
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v

# 단일 파일 테스트
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_scoring.py -v

# 린트
.venv/bin/ruff check src/ tests/

# 포맷
.venv/bin/ruff format src/ tests/

# 게임 실행 (풀스크린)
python -m exca_dance

# 게임 실행 (창 모드)
python -m exca_dance --windowed

# 헤드리스 실행 (CI/디스플레이 없음)
xvfb-run -a SDL_AUDIODRIVER=dummy python -m exca_dance

# ROS2 모드 실행
python -m exca_dance --mode real
```

---

## 커밋 컨벤션

```bash
git add -A
git commit -m "<type>(<scope>): <description>"
```

| 타입 | 설명 |
|------|------|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `refactor` | 리팩토링 |
| `test` | 테스트 |
| `docs` | 문서 |
| `chore` | 기타 잡무 |
| `perf` | 성능 개선 |

스코프: `rendering`, `audio`, `core`, `ui`, `ros2`, `editor`

**규칙**: 하나의 논리적 변경 = 하나의 커밋. 미커밋 변경 누적 금지.

---

## 작업별 참조 테이블

| 작업 | 수정할 파일 | 주의사항 |
|------|-----------|---------|
| 새 스크린 추가 | `ui/screens/` + `game_state.py` + `__main__.py` | 4-메서드 프로토콜 준수, ScreenName 등록 |
| 스코어링 변경 | `core/scoring.py` + `tests/test_scoring.py` | 테스트 업데이트 필수 |
| 3D 모델 변경 | `rendering/excavator_model.py` | STL→VBO 패턴 따름 |
| 관절 제한 변경 | `core/constants.py:JOINT_LIMITS` | FK에 영향 |
| 링크 길이 변경 | `core/constants.py:BOOM_LENGTH` 등 | FK + 렌더링에 영향 |
| 비트맵 이벤트 추가 | `assets/beatmaps/*.json` | 소문자 관절 키, 절대 ms |
| 고스트/현재 포즈 색상 | `rendering/theme.py:NeonTheme` | Color 데이터클래스 |
| 오디오 타이밍 수정 | `audio/audio_system.py` | perf_counter 기반 |
| 뷰포트/카메라 추가 | `rendering/viewport_layout.py:_build_matrices()` | MVP 정적, GL 원점=좌하단 |
| 새 서브시스템 와이어링 | `__main__.py:main()` | DI 없음, 수동 생성 |
| ROS2 연동 | `ros2_bridge/` | 서브프로세스 전용 |
| 키 바인딩 추가 | `core/keybinding.py` + `constants.py` | — |
| 판정 윈도우 조정 | `core/constants.py:JUDGMENT_WINDOWS` | ms 단위, 반창 |
| 블룸 효과 조정 | `rendering/renderer.py:_apply_bloom()` | 임계값 0.7, 13-tap 가우시안 |
| 새 셰이더 추가 | `rendering/renderer.py:_compile_shaders()` | 시작 시 한 번만 컴파일 |
| 텍스트 렌더링 수정 | `rendering/gl_text.py` | pygame.font→GL 텍스처, 캐싱 확인 |
| HUD 요소 추가 | `ui/gameplay_hud.py` | GameplayScreen.render()에서 호출 |
| 비트맵 검증 추가 | `core/beatmap.py:validate_beatmap()` | 테스트도 추가 |
| 리더보드 변경 | `core/leaderboard.py` + `tests/test_leaderboard.py` | JSON 영속성 |
