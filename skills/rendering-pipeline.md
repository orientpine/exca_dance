# Rendering — OpenGL 렌더링 파이프라인

> **목적**: exca_dance의 ModernGL 기반 렌더링 시스템 — 컨텍스트 초기화, 셰이더, VBO/VAO 패턴, 행렬 컨벤션, 블렌드 모드, 뷰포트, 테마, 텍스트 렌더링을 정의한다.
>
> **대상 파일**: `src/exca_dance/rendering/` 전체

---

## ModernGL 컨텍스트 초기화

```python
pygame.display.init()
flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.NOFRAME
surface = pygame.display.set_mode((W, H), flags)
ctx = moderngl.create_context()
ctx.enable(moderngl.BLEND)
ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
```

- pygame은 윈도우 백엔드 역할 (OPENGL 플래그 필수)
- DOUBLEBUF으로 더블 버퍼링
- 블렌드 기본 활성화

---

## 셰이더 프로그램 (6개)

모든 셰이더는 시작 시 `GameRenderer._compile_shaders()`에서 한 번만 컴파일.

### prog_solid — 3D 지오메트리 + 조명

| 어트리뷰트 | 포맷 | 설명 |
|-----------|------|------|
| `in_position` | 3f | 정점 위치 |
| `in_color` | 3f | 정점 색상 (RGB) |
| `in_normal` | 3f | 정점 노멀 |

| 유니폼 | 타입 | 설명 |
|--------|------|------|
| `mvp` | mat4 | Model-View-Projection 행렬 |
| `model` | mat4 | 모델 행렬 (파트별 차분 트랜스폼) |
| `alpha` | float | 전역 알파 곱수 |

프래그먼트 셰이더: 방향 조명, `ambient=0.35`, `light_dir=(0.3, -0.5, 0.8)`

### prog_tex — 텍스처 쿼드 (GL 텍스트)

| 어트리뷰트 | 포맷 | 설명 |
|-----------|------|------|
| `in_position` | 2f | 쿼드 정점 위치 |
| `in_uv` | 2f | 텍스처 좌표 |

| 유니폼 | 타입 | 설명 |
|--------|------|------|
| `screen_size` | vec2 | 윈도우 크기 |
| `pos` | vec2 | 스크린 위치 (좌상단) |
| `size` | vec2 | 쿼드 크기 |
| `tex` | sampler2D | 폰트 텍스처 아틀라스 |
| `color` | vec4 | RGBA 색상 |

### prog_additive — 글로우/네온 이펙트

| 어트리뷰트 | 포맷 | 설명 |
|-----------|------|------|
| `in_position` | 3f | 정점 위치 |
| `in_color` | 4f | 정점 색상 (RGBA) |

| 유니폼 | 타입 | 설명 |
|--------|------|------|
| `mvp` | mat4 | MVP 행렬 |
| `alpha_mult` | float | 아웃라인 펄스 곱수 |

### prog_bloom_extract / prog_bloom_blit — 블룸 파이프라인

- **Extract**: 밝기 > 0.7 → 별도 텍스처 (절반 해상도)
- **Blur**: 13-tap 가우시안 (분리형, 수평+수직)
- **Composite**: 장면 + 블룸 가산 합성

---

## VBO/VAO 패턴

### 정적 VBO (굴착기 모델 — 파트별)

```python
# 인터리빙: position(3f) + color(3f) + normal(3f) = 9 floats
interleaved = np.empty((n, 9), dtype=np.float32)
interleaved[:, :3] = vertices
interleaved[:, 3:6] = colors
interleaved[:, 6:9] = normals

vbo = ctx.buffer(interleaved.ravel().tobytes())
vao = ctx.vertex_array(prog, [(vbo, "3f 3f 3f", "in_position", "in_color", "in_normal")])
```

파트별 정적 VBO, 시작 시 한 번 업로드. 매 프레임 = 4×4 행렬 계산 + `model` 유니폼 갱신.

### 동적 VBO (비주얼 큐 — 사전 할당)

```python
self._tl_solid_vbo = ctx.buffer(reserve=RESERVE_SIZE)
self._tl_solid_vao = ctx.vertex_array(prog, [(self._tl_solid_vbo, "3f 3f", "in_position", "in_color")])
# 매 프레임: vbo.write(data)
```

### 임시 VBO (그리드 — 매 프레임 생성/해제)

```python
vbo = ctx.buffer(data)
vao = ctx.vertex_array(prog, [(vbo, "3f 3f", "in_position", "in_color")])
vao.render(moderngl.LINES)
vao.release()
vbo.release()
```

---

## 행렬 컨벤션 (★ 핵심)

**NumPy는 row-major, GL은 column-major** — 반드시 전치(`.T`) 필요:

```python
# ✅ 올바른 방법
prog["mvp"].write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())

# ❌ 잘못된 방법 (전치 누락)
prog["mvp"].write(mvp.tobytes())
prog["mvp"].write(mvp.astype("f4").tobytes())
```

검증:
```python
def validate_gl_matrix(mat: np.ndarray) -> bool:
    arr = np.asarray(mat)
    return bool(arr.shape == (4, 4) and arr.dtype == np.dtype("f4") and np.all(np.isfinite(arr)))
```

---

## 블렌드 모드

| 모드 | 용도 | 코드 |
|------|------|------|
| 표준 | 지오메트리, 텍스트 | `ctx.blend_func = (SRC_ALPHA, ONE_MINUS_SRC_ALPHA)` |
| 가산 | 글로우, 타임라인, 고스트 | `ctx.blend_func = (SRC_ALPHA, ONE)` |

```python
# 가산 블렌딩 사용 패턴 (반드시 try/finally)
ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
try:
    # ... 가산 렌더링 ...
finally:
    ctx.blend_func = moderngl.DEFAULT_BLENDING
```

> **경고**: `ctx.blend_func` getter는 ModernGL 5.x에서 `NotImplementedError`를 발생시킨다. 읽기 금지.

---

## 뷰포트 레이아웃 (1920×1080)

```
┌──────────────────────────┬──────────┐
│       MAIN_3D            │  TOP_2D   │  y=540..1080
│   (1440×1080)            │ (480×540) │
│   perspective 45°         ├──────────┤
│   eye=[6,-8,5]           │  SIDE_2D  │  y=0..540
│                          │ (480×540) │
└──────────────────────────┴──────────┘
```

**GL 원점은 좌하단.** 뷰포트 rect: `(x, y, width, height)`.

| 뷰 | 프로젝션 | 카메라 |
|-----|---------|--------|
| `mvp_3d` | perspective(45°) | look_at(eye=[6,-8,5], target=[2,0,1.5]) |
| `mvp_top` | orthographic | look_at(eye=[2,0,15], target=[2,0,0]) — XY 탑다운 |
| `mvp_side` | orthographic | look_at(eye=[0,-12,3], target=[2,0,3]) — XZ 사이드 |

MVP 행렬은 **정적** — 카메라 이동 없음.

---

## 테마 시스템 (`rendering/theme.py`)

```python
@dataclass(frozen=True)
class Color:
    r: float; g: float; b: float; a: float = 1.0
    def as_tuple(self) -> tuple[float, float, float, float]: ...
    def as_rgb(self) -> tuple[float, float, float]: ...
    def as_pygame_rgb(self) -> tuple[int, int, int]: ...
    def with_alpha(self, a: float) -> Color: ...
```

**NeonTheme 팔레트 (주요):**

| 상수 | 색상 | 용도 |
|------|------|------|
| `BG` | (0.04, 0.04, 0.10) | 메인 배경 |
| `NEON_BLUE` | #00D4FF | 테두리, 히트라인 |
| `NEON_PINK` | #FF0066 | 글로우 링 |
| `JOINT_BOOM` | 오렌지 (1.0, 0.4, 0.0) | 현재 붐 |
| `JOINT_ARM` | 노랑 (1.0, 0.8, 0.0) | 현재 암 |
| `JOINT_BUCKET` | 시안 (0.0, 0.8, 1.0) | 현재 버킷 |
| `GHOST_BOOM` | 보라 (0.6, 0.4, 1.0) | 고스트 붐 |
| `GHOST_ARM` | 라벤더 (0.8, 0.5, 1.0) | 고스트 암 |
| `GHOST_BUCKET` | 핑크보라 (1.0, 0.7, 1.0) | 고스트 버킷 |
| `PERFECT` | 골드 #FFD700 | 판정 색상 |
| `GREAT` | 시안 #00CCFF | 판정 색상 |
| `GOOD` | 초록 #00FF88 | 판정 색상 |
| `MISS` | 빨강 #FF0044 | 판정 색상 |

---

## 텍스트 렌더링 (`rendering/gl_text.py`)

1. **pygame.font** → 흰색 텍스트 서피스 렌더 (per-pixel alpha)
2. **알파 채널 추출** → 글리프 마스크 (GL row-major 위해 전치)
3. **moderngl.Texture** 생성 (`dtype="f1"`, uint8 alpha)
4. **셰이더**가 텍스처 알파 × `color` 유니폼으로 렌더

캐싱: `dict[tuple[str, int], tuple[Texture, w, h]]` — 키: (text, id(font))

---

## 게임플레이 렌더 순서

```
1. viewport_layout.render_all(model)          # 3개 뷰포트에 굴착기
2. viewport_layout.render_2d_grid("top_2d")   # 참조 그리드
3. viewport_layout.render_2d_grid("side_2d")
4. visual_cues.render_ghost(mvp_*)            # 각 뷰포트에 고스트
5. ctx.viewport = (0, 0, W, H)                # 풀스크린으로 리셋
6. viewport_layout.render_viewport_decorations(text_renderer)
7. hud.render(joint_angles)                   # 2D 오버레이
```

---

## URDF FK 시스템 (`rendering/urdf_kin.py`)

```python
GAME_JOINT_MAP: dict[JointName, str] = {
    JointName.SWING: "swing_joint",
    JointName.BOOM: "boom_joint",
    JointName.ARM: "stick_joint",
    JointName.BUCKET: "bucket_joint",
}

def compute_link_transforms(joint_angles: dict[JointName, float]) -> dict[str, np.ndarray]:
    # 입력: 각도(도), 출력: link_name → 4×4 float64 월드 트랜스폼
    ...
```

**차분 트랜스폼 패턴:**
```python
model = link_T @ part.inv_zero_T
self._write_model_matrix(prog, model)
part.vao.render(moderngl.TRIANGLES, vertices=part.vertex_count)
```

---

## 렌더링 안티패턴

```python
# ❌ 모든 렌더링은 OpenGL
surface.blit(...)
pygame.draw.line(...)

# ❌ 행렬 전치 누락
prog["mvp"].write(mvp.tobytes())

# ❌ 셰이더 런타임 컴파일
renderer.prog_solid = ctx.program(...)

# ❌ blend_func getter (ModernGL 5.x)
old = ctx.blend_func  # NotImplementedError
```
