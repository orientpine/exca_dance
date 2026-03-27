# Python 컨벤션 및 툴링

> **목적**: exca_dance 프로젝트의 Python 환경 설정, 의존성, 코드 스타일, 타입 어노테이션 규칙을 정의한다. 모든 모듈에 공통 적용된다.

---

## Python 버전

- **최소 요구**: Python 3.10 (`requires-python = ">=3.10"`)
- Ruff target: `py310`

---

## 의존성

**런타임:**
| 패키지 | 버전 | 용도 |
|---------|------|------|
| `pygame-ce` | ≥2.4 | 윈도우 백엔드, 입력, 오디오 |
| `moderngl` | ≥5.10 | OpenGL 렌더링 컨텍스트 |
| `PyOpenGL` | ≥3.1 | 저수준 GL 바인딩 |
| `numpy` | ≥1.24 | 행렬 연산, 배열 처리 |

**개발:**
| 패키지 | 버전 | 용도 |
|---------|------|------|
| `pytest` | ≥7.0 | 테스트 러너 |
| `ruff` | ≥0.1 | 린터 + 포매터 |

**선택:**
| 패키지 | 용도 |
|---------|------|
| `pyinstaller` ≥6.0 | 실행 파일 빌드 |
| `rclpy` + `sensor_msgs` | ROS2 연동 (별도 설치) |

---

## Ruff 설정

```toml
[tool.ruff]
line-length = 100
target-version = "py310"
```

- **줄 길이**: 100자 (강제)
- 별도 `ruff.toml` 없음 — 모든 설정은 `pyproject.toml`에 있음
- `pyrightconfig.json` / `basedpyrightconfig.json` 없음

---

## 필수 패턴 (모든 파일에 적용)

| 규칙 | 예시 | 비고 |
|------|------|------|
| Future annotations | `from __future__ import annotations` | 모든 .py 파일 첫 줄 |
| 전체 도트 임포트 | `from exca_dance.rendering.renderer import GameRenderer` | 상대 임포트 금지 |
| 예외: core 재수출 | `from exca_dance.core import JointName` | `core/__init__.py`의 `__all__` 통해 허용 |
| 반환 타입 표기 | `def func() -> None:` | 모든 함수/메서드에 필수 (테스트 포함) |
| 100자 줄 길이 | — | Ruff가 강제 |
| `type: ignore` 금지 | — | 코드베이스에 0건, 유지 필수 |
| `noqa` 금지 | — | 코드베이스에 0건, 유지 필수 |
| `as any` 금지 | — | 타입 억제 일절 불가 |

---

## 임포트 순서

```python
from __future__ import annotations    # 항상 첫 줄

import argparse                        # 1. 표준 라이브러리
import logging
from pathlib import Path
from typing import cast

import pygame                          # 2. 서드파티
import moderngl
import numpy as np

from exca_dance.core.models import JointName   # 3. 프로젝트 내부
from exca_dance.core.constants import TARGET_FPS
```

---

## 타입 어노테이션

- **100% 커버리지**: 모든 함수에 완전한 타입 어노테이션 필수
- **cast() 사용**: enum dict 키, numpy 스칼라 표현식에 `typing.cast()` 사용
- **복합 타입**: `dict[Judgment, pygame.mixer.Sound]`, `list[tuple[float, float]]`
- **Union**: `list[str] | None`, `BeatMap | None` (Python 3.10+ 문법)

```python
# 클래스 인스턴스 변수
class ExcavatorFK:
    def __init__(self, boom_length: float = BOOM_LENGTH) -> None:
        self.boom_length: float = boom_length

# 프로퍼티
@property
def ctx(self) -> moderngl.Context:
    return self._ctx
```

---

## 데이터 단위 규칙

| 단위 | 사용 위치 | 비고 |
|------|-----------|------|
| **각도(degree)** | API 경계, 모든 게임 로직 | 기본 단위 |
| **라디안(radian)** | `kinematics.py` 내부만 | 외부 노출 금지 |
| **밀리초(ms)** | 시간 관련 전체 (`time_ms`, `duration_ms`, 판정 윈도우) | — |
| **미터(m)** | 링크 길이 (`BOOM_LENGTH=2.5`, `ARM_LENGTH=2.0`, `BUCKET_LENGTH=0.8`) | — |

---

## 네이밍

- 파일명: `snake_case.py`
- 클래스: `PascalCase` (예: `GameRenderer`, `ScoringEngine`)
- 함수/변수: `snake_case`
- 상수: `UPPER_SNAKE_CASE`
- 프라이빗: `_prefix` (단일 언더스코어)
- 테스트: `test_<주제>_<조건>_<기대값>()`

---

## 빠른 체크리스트

새 코드 작성 전 확인:

- [ ] `from __future__ import annotations` 첫 줄에 있는가?
- [ ] 전체 도트 임포트 사용하는가? (`from exca_dance.xxx.yyy import Zzz`)
- [ ] 모든 함수/메서드에 타입 어노테이션이 있는가?
- [ ] 줄 길이 100자 이하인가?
- [ ] 각도는 도(degree) 단위인가? (kinematics.py 내부 제외)
- [ ] 시간은 ms 단위인가?
- [ ] `type: ignore`, `noqa`, `as any` 사용하지 않았는가?
- [ ] 테스트 작성 시 `-> None` 반환 타입 표기했는가?
