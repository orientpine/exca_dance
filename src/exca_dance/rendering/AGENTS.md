# AGENTS.md — rendering/

ModernGL-based 3D rendering pipeline. All rendering is OpenGL — no pygame Surface.blit() anywhere.

---

## REQUIRED SKILLS

> 이 모듈 작업 전 반드시 읽어야 할 스킬 문서:

| 스킬 | 파일 | 핵심 내용 |
|------|------|-----------|
| Python 컨벤션 | `skills/python-conventions.md` | 임포트 규칙, 타입, 코드 스타일 |
| 렌더링 파이프라인 | `skills/rendering-pipeline.md` | ModernGL, 셰이더, VBO/VAO, 뷰포트, 테마 |
| 안티패턴 | `skills/anti-patterns.md` | 금지 패턴, 명령어, blend_func getter 금지 |

---

## STRUCTURE

```
rendering/
├── renderer.py          # GameRenderer — ModernGL context, 3 shader programs, frame lifecycle
├── excavator_model.py   # ExcavatorModel — 3D geometry from FK, VBO/VAO management
├── viewport.py          # ViewportManager — raw GL viewport rect management
├── viewport_layout.py   # GameViewportLayout — 3-panel MVP matrices, decorations, grid
├── visual_cues.py       # VisualCueRenderer — ghost pose, beat timeline, glow effects
├── theme.py             # NeonTheme — all color constants (cyberpunk palette)
├── gl_text.py           # GLTextRenderer — pygame.font → GL texture atlas
└── render_math.py       # Pure math utilities — direction_vector, make_oriented_box, etc.
```

---

## SHADER PROGRAMS

All compiled once at startup in `GameRenderer._compile_shaders()`:

| Program | VBO layout | Uniforms | Used for |
|---------|-----------|----------|----------|
| `prog_solid` | `3f 3f 3f` → `in_position, in_color, in_normal` | `mvp: mat4`, `alpha: float` | 3D geometry, grid lines, HUD rects |
| `prog_tex` | `2f 2f` → `in_position, in_uv` | `screen_size`, `pos`, `size`, `tex`, `color` | GL text (font atlas) |
| `prog_additive` | `3f 4f` → `in_position, in_color` | `mvp: mat4` | Glow/neon effects (additive blend) |

`prog_solid` fragment shader applies directional lighting: `ambient=0.35`, `light_dir=(0.3, -0.5, 0.8)`.

---

## VIEWPORT LAYOUT (1920×1080)

```
┌──────────────────────────┬──────────┐
│       MAIN_3D            │  TOP_2D  │  y=540..1080
│   (1440×1080)            │ (480×540)│
│   perspective 45°        ├──────────┤
│   eye=[6,-8,5]           │  SIDE_2D │  y=0..540
│                          │ (480×540)│
└──────────────────────────┴──────────┘
```

GL origin is **bottom-left**. Viewport rects: `(x, y, w, h)`.

Pre-computed MVP matrices (static — camera never moves):
- `mvp_3d`: perspective(45°) × look_at(eye=[6,-8,5], target=[2,0,1.5])
- `mvp_top`: ortho × look_at(eye=[2,0,15], target=[2,0,0]) — XY top-down
- `mvp_side`: ortho × look_at(eye=[0,-12,3], target=[2,0,3]) — XZ side

---

## GAMEPLAY RENDER ORDER

```
1. viewport_layout.render_all(model)          # excavator in all 3 viewports
2. viewport_layout.render_2d_grid("top_2d")   # reference grid
3. viewport_layout.render_2d_grid("side_2d")
4. visual_cues.render_ghost(mvp_*)            # ghost in each viewport (set_viewport first)
5. ctx.viewport = (0, 0, W, H)               # RESET to full screen
6. viewport_layout.render_viewport_decorations(text_renderer)  # borders + labels
7. hud.render(joint_angles)                   # 2D overlay
```

---

## MATRIX CONVENTION

Numpy is row-major; GL expects column-major:

```python
prog["mvp"].write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
```

Always `.T.tobytes()` when sending a matrix uniform. `render_math.validate_gl_matrix()` checks shape + dtype + finite values.

---

## NEON THEME COLORS

```python
# Current pose joints
NeonTheme.JOINT_BOOM    # orange  (1.0, 0.4, 0.0)
NeonTheme.JOINT_ARM     # yellow  (1.0, 0.8, 0.0)
NeonTheme.JOINT_BUCKET  # cyan    (0.0, 0.8, 1.0)

# Ghost (target pose) — violet/purple palette
NeonTheme.GHOST_BOOM    # vivid violet-blue  (0.4, 0.2, 1.0)
NeonTheme.GHOST_ARM     # lavender           (0.6, 0.3, 1.0)
NeonTheme.GHOST_BUCKET  # bright violet      (0.8, 0.4, 1.0)
NeonTheme.GHOST_ALPHA   # 0.55

# UI
NeonTheme.NEON_BLUE     # #00D4FF
NeonTheme.NEON_PINK     # #FF0066
NeonTheme.BORDER        # electric blue 60% alpha
NeonTheme.BG            # near-black navy (0.04, 0.04, 0.10)
```

---

## EXCAVATOR MODEL

`ExcavatorModel(renderer, fk=None, joint_colors=None)`

- `joint_colors` dict overrides default `JOINT_COLORS` — used by ghost model for violet palette
- `_make_link_verts(p1, p2, w, h, color)` — oriented box along p1→p2 direction vector
- `_make_box_verts(cx, cy, cz, lx, ly, lz, color)` — axis-aligned box with face normals
- VBO layout: `position(3) + color(3) + normal(3)` = 9 floats/vertex, 36 vertices/box

---

## ANTI-PATTERNS

```python
# FORBIDDEN — all rendering is OpenGL
surface.blit(...)

# FORBIDDEN — wrong matrix convention
prog["mvp"].write(mvp.tobytes())          # missing .T
prog["mvp"].write(mvp.astype("f4").tobytes())  # still missing .T

# FORBIDDEN — modifying shader source at runtime
renderer.prog_solid = ctx.program(...)    # shaders are compiled once

# FORBIDDEN — blend_func is WRITE-ONLY in ModernGL 5.x (getter raises NotImplementedError)
old = ctx.blend_func              # crashes at runtime
# Instead: set what you need, restore with DEFAULT_BLENDING in finally block
ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)  # set
ctx.blend_func = moderngl.DEFAULT_BLENDING            # restore
```
