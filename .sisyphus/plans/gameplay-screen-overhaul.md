# Gameplay Screen Production-Level Overhaul

## TL;DR

> **Quick Summary**: Ghost(목표 포즈)의 가시성을 네온 아웃라인으로 대폭 개선하고, 2D 사이드/탑 뷰에 관절 비교 오버레이를 추가하며, 미연결 기능(타임라인/히트사운드/각도피드백)을 활성화하여 게임플레이 화면을 프로덕션 수준으로 완성한다.
> 
> **Deliverables**:
> - Ghost 굴착기: 밝은 네온 아웃라인 + 펄스 애니메이션 + VBO 버그 수정
> - 2D 뷰: 현재 포즈 vs 목표 포즈 선분 비교 오버레이 + 관절별 각도 일치율 텍스트
> - 미연결 기능 활성화: 비트 타임라인, 히트 사운드, 각도 일치 피드백
> - HUD 레이아웃 정리 (뷰포트 개선에 맞춰 위치 조정)
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves + final verification
> **Critical Path**: T1(VBO fix) → T7(neon outline) → T10(HUD layout)

---

## Context

### Original Request
게임 메인 플레이 화면이 이상하다. (1) 목표 굴착기 상태가 잘 보이지 않음. (2) 2D 사이드뷰, 탑뷰가 화면 상에 구성이 되지 않음. 해당 메인 화면을 프로덕션 레벨의 완결성을 갖춘 화면 구성으로 변경하고 싶다.

### Interview Summary
**Key Discussions**:
- **레이아웃**: 현재 75/25 비율(main_3d 1440×1080, top_2d/side_2d 480×540) 유지, 품질만 개선
- **Ghost 스타일**: 밝은 네온 아웃라인/와이어프레임 + BPM 동기 펄스 애니메이션
- **2D 뷰 역할**: 관절 각도 호(arc) + 현재 vs 목표 비교 오버레이 + 일치율 색상 피드백
- **미연결 기능**: 3개 모두 포함 (비트 타임라인, 히트 사운드, 각도 일치율 피드백)
- **HUD**: 뷰포트 개선에 맞춰 위치/디자인 정리
- **테스트**: 없음 — 에이전트 실행 QA로만 검증

**Research Findings**:
- Ghost 가시성 저하의 6가지 복합 원인 발견: 낮은 알파(max 55%), 어두운 색상, 약한 글로우(7%), 미구현 아웃라인, VBO stride 버그
- VBO stride 버그가 silent corruption 유발: 180개 정점 × 9 floats를 6 floats로 파싱 → 2/3 glow 삼각형이 깨진 좌표로 렌더링
- 2D 뷰는 3D 렌더 경로를 그대로 직교 투영할 뿐, 2D 전용 시각화 전무
- FK 2D 헬퍼(`get_joint_positions_2d_side/top`) 존재하나 미사용
- `render_timeline()`, `get_angle_match_pct()` 구현되었으나 미호출
- `assets/sounds/hit_*.wav` 파일 존재하나 재생 코드 없음
- 기존 `prog_additive` 셰이더로 네온 아웃라인 구현 가능 (새 셰이더 불필요)
- `prog_solid`를 `"3f 3f"` 포맷(노말 없이)으로 사용 가능 (그리드 렌더링에서 확인)

### Metis Review
**Identified Gaps** (addressed):
- VBO stride 버그 → 독립 태스크로 최우선 수정, reshape(-1, 9)로 교정
- `ctx.line_width > 1.0` 비신뢰적 → 1.0만 사용, 시각 분리는 스케일업(1.02×)으로 해결
- Ghost/outline z-fighting → outline 패스에서 depth test 비활성화
- render_timeline()과 progress bar 위치 충돌 → HUD 재배치 태스크에서 해결
- Windowed mode(800x600) 뷰포트 장식 깨짐 → 스코프 외 명시
- 2D 오버레이 스코프 크리프 위험 → "착색 선분 + 텍스트 라벨" 수준으로 한정, arc 테셀레이션 없음
- Ghost rebuild 빈도 → 이벤트 변경 시에만 rebuild (최적화 기회, 별도 태스크 불필요)

---

## Work Objectives

### Core Objective
게임플레이 화면의 시각적 완성도를 프로덕션 수준으로 끌어올린다. Ghost 포즈를 명확하게 인지할 수 있게 하고, 2D 뷰에 유의미한 정보를 표시하며, 이미 구현된 미연결 기능을 활성화한다.

### Concrete Deliverables
- `src/exca_dance/rendering/visual_cues.py` — VBO stride 수정 + 네온 아웃라인 + 펄스 애니메이션
- `src/exca_dance/rendering/theme.py` — Ghost 색상/알파 개선
- `src/exca_dance/rendering/overlay_2d.py` — **NEW** 2D 관절 비교 오버레이 렌더러
- `src/exca_dance/ui/screens/gameplay_screen.py` — 타임라인/오버레이/사운드 와이어링
- `src/exca_dance/ui/gameplay_hud.py` — 각도 피드백 연결 + 레이아웃 정리
- `src/exca_dance/__main__.py` — 히트 사운드 로딩 + visual_cues→HUD 참조 전달

### Definition of Done
- [ ] Ghost 굴착기가 네온 아웃라인으로 렌더링되며 펄스 애니메이션 동작
- [ ] 2D 뷰(탑/사이드)에 현재 vs 목표 포즈 비교 선분 + 각도 텍스트 표시
- [ ] 비트 타임라인이 화면 하단에 표시
- [ ] 판정 시 히트 사운드 재생
- [ ] 관절별 각도 일치율이 HUD에 색상 피드백으로 표시
- [ ] HUD 요소가 뷰포트와 겹치지 않게 배치
- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` — 기존 56개 테스트 전부 PASS
- [ ] `.venv/bin/ruff check src/ tests/` — zero violations

### Must Have
- Ghost가 어두운 배경에서 확실히 인지 가능 (네온 아웃라인)
- 2D 뷰에서 현재 포즈와 목표 포즈의 차이가 시각적으로 구분 가능
- VBO stride 버그 수정 (glow 렌더링 정상화)
- 기존 56개 테스트 깨지지 않음
- ruff check/format 통과

### Must NOT Have (Guardrails)
- **FBO / 포스트프로세싱 추가 금지** — 현재 직접 프레임버퍼 렌더링 유지
- **새 셰이더 프로그램 생성 금지** — `prog_solid`, `prog_tex`, `prog_additive` 3개만 사용
- **ExcavatorModel/ExcavatorFK 클래스 수정 금지** — 변경은 VisualCueRenderer, 새 오버레이, 와이어링에만
- **`ctx.line_width > 1.0` 사용 금지** — Mesa/llvmpipe에서 비신뢰적
- **`# type: ignore` / `# noqa` 추가 금지** — 코드베이스에 zero, 유지
- **`surface.blit()` 사용 금지** — 모든 렌더링은 GL
- **`pygame.mixer.music.get_pos()` 사용 금지** — timing drift
- **Arc 테셀레이션/곡선 렌더링 금지** — v1은 직선 선분 + 텍스트만
- **해상도 독립성 구현 금지** — 1920×1080 전용, windowed mode는 현 상태 유지
- **커스텀 폰트 로딩 금지** — 기존 시스템 폰트 유지
- **과도한 주석/JSDoc 금지** — AI slop 방지, 코드가 자체 설명적이어야 함

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (56 tests, pytest)
- **Automated tests**: None — GL 렌더링 변경이 대부분이라 단위 테스트 비용 대비 가치 낮음
- **Framework**: pytest (기존)
- **Verification method**: Agent-Executed QA scenarios (시각적 확인 + 코드 검증)

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **렌더링 변경**: xvfb-run + Bash로 게임 실행 → 스크린샷 캡처 또는 crash 없음 확인
- **코드 로직**: Bash로 python 인라인 테스트 실행 (numpy reshape, 색상값 검증 등)
- **와이어링**: grep/ast_grep으로 호출 체인 검증 + 실행 시 에러 없음 확인

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — 6 independent tasks):
├── T1: Fix VBO stride bug in ghost glow [quick]
├── T2: Improve ghost theme colors + alpha [quick]
├── T3: Wire render_timeline() to gameplay screen [quick]
├── T4: Wire hit sound effects on judgment [quick]
├── T5: Wire angle match feedback to HUD [quick]
└── T6: Create 2D joint comparison overlay renderer [unspecified-high]

Wave 2 (After Wave 1 — core visual improvements):
├── T7: Build ghost neon outline with pulse animation (depends: T1, T2) [deep]
├── T8: Integrate 2D overlay into gameplay viewports (depends: T6) [unspecified-high]
└── T9: Improve viewport border decorations + labels (depends: T8) [quick]

Wave 3 (After Wave 2 — final layout):
└── T10: HUD layout repositioning + cleanup (depends: T3, T5, T7, T8, T9) [quick]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real manual QA (unspecified-high)
└── F4: Scope fidelity check (deep)
→ Present results → Get explicit user okay

Critical Path: T1 → T7 → T10 → F1-F4 → user okay
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 6 (Wave 1)
```

### Dependency Matrix

| Task | Blocked By | Blocks |
|------|-----------|--------|
| T1 | — | T7 |
| T2 | — | T7 |
| T3 | — | T10 |
| T4 | — | — |
| T5 | — | T10 |
| T6 | — | T8 |
| T7 | T1, T2 | T10 |
| T8 | T6 | T9, T10 |
| T9 | T8 | T10 |
| T10 | T3, T5, T7, T8, T9 | — |

### Agent Dispatch Summary

- **Wave 1**: **6** — T1→`quick`, T2→`quick`, T3→`quick`, T4→`quick`, T5→`quick`, T6→`unspecified-high`
- **Wave 2**: **3** — T7→`deep`, T8→`unspecified-high`, T9→`quick`
- **Wave 3**: **1** — T10→`quick`
- **FINAL**: **4** — F1→`oracle`, F2→`unspecified-high`, F3→`unspecified-high`, F4→`deep`

---

## TODOs

- [x] 1. Fix VBO stride bug in ghost glow rebuild

  **What to do**:
  - In `src/exca_dance/rendering/visual_cues.py`, method `_rebuild_ghost_glow()` (around line 67-91):
    - Change `raw.reshape(-1, 6)` to `raw.reshape(-1, 9)` to match the actual VBO format (pos3 + color3 + normal3)
    - Extract positions as `raw_9[:, :3]` and colors as `raw_9[:, 3:6]` (skip normals at indices 6-8)
    - Fix the guard check from `raw.size % 6 != 0` to `raw.size % 9 != 0`
    - Build glow_data as `np.column_stack([positions, colors_with_alpha])` where colors_with_alpha is RGBA (add glow_alpha column)
    - Ensure the resulting VBO matches `prog_additive` format: `"3f 4f"` (position3 + rgba4)
  - Verify the glow VBO vertex count changes from 270 (corrupted) to 180 (correct)

  **Must NOT do**:
  - Do NOT change `ExcavatorModel._vbo` format — only fix how `VisualCueRenderer` reads it
  - Do NOT modify the glow alpha formula (`alpha * 0.25`) — that will be adjusted in T7
  - Do NOT change any other method in `VisualCueRenderer`

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single-file, surgical fix of a known bug with clear before/after
  - **Skills**: []
    - No special skills needed — pure Python/numpy fix

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T2, T3, T4, T5, T6)
  - **Blocks**: T7 (neon outline depends on working glow infrastructure)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/visual_cues.py:67-91` — `_rebuild_ghost_glow()` method containing the bug
  - `src/exca_dance/rendering/excavator_model.py:159` — confirms VBO vertex count: `len(data) // 9`
  - `src/exca_dance/rendering/excavator_model.py:161-163` — VBO creation with format `"3f 3f 3f"` (pos + color + normal = 9 floats)

  **API/Type References**:
  - `src/exca_dance/rendering/renderer.py:92-110` — `prog_additive` shader expects `"3f 4f"` (position3 + rgba4)

  **WHY Each Reference Matters**:
  - `visual_cues.py:67-91`: This IS the buggy code. Line 73 checks `% 6` (wrong), line 77 reshapes as `(-1, 6)` (wrong). Must change to `% 9` and `(-1, 9)`
  - `excavator_model.py:159-163`: Proves the VBO format is `"3f 3f 3f"` = 9 floats/vertex, not 6. This is the ground truth for the fix
  - `renderer.py:92-110`: Confirms the additive shader VAO needs `"3f 4f"` format — the output of the fixed glow data must match this

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: VBO reshape produces correct vertex count
    Tool: Bash (python inline)
    Preconditions: None
    Steps:
      1. Run: `.venv/bin/python -c "
         import numpy as np;
         fake_vbo = np.random.rand(180 * 9).astype('f4');
         reshaped = fake_vbo.reshape(-1, 9);
         positions = reshaped[:, :3];
         colors = reshaped[:, 3:6];
         assert reshaped.shape == (180, 9), f'Expected (180,9) got {reshaped.shape}';
         assert positions.shape == (180, 3), f'Expected (180,3) got {positions.shape}';
         assert colors.shape == (180, 3), f'Expected (180,3) got {colors.shape}';
         print('PASS: VBO stride fix produces correct shapes')
         "`
    Expected Result: Prints 'PASS: VBO stride fix produces correct shapes'
    Failure Indicators: AssertionError or shape mismatch
    Evidence: .sisyphus/evidence/task-1-vbo-reshape.txt

  Scenario: Fixed code no longer contains stride-6 patterns
    Tool: Bash (grep)
    Preconditions: T1 changes applied
    Steps:
      1. Run: `grep -n 'reshape.*6' src/exca_dance/rendering/visual_cues.py`
      2. Run: `grep -n '% 6' src/exca_dance/rendering/visual_cues.py`
    Expected Result: No matches for stride-6 patterns in the glow rebuild method
    Failure Indicators: Any line matching `reshape(-1, 6)` or `% 6` in `_rebuild_ghost_glow`
    Evidence: .sisyphus/evidence/task-1-no-stride6.txt

  Scenario: Game launches without crash after fix
    Tool: Bash
    Preconditions: Fix applied
    Steps:
      1. Run: `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed`
    Expected Result: Exit code 0 or 124 (timeout, meaning it ran without crash)
    Failure Indicators: Python traceback, exit code 1, segfault
    Evidence: .sisyphus/evidence/task-1-launch-test.txt
  ```

  **Commit**: YES
  - Message: `fix(rendering): correct VBO stride in ghost glow rebuild`
  - Files: `src/exca_dance/rendering/visual_cues.py`
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v && .venv/bin/ruff check src/`

- [x] 2. Improve ghost theme colors and alpha for visibility

  **What to do**:
  - In `src/exca_dance/rendering/theme.py`:
    - Increase `GHOST_ALPHA` from `0.55` to `0.85` — ghost solid body should be much more visible
    - Brighten ghost joint colors to contrast against dark navy background (0.04, 0.04, 0.10):
      - `GHOST_SWING`: (0.2, 0.1, 0.4) → (0.5, 0.3, 0.9) — brighter violet
      - `GHOST_BOOM`: (0.4, 0.2, 1.0) → (0.6, 0.4, 1.0) — brighter blue-violet
      - `GHOST_ARM`: (0.6, 0.3, 1.0) → (0.8, 0.5, 1.0) — bright lavender
      - `GHOST_BUCKET`: (0.8, 0.4, 1.0) → (1.0, 0.7, 1.0) — bright pink-white
    - Verify `GHOST_OUTLINE` value is suitable for neon: currently (0.8, 0.4, 1.0, 0.9) — consider boosting to (1.0, 0.6, 1.0, 1.0) for maximum neon brightness
    - Add new constant `GHOST_OUTLINE_PULSE_MIN = 0.4` — minimum alpha during pulse cycle
    - Add new constant `GHOST_OUTLINE_PULSE_SPEED = 4.0` — pulse frequency multiplier

  **Must NOT do**:
  - Do NOT change non-ghost colors (NEON_*, ACCENT_*, BG, TEXT_*)
  - Do NOT change GHOST_FADE_MS (fade timing will be handled in T7)
  - Do NOT modify theme structure or class interface

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single-file constant value changes with no logic
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T3, T4, T5, T6)
  - **Blocks**: T7 (outline uses these color values)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/theme.py:55-76` — Current NeonTheme class with all ghost color constants
  - `src/exca_dance/rendering/theme.py:40-50` — Background and accent colors (DO NOT CHANGE, reference for contrast checking)

  **WHY Each Reference Matters**:
  - `theme.py:55-76`: These are the exact constants to modify. Current GHOST_SWING (0.2,0.1,0.4) is nearly invisible against BG (0.04,0.04,0.10)
  - `theme.py:40-50`: BG color is the contrast reference — new ghost colors must stand out against (0.04, 0.04, 0.10)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Ghost alpha increased to 0.85
    Tool: Bash (python inline)
    Preconditions: T2 changes applied
    Steps:
      1. Run: `.venv/bin/python -c "
         from exca_dance.rendering.theme import NeonTheme;
         assert NeonTheme.GHOST_ALPHA >= 0.85, f'GHOST_ALPHA={NeonTheme.GHOST_ALPHA}, expected >= 0.85';
         print(f'PASS: GHOST_ALPHA={NeonTheme.GHOST_ALPHA}')
         "`
    Expected Result: Prints 'PASS: GHOST_ALPHA=0.85' (or higher)
    Failure Indicators: AssertionError
    Evidence: .sisyphus/evidence/task-2-ghost-alpha.txt

  Scenario: Ghost colors are brighter than background
    Tool: Bash (python inline)
    Preconditions: T2 changes applied
    Steps:
      1. Run: `.venv/bin/python -c "
         from exca_dance.rendering.theme import NeonTheme;
         bg = (0.04, 0.04, 0.10);
         for name in ['GHOST_SWING', 'GHOST_BOOM', 'GHOST_ARM', 'GHOST_BUCKET']:
             color = getattr(NeonTheme, name);
             contrast = sum(c - b for c, b in zip(color, bg)) / 3;
             assert contrast > 0.3, f'{name} contrast {contrast:.2f} too low';
             print(f'PASS: {name}={color}, contrast={contrast:.2f}');
         print('ALL GHOST COLORS PASS')
         "`
    Expected Result: All 4 ghost colors pass contrast check (>0.3 average channel difference from BG)
    Failure Indicators: Any color fails contrast assertion
    Evidence: .sisyphus/evidence/task-2-ghost-colors.txt

  Scenario: New pulse constants exist
    Tool: Bash (python inline)
    Preconditions: T2 changes applied
    Steps:
      1. Run: `.venv/bin/python -c "
         from exca_dance.rendering.theme import NeonTheme;
         assert hasattr(NeonTheme, 'GHOST_OUTLINE_PULSE_MIN');
         assert hasattr(NeonTheme, 'GHOST_OUTLINE_PULSE_SPEED');
         print(f'PASS: pulse_min={NeonTheme.GHOST_OUTLINE_PULSE_MIN}, pulse_speed={NeonTheme.GHOST_OUTLINE_PULSE_SPEED}')
         "`
    Expected Result: Both constants exist with numeric values
    Failure Indicators: AttributeError
    Evidence: .sisyphus/evidence/task-2-pulse-constants.txt
  ```

  **Commit**: YES
  - Message: `feat(rendering): improve ghost theme colors and alpha for visibility`
  - Files: `src/exca_dance/rendering/theme.py`
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v && .venv/bin/ruff check src/`


- [x] 3. Wire render_timeline() to gameplay screen

  **What to do**:
  - In `src/exca_dance/ui/screens/gameplay_screen.py`, method `render()`:
    - After viewport reset to full screen (after the ghost rendering loop, around line 112), add a call to `self._visual_cues.render_timeline()`
    - Pass the required parameters: `self._text`, current audio position from `self._game_loop`, screen dimensions, and the upcoming events list from `self._game_loop`
    - Verify `render_timeline()` signature in `visual_cues.py:153-168` to match the exact parameters
    - Ensure the call is BEFORE `hud.render()` so HUD draws on top of timeline
  - Check for vertical overlap with progress bar (HUD renders progress bar at `H - 30`). If `render_timeline()` uses `H - 40`, adjust one of them to avoid overlap. The timeline should be ABOVE the progress bar.

  **Must NOT do**:
  - Do NOT modify `render_timeline()` implementation itself — just wire it
  - Do NOT change the render order of other elements (ghost, HUD, viewport decorations)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single wiring call addition to an existing render method
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T2, T4, T5, T6)
  - **Blocks**: T10 (HUD repositioning needs to account for timeline)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/visual_cues.py:153-168` — `render_timeline()` method signature and implementation. Note the parameters it expects
  - `src/exca_dance/ui/screens/gameplay_screen.py:87-137` — Current `render()` method showing the full render order
  - `src/exca_dance/ui/screens/gameplay_screen.py:112` — Viewport reset to full screen — timeline call goes AFTER this line

  **API/Type References**:
  - `src/exca_dance/rendering/visual_cues.py:153` — Method signature: check exact parameter names and types
  - `src/exca_dance/core/game_loop.py` — How to access audio position and upcoming events from GameLoop

  **WHY Each Reference Matters**:
  - `visual_cues.py:153-168`: The method is already fully implemented. You need its exact signature to wire the call correctly
  - `gameplay_screen.py:87-137`: Shows render order. Timeline must go after viewport reset (line 112) and before HUD render
  - `game_loop.py`: GameLoop exposes the data (audio position, events) that `render_timeline()` needs

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: render_timeline() is called in gameplay render
    Tool: Bash (grep)
    Preconditions: T3 changes applied
    Steps:
      1. Run: `grep -n 'render_timeline' src/exca_dance/ui/screens/gameplay_screen.py`
    Expected Result: At least one line calling `render_timeline` in the render method
    Failure Indicators: No matches — timeline not wired
    Evidence: .sisyphus/evidence/task-3-timeline-wired.txt

  Scenario: Timeline call is after viewport reset and before HUD
    Tool: Bash (grep with line numbers)
    Preconditions: T3 changes applied
    Steps:
      1. Run: `grep -n 'ctx.viewport\|render_timeline\|hud.render\|render_viewport' src/exca_dance/ui/screens/gameplay_screen.py`
      2. Verify the line order: viewport reset < render_timeline < hud.render
    Expected Result: render_timeline line number is between viewport reset and hud.render
    Failure Indicators: Wrong ordering
    Evidence: .sisyphus/evidence/task-3-render-order.txt

  Scenario: Game launches without crash after wiring
    Tool: Bash
    Preconditions: T3 changes applied
    Steps:
      1. Run: `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed`
    Expected Result: Exit code 0 or 124 (timeout = ran without crash)
    Failure Indicators: Python traceback, exit code 1
    Evidence: .sisyphus/evidence/task-3-launch-test.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): wire beat timeline to gameplay screen`
  - Files: `src/exca_dance/ui/screens/gameplay_screen.py`
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v && .venv/bin/ruff check src/`

- [x] 4. Wire hit sound effects on judgment

  **What to do**:
  - In `src/exca_dance/__main__.py`:
    - After `AudioSystem` construction, load the 4 hit sound effect files using pygame.mixer.Sound:
      - `assets/sounds/hit_perfect.wav`
      - `assets/sounds/hit_great.wav`
      - `assets/sounds/hit_good.wav`
      - `assets/sounds/hit_miss.wav`
    - Store them in a dict keyed by `Judgment` enum value (PERFECT, GREAT, GOOD, MISS)
    - Pass this dict to `GameplayScreen` constructor (add parameter)
  - In `src/exca_dance/ui/screens/gameplay_screen.py`:
    - Store the hit sounds dict in `self._hit_sounds`
    - In `update()` method, inside the `for result in hit_results` loop:
      - Look up the sound for `result.judgment` and call `.play()` on it
    - Respect `SDL_AUDIODRIVER=dummy` — pygame.mixer.Sound.play() is a no-op when audio is dummy, so no special handling needed

  **Must NOT do**:
  - Do NOT use `pygame.mixer.music` — that's for background music only
  - Do NOT create a new audio subsystem — use pygame.mixer.Sound directly
  - Do NOT modify AudioSystem class
  - Do NOT add volume control (can be added later)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward wiring of existing wav files to existing judgment events
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T2, T3, T5, T6)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/exca_dance/__main__.py:60-90` — Subsystem construction section. Add sound loading after AudioSystem
  - `src/exca_dance/__main__.py:107` — GameplayScreen constructor call. Add hit_sounds parameter
  - `src/exca_dance/ui/screens/gameplay_screen.py:50-75` — `update()` method with `for result in hit_results` loop

  **API/Type References**:
  - `src/exca_dance/core/models.py:Judgment` — Enum with PERFECT, GREAT, GOOD, MISS values
  - `src/exca_dance/core/models.py:HitResult` — Dataclass with `.judgment` field

  **External References**:
  - pygame.mixer.Sound: `pygame.mixer.Sound(filename).play()` — simple API, no streaming needed for short SFX

  **WHY Each Reference Matters**:
  - `__main__.py:60-90`: This is where all subsystems are constructed. Sound loading goes here to follow the existing pattern
  - `gameplay_screen.py:50-75`: The `update()` method already iterates over `hit_results` — adding sound playback is one line per result
  - `models.py:Judgment`: The sound dict should be keyed by these enum values for clean lookup

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Hit sound files are loaded without error
    Tool: Bash (python inline)
    Preconditions: T4 changes applied
    Steps:
      1. Run: `SDL_AUDIODRIVER=dummy .venv/bin/python -c "
         import pygame; pygame.mixer.init();
         import os;
         sounds = ['assets/sounds/hit_perfect.wav', 'assets/sounds/hit_great.wav',
                   'assets/sounds/hit_good.wav', 'assets/sounds/hit_miss.wav'];
         for s in sounds:
             assert os.path.exists(s), f'Missing: {s}';
             snd = pygame.mixer.Sound(s);
             print(f'PASS: {s} loaded, length={snd.get_length():.2f}s');
         print('ALL SOUNDS LOADED')
         "`
    Expected Result: All 4 sounds load successfully with non-zero length
    Failure Indicators: FileNotFoundError or pygame error
    Evidence: .sisyphus/evidence/task-4-sounds-loaded.txt

  Scenario: Hit sounds dict is passed to GameplayScreen
    Tool: Bash (grep)
    Preconditions: T4 changes applied
    Steps:
      1. Run: `grep -n 'hit_sound' src/exca_dance/ui/screens/gameplay_screen.py`
      2. Run: `grep -n 'hit_sound' src/exca_dance/__main__.py`
    Expected Result: Both files reference hit_sounds — __main__ passes it, gameplay_screen stores and uses it
    Failure Indicators: No references in either file
    Evidence: .sisyphus/evidence/task-4-hit-sounds-wired.txt

  Scenario: Sound plays on judgment in update loop
    Tool: Bash (grep)
    Preconditions: T4 changes applied
    Steps:
      1. Run: `grep -A5 'for result in' src/exca_dance/ui/screens/gameplay_screen.py | grep -i 'play\|sound'`
    Expected Result: A .play() call inside the hit_results loop
    Failure Indicators: No play() call found near the results loop
    Evidence: .sisyphus/evidence/task-4-play-in-loop.txt
  ```

  **Commit**: YES
  - Message: `feat(audio): wire hit sound effects on judgment`
  - Files: `src/exca_dance/__main__.py`, `src/exca_dance/ui/screens/gameplay_screen.py`
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v && .venv/bin/ruff check src/`

- [x] 5. Wire angle match feedback to HUD

  **What to do**:
  - In `src/exca_dance/__main__.py`:
    - Pass `visual_cues` reference to `GameplayHUD` constructor (currently line ~85, HUD doesn't receive visual_cues)
    - The HUD needs access to `visual_cues.get_angle_match_pct()` for per-joint match feedback
  - In `src/exca_dance/ui/gameplay_hud.py`:
    - Add `visual_cues` parameter to `__init__()` and store as `self._visual_cues`
    - In the joint status panel rendering section (around line 149, where it shows joint angles):
      - Call `self._visual_cues.get_angle_match_pct(current_angles, target_angles)` to get per-joint match percentage
      - Color-code each joint's angle display based on match quality:
        - ≥ 90%: NeonTheme.NEON_GREEN (green = good match)
        - ≥ 60%: NeonTheme.NEON_YELLOW or ACCENT_YELLOW (yellow = moderate)
        - < 60%: NeonTheme.NEON_PINK or (1.0, 0.3, 0.3) (red/pink = poor match)
      - Display the match percentage as text next to the joint angle, e.g., `BOOM: 45° (87%)`

  **Must NOT do**:
  - Do NOT modify `get_angle_match_pct()` implementation — just consume its output
  - Do NOT change HUD functionality — only add color coding and match text
  - Do NOT remove existing joint angle display

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Wiring existing function output to existing HUD element with color mapping
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T2, T3, T4, T6)
  - **Blocks**: T10 (HUD layout needs to know final content width/height)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/visual_cues.py:197-207` — `get_angle_match_pct()` implementation: takes a single `JointName`, returns 0.0-1.0 float. Must be called per-joint in a loop
  - `src/exca_dance/ui/gameplay_hud.py:140-180` — Joint status panel rendering section — where to add color coding
  - `src/exca_dance/ui/gameplay_hud.py:170-239` — `_draw_rect_2d()` pattern for colored rectangles

  **API/Type References**:
  - `src/exca_dance/rendering/visual_cues.py:197` — `get_angle_match_pct(self, joint: JointName) -> float` — NOTE: takes a single joint, NOT a dict. Call in a loop: `{j: visual_cues.get_angle_match_pct(j) for j in JointName}`
  - `src/exca_dance/rendering/theme.py:30-38` — Neon color constants (NEON_GREEN, NEON_YELLOW, NEON_PINK) for match quality coloring

  **WHY Each Reference Matters**:
  - `visual_cues.py:197-207`: This is the function to call. Returns dict mapping joint names to 0.0-1.0 match values (30° = 0.0, 0° = 1.0)
  - `gameplay_hud.py:140-180`: The exact rendering section where joint angles are displayed — add match percentage and color here
  - `theme.py:30-38`: Color palette for the traffic-light feedback (green/yellow/red)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: GameplayHUD now accepts visual_cues parameter
    Tool: Bash (grep)
    Preconditions: T5 changes applied
    Steps:
      1. Run: `grep -n 'visual_cues' src/exca_dance/ui/gameplay_hud.py | head -5`
      2. Run: `grep -n 'visual_cues' src/exca_dance/__main__.py | grep -i 'hud'`
    Expected Result: HUD __init__ accepts visual_cues; __main__ passes it
    Failure Indicators: No visual_cues references in HUD
    Evidence: .sisyphus/evidence/task-5-hud-visual-cues.txt

  Scenario: get_angle_match_pct is called in HUD render
    Tool: Bash (grep)
    Preconditions: T5 changes applied
    Steps:
      1. Run: `grep -n 'angle_match\|match_pct\|get_angle_match' src/exca_dance/ui/gameplay_hud.py`
    Expected Result: At least one call to get_angle_match_pct or usage of match percentage data
    Failure Indicators: No match percentage references in HUD
    Evidence: .sisyphus/evidence/task-5-match-pct-used.txt

  Scenario: Color coding logic exists for match quality
    Tool: Bash (grep)
    Preconditions: T5 changes applied
    Steps:
      1. Run: `grep -n 'NEON_GREEN\|NEON_YELLOW\|NEON_PINK\|0\.9\|0\.6' src/exca_dance/ui/gameplay_hud.py`
    Expected Result: Threshold-based color selection in HUD
    Failure Indicators: No color thresholds found
    Evidence: .sisyphus/evidence/task-5-color-coding.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): wire angle match feedback to HUD`
  - Files: `src/exca_dance/ui/gameplay_hud.py`, `src/exca_dance/__main__.py`
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v && .venv/bin/ruff check src/`

- [x] 6. Create 2D joint comparison overlay renderer

  **What to do**:
  - Create NEW file `src/exca_dance/rendering/overlay_2d.py`:
    - `from __future__ import annotations` at top
    - Class `Overlay2DRenderer` with constructor taking `renderer: GameRenderer` and `fk: ExcavatorFK`
    - Method `render(self, viewport_name: str, mvp: np.ndarray, current_angles: dict, target_angles: dict | None, text_renderer, match_pct: dict | None) -> None`:
      - If `target_angles` is None, only render current pose lines
      - Get 2D joint positions using FK helpers:
        - For `"side_2d"`: call `self._fk.get_joint_positions_2d_side(angles)` — returns (x, z) pairs
        - For `"top_2d"`: call `self._fk.get_joint_positions_2d_top(angles)` — returns (x, y) pairs
      - Render current pose as connected line segments (bright cyan/white color, full alpha)
      - Render target pose as connected line segments (neon violet color, e.g., NeonTheme.GHOST_OUTLINE[:3])
      - For each joint, render angle match percentage as text near the joint position:
        - Convert world-space joint position to screen-space using MVP matrix
        - Color text by match quality (green/yellow/red using same thresholds as T5)
    - Use `prog_solid` with `"3f 3f"` format (no normals) for line segments — same pattern as grid rendering
    - Use `moderngl.LINES` render mode
    - Manage VBO/VAO lifecycle with `try/finally` for cleanup (follow `render_2d_grid` pattern)
    - For 2D helpers: joint positions are returned as list of (name, x, y) tuples. Convert to 3D for MVP:
      - Side view: world coords are (x, 0, z) — put y=0 since side view looks along Y axis
      - Top view: world coords are (x, y, 0) — put z=0 since top view looks along Z axis

  **Must NOT do**:
  - Do NOT modify `ExcavatorFK` or `ExcavatorModel` classes
  - Do NOT implement arc tessellation — straight line segments only
  - Do NOT create new shader programs — use existing `prog_solid`
  - Do NOT build a general-purpose 2D rendering pipeline
  - Do NOT render this in `main_3d` viewport — 2D overlays are for side and top viewports only

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: New file creation with ModernGL rendering logic, coordinate transforms, and multiple concerns
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T2, T3, T4, T5)
  - **Blocks**: T8 (integration into gameplay screen)
  - **Blocked By**: None (uses FK helpers that already exist, no dependency on ghost fixes)

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/viewport_layout.py:130-186` — `render_2d_grid()` method. Follow this EXACT pattern for:
    - VBO creation: `ctx.buffer(data.astype('f4').tobytes())`
    - VAO creation: `ctx.vertex_array(prog, [(vbo, '3f 3f', 'in_position', 'in_color')])`
    - Render: `vao.render(moderngl.LINES)`
    - Cleanup: `vbo.release(); vao.release()` in `finally` block
  - `src/exca_dance/rendering/viewport_layout.py:175` — Confirms `prog_solid` works with `"3f 3f"` (no normals)

  **API/Type References**:
  - `src/exca_dance/core/kinematics.py:50-70` — `get_joint_positions_2d_side()` returns list of `(x, z)` tuples (NO joint name): `[(x, z), (x, z), ...]`. Order follows FK chain: base → swing_pivot → boom_pivot → arm_pivot → bucket_tip
  - `src/exca_dance/core/kinematics.py:72-87` — `get_joint_positions_2d_top()` returns list of `(x, y)` tuples (NO joint name): `[(x, y), (x, y), ...]`. Same order as side view
  - `src/exca_dance/rendering/renderer.py:31-60` — `prog_solid` shader: expects `in_position(3f)`, `in_color(3f)`, optional `in_normal(3f)`
  - `src/exca_dance/rendering/theme.py:30-38` — Neon colors for line coloring

  **WHY Each Reference Matters**:
  - `viewport_layout.py:130-186`: THE pattern to copy. VBO lifecycle, format string, cleanup. Do not deviate from this pattern
  - `kinematics.py:50-87`: These FK helpers return the 2D positions you need. Understand the return format to build line vertices correctly
  - `renderer.py:31-60`: Shader expects specific attribute names (`in_position`, `in_color`). The VAO must match

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: overlay_2d.py module exists and is importable
    Tool: Bash (python inline)
    Preconditions: T6 code written
    Steps:
      1. Run: `.venv/bin/python -c "
         from exca_dance.rendering.overlay_2d import Overlay2DRenderer;
         print(f'PASS: Overlay2DRenderer imported, methods: {[m for m in dir(Overlay2DRenderer) if not m.startswith(\"_\")]}')
         "`
    Expected Result: Successful import, 'render' method visible
    Failure Indicators: ImportError or missing render method
    Evidence: .sisyphus/evidence/task-6-overlay-import.txt

  Scenario: FK 2D helpers return expected format
    Tool: Bash (python inline)
    Preconditions: None (verifying existing API)
    Steps:
      1. Run: `.venv/bin/python -c "
         from exca_dance.core.kinematics import ExcavatorFK;
         fk = ExcavatorFK();
         angles = {'swing': 0, 'boom': 45, 'arm': -20, 'bucket': 10};
         side = fk.get_joint_positions_2d_side(angles);
         top = fk.get_joint_positions_2d_top(angles);
         print(f'Side view: {len(side)} joints, first={side[0]}');
         print(f'Top view: {len(top)} joints, first={top[0]}');
         assert len(side) >= 4, 'Expected at least 4 joints';
         print('PASS: FK 2D helpers work correctly')
         "`
    Expected Result: Both helpers return 4+ joints with (name, x, y) tuples
    Failure Indicators: Error or fewer than 4 joints
    Evidence: .sisyphus/evidence/task-6-fk-2d-helpers.txt

  Scenario: Overlay follows grid rendering VBO pattern
    Tool: Bash (grep)
    Preconditions: T6 code written
    Steps:
      1. Run: `grep -n 'release()\|finally\|ctx.buffer\|vertex_array\|LINES' src/exca_dance/rendering/overlay_2d.py`
    Expected Result: VBO/VAO creation, LINES render mode, and finally-block cleanup all present
    Failure Indicators: Missing cleanup or wrong render mode
    Evidence: .sisyphus/evidence/task-6-vbo-pattern.txt
  ```

  **Commit**: YES
  - Message: `feat(rendering): add 2D joint comparison overlay renderer`
  - Files: `src/exca_dance/rendering/overlay_2d.py` (NEW)
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v && .venv/bin/ruff check src/`

- [x] 7. Build ghost neon outline with pulse animation

  **What to do**:
  - In `src/exca_dance/rendering/visual_cues.py`:
    - Add method `_extract_edges(self, vertices: np.ndarray) -> np.ndarray`:
      - Takes the ghost model's 180 vertices (already reshaped as (-1, 9) after T1 fix)
      - Each box part has 36 vertices (12 triangles). Extract unique edges from triangle faces
      - For each triangle (3 consecutive vertices), extract 3 edges as (v0,v1), (v1,v2), (v2,v0)
      - Deduplicate edges (edge (a,b) == edge (b,a)) using sorted tuple set
      - Return flat array of edge vertex pairs suitable for `moderngl.LINES`
    - Add method `_build_outline_vao(self, edge_positions: np.ndarray, color: tuple, alpha: float) -> tuple[moderngl.Buffer, moderngl.VertexArray]`:
      - Build VBO with format `"3f 4f"` for `prog_additive`: position(3) + rgba(4)
      - Each edge vertex gets the neon color + alpha
      - Return (vbo, vao) pair for caller to manage lifecycle
    - Add method `render_outline(self, mvp: np.ndarray) -> None`:
      - Called from `gameplay_screen.py` after `render_ghost()` for each viewport
      - If no active ghost event, return early
      - Get ghost model positions from `self._ghost_model._vbo.read()`
      - Apply T1 fix: reshape as (-1, 9), extract positions [:, :3]
      - Extract edges via `_extract_edges()`
      - Compute pulse alpha: `base_alpha + amplitude * sin(time.perf_counter() * NeonTheme.GHOST_OUTLINE_PULSE_SPEED * 2π)`
        - `base_alpha = (NeonTheme.GHOST_OUTLINE_PULSE_MIN + NeonTheme.GHOST_OUTLINE[3]) / 2`
        - `amplitude = (NeonTheme.GHOST_OUTLINE[3] - NeonTheme.GHOST_OUTLINE_PULSE_MIN) / 2`
      - Build outline VBO/VAO with `NeonTheme.GHOST_OUTLINE[:3]` color and pulsing alpha
      - Render with:
        - Depth test DISABLED (`ctx.disable(moderngl.DEPTH_TEST)`) — outline always on top
        - Additive blend ENABLED (`ctx.enable(moderngl.BLEND); ctx.blend_func = SRC_ALPHA, ONE`)
        - `vao.render(moderngl.LINES)`
      - Restore blend state in `finally` block
      - Release VBO/VAO in `finally` block
    - Also improve `render_ghost()` method:
      - Increase glow_alpha multiplier from `alpha * 0.25` to `alpha * 0.5` — glow should be visible now that VBO is fixed
      - Shorten `GHOST_FADE_MS` from `2000.0` to `1500.0` — ghost appears closer to beat, higher alpha for more of its visible time

  **Must NOT do**:
  - Do NOT use `ctx.wireframe = True` — doesn't allow independent color/alpha control
  - Do NOT use `ctx.line_width > 1.0` — unreliable on Mesa/llvmpipe
  - Do NOT create new shader programs — use existing `prog_additive`
  - Do NOT modify `ExcavatorModel` class — only read its VBO data
  - Do NOT change the ghost solid body rendering (only add outline on top)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex rendering logic with edge extraction, VBO construction, blend state management, and animation math
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (with T8, T9)
  - **Blocks**: T10 (HUD needs to account for visual changes)
  - **Blocked By**: T1 (VBO stride fix), T2 (theme colors)

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/visual_cues.py:144-151` — Additive blend state management pattern (try/finally, save+restore blend_func). Copy this EXACTLY for outline rendering
  - `src/exca_dance/rendering/visual_cues.py:67-91` — `_rebuild_ghost_glow()` — shows how to read ghost model VBO and extract vertex data (AFTER T1 fix)
  - `src/exca_dance/rendering/visual_cues.py:118-140` — `render_ghost()` — shows alpha computation from `GHOST_FADE_MS` and `time_to_event`
  - `src/exca_dance/rendering/viewport_layout.py:130-186` — VBO/VAO lifecycle with `try/finally` cleanup

  **API/Type References**:
  - `src/exca_dance/rendering/renderer.py:92-110` — `prog_additive` shader: `"3f 4f"` format (position3 + rgba4)
  - `src/exca_dance/rendering/theme.py:67` — `GHOST_OUTLINE` = (0.8, 0.4, 1.0, 0.9) — neon outline color (may be boosted in T2)
  - `src/exca_dance/rendering/theme.py` — `GHOST_OUTLINE_PULSE_MIN`, `GHOST_OUTLINE_PULSE_SPEED` (added in T2)

  **External References**:
  - ModernGL `ctx.disable(moderngl.DEPTH_TEST)` — disables depth testing for outline-on-top rendering
  - ModernGL `ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)` — additive blending for neon glow effect

  **WHY Each Reference Matters**:
  - `visual_cues.py:144-151`: The blend state pattern is CRITICAL. Outline uses additive blend, must restore state. Copy this exactly
  - `visual_cues.py:67-91`: After T1 fix, this shows the correct way to read ghost VBO data. Outline reuses the same data source
  - `renderer.py:92-110`: Outline VAO must match `prog_additive` attribute layout exactly
  - `theme.py`: All color/pulse constants come from here — outline code should not hardcode colors

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: render_outline method exists and is callable
    Tool: Bash (python inline)
    Preconditions: T7 code written
    Steps:
      1. Run: `.venv/bin/python -c "
         from exca_dance.rendering.visual_cues import VisualCueRenderer;
         assert hasattr(VisualCueRenderer, 'render_outline');
         print('PASS: render_outline method exists')
         "`
    Expected Result: Method exists on VisualCueRenderer
    Failure Indicators: AttributeError
    Evidence: .sisyphus/evidence/task-7-outline-method.txt

  Scenario: Edge extraction produces valid line data
    Tool: Bash (python inline)
    Preconditions: T7 code written
    Steps:
      1. Run: `.venv/bin/python -c "
         import numpy as np;
         # Simulate one box: 36 vertices (12 triangles)
         # A cube has 12 unique edges
         # Each triangle shares edges with neighbors
         verts = np.random.rand(36, 3).astype('f4');
         # Extract edges: for each triangle (3 verts), 3 edges
         edges = set();
         for i in range(0, 36, 3):
             t = (i, i+1, i+2);
             for a, b in [(t[0],t[1]), (t[1],t[2]), (t[2],t[0])]:
                 edge = tuple(sorted([tuple(verts[a].round(6)), tuple(verts[b].round(6))]));
                 edges.add(edge);
         print(f'Unique edges from 1 box: {len(edges)}');
         assert len(edges) <= 18, 'Too many edges for one box';
         print('PASS: Edge extraction logic validated')
         "`
    Expected Result: 12-18 unique edges extracted from one box (12 for perfect cube, up to 18 for non-shared edges)
    Failure Indicators: More than 18 edges or assertion error
    Evidence: .sisyphus/evidence/task-7-edge-extraction.txt

  Scenario: Outline uses additive blend and disables depth test
    Tool: Bash (grep)
    Preconditions: T7 code written
    Steps:
      1. Run: `grep -n 'DEPTH_TEST\|disable.*DEPTH\|SRC_ALPHA.*ONE\|additive\|blend_func' src/exca_dance/rendering/visual_cues.py`
    Expected Result: DEPTH_TEST disable and additive blend setup found in outline method
    Failure Indicators: Missing depth test disable or blend state management
    Evidence: .sisyphus/evidence/task-7-blend-state.txt

  Scenario: Pulse animation uses perf_counter (not pygame)
    Tool: Bash (grep)
    Preconditions: T7 code written
    Steps:
      1. Run: `grep -n 'perf_counter\|PULSE_SPEED\|sin(' src/exca_dance/rendering/visual_cues.py`
    Expected Result: time.perf_counter() used with sin() for pulse alpha calculation
    Failure Indicators: pygame.time or hardcoded alpha without animation
    Evidence: .sisyphus/evidence/task-7-pulse-animation.txt

  Scenario: Game launches without crash after outline addition
    Tool: Bash
    Preconditions: T1 + T2 + T7 applied
    Steps:
      1. Run: `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed`
    Expected Result: Exit code 0 or 124
    Failure Indicators: Traceback, segfault
    Evidence: .sisyphus/evidence/task-7-launch-test.txt
  ```

  **Commit**: YES
  - Message: `feat(rendering): add ghost neon outline with pulse animation`
  - Files: `src/exca_dance/rendering/visual_cues.py`
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v && .venv/bin/ruff check src/`

- [x] 8. Integrate 2D overlay into gameplay viewports

  **What to do**:
  - In `src/exca_dance/__main__.py`:
    - Construct `Overlay2DRenderer` with `renderer` and `fk` references
    - Pass it to `GameplayScreen` constructor (add parameter)
  - In `src/exca_dance/ui/screens/gameplay_screen.py`:
    - Store `Overlay2DRenderer` as `self._overlay_2d`
    - In `render()` method, after rendering grids for 2D viewports (around lines that call `render_2d_grid`) and after ghost rendering in 2D viewports:
      - Set viewport to `"top_2d"`
      - Call `self._overlay_2d.render("top_2d", mvp_top, current_angles, target_angles, self._text, match_pct)`
      - Set viewport to `"side_2d"`
      - Call `self._overlay_2d.render("side_2d", mvp_side, current_angles, target_angles, self._text, match_pct)`
    - Get `current_angles` from `self._game_loop` (excavator state)
    - Get `target_angles` from current beat event (if any active ghost event)
    - Get `match_pct` from `self._visual_cues.get_angle_match_pct()` (if target exists)

  **Must NOT do**:
  - Do NOT render overlay in `main_3d` viewport — 3D view already has ghost
  - Do NOT modify `Overlay2DRenderer` class (already created in T6)
  - Do NOT change viewport render order for existing elements

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multi-file wiring with data plumbing between game_loop, visual_cues, and new overlay
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 2, parallel with T7, T9)
  - **Parallel Group**: Wave 2
  - **Blocks**: T9, T10
  - **Blocked By**: T6 (overlay renderer must exist)

  **References**:

  **Pattern References**:
  - `src/exca_dance/ui/screens/gameplay_screen.py:87-117` — Current render() method. Shows where 2D viewport rendering happens and where to insert overlay calls
  - `src/exca_dance/ui/screens/gameplay_screen.py:94-97` — Grid rendering for 2D viewports. Insert overlay AFTER grids
  - `src/exca_dance/__main__.py:107` — GameplayScreen construction. Add overlay_2d parameter here

  **API/Type References**:
  - `src/exca_dance/rendering/overlay_2d.py:Overlay2DRenderer.render()` — Method signature from T6 (viewport_name, mvp, current_angles, target_angles, text_renderer, match_pct)
  - `src/exca_dance/core/game_loop.py` — Access to current excavator state (angles) and current beat event (target angles)
  - `src/exca_dance/rendering/visual_cues.py:197` — `get_angle_match_pct()` for match percentages

  **WHY Each Reference Matters**:
  - `gameplay_screen.py:87-117`: You need to understand the render order to insert overlay calls at the right point (after grid, after ghost, before decorations)
  - `__main__.py:107`: Wiring point — overlay_2d must be constructed and passed to GameplayScreen
  - `game_loop.py`: Source of current_angles and target_angles data for the overlay

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Overlay is rendered in both 2D viewports
    Tool: Bash (grep)
    Preconditions: T8 changes applied
    Steps:
      1. Run: `grep -n 'overlay_2d.*render\|render.*overlay' src/exca_dance/ui/screens/gameplay_screen.py`
    Expected Result: At least 2 calls to overlay_2d.render (one for top_2d, one for side_2d)
    Failure Indicators: Fewer than 2 overlay render calls
    Evidence: .sisyphus/evidence/task-8-overlay-calls.txt

  Scenario: Overlay is constructed and passed in __main__
    Tool: Bash (grep)
    Preconditions: T8 changes applied
    Steps:
      1. Run: `grep -n 'Overlay2DRenderer\|overlay_2d' src/exca_dance/__main__.py`
    Expected Result: Construction and passing to GameplayScreen
    Failure Indicators: No Overlay2DRenderer reference in __main__
    Evidence: .sisyphus/evidence/task-8-overlay-wiring.txt

  Scenario: Overlay is NOT rendered in main_3d viewport
    Tool: Bash (grep)
    Preconditions: T8 changes applied
    Steps:
      1. Run: `grep -B2 -A2 'overlay_2d' src/exca_dance/ui/screens/gameplay_screen.py | grep -i 'main_3d'`
    Expected Result: No match — overlay should not reference main_3d
    Failure Indicators: Any overlay call associated with main_3d viewport
    Evidence: .sisyphus/evidence/task-8-no-main3d.txt

  Scenario: Game launches without crash after integration
    Tool: Bash
    Preconditions: T6 + T8 applied
    Steps:
      1. Run: `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed`
    Expected Result: Exit code 0 or 124
    Failure Indicators: Traceback, segfault
    Evidence: .sisyphus/evidence/task-8-launch-test.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): integrate 2D overlay into gameplay viewports`
  - Files: `src/exca_dance/ui/screens/gameplay_screen.py`, `src/exca_dance/__main__.py`
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v && .venv/bin/ruff check src/`

- [x] 9. Improve viewport border decorations and labels

  **What to do**:
  - In `src/exca_dance/rendering/viewport_layout.py`:
    - Replace hardcoded pixel values in `render_viewport_decorations()` (lines ~205-206):
      - Change `vx = (1440 / W) * 2.0 - 1.0` to use `self._vm.rects["main_3d"].w` (or proportional 0.75)
      - Change `hy = 1.0 - (540 / H) * 2.0` to use `self._vm.rects["top_2d"].h` (or proportional 0.5)
    - Improve viewport label positioning (lines ~305-307):
      - Move labels to be inside each viewport panel with small padding (e.g., 10px from corner)
      - Use viewport rect coordinates instead of hardcoded `W - 470`
    - Increase grid visibility:
      - Boost grid alpha from `0.3` to `0.5`
      - Brighten grid color: increase from `TEXT_DIM * 0.4` to `TEXT_DIM * 0.7`
    - Add panel background tinting:
      - Before rendering excavator in 2D panels, render a very subtle background fill (slightly brighter than main BG) to visually separate the panels
      - Use `_draw_rect_2d` pattern from HUD or render a full-viewport quad with alpha ~0.05

  **Must NOT do**:
  - Do NOT change viewport dimensions or proportions (75/25 split stays)
  - Do NOT change camera matrices (MVP stays the same)
  - Do NOT implement resolution independence — just derive from viewport rects instead of pixel literals
  - Do NOT change border/decoration colors from NeonTheme — only adjust alpha/brightness

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Value adjustments and simple coordinate derivation in a single file
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 2, after T8)
  - **Parallel Group**: Wave 2 (depends on T8 for overlay rendering order)
  - **Blocks**: T10
  - **Blocked By**: T8 (need overlay integrated to verify visual consistency)

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/viewport_layout.py:200-220` — `render_viewport_decorations()` with hardcoded 1440/540 values to replace
  - `src/exca_dance/rendering/viewport_layout.py:300-310` — Label text positioning with hardcoded `W - 470`
  - `src/exca_dance/rendering/viewport_layout.py:130-186` — Grid rendering with alpha=0.3 and dim color to improve
  - `src/exca_dance/rendering/viewport.py:20-27` — `ViewportManager.rects` dict with named viewport rectangles

  **WHY Each Reference Matters**:
  - `viewport_layout.py:200-220`: The border code hardcodes `1440` and `540`. Replace with `self._vm.rects["main_3d"].w` and `self._vm.rects["top_2d"].h`
  - `viewport_layout.py:300-310`: Label positions use `W - 470` which is 10px into right panel. Calculate from viewport rects instead
  - `viewport.py:20-27`: The `rects` dict provides the actual viewport dimensions needed to replace hardcoded values

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: No hardcoded 1440 or 540 pixel values in decorations
    Tool: Bash (grep)
    Preconditions: T9 changes applied
    Steps:
      1. Run: `grep -n '1440\|540' src/exca_dance/rendering/viewport_layout.py | grep -v '^#'`
    Expected Result: No hardcoded 1440/540 in decoration methods (may still exist in viewport rect definition, which is fine)
    Failure Indicators: 1440 or 540 appearing in render_viewport_decorations or label methods
    Evidence: .sisyphus/evidence/task-9-no-hardcoded.txt

  Scenario: Grid alpha is increased
    Tool: Bash (grep)
    Preconditions: T9 changes applied
    Steps:
      1. Run: `grep -n 'grid.*alpha\|alpha.*0\.[0-9]' src/exca_dance/rendering/viewport_layout.py`
    Expected Result: Grid alpha ≥ 0.5 (was 0.3)
    Failure Indicators: Alpha still 0.3 or lower
    Evidence: .sisyphus/evidence/task-9-grid-alpha.txt

  Scenario: Game launches without crash
    Tool: Bash
    Preconditions: T9 changes applied
    Steps:
      1. Run: `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 5 python -m exca_dance --windowed`
    Expected Result: Exit code 0 or 124
    Failure Indicators: Traceback
    Evidence: .sisyphus/evidence/task-9-launch-test.txt
  ```

  **Commit**: YES
  - Message: `fix(ui): improve viewport border decorations and labels`
  - Files: `src/exca_dance/rendering/viewport_layout.py`
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v && .venv/bin/ruff check src/`

- [x] 10. HUD layout repositioning and cleanup

  **What to do**:
  - In `src/exca_dance/ui/gameplay_hud.py`:
    - **Joint status panel** (left side, currently at x=20, y=120):
      - Move to the right panel area OR make it more compact
      - Currently takes 70px vertical spacing per joint (4 joints = 280px) on the left side of main_3d viewport
      - Option A: Keep on left but make more compact (single line per joint: `BOOM: 45° → 50° [87%]`)
      - Option B: Move to bottom-left of main_3d viewport, horizontal layout
      - Choose whichever is cleaner — priority is not obscuring the 3D scene
    - **Progress bar** (currently at y=H-30, full width):
      - Constrain width to main_3d viewport (0 to 1440px, not full 1920px)
      - This prevents the progress bar from overlapping the 2D panels
    - **Timeline positioning** (wired in T3):
      - Verify timeline doesn't overlap progress bar
      - If overlap: move timeline above progress bar (e.g., y = H - 60 instead of H - 40)
      - Or move progress bar to y = H - 15 and timeline to y = H - 45
    - **Score/Combo** (top area):
      - Keep positions but ensure they're within main_3d viewport bounds (x < 1440)
      - Score: top-right of main_3d area (x = 1420 instead of W-20)
      - Combo: top-center of main_3d area (x = 720 instead of W//2)
    - **FPS counter** (top-left): Keep as-is (10, 10) — it's fine
    - **Judgment flash** (center): Keep centered on main_3d viewport (x=720) not full screen center

  **Must NOT do**:
  - Do NOT change HUD element functionality — only reposition
  - Do NOT change score calculation or combo logic
  - Do NOT change text content or formatting
  - Do NOT change FPS counter position
  - Do NOT add new HUD elements

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Coordinate adjustments in a single file, no logic changes
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (solo)
  - **Blocks**: None
  - **Blocked By**: T3 (timeline), T5 (angle feedback), T7 (ghost outline), T8 (2D overlay), T9 (viewport decorations)

  **References**:

  **Pattern References**:
  - `src/exca_dance/ui/gameplay_hud.py:30-50` — Score rendering at top-right (W-20, 20). Change to use main_3d viewport width
  - `src/exca_dance/ui/gameplay_hud.py:55-70` — Combo rendering at top-center (W//2, 20). Center on main_3d viewport
  - `src/exca_dance/ui/gameplay_hud.py:80-100` — Progress bar at bottom (20, H-30, width=W-40). Constrain to main_3d width
  - `src/exca_dance/ui/gameplay_hud.py:140-180` — Joint status panel at left (20, 120). Make compact or relocate
  - `src/exca_dance/rendering/visual_cues.py:153-168` — Timeline positioning (check for overlap with progress bar)

  **API/Type References**:
  - `src/exca_dance/rendering/viewport.py:20-27` — ViewportManager rects for main_3d dimensions (use to constrain HUD)

  **WHY Each Reference Matters**:
  - `gameplay_hud.py:30-100`: All the coordinate values to change. Each element uses full-screen coordinates that need constraining to main_3d
  - `viewport.py:20-27`: main_3d width (1440) is the boundary — all HUD elements must stay within
  - `visual_cues.py:153-168`: Timeline Y position must not collide with progress bar Y position

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Progress bar width is constrained to main_3d viewport
    Tool: Bash (grep)
    Preconditions: T10 changes applied
    Steps:
      1. Run: `grep -n 'bar_w\|bar_x\|progress.*width\|W - 40' src/exca_dance/ui/gameplay_hud.py`
    Expected Result: Progress bar width references main_3d viewport width (~1440) instead of full screen width (1920)
    Failure Indicators: `W - 40` still present (full-screen width)
    Evidence: .sisyphus/evidence/task-10-progress-bar.txt

  Scenario: Score position is within main_3d bounds
    Tool: Bash (grep)
    Preconditions: T10 changes applied
    Steps:
      1. Run: `grep -n 'score.*W\|W.*score\|1420\|main_3d.*w' src/exca_dance/ui/gameplay_hud.py`
    Expected Result: Score x-position references main_3d width, not full screen width
    Failure Indicators: `W - 20` still present for score
    Evidence: .sisyphus/evidence/task-10-score-position.txt

  Scenario: No timeline/progress bar vertical overlap
    Tool: Bash (grep)
    Preconditions: T3 + T10 applied
    Steps:
      1. Run: `grep -n 'H - [0-9]\+\|timeline_y\|bar_y\|progress.*y' src/exca_dance/ui/gameplay_hud.py src/exca_dance/rendering/visual_cues.py`
    Expected Result: Timeline y-position and progress bar y-position differ by at least 15px
    Failure Indicators: Both using same or overlapping y-positions
    Evidence: .sisyphus/evidence/task-10-no-overlap.txt

  Scenario: All tests still pass + lint clean
    Tool: Bash
    Preconditions: All T1-T10 applied
    Steps:
      1. Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v`
      2. Run: `.venv/bin/ruff check src/ tests/`
      3. Run: `.venv/bin/ruff format --check src/ tests/`
    Expected Result: All 56 tests pass, zero lint violations, format clean
    Failure Indicators: Any test failure or lint error
    Evidence: .sisyphus/evidence/task-10-final-checks.txt

  Scenario: Full game launch without crash
    Tool: Bash
    Preconditions: All T1-T10 applied
    Steps:
      1. Run: `xvfb-run -a SDL_AUDIODRIVER=dummy timeout 8 python -m exca_dance --windowed`
    Expected Result: Exit code 0 or 124 (timeout = ran successfully)
    Failure Indicators: Any traceback or segfault
    Evidence: .sisyphus/evidence/task-10-launch-test.txt
  ```

  **Commit**: YES
  - Message: `fix(ui): reposition HUD elements to avoid viewport overlap`
  - Files: `src/exca_dance/ui/gameplay_hud.py`
  - Pre-commit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v && .venv/bin/ruff check src/`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read `.sisyphus/plans/gameplay-screen-overhaul.md` end-to-end. For each "Must Have": verify implementation exists (read file, grep for patterns). For each "Must NOT Have": search codebase for forbidden patterns (`surface.blit`, `# type: ignore`, `ctx.line_width` >1, new shader programs) — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v` + `.venv/bin/ruff check src/ tests/` + `.venv/bin/ruff format --check src/ tests/`. Review all changed files for: `as any`/`@ts-ignore` equivalent (`# type: ignore`), empty except blocks, print() in prod code, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic variable names.
  Output: `Tests [N pass/N fail] | Lint [PASS/FAIL] | Format [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Run `xvfb-run -a SDL_AUDIODRIVER=dummy python -m exca_dance` in tmux. Navigate to gameplay (select sample1 beatmap). Verify: (1) Ghost appears with neon outline before each beat, (2) 2D views show comparison overlays, (3) timeline dots scroll at bottom, (4) HUD elements don't overlap viewports, (5) No crashes for full song duration. Capture screenshots. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Visual [N/N pass] | Stability [PASS/FAIL] | Screenshots [N captured] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  `git diff main...HEAD --stat` to list all changed files. For each task: read "What to do", verify actual diff matches 1:1. Check "Must NOT do" compliance: no FBO code, no new shaders, no ExcavatorModel changes, no ExcavatorFK changes. Detect unaccounted changes. Flag any file changed that's not in any task spec.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Order | Commit | Files |
|-------|--------|-------|
| 1 | `fix(rendering): correct VBO stride in ghost glow rebuild` | `visual_cues.py` |
| 2 | `feat(rendering): improve ghost theme colors and alpha for visibility` | `theme.py` |
| 3 | `feat(ui): wire beat timeline to gameplay screen` | `gameplay_screen.py` |
| 4 | `feat(audio): wire hit sound effects on judgment` | `__main__.py`, `gameplay_screen.py` |
| 5 | `feat(ui): wire angle match feedback to HUD` | `gameplay_hud.py`, `__main__.py` |
| 6 | `feat(rendering): add 2D joint comparison overlay renderer` | `overlay_2d.py` (new) |
| 7 | `feat(rendering): add ghost neon outline with pulse animation` | `visual_cues.py` |
| 8 | `feat(ui): integrate 2D overlay into gameplay viewports` | `gameplay_screen.py`, `viewport_layout.py` |
| 9 | `fix(ui): improve viewport border decorations and labels` | `viewport_layout.py` |
| 10 | `fix(ui): reposition HUD elements to avoid viewport overlap` | `gameplay_hud.py` |

---

## Success Criteria

### Verification Commands
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v  # Expected: 56 passed
.venv/bin/ruff check src/ tests/                              # Expected: All checks passed
.venv/bin/ruff format --check src/ tests/                     # Expected: N files already formatted
xvfb-run -a SDL_AUDIODRIVER=dummy timeout 10 python -m exca_dance --windowed  # Expected: no crash
```

### Final Checklist
- [ ] Ghost 네온 아웃라인이 어두운 배경에서 확실히 보임
- [ ] 2D 뷰에 현재/목표 포즈 비교 오버레이 표시
- [ ] 비트 타임라인 화면에 표시
- [ ] 판정 시 히트 사운드 재생
- [ ] 각도 일치율 HUD 피드백 표시
- [ ] HUD 요소 뷰포트 미겹침
- [ ] 기존 테스트 전부 통과
- [ ] ruff lint/format 통과
- [ ] VBO stride 버그 수정 확인
