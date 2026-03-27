# AGENTS.md — tests/

56 tests. No GL coverage. No shared fixtures.

---

## REQUIRED SKILLS

> 이 모듈 작업 전 반드시 읽어야 할 스킬 문서:

| 스킬 | 파일 | 핵심 내용 |
|------|------|-----------|
| Python 컨벤션 | `skills/python-conventions.md` | 임포트 규칙, 타입, 코드 스타일 |
| 테스팅 | `skills/testing.md` | 테스트 실행, 작성 규칙, 단언 스타일 |
| 안티패턴 | `skills/anti-patterns.md` | 금지 패턴, 명령어 |

---

## RUN COMMAND

```bash
# MANDATORY prefix — ROS launch plugin breaks pytest without it
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v

# Single file
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/test_scoring.py -v

# Headless GL (if ever needed)
xvfb-run -a SDL_AUDIODRIVER=dummy PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v
```

---

## TEST FILES

| File | Tests | What it covers |
|------|-------|----------------|
| `test_kinematics.py` | 6 | FK joint positions, Z-up coordinate system |
| `test_scoring.py` | 12 | Judgment windows, combo multiplier, grade, angle accuracy |
| `test_beatmap.py` | 8 | JSON load/save/validate, schema errors |
| `test_leaderboard.py` | 7 | Persistence, top-N, parametrize |
| `test_keybinding.py` | 7 | Key→joint mapping, save/reload roundtrip |
| `test_render_math.py` | 9 | direction_vector, rotation_matrix, oriented box, degenerate cases |
| `test_ros2_interface.py` | 4 | AST-based import verification, no ROS2 needed |

**No GL/rendering tests exist.** `renderer.py`, `excavator_model.py`, `viewport_layout.py` have zero test coverage.

---

## CONVENTIONS

```python
from __future__ import annotations
# module-level functions only — no test classes
# return type -> None on all test functions
# descriptive names: test_<subject>_<condition>_<expected>

def test_perfect_judgment_at_zero_timing_error() -> None:
    s = ScoringEngine()
    result = s.judge({}, 0.0)
    assert result.judgment == Judgment.PERFECT
```

- **No `@pytest.fixture`** — `conftest.py` is empty
- **Only built-in fixture**: `tmp_path: Path` (for file I/O tests)
- **Only marker**: `@pytest.mark.parametrize` (in `test_leaderboard.py`)
- **No mocking** anywhere
- Helper functions (not fixtures) for shared data: `_valid_payload() -> dict`

---

## ADDING NEW TESTS

- Follow the `from __future__ import annotations` + `-> None` pattern
- No GL context available in tests — test pure math/logic only
- For GL tests: use `moderngl.create_standalone_context()` (no pygame needed) + `xvfb-run -a`
- `typing.cast` to silence basedpyright on numpy scalar expressions
- `pytest.raises(ValueError)` for exception tests
