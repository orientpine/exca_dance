# Testing — 테스트 컨벤션

> **목적**: exca_dance의 테스트 실행 방법, 작성 규칙, 단언 스타일, 커버리지 현황을 정의한다.
>
> **대상 파일**: `tests/`

---

## 실행 명령 (★ 플러그인 플래그 필수)

```bash
# 전체 테스트
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v

# 단일 파일
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_scoring.py -v

# 헤드리스
xvfb-run -a SDL_AUDIODRIVER=dummy PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v
```

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` — ROS launch 플러그인이 pytest 충돌을 일으킴

---

## 테스트 구조 (56개 테스트)

| 파일 | 테스트 수 | 커버리지 |
|------|----------|----------|
| `test_kinematics.py` | 6 | FK 관절 위치, Z-up 좌표 |
| `test_scoring.py` | 12 | 판정 윈도우, 콤보, 등급, 각도 정확도 |
| `test_beatmap.py` | 8 | JSON 로드/저장/검증, 스키마 에러 |
| `test_leaderboard.py` | 7 | 영속성, top-N, parametrize |
| `test_keybinding.py` | 7 | 키→관절 매핑, 저장/리로드 |
| `test_render_math.py` | 9 | direction_vector, rotation_matrix, oriented box |
| `test_ros2_interface.py` | 4 | AST 임포트 검증 |

---

## 테스트 작성 규칙

```python
from __future__ import annotations            # 필수 첫 줄

from exca_dance.core.scoring import ScoringEngine
from exca_dance.core.models import Judgment

def test_perfect_judgment_at_zero_timing_error() -> None:
    """테스트 이름: test_<주제>_<조건>_<기대값>"""
    engine = ScoringEngine()
    result = engine.judge({}, 0.0)
    assert result.judgment == Judgment.PERFECT
```

| 규칙 | 설명 |
|------|------|
| 모듈 수준 함수만 | 테스트 클래스 사용하지 않음 |
| 반환 타입 `-> None` | 모든 테스트 함수에 필수 |
| 픽스처 없음 | `conftest.py`는 비어 있음 |
| 직접 인스턴스화 | 각 테스트에서 객체 직접 생성 |
| 내장 `tmp_path` | 파일 I/O 테스트에만 사용 |
| `@pytest.mark.parametrize` | `test_leaderboard.py`에서 사용 |

---

## 단언(Assertion) 스타일

| 타입 | 패턴 |
|------|------|
| 동등 비교 | `assert result.judgment == Judgment.PERFECT` |
| 부동소수 | `assert np.allclose(...)` 또는 `math.isclose(..., abs_tol=1e-9)` |
| Numpy 스칼라 | `cast(float, np.min(...))` — basedpyright 침묵용 |
| 예외 | `with pytest.raises(ValueError): ...` |
| 에러 문자열 | `assert any("title" in error for error in errors)` |

---

## 모킹: 사용하지 않음

- 코드베이스에 **모킹 없음** — 실제 로직만 테스트
- GL 컨텍스트 불필요 — 순수 수학/로직만 커버
- GL 테스트 필요 시: `moderngl.create_standalone_context()` + `xvfb-run -a`

---

## 커버리지 갭

- ❌ GL/렌더링 테스트 없음
- ❌ 오디오 테스트 없음
- ❌ UI/스크린 테스트 없음
- ❌ GameLoop 테스트 없음
