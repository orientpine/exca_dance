# HANDOFF CONTEXT

## USER REQUESTS (AS-IS)

- "joint 축은 얼추 정돈된것 같은데, 아직 joint origin들이 올바르게 정리된 것 같지 않아. 공중에서 boom, arm, bucket이 떠다녀. 이 문제를 근본적으로 해결할수있는 테스트 셋과 해결책을 강구해."
- "'/home/cha/Documents/hr35_modeling/renders/ix35e_urdf_render.png' 여기 있는 자세가 올바르게 결합되어 있는 이미지야. 해당 이미지를 만들었던 과정을 검토해서, 테스트 셋을 만들어."
- "회전 축의 벡터는 일치된것 같아. 하지만 회전 축의 위치가 틀려. 현재는 boom을 움직이면 회전축이 링크 내부에 존재하는 것이 아니라 허공에 존재해서 링크가 베이스 링크를 벗어나."
- "정확한 위치를 표기할 수 있도록 네가 모델 스크린샷을 제공+기록할 수있는 프로그램을 간단하지만 효과적으로 작성해서, 그 프로그램으로 기록된 좌표 정보를 전달해주는 방법으로 진행해."
- "지금 이상해졌어. 여전히 올바른 joint 위치가 아니야... default 자세에서 출발해서 측정된 joint값을 적용해야하는데, 지금은 측정된 joint 위치 값을 적용할떄, default 자세가 틀어진 느낌이야."
- "이걸 문서화 하고, 개선안대로 진행해."

---

## GOAL

ix35e 굴착기의 3D FK 렌더링에서 조인트 피벗 위치와 메시 프레임을 올바르게 분리하여, zero-pose 조립이 정상이면서 동시에 회전이 정확한 물리적 핀 위치에서 일어나도록 하는 이중 프레임 구조를 완성하고 검증하는 것.

---

## WORK COMPLETED

- STL collision mesh가 urdfpy FK 기준으로 link-local 좌표 export 됨을 진단 (`hr35_modeling/ix35e_description/scripts/convert_fbx.py`의 `inv(link_world_transform)` 적용)
- 기존 차분 트랜스폼 (`link_T @ inv_zero_T`) 제거, direct `link_T` 렌더링으로 전환 후 world→parent-relative origin 변환 복원
- boom/stick/bucket 회전 축을 `(0,1,0)` → `(1,0,0)` 교정 (Z-up 좌표계에서 시상면 회전 필요)
- `tools/joint_marker.py` 제작 — 3패널 직교 뷰(Side YZ, Top XY, Front XZ), 클릭 좌표 설정, 화살표 미세조정, 중클릭 패닝, 스크롤 줌, JSON 저장
- 사용자가 도구로 실제 물리적 핀 위치 측정 → `tools/joint_markers.json` 저장
- `origin_xyz` 직접 교체 시 zero-pose 메시 정렬이 깨짐을 발견 (origin_xyz가 메시 프레임과 피벗 프레임 두 용도로 사용)
- **이중 프레임 아키텍처** 구현:
  - `origin_xyz` → 원본 유지 (메시 프레임, 불변)
  - `MEASURED_PIVOTS` → 측정값 별도 저장 (피벗 프레임)
  - `_build_parent_relative_origins()` → 측정값 사용
  - `compute_mesh_corrections()` = `inv(피벗FK_zero) @ raw_FK_zero`
- `skills/rendering-pipeline.md`에 이중 프레임 구조 문서화
- `skills/error-log.md`에 ERR-007(축), ERR-008(피벗/메시 커플링) 기록
- `AGENTS.md`에 한국어 응답 지침(`LANGUAGE` 섹션) 추가
- 테스트 123개 전부 통과, headless 기동 정상

---

## CURRENT STATE

- 최신 커밋: `b3c237c` → `origin/main` 푸시 완료
- 123 테스트 전부 통과
- headless 기동 (`xvfb-run -a SDL_AUDIODRIVER=dummy python -m exca_dance --windowed`) 정상 종료
- 이중 프레임 FK 아키텍처 구현 및 문서화 완료
- **사용자가 최신 수정 결과를 게임에서 시각적으로 아직 확인하지 않음** — 이것이 다음 단계
- 미커밋 변경: `.opencode` 설정, `data/error.log`, `src/exca_dance/__main__.py` (미미), `debug_screenshot.png` — FK 작업과 무관

---

## PENDING TASKS

- 사용자가 게임을 실행하여 boom/arm/bucket 회전이 올바른지 시각적 확인
- 피벗이 여전히 틀리다면 `python tools/joint_marker.py`로 재측정 → `MEASURED_PIVOTS`만 업데이트
- 진행 중인 플랜 `.sisyphus/plans/gameplay-screen-overhaul.md` 재개 (14/31 완료, 이번 FK 작업은 계획 외 이탈)

---

## KEY FILES

| 파일 | 역할 |
|------|------|
| `src/exca_dance/rendering/urdf_kin.py` | FK 체인 — `MEASURED_PIVOTS`, `_build_parent_relative_origins()`, `compute_mesh_corrections()` |
| `src/exca_dance/rendering/excavator_model.py` | `build_model_matrix(link_T, correction)`, `_mesh_corrections` 사전 계산 |
| `tests/test_urdf_kin.py` | 12개 테스트: 포즈 레퍼런스 6종, 자식 origin, 시상면 회전, 메시 센트로이드 |
| `tools/joint_marker.py` | 3패널 직교 뷰 조인트 위치 측정 도구 |
| `tools/joint_markers.json` | 사용자 측정 피벗 위치 (swing/boom/arm/bucket) |
| `skills/rendering-pipeline.md` | 이중 프레임 아키텍처 문서 포함 |
| `skills/error-log.md` | ERR-007(축), ERR-008(피벗/메시 커플링) |
| `/home/cha/Documents/hr35_modeling/scripts/render_urdf.py` | 올바른 조립 이미지를 만든 레퍼런스 렌더링 파이프라인 |
| `/home/cha/Documents/hr35_modeling/ix35e_description/urdf/ix35e.urdf` | 소스 URDF (origin_xyz는 world-frame, 축은 이 게임에서 틀림) |

---

## IMPORTANT DECISIONS

- URDF `origin_xyz`는 world-frame 좌표 (표준 URDF의 parent-relative가 아님) → `_build_parent_relative_origins()`가 변환
- 메시 프레임과 피벗 프레임은 **반드시 분리** — `origin_xyz`는 메시 배치(불변), `MEASURED_PIVOTS`는 회전 피벗(독립 업데이트 가능)
- boom/stick/bucket 축은 `(1,0,0)` — 소스 URDF의 `(0,1,0)`은 Z-up 게임 좌표계에서 틀림
- 레퍼런스 렌더 이미지는 zero-pose였기 때문에 축/피벗 오류가 이미지에 나타나지 않았음
- `compute_mesh_corrections()` = `inv(피벗FK_zero) @ raw_FK_zero` 가 두 프레임을 연결

---

## EXPLICIT CONSTRAINTS

- 모든 응답은 **한국어**로 작성한다. 코드, 커밋 메시지, 변수명은 영어 유지.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`은 테스트 실행 시 필수.
- `origin_xyz`와 `MEASURED_PIVOTS`는 독립적으로 관리. 동시에 변경 금지.
- `blend_func`은 ModernGL 5.x에서 쓰기 전용 — getter 사용 금지 (`NotImplementedError`).
- `# type: ignore`, `# noqa` 사용 금지 — 코드베이스에 없음, 유지할 것.

---

## CONTEXT FOR CONTINUATION

- 사용자는 최신 이중 프레임 수정이 게임에서 올바른 시각 결과를 내는지 확인 중
- 시각 결과가 여전히 틀리면 `MEASURED_PIVOTS` 값 재측정 (`python tools/joint_marker.py`)
- 재측정 후 `urdf_kin.py`의 `MEASURED_PIVOTS`만 업데이트하고 테스트 레퍼런스 재계산
- 테스트 재계산: `compute_link_transforms()` 결과를 python으로 직접 출력해 붙여넣기
- FK 작업 완료 후 `.sisyphus/plans/gameplay-screen-overhaul.md`의 첫 번째 미완료 체크박스부터 재개
- hr35_modeling 레포 (`/home/cha/Documents/hr35_modeling`)에 ground truth URDF, 메시 export 스크립트, 레퍼런스 렌더 존재
- **핵심 주의사항**: 소스 URDF 축 `(0,1,0)`은 이 게임에서 항상 틀림 — boom/stick/bucket은 `(1,0,0)` 고정
- **핵심 주의사항**: `origin_xyz`를 측정값으로 직접 교체하면 메시 정렬이 깨짐 — 반드시 `MEASURED_PIVOTS` 분리 구조 유지
