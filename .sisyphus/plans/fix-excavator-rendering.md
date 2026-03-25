# Fix Excavator 3D Model & 2D Layout Rendering

## TL;DR

> **Quick Summary**: 굴착기 3D 모델의 박스가 링크 방향으로 회전하지 않고, 2D 뷰의 행렬이 잘못 설정되어 정상 표시되지 않는 문제를 수정한다. 행렬 컨벤션 검증 → 핵심 지오메트리/뷰 수정 → 뷰포트 경계/라벨 추가 순으로 진행.
> 
> **Deliverables**:
> - 링크 방향으로 정확히 회전하는 3D 굴착기 모델
> - XZ 평면(측면)과 XY 평면(상면)이 올바르게 표시되는 2D 뷰
> - 뷰포트 경계선과 라벨("3D", "TOP", "SIDE")
> - 행렬 컨벤션 검증 테스트
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: T1(validate) → T2(matrix fix if needed) → T3(box rotation) → T4(side view) → T5(borders) → F1-F4

---

## Context

### Original Request
"굴착기 3d 모델, 2d 레이아웃이 잘 보이지 않아. 제대로 되었는지 확인하고 개선해."

### Code Analysis Summary
**Key Findings**:
- `excavator_model.py`: `_make_box_verts()` creates axis-aligned boxes at midpoints between joints — boxes never rotate with joint angles
- `viewport_layout.py`: `_mvp_side` uses only `_ortho(-2, 10, -1, 7)` without `_look_at` — shows XY plane instead of XZ
- `viewport_layout.py`: `_mvp_top` uses only `_ortho(-8, 8, -6, 6)` without `_look_at` — **Metis disputed**: with identity view + symmetric ortho, this already shows XY plane correctly. Validation needed.
- No viewport borders or labels exist — theme defines `NeonTheme.BORDER` but it's unused
- **Metis discovery**: numpy row-major matrices passed to GL as bytes without transpose → GL interprets as column-major → effective transposition. Affects asymmetric ortho (side view) and 3D MVP multiplication order.

**Technology**:
- Python + ModernGL + pygame
- GLSL #version 330 shaders
- FK kinematics returns `dict[str, tuple[float, float, float]]` — positions only, no rotation data
- Constants: BOOM=2.5m, ARM=2.0m, BUCKET=0.8m, max reach ~5.3m
- Screen: 1920×1080, 3-panel layout (75% 3D + 25% top/side)

### Metis Review
**Identified Gaps** (addressed):
- Matrix convention (row/column-major) needs validation before any fix — could be root cause
- Top-down view Bug #3 may not exist (identity view + symmetric ortho is correct for XY projection)
- Box rotation must compute orientation FROM direction vector (FK returns positions only)
- Viewport borders must be drawn in full-screen viewport to avoid edge clipping
- Degenerate link direction (zero-length) must be guarded against NaN/crash
- Ghost excavator (`VisualCueRenderer`) auto-fixed since it reuses `ExcavatorModel`

---

## Work Objectives

### Core Objective
굴착기 3D 모델의 링크가 관절 각도에 따라 정확히 회전하고, 2D 뷰(측면/상면)가 올바른 투영으로 표시되도록 렌더링 코드를 수정한다.

### Concrete Deliverables
- `src/exca_dance/rendering/excavator_model.py` — 회전 지오메트리 수정
- `src/exca_dance/rendering/viewport_layout.py` — 뷰 행렬 추가 및 행렬 컨벤션 수정
- `src/exca_dance/rendering/viewport_layout.py` — 뷰포트 경계선/라벨 렌더링
- `tests/test_rendering_math.py` — 행렬/지오메트리 검증 테스트

### Definition of Done
- [ ] Boom 30° 시 boom 박스가 swing_pivot → boom_pivot 방향으로 정확히 회전
- [ ] Side 2D 뷰에서 X 수평, Z 수직으로 표시 (XZ 평면)
- [ ] Top 2D 뷰에서 X 수평, Y 수직으로 표시 (XY 평면)
- [ ] 3개 뷰포트에 전기 파란색 경계선과 라벨 표시
- [ ] `pytest tests/` 전체 PASS (기존 42개 + 신규 테스트)

### Must Have
- 링크 박스가 관절 각도에 따라 방향 벡터 기준으로 회전
- Side view에 `_look_at` 뷰 행렬 적용 (XZ 평면 표시)
- 뷰포트 경계선 (NeonTheme.BORDER 색상)
- 뷰포트 라벨 ("3D", "TOP", "SIDE")
- 제로 길이 링크(degenerate case) 안전 처리
- 기존 테스트 42개 전부 통과 (6개 파일: test_scoring 10, test_beatmap 8, test_leaderboard 7, test_keybinding 7, test_kinematics 6, test_ros2 4)

### Must NOT Have (Guardrails)
- `core/kinematics.py` 수정 금지 — FK 모듈은 READ-ONLY (기존 테스트 보호)
- `renderer.py` 셰이더 소스 수정 금지 — 셰이더는 표준 구현으로 정상
- ortho 범위 임의 조정 금지 — 현재 범위가 굴착기를 포함함
- 마우스 카메라 인터랙션 추가 금지 — 기능이 아닌 버그 수정만
- 그리드/축 인디케이터 추가 금지 — 범위 밖
- `render_timeline` 플레이스홀더 수정 금지 — 별도 이슈
- `_make_box_verts` 범용 메시 유틸리티로 리팩토링 금지 — 리팩토링 아닌 수정만
- 프레임 당 VBO/VAO 할당 증가 금지 — 현재 release+recreate 패턴 유지

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, 6 existing tests)
- **Automated tests**: YES (Tests-after) — 행렬/지오메트리 수학 검증은 GL 컨텍스트 불필요
- **Framework**: pytest
- **Strategy**: 데이터 레벨 테스트 (MVP 행렬 × 알려진 벡터 → 예상 클립 좌표), 시각 검증은 게임 실행 스크린샷

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Math/Geometry**: Use Bash (python REPL) — Import module, compute vertices, compare
- **Visual rendering**: Use interactive_bash (tmux) — Run game, capture screenshot
- **Tests**: Use Bash (pytest) — Run test suite, assert all pass

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — validation + foundation):
├── Task 1: Matrix convention validation test [deep]
├── Task 2: Top view validation (is it actually broken?) [deep]
└── Task 3: Add oriented box vertex generation helper [deep]

Wave 2 (After Wave 1 — core rendering fixes):
├── Task 4: Fix matrix convention if broken (based on T1 result) [deep]
├── Task 5: Apply box rotation to excavator model [deep]
└── Task 6: Fix side view + top view matrices [deep]

Wave 3 (After Wave 2 — polish):
├── Task 7: Viewport borders and labels [quick]
└── Task 8: Integration test + visual verification [unspecified-high]

Wave FINAL (After ALL tasks — 4 parallel reviews, then user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| T1 | — | T4 | 1 |
| T2 | — | T6 | 1 |
| T3 | — | T5 | 1 |
| T4 | T1 | T5, T6 | 2 |
| T5 | T3, T4 | T8 | 2 |
| T6 | T2, T4 | T8 | 2 |
| T7 | — | T8 | 3 (can start wave 2, no deps) |
| T8 | T5, T6, T7 | F1-F4 | 3 |
| F1-F4 | T8 | user okay | FINAL |

### Agent Dispatch Summary

- **Wave 1**: **3** — T1 → `deep`, T2 → `deep`, T3 → `deep`
- **Wave 2**: **3** — T4 → `deep`, T5 → `deep`, T6 → `deep`
- **Wave 3**: **2** — T7 → `quick`, T8 → `unspecified-high`
- **FINAL**: **4** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.

- [ ] 1. Matrix Convention Validation Test

  **What to do**:
  - Create `tests/test_rendering_math.py` with tests that verify numpy→GL matrix convention
  - Test 1: Build `_perspective(45, 16/9, 0.1, 100)` matrix, apply to known vertex `(2, 0, -5, 1)`, compute expected clip coords by hand. Then simulate what GL sees by interpreting the matrix bytes as column-major (= numpy transpose). Compare results.
  - Test 2: Build `_ortho(-2, 10, -1, 7)` (asymmetric side view), apply to vertex `(4, 3, 2, 1)`. Check if w=1.0 in output. If w≠1.0, convention is broken.
  - Test 3: Build `_ortho(-8, 8, -6, 6)` (symmetric top view), apply to vertex. Verify result same whether transposed or not (symmetric → self-transpose).
  - Test 4: Compose `proj @ view` vs `view @ proj`, transpose each, check which matches standard GL `P * V * vertex` result.
  - Import `_perspective`, `_ortho`, `_look_at` from `viewport_layout.py` — they may need to be made importable (move to module scope or add `__all__`)
  - **Decision gate**: Based on test results, set a flag/comment indicating whether Bug #5 (convention) is real. T4 reads this.

  **Must NOT do**:
  - Do not modify any rendering code — tests only
  - Do not require GL context — pure numpy math tests

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Requires careful mathematical reasoning about matrix conventions and GL byte interpretation
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - None applicable — pure math/testing task

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Task 4 (matrix fix depends on validation result)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/viewport_layout.py:9-55` — `_perspective()`, `_ortho()`, `_look_at()` implementations
  - `src/exca_dance/rendering/viewport_layout.py:83-95` — `_build_matrices()` where MVP is composed as `proj_3d @ view_3d`
  - `src/exca_dance/rendering/excavator_model.py:145-154` — `render_3d()` where `mvp.astype('f4').tobytes()` sends to GL

  **API/Type References**:
  - numpy `.tobytes()` defaults to C-order (row-major) — this is the crux of the convention question
  - ModernGL `prog['mvp'].write(data)` calls `glUniformMatrix4fv` with `GL_FALSE` (no transpose) — GL interprets bytes as column-major

  **Test References**:
  - `tests/test_kinematics.py` — existing test structure and patterns for this project

  **WHY Each Reference Matters**:
  - `viewport_layout.py:9-55`: These are the exact functions being tested — must understand their numpy indexing convention
  - `viewport_layout.py:83-95`: The composition `proj @ view` is what we're validating — need to check if GL sees `P*V` or `V*P`
  - `excavator_model.py:145-154`: Shows how bytes flow to GPU — `.astype('f4').tobytes()` then `.write()` — the complete data pipeline

  **Acceptance Criteria**:
  - [ ] `tests/test_rendering_math.py` created with ≥4 test functions
  - [ ] `pytest tests/test_rendering_math.py -v` → PASS (all tests)
  - [ ] `pytest tests/` → PASS (existing 42 + new tests)
  - [ ] Test output clearly documents whether Bug #5 (convention mismatch) is real or not

  **QA Scenarios (MANDATORY):**
  ```
  Scenario: Matrix convention tests pass
    Tool: Bash (pytest)
    Preconditions: tests/test_rendering_math.py exists
    Steps:
      1. Run `pytest tests/test_rendering_math.py -v`
      2. Assert exit code 0
      3. Assert output contains 'passed' for all 4+ tests
    Expected Result: All tests PASS, output includes clear convention determination
    Failure Indicators: Any test FAILED, or import errors from viewport_layout
    Evidence: .sisyphus/evidence/task-1-matrix-convention-tests.txt

  Scenario: Existing tests still pass
    Tool: Bash (pytest)
    Preconditions: No rendering code was modified
    Steps:
      1. Run `pytest tests/ -v`
      2. Assert all 6 existing tests pass
    Expected Result: 6+ tests PASS
    Failure Indicators: Any existing test fails
    Evidence: .sisyphus/evidence/task-1-full-test-suite.txt
  ```

  **Commit**: YES
  - Message: `test(rendering): add matrix convention and geometry validation tests`
  - Files: `tests/test_rendering_math.py`
  - Pre-commit: `pytest tests/`

- [ ] 2. Top View Validation (Is Bug #3 Real?)

  **What to do**:
  - Analyze whether the current top-down view (`_mvp_top = _ortho(-8, 8, -6, 6)`) correctly shows the XY plane WITHOUT a `_look_at` view matrix
  - With identity view: X→screenX, Y→screenY, Z→depth. For top-down view looking down Z-axis, this IS correct
  - **Validation approach**: In `tests/test_rendering_math.py` (same file as T1), add tests:
    - Apply `_mvp_top` to vertex (3, 2, 1, 1) — expect x ∝ 3, y ∝ 2 (XY preserved), w should be 1.0
    - Apply to vertex (0, 0, 5, 1) — Z=5 should map to depth, not affect x/y
    - With swing=45° FK output, verify XY positions are non-degenerate (not collapsed to a line)
  - **Key insight from Metis**: Symmetric ortho has no off-diagonal translation → self-transposing → convention issue doesn't affect it
  - Write determination as test docstring: "Top view is CORRECT/INCORRECT as-is"

  **Must NOT do**:
  - Do not modify viewport_layout.py — validation only
  - Do not add view matrix to top view preemptively

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Mathematical reasoning about projection correctness
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Task 6 (view fix depends on knowing if top view needs fixing)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/viewport_layout.py:92` — `_mvp_top = _ortho(-8.0, 8.0, -6.0, 6.0)` — the matrix being validated
  - `src/exca_dance/rendering/viewport_layout.py:21-38` — `_ortho()` function implementation

  **API/Type References**:
  - `src/exca_dance/core/kinematics.py:81-87` — `get_joint_positions_2d_top()` returns `[(x,y)]` pairs — confirms top view is XY plane

  **WHY Each Reference Matters**:
  - `viewport_layout.py:92`: This is the exact matrix being validated — we need its ortho bounds
  - `_ortho()` function: Must understand how bounds map to NDC to verify if the output is correct
  - `kinematics.py:81-87`: Confirms the expected 2D projection for top view is X,Y not X,Z

  **Acceptance Criteria**:
  - [ ] Validation tests added to `tests/test_rendering_math.py`
  - [ ] Clear determination: top view needs fix or not
  - [ ] All tests pass

  **QA Scenarios (MANDATORY):**
  ```
  Scenario: Top view validation tests pass
    Tool: Bash (pytest)
    Preconditions: tests/test_rendering_math.py has top view tests
    Steps:
      1. Run `pytest tests/test_rendering_math.py -v -k 'top'`
      2. Check test docstrings for determination
    Expected Result: Tests pass and clearly state whether top view is correct as-is
    Failure Indicators: Tests fail or determination is ambiguous
    Evidence: .sisyphus/evidence/task-2-top-view-validation.txt
  ```

  **Commit**: YES (grouped with T1)
  - Message: `test(rendering): add matrix convention and geometry validation tests`
  - Files: `tests/test_rendering_math.py`
  - Pre-commit: `pytest tests/`

- [ ] 3. Oriented Box Vertex Generation Helper

  **What to do**:
  - Create a new function `_make_oriented_box_verts()` in `excavator_model.py` that generates box vertices oriented along a given direction vector
  - Function signature: `_make_oriented_box_verts(p0: tuple, p1: tuple, cross_w: float, cross_h: float, color: tuple) -> list[float]`
    - `p0`, `p1`: link start/end positions (3D tuples from FK)
    - `cross_w`, `cross_h`: cross-section width and height (perpendicular to link direction)
    - `color`: RGB tuple
  - Implementation approach:
    1. Compute direction vector `d = p1 - p0`, normalize to `d_hat`
    2. Compute perpendicular axes: `right = cross(d_hat, world_up)`, `up = cross(right, d_hat)`
       - If `d_hat` is parallel to world_up `(0,0,1)`, use fallback `(1,0,0)` for cross product
    3. Scale: `right *= cross_w/2`, `up *= cross_h/2`
    4. Generate 8 corner vertices at `p0 ± right ± up` and `p1 ± right ± up`
    5. Build 12 triangles (36 vertices) from 8 corners, each with position + color (6 floats)
  - **Degenerate case guard**: If `norm(d) < 1e-6`, return empty list (skip rendering zero-length link)
  - Keep old `_make_box_verts()` for base and turret (static axis-aligned boxes)
  - Add unit tests for the new function in `tests/test_rendering_math.py`:
    - Test: boom at 0° → box aligned along X axis
    - Test: boom at 90° → box aligned along Z axis
    - Test: degenerate case (p0 == p1) → returns empty list

  **Must NOT do**:
  - Do not remove `_make_box_verts` — still needed for base/turret
  - Do not change the color scheme or cross-section sizes
  - Do not add new VBO/VAO allocations — return vertex list like existing function

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 3D geometry math (cross products, rotation, degenerate cases)
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Task 5 (box rotation applies this helper)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/excavator_model.py:21-72` — existing `_make_box_verts()` — vertex format (3f pos + 3f color), face winding, and return type
  - `src/exca_dance/rendering/excavator_model.py:92-129` — `_update_geometry()` where box midpoint/direction is already computed per link

  **API/Type References**:
  - Vertex format: `3f 3f` = `(x, y, z, r, g, b)` per vertex — must match `renderer.py:142` VAO layout
  - Each face: 6 vertices (2 triangles), total 6 faces = 36 vertices per box

  **WHY Each Reference Matters**:
  - `_make_box_verts()`: New function must match EXACTLY the same output format (flat list of floats, 6 per vertex, 36 verts per box) so existing VBO construction works unchanged
  - `_update_geometry()`: Shows how direction vectors `(dx, dy, dz)` are already available per link — new function just needs these

  **Acceptance Criteria**:
  - [ ] `_make_oriented_box_verts()` function exists in `excavator_model.py`
  - [ ] Boom at 0°: box vertices span from p0.x to p1.x along X, centered in Y/Z
  - [ ] Boom at 30°: box endpoint centroid matches FK pivot positions (±0.05m tolerance)
  - [ ] Degenerate p0==p1: returns `[]`, no crash/NaN
  - [ ] Returns 36 vertices × 6 floats = 216 floats per box
  - [ ] `pytest tests/` → all PASS

  **QA Scenarios (MANDATORY):**
  ```
  Scenario: Oriented box at boom angle 0
    Tool: Bash (python REPL)
    Preconditions: _make_oriented_box_verts exists
    Steps:
      1. Import the function
      2. Call with p0=(0,0,0.5), p1=(2.5,0,0.5), cross_w=0.25, cross_h=0.25, color=(1,0.4,0)
      3. Extract all X coords from returned vertices
      4. Assert min(X) ≈ 0.0, max(X) ≈ 2.5 (link spans correctly)
    Expected Result: Box spans from p0 to p1 along X, cross-section perpendicular
    Failure Indicators: X range doesn't match, or vertices contain NaN
    Evidence: .sisyphus/evidence/task-3-oriented-box-0deg.txt

  Scenario: Degenerate case (zero-length link)
    Tool: Bash (python REPL)
    Preconditions: _make_oriented_box_verts exists
    Steps:
      1. Call with p0=(1,1,1), p1=(1,1,1)
      2. Assert result is empty list
    Expected Result: Returns [] without crash
    Failure Indicators: Crash, NaN, or non-empty list
    Evidence: .sisyphus/evidence/task-3-degenerate-case.txt
  ```

  **Commit**: YES
  - Message: `feat(rendering): add oriented box vertex generation for link rotation`
  - Files: `src/exca_dance/rendering/excavator_model.py`, `tests/test_rendering_math.py`
  - Pre-commit: `pytest tests/`

- [ ] 4. Fix Matrix Convention (Conditional — Based on T1 Results)

  **What to do**:
  - Read T1 test results to determine if matrix convention is broken (row-major→GL column-major mismatch)
  - **IF convention IS broken** (T1 tests show w≠1.0 for ortho, or reversed P*V order):
    1. In `viewport_layout.py`, change `_build_matrices()` to transpose MVP matrices before storing:
       - Option A: Add `.T` before `.astype('f4')` on each MVP: `self._mvp_3d = (proj_3d @ view_3d).T.astype('f4')`
       - Option B: Swap multiplication order: `self._mvp_3d = (view_3d @ proj_3d).astype('f4')`
       - Choose based on T1 test results — whichever produces correct clip coords
    2. Apply same fix to `_mvp_top` and `_mvp_side`
    3. Also fix `excavator_model.py:render_3d()` if the `.tobytes()` call needs `.T`
    4. Update T1 tests to assert the FIXED convention produces correct results
  - **IF convention is NOT broken** (T1 tests show correct results as-is):
    1. Add a comment in `_build_matrices()`: `# NOTE: numpy row-major matches GL column-major for this use case (validated in test_rendering_math.py)`
    2. Skip to next task
  - **CRITICAL**: The `_ortho()`, `_look_at()`, `_perspective()` helper functions must NOT be modified — only how their results are composed and sent to GL

  **Must NOT do**:
  - Do not modify `_ortho()`, `_look_at()`, `_perspective()` helper functions
  - Do not modify shader source in `renderer.py`
  - Do not change `kinematics.py`

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Must understand GL matrix conventions and make correct fix decision based on test results
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (sequential start)
  - **Blocks**: Tasks 5, 6 (both depend on correct convention)
  - **Blocked By**: Task 1 (needs validation results)

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/viewport_layout.py:83-95` — `_build_matrices()` where all MVPs are composed
  - `src/exca_dance/rendering/excavator_model.py:145-154` — `render_3d()` with `.tobytes()` call
  - `tests/test_rendering_math.py` — T1 validation results (read test output/docstrings)

  **WHY Each Reference Matters**:
  - `_build_matrices()`: This is where ALL MVP matrices are composed — the fix goes here
  - `render_3d()`: If fix is `.T` on the stored MVP, the `.tobytes()` call may need adjustment too
  - Test results: The test determines WHETHER and HOW to fix — must read T1 output first

  **Acceptance Criteria**:
  - [ ] If convention broken: MVP matrices produce correct clip coords after fix (verified by T1 tests)
  - [ ] If convention correct: Comment added documenting validation
  - [ ] `pytest tests/` → all PASS
  - [ ] `_ortho()`, `_look_at()`, `_perspective()` functions UNMODIFIED (diff check)

  **QA Scenarios (MANDATORY):**
  ```
  Scenario: Matrix convention fix produces correct clip coords
    Tool: Bash (pytest)
    Preconditions: T1 tests exist and convention status determined
    Steps:
      1. Run `pytest tests/test_rendering_math.py -v`
      2. Assert all convention-related tests pass
      3. If fix applied, verify ortho side view vertex (4, 3, 2, 1) gives w=1.0
    Expected Result: All matrix convention tests pass
    Failure Indicators: w≠1.0 for ortho matrices, or reversed transformation order
    Evidence: .sisyphus/evidence/task-4-convention-fix.txt

  Scenario: Helper functions remain unmodified
    Tool: Bash (git diff)
    Preconditions: Fix has been applied
    Steps:
      1. Run `git diff src/exca_dance/rendering/viewport_layout.py`
      2. Verify that lines 9-55 (_perspective, _ortho, _look_at functions) show NO changes
    Expected Result: Only _build_matrices() and composition lines changed
    Failure Indicators: Changes detected in helper function bodies
    Evidence: .sisyphus/evidence/task-4-scope-check.txt
  ```

  **Commit**: YES
  - Message: `fix(rendering): correct matrix row/column-major convention for GL`
  - Files: `src/exca_dance/rendering/viewport_layout.py`
  - Pre-commit: `pytest tests/`

- [ ] 5. Apply Box Rotation to Excavator Model

  **What to do**:
  - Replace axis-aligned box calls for boom, arm, and bucket links in `_update_geometry()` with the new `_make_oriented_box_verts()` from T3
  - Current code (lines 104-129):
    ```python
    # Boom: _make_box_verts(cx, cy, cz, length, 0.25, 0.25, color)
    # Arm:  _make_box_verts(cx2, cy2, cz2, length2, 0.20, 0.20, color)
    # Bucket: _make_box_verts(cx3, cy3, cz3, length3, 0.30, 0.25, color)
    ```
  - Replace with:
    ```python
    # Boom:
    verts += _make_oriented_box_verts(sp, bp, 0.25, 0.25, JOINT_COLORS[JointName.BOOM])
    # Arm:
    verts += _make_oriented_box_verts(bp, ap, 0.20, 0.20, JOINT_COLORS[JointName.ARM])
    # Bucket:
    verts += _make_oriented_box_verts(ap, bt, 0.30, 0.25, JOINT_COLORS[JointName.BUCKET])
    ```
  - The `sp`, `bp`, `ap`, `bt` variables (swing_pivot, boom_pivot, arm_pivot, bucket_tip) are already extracted from FK results
  - Keep base body and turret as axis-aligned `_make_box_verts()` — they don't rotate
  - Remove intermediate midpoint calculations (cx/cy/cz, dx/dy/dz, length) for the 3 rotating links — no longer needed
  - Update vertex count: should remain consistent (base 36 + turret 36 + boom 36 + arm 36 + bucket 36 = 180 total, same as before since both functions produce 36 verts)

  **Must NOT do**:
  - Do not change base body or turret rendering (axis-aligned is correct for them)
  - Do not change JOINT_COLORS or cross-section sizes (0.25, 0.20, 0.30)
  - Do not add new VBO/VAO allocations — keep release+recreate pattern
  - Do not modify FK return values

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Must correctly integrate 3D rotation geometry and validate visually
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after T3, T4)
  - **Blocks**: Task 8 (integration test)
  - **Blocked By**: Task 3 (oriented box helper), Task 4 (matrix convention)

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/excavator_model.py:92-143` — full `_update_geometry()` method
  - `src/exca_dance/rendering/excavator_model.py:131-143` — VBO/VAO release+recreate pattern (must keep)

  **API/Type References**:
  - FK output keys: `"base"`, `"swing_pivot"`, `"boom_pivot"`, `"arm_pivot"`, `"bucket_tip"` — each is `tuple[float, float, float]`
  - Variable names in existing code: `sp`, `bp`, `ap`, `bt` — already extracted from FK

  **WHY Each Reference Matters**:
  - `_update_geometry()`: This is the ONLY function being modified — all changes go here
  - VBO pattern: Must maintain the release+recreate approach, not add new allocations
  - FK keys: Must use the exact same dictionary keys to get pivot positions

  **Acceptance Criteria**:
  - [ ] `_update_geometry()` uses `_make_oriented_box_verts()` for boom, arm, bucket
  - [ ] Base and turret still use `_make_box_verts()` (axis-aligned)
  - [ ] Total vertex count unchanged (180 vertices = 5 boxes × 36 verts)
  - [ ] No new VBO/VAO allocations per frame
  - [ ] `pytest tests/` → all PASS

  **QA Scenarios (MANDATORY):**
  ```
  Scenario: Boom rotates visually with boom angle
    Tool: Bash (python REPL)
    Preconditions: _update_geometry uses _make_oriented_box_verts
    Steps:
      1. Create ExcavatorFK, compute forward_kinematics with boom=30°
      2. Get swing_pivot and boom_pivot positions
      3. Create _make_oriented_box_verts(sp, bp, 0.25, 0.25, color)
      4. Extract vertex positions, compute centroid of all vertices
      5. Assert centroid is at midpoint of sp↔bp (±0.1m tolerance)
      6. Assert vertex spread direction aligns with sp→bp vector
    Expected Result: Box centroid at link midpoint, vertices spread along link direction
    Failure Indicators: Centroid off-center, or box still axis-aligned
    Evidence: .sisyphus/evidence/task-5-boom-rotation.txt

  Scenario: Vertex count unchanged
    Tool: Bash (python REPL)
    Preconditions: Modified _update_geometry
    Steps:
      1. Count total floats in vertex array after _update_geometry()
      2. Assert count == 180 * 6 = 1080 (5 boxes × 36 verts × 6 floats)
    Expected Result: 1080 floats total
    Failure Indicators: Different count (means box generation changed)
    Evidence: .sisyphus/evidence/task-5-vertex-count.txt
  ```

  **Commit**: YES
  - Message: `fix(rendering): orient excavator link boxes along joint direction vectors`
  - Files: `src/exca_dance/rendering/excavator_model.py`
  - Pre-commit: `pytest tests/`

- [ ] 6. Fix Side View + Top View Matrices

  **What to do**:
  - **Side view (REQUIRED)**: Add `_look_at()` view matrix to `_mvp_side` in `_build_matrices()`
    - Camera looks along negative Y-axis to show XZ plane:
      ```python
      side_eye = np.array([4.0, -20.0, 3.0], dtype='f4')
      side_target = np.array([4.0, 0.0, 3.0], dtype='f4')
      side_up = np.array([0.0, 0.0, 1.0], dtype='f4')
      side_view = _look_at(side_eye, side_target, side_up)
      self._mvp_side = (side_ortho @ side_view).astype('f4')  # apply convention fix from T4
      ```
    - Ortho bounds: keep `_ortho(-2.0, 10.0, -1.0, 7.0)` — maps X range [-2,10], Z range [-1,7] to screen
  - **Top view (CONDITIONAL — based on T2 results)**:
    - IF T2 says top view is broken: Add `_look_at()` similarly:
      ```python
      top_eye = np.array([2.0, 0.0, 20.0], dtype='f4')
      top_target = np.array([2.0, 0.0, 0.0], dtype='f4')
      top_up = np.array([0.0, 1.0, 0.0], dtype='f4')
      top_view = _look_at(top_eye, top_target, top_up)
      self._mvp_top = (top_ortho @ top_view).astype('f4')
      ```
    - IF T2 says top view is correct: Leave `_mvp_top` as-is, add comment: `# Identity view — correct for XY plane top-down (validated in test_rendering_math.py)`
  - **Apply T4 convention fix**: If matrix convention was fixed in T4, use the same transpose/order approach here
  - Add tests in `tests/test_rendering_math.py`:
    - Test: side MVP × vertex (4, 0, 3, 1) → x proportional to 4, y proportional to 3 (X→screenX, Z→screenY)
    - Test: side MVP × vertex (4, 5, 3, 1) → same x,y as above (Y is depth, invisible)

  **Must NOT do**:
  - Do not modify `_ortho()` or `_look_at()` function implementations
  - Do not change ortho bounds values
  - Do not add camera interactivity (mouse/keyboard controls)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: View matrix setup with correct camera parameters for each projection
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (parallel with T5 after T4 completes)
  - **Parallel Group**: Wave 2 (with Task 5, after T2 and T4)
  - **Blocks**: Task 8 (integration test)
  - **Blocked By**: Task 2 (top view determination), Task 4 (matrix convention)

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/viewport_layout.py:66-95` — existing `_build_matrices()` and camera setup for 3D view
  - `src/exca_dance/rendering/viewport_layout.py:41-55` — `_look_at()` implementation
  - `src/exca_dance/rendering/viewport_layout.py:88` — existing 3D MVP composition pattern: `proj @ view`

  **API/Type References**:
  - `_look_at(eye, target, up)` → 4×4 float32 view matrix
  - Camera params: eye position should be far enough to capture full excavator reach (~5.3m)

  **WHY Each Reference Matters**:
  - `_build_matrices()`: Where the fix goes — must add view matrices for side and conditionally top
  - `_look_at()`: Must use the EXISTING implementation, not create a new one
  - 3D camera setup: Shows the convention for composing proj@view that must be followed (or adjusted per T4)

  **Acceptance Criteria**:
  - [ ] Side view MVP maps X→screenX, Z→screenY (XZ plane visible)
  - [ ] Side view: boom at 30° shows boom angling upward on screen
  - [ ] Top view: either fixed with look_at or documented as correct with comment
  - [ ] Tests verifying side MVP transformation added
  - [ ] `pytest tests/` → all PASS

  **QA Scenarios (MANDATORY):**
  ```
  Scenario: Side view shows XZ plane correctly
    Tool: Bash (python)
    Preconditions: Side view MVP has look_at view matrix
    Steps:
      1. Import _build_matrices results or construct side MVP
      2. Apply MVP to vertex (4, 0, 3, 1) → get clip coords
      3. Apply MVP to vertex (4, 5, 3, 1) → get clip coords
      4. Assert both give same screen x,y (Y is depth only)
      5. Apply to (0, 0, 0, 1) and (6, 0, 0, 1) → different screen x (X maps to screen X)
      6. Apply to (4, 0, 0, 1) and (4, 0, 5, 1) → different screen y (Z maps to screen Y)
    Expected Result: Y-axis goes to depth, X→screenX, Z→screenY
    Failure Indicators: Y affects screen position, or Z goes to depth
    Evidence: .sisyphus/evidence/task-6-side-view-matrix.txt
  ```

  **Commit**: YES
  - Message: `fix(rendering): add look-at view matrices for side and top 2D views`
  - Files: `src/exca_dance/rendering/viewport_layout.py`, `tests/test_rendering_math.py`
  - Pre-commit: `pytest tests/`

- [ ] 7. Viewport Borders and Labels

  **What to do**:
  - Add viewport borders and labels to `GameViewportLayout.render_all()` in `viewport_layout.py`
  - **Borders**:
    - Draw 1-2px lines at viewport panel boundaries using GL_LINES
    - Color: `NeonTheme.BORDER` = `Color(0.0, 0.83, 1.0, 0.6)` (electric blue, 60% alpha)
    - Borders are drawn in the FULL-SCREEN viewport (after resetting viewport) to avoid edge clipping
    - Need a simple line VBO/VAO using `prog_solid` shader with alpha
    - Lines: vertical separator at x=75% (main/panel boundary), horizontal separator at panel midpoint
  - **Labels**:
    - Use existing `GLTextRenderer` (passed from gameplay_screen/editor_screen)
    - Accept `text_renderer` as parameter in `render_all()` (add optional param with default None)
    - Labels: "3D" (top-left of main viewport), "TOP" (top-left of top panel), "SIDE" (top-left of side panel)
    - Color: `NeonTheme.TEXT_DIM` = `Color(0.6, 0.6, 0.7)` — subtle, not distracting
    - Scale: 0.75 (small, informational)
    - Position: 5px from top-left corner of each viewport region
  - Update callers: `gameplay_screen.py:77` and `editor_screen.py:194` to pass `text_renderer` if available

  **Must NOT do**:
  - Do not add scissor test unless bleeding is observed
  - Do not create a new text rendering system — use existing `GLTextRenderer`
  - Do not add grid lines or axis indicators — just borders and labels

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward GL line drawing + text rendering, no complex math
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (no deps on T4/T5/T6)
  - **Parallel Group**: Wave 3 (can start as early as Wave 2)
  - **Blocks**: Task 8 (integration test)
  - **Blocked By**: None (viewport regions already defined in ViewportManager)

  **References**:

  **Pattern References**:
  - `src/exca_dance/rendering/viewport_layout.py:97-117` — `render_all()` current implementation
  - `src/exca_dance/rendering/viewport.py:23-27` — viewport regions with pixel coordinates
  - `src/exca_dance/rendering/theme.py:52-53` — `NeonTheme.BORDER` color already defined
  - `src/exca_dance/ui/gameplay_hud.py:171-176` — `_draw_rect_2d()` pattern (placeholder but shows approach)

  **API/Type References**:
  - `ViewportManager._viewports` dict: `{name: (x, y, w, h)}` — exact pixel regions
  - `GLTextRenderer.render(text, x, y, color, scale, align)` — text rendering API
  - `prog_solid` shader: `in_position(3f), in_color(3f), uniform mvp(mat4), uniform alpha(float)`

  **WHY Each Reference Matters**:
  - `render_all()`: This is where borders/labels are added — after viewport rendering, before reset
  - `_viewports` dict: Provides exact pixel coordinates for border line positions
  - `NeonTheme.BORDER`: Pre-defined color for this exact purpose — must use it
  - `_draw_rect_2d()`: Shows the team's intended approach for 2D overlay drawing

  **Acceptance Criteria**:
  - [ ] Vertical border line visible at 75% width (main/panel separator)
  - [ ] Horizontal border line visible at panel midpoint (top/side separator)
  - [ ] Border color matches `NeonTheme.BORDER` (electric blue, semi-transparent)
  - [ ] Labels "3D", "TOP", "SIDE" visible in respective viewport corners
  - [ ] Labels use `NeonTheme.TEXT_DIM` color at scale 0.75
  - [ ] `gameplay_screen.py` and `editor_screen.py` updated to pass text_renderer
  - [ ] `pytest tests/` → all PASS

  **QA Scenarios (MANDATORY):**
  ```
  Scenario: Viewport borders render without crash
    Tool: Bash (python)
    Preconditions: Border rendering code added
    Steps:
      1. Import GameViewportLayout
      2. Check that render_all accepts text_renderer param
      3. Verify NeonTheme.BORDER.as_tuple() returns (0.0, 0.83, 1.0, 0.6)
    Expected Result: API accepts text_renderer, border color correct
    Failure Indicators: TypeError on render_all call, wrong color values
    Evidence: .sisyphus/evidence/task-7-border-api.txt

  Scenario: Callers updated to pass text_renderer
    Tool: Bash (grep)
    Preconditions: gameplay_screen.py and editor_screen.py modified
    Steps:
      1. Grep for 'render_all' in gameplay_screen.py and editor_screen.py
      2. Assert text_renderer is passed as argument
    Expected Result: Both callers pass text_renderer
    Failure Indicators: render_all called without text_renderer
    Evidence: .sisyphus/evidence/task-7-caller-update.txt
  ```

  **Commit**: YES
  - Message: `feat(rendering): add viewport borders and labels`
  - Files: `src/exca_dance/rendering/viewport_layout.py`, `src/exca_dance/ui/screens/gameplay_screen.py`, `src/exca_dance/editor/editor_screen.py`
  - Pre-commit: `pytest tests/`

- [ ] 8. Integration Test + Visual Verification

  **What to do**:
  - Run the full application and visually verify ALL rendering fixes work together
  - Steps:
    1. Run `python -m exca_dance --windowed` in tmux session
    2. Navigate to Editor screen (which shows the excavator model + viewport layout)
    3. Use keyboard to rotate boom (W/S keys) to ~30° and verify:
       - 3D view: boom box angles upward, connected to base
       - Side view: XZ plane shows boom angling up
       - Top view: boom extends along X (or at angle if swing is rotated)
    4. Rotate swing (A/D keys) to verify side+top views update correctly
    5. Test all joints at extreme angles (limits)
    6. Verify viewport borders and labels visible
    7. Screenshot each state
  - Also run `pytest tests/ -v` to verify all tests pass
  - Document results with screenshots and test output

  **Must NOT do**:
  - Do not modify any code — this is a verification-only task
  - Do not tune rendering parameters based on visual inspection

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Needs tmux for interactive app + visual verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (after all implementation tasks)
  - **Blocks**: F1-F4 (final verification)
  - **Blocked By**: Tasks 5, 6, 7 (all implementation must be complete)

  **References**:

  **Pattern References**:
  - `src/exca_dance/__main__.py:105` — Editor screen registration, access via menu
  - `src/exca_dance/editor/editor_screen.py:165-173` — Keyboard controls: W/S (boom), A/D (swing), UP/DOWN (arm), LEFT/RIGHT (bucket)
  - `src/exca_dance/core/constants.py:8-13` — Joint limits for extreme angle testing

  **WHY Each Reference Matters**:
  - `__main__.py`: Shows how to access the editor screen for visual testing
  - `editor_screen.py`: Keyboard controls needed to manipulate the excavator interactively
  - `constants.py`: Joint limits define the extreme test cases

  **Acceptance Criteria**:
  - [ ] Game launches without crash: `python -m exca_dance --windowed`
  - [ ] 3D view: boom visually rotates with W/S keys
  - [ ] Side view: XZ plane, boom angles upward when W pressed
  - [ ] Top view: XY plane, arm sweeps when A/D pressed
  - [ ] Viewport borders visible in electric blue
  - [ ] Labels "3D", "TOP", "SIDE" visible
  - [ ] All joints at limits: no visual glitches or crashes
  - [ ] `pytest tests/ -v` → all PASS
  - [ ] Screenshots captured as evidence

  **QA Scenarios (MANDATORY):**
  ```
  Scenario: Game launches and renders correctly
    Tool: interactive_bash (tmux)
    Preconditions: All implementation tasks complete
    Steps:
      1. Start tmux session: new-session -d -s exca-test
      2. Run: send-keys -t exca-test 'python -m exca_dance --windowed' Enter
      3. Wait 3s for window to appear
      4. Navigate to editor screen
      5. Press W key several times to rotate boom
      6. Take screenshot
      7. Press A key several times to rotate swing
      8. Take screenshot
      9. Quit game (ESC → Q)
    Expected Result: Game runs, excavator visible with rotating links in all viewports
    Failure Indicators: Black screen, crash, axis-aligned boxes, missing viewports
    Evidence: .sisyphus/evidence/task-8-visual-integration.png

  Scenario: All tests pass after integration
    Tool: Bash (pytest)
    Preconditions: Game tested visually
    Steps:
      1. Run `pytest tests/ -v`
      2. Assert all tests pass (original 6 + new rendering tests)
    Expected Result: All tests PASS
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-8-test-suite.txt
  ```

  **Commit**: NO (verification only, no code changes)
## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read `.sisyphus/plans/fix-excavator-rendering.md` end-to-end. For each "Must Have": verify implementation exists (read file, run test). For each "Must NOT Have": grep codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `pytest tests/` + lsp_diagnostics on all modified files. Review changed files for: `as any`/`# type: ignore`, empty catches, `print()` in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Tests [N pass/N fail] | Diagnostics [N errors] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start game with `python -m exca_dance --windowed`. On gameplay or editor screen: (1) Set boom=30° and verify boom box angles upward, (2) Verify side view shows XZ plane, (3) Verify top view shows XY plane, (4) Verify viewport borders visible, (5) Test extreme angles (all joints at limits). Screenshot each. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git diff). Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance: kinematics.py untouched, renderer.py shaders untouched, no ortho range changes. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Scope [CLEAN/N issues] | Forbidden [CLEAN/N violations] | VERDICT`

---

## Commit Strategy

| Commit | Message | Files | Pre-commit |
|--------|---------|-------|------------|
| 1 | `test(rendering): add matrix convention and geometry validation tests` | `tests/test_rendering_math.py` | `pytest tests/` |
| 2 | `fix(rendering): correct matrix row/column-major convention for GL` | `viewport_layout.py` | `pytest tests/` |
| 3 | `fix(rendering): orient excavator link boxes along joint direction vectors` | `excavator_model.py` | `pytest tests/` |
| 4 | `fix(rendering): add look-at view matrices for side and top 2D views` | `viewport_layout.py` | `pytest tests/` |
| 5 | `feat(rendering): add viewport borders and labels` | `viewport_layout.py` | `pytest tests/` |

---

## Success Criteria

### Verification Commands
```bash
pytest tests/ -v            # Expected: all tests PASS including new test_rendering_math.py
python -m exca_dance --windowed  # Expected: 3D model shows connected rotating links, 2D views show correct projections
```

### Final Checklist
- [ ] 3D 모델 링크가 관절 방향으로 회전
- [ ] Side 2D 뷰가 XZ 평면 표시
- [ ] Top 2D 뷰가 XY 평면 표시
- [ ] 뷰포트 경계선 + 라벨 표시
- [ ] 행렬 컨벤션 검증 테스트 통과
- [ ] 기존 테스트 42개 전부 통과
- [ ] kinematics.py 미변경
- [ ] renderer.py 셰이더 미변경
- [ ] 제로 길이 링크 안전 처리
