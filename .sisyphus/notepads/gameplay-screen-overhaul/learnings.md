# Learnings — gameplay-screen-overhaul

## Project Context
- Stack: Python 3.12, pygame-ce 2.5.7, ModernGL 5.x, numpy
- Existing shaders: `prog_solid` (3f 3f 3f=pos+color+normal), `prog_tex` (text), `prog_additive` (3f 4f=pos+rgba)
- VBO format in ExcavatorModel: `"3f 3f 3f"` = 9 floats/vertex (pos + color + normal)
- Ghost model: 5 parts × 36 vertices = 180 vertices × 9 floats = 1620 floats total

## Key Bugs Found
- VBO stride bug in `visual_cues.py:_rebuild_ghost_glow()`: reshapes as (-1,6) instead of (-1,9) → 2/3 glow triangles corrupted
- Fixed glow VBO readback to use 9-float vertices and rebuild additive glow data as `[pos, color, alpha]` rows
- Ghost glow alpha ceiling: 0.55 × 0.25 = 13.75% max → nearly invisible
- GHOST_OUTLINE color defined in theme.py but never used

## Architecture Notes
- `prog_solid` works with "3f 3f" format (no normals) — confirmed in viewport_layout.py:175
- `prog_additive` format: "3f 4f" (position3 + rgba4), additive blend: SRC_ALPHA, ONE
- Depth test must be DISABLED for outline pass to avoid z-fighting
- `time.perf_counter()` for ALL timing — never pygame clock
- ALL new files need `from __future__ import annotations` at top
- Line length: 100 chars (ruff enforced)
- Numpy matrices to GL: `np.ascontiguousarray(mat.astype("f4").T).tobytes()`

## FK 2D Helpers
- `ExcavatorFK.get_joint_positions_2d_side()` returns list of `(x, z)` tuples (NO name)
- `ExcavatorFK.get_joint_positions_2d_top()` returns list of `(x, y)` tuples (NO name)
- Order: base → swing_pivot → boom_pivot → arm_pivot → bucket_tip (5 points)

## API Notes
- `VisualCueRenderer.get_angle_match_pct(joint: JointName) -> float` — takes SINGLE joint, NOT dict
- Call per-joint: `{j: visual_cues.get_angle_match_pct(j) for j in JointName}`
- `render_timeline(self, renderer, text_renderer, song_duration_ms)` — internal state handles time/events

## VBO Lifecycle Pattern (MUST FOLLOW)
```python
vbo = ctx.buffer(data.astype('f4').tobytes())
vao = ctx.vertex_array(prog, [(vbo, '3f 3f', 'in_position', 'in_color')])
try:
    vao.render(moderngl.LINES)
finally:
    vbo.release()
    vao.release()
```

## Gameplay Screen Wiring
- `GameplayScreen.render()` now calls `render_timeline()` after `ctx.viewport` is reset and before `hud.render()`.
- `render_timeline()` still uses HUD song duration state for its unused duration argument; implementation remains untouched.
