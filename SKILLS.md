# SKILLS.md — exca_dance 스킬 문서 인덱스

> **목적**: AI 에이전트가 본 프로젝트의 코드를 올바르게 작성·수정·확장할 수 있도록, 목적별로 분리된 스킬 문서를 안내한다.
>
> **사용법**: 각 AGENTS.md의 `REQUIRED SKILLS` 섹션이 해당 모듈에 필요한 스킬만 인용한다. 전체를 읽을 필요 없이, 작업 대상 모듈의 AGENTS.md가 가리키는 스킬만 읽으면 된다.

---

## 스킬 문서 목록

| # | 스킬 | 파일 | 핵심 내용 | 적용 범위 |
|---|------|------|-----------|-----------|
| 1 | Python 컨벤션 | `skills/python-conventions.md` | 임포트 규칙, 타입 어노테이션, 코드 스타일, 데이터 단위 | 모든 모듈 |
| 2 | 아키텍처 | `skills/architecture.md` | 서브시스템 와이어링, 메인 루프, 설계 원칙 | root, ui/screens |
| 3 | Core 게임 로직 | `skills/core-game-logic.md` | 모델, 상수, 스코어링, FK, GameLoop, 비트맵 | core/ |
| 4 | 렌더링 파이프라인 | `skills/rendering-pipeline.md` | ModernGL, 셰이더, VBO/VAO, 뷰포트, 테마 | rendering/ |
| 5 | 오디오 타이밍 | `skills/audio-timing.md` | perf_counter, 비트 동기화, 사일런트 모드 | audio/ |
| 6 | UI 스크린 | `skills/ui-screens.md` | 스크린 프로토콜, 전환 맵, HUD | ui/screens/ |
| 7 | ROS2 브릿지 | `skills/ros2-bridge.md` | 서브프로세스 격리, IPC, 메시지 포맷 | ros2_bridge/ |
| 8 | 테스팅 | `skills/testing.md` | 테스트 실행, 작성 규칙, 단언 스타일 | tests/ |
| 9 | 안티패턴 | `skills/anti-patterns.md` | 금지 패턴, 명령어, 작업별 참조 테이블 | 모든 모듈 |
| 10 | 에러 로그 | `skills/error-log.md` | 발견된 에러와 수정 이력, 재발 방지 규칙 | 모든 모듈 |

---

## AGENTS.md ↔ 스킬 매핑

| AGENTS.md 위치 | 인용하는 스킬 |
|---------------|-------------|
| `AGENTS.md` (root) | 전체 (1~10) |
| `src/exca_dance/core/AGENTS.md` | 1, 3, 8, 9, 10 |
| `src/exca_dance/rendering/AGENTS.md` | 1, 4, 9, 10 |
| `src/exca_dance/audio/AGENTS.md` | 1, 5, 9, 10 |
| `src/exca_dance/ui/screens/AGENTS.md` | 1, 2, 6, 9, 10 |
| `src/exca_dance/ros2_bridge/AGENTS.md` | 1, 7, 9, 10 |
| `tests/AGENTS.md` | 1, 8, 9, 10 |
