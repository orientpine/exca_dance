#!/usr/bin/env python3
"""Joint position marker tool — 3-panel orthographic views.

Three orthographic panels let you triangulate precise 3D joint positions:
  SIDE  (left,  large) — looking along -X → click sets Y, Z
  TOP   (right-top)    — looking along -Z → click sets X, Y
  FRONT (right-bottom) — looking along +Y → click sets X, Z

Controls:
  Left-click     — set 2 coordinates from the clicked panel
  1/2/3/4        — select joint: 1=swing, 2=boom, 3=arm, 4=bucket
  Arrow keys     — fine-adjust current marker (0.005m per press)
    Left/Right   — adjust axis-1 of last-clicked panel
    Up/Down      — adjust axis-2 of last-clicked panel
  Shift+Arrows   — coarse adjust (0.05m)
  S              — save markers to tools/joint_markers.json
  R              — reset current marker
  ESC            — quit
  Scroll         — zoom in/out (on hovered panel)
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import moderngl
import numpy as np
import pygame

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from exca_dance.rendering.stl_loader import load_binary_stl  # noqa: E402
from exca_dance.rendering.urdf_kin import MESH_TO_LINK, _compute_raw_origin_fk  # noqa: E402

MESH_DIR = ROOT / "assets" / "meshes" / "collision"
OUTPUT = ROOT / "tools" / "joint_markers.json"
W, H = 1280, 900

JOINT_NAMES = ["swing", "boom", "arm", "bucket"]
JOINT_COLORS_RGB = {
    "swing": (0.0, 1.0, 0.0),
    "boom": (1.0, 0.4, 0.0),
    "arm": (1.0, 0.8, 0.0),
    "bucket": (0.0, 0.8, 1.0),
}

VERT_SRC = """
#version 330
in vec3 in_position;
in vec3 in_color;
in vec3 in_normal;
uniform mat4 mvp;
uniform mat4 model;
out vec3 v_color;
out vec3 v_normal;
void main() {
    vec4 world = model * vec4(in_position, 1.0);
    gl_Position = mvp * world;
    v_color = in_color;
    v_normal = mat3(model) * in_normal;
}
"""

FRAG_SRC = """
#version 330
in vec3 v_color;
in vec3 v_normal;
uniform float alpha;
out vec4 fragColor;
void main() {
    vec3 ld = normalize(vec3(0.3, -0.5, 0.8));
    float d = max(dot(normalize(v_normal), ld), 0.0);
    fragColor = vec4(v_color * (0.35 + 0.65 * d), alpha);
}
"""

LINE_VERT = """
#version 330
in vec3 in_position;
uniform mat4 mvp;
uniform vec3 line_color;
out vec3 v_color;
void main() {
    gl_Position = mvp * vec4(in_position, 1.0);
    v_color = line_color;
}
"""

LINE_FRAG = """
#version 330
in vec3 v_color;
out vec4 fragColor;
void main() {
    fragColor = vec4(v_color, 0.8);
}
"""


@dataclass
class Panel:
    name: str
    vp: tuple[int, int, int, int]  # GL viewport (x, y, w, h)
    eye_dir: np.ndarray  # unit vector camera looks FROM
    up: np.ndarray
    center: np.ndarray  # look-at target
    half_size: float  # ortho half-extent
    axis_h: int  # world axis mapped to screen horizontal (0=X, 1=Y, 2=Z)
    axis_v: int  # world axis mapped to screen vertical
    flip_h: bool = False


def ortho(l: float, r: float, b: float, t: float, n: float, f: float) -> np.ndarray:
    m = np.zeros((4, 4), dtype=np.float64)
    m[0, 0] = 2 / (r - l)
    m[1, 1] = 2 / (t - b)
    m[2, 2] = -2 / (f - n)
    m[0, 3] = -(r + l) / (r - l)
    m[1, 3] = -(t + b) / (t - b)
    m[2, 3] = -(f + n) / (f - n)
    m[3, 3] = 1
    return m


def look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    f = target - eye
    f = f / np.linalg.norm(f)
    s = np.cross(f, up)
    sn = np.linalg.norm(s)
    if sn < 1e-9:
        up2 = np.array([1, 0, 0], dtype=np.float64)
        s = np.cross(f, up2)
        sn = np.linalg.norm(s)
    s = s / sn
    u = np.cross(s, f)
    m = np.eye(4, dtype=np.float64)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = -np.dot(s, eye)
    m[1, 3] = -np.dot(u, eye)
    m[2, 3] = np.dot(f, eye)
    return m


def to_gl(mat: np.ndarray) -> bytes:
    return np.ascontiguousarray(mat.astype("f4").T).tobytes()


def build_mvp(panel: Panel) -> np.ndarray:
    aspect = panel.vp[2] / panel.vp[3]
    h = panel.half_size
    proj = ortho(-h * aspect, h * aspect, -h, h, -50, 50)
    eye = panel.center + panel.eye_dir * 20.0
    view = look_at(eye, panel.center, panel.up)
    return proj @ view


def screen_to_world(
    panel: Panel, mvp: np.ndarray, sx: int, sy: int
) -> tuple[int, int, float, float]:
    vx, vy, vw, vh = panel.vp
    nx = (sx - vx) / vw * 2.0 - 1.0
    ny = (sy - vy) / vh * 2.0 - 1.0
    inv_mvp = np.linalg.inv(mvp)
    clip = np.array([nx, ny, 0.0, 1.0], dtype=np.float64)
    world = inv_mvp @ clip
    world /= world[3]
    return panel.axis_h, panel.axis_v, float(world[panel.axis_h]), float(world[panel.axis_v])


def make_crosshair_verts(pos: list[float], panel: Panel, extent: float = 20.0) -> np.ndarray:
    lines = []
    ah, av = panel.axis_h, panel.axis_v
    for axis, coord in [(ah, pos[ah]), (av, pos[av])]:
        p1 = list(pos)
        p2 = list(pos)
        p1[axis] = coord - extent
        p2[axis] = coord + extent
        lines.extend([p1, p2])
    return np.array(lines, dtype=np.float32)


def main() -> None:
    pygame.init()
    pygame.display.set_mode((W, H), pygame.OPENGL | pygame.DOUBLEBUF)
    pygame.display.set_caption("Joint Marker — 3-Panel Ortho")
    ctx = moderngl.create_context()

    prog = ctx.program(vertex_shader=VERT_SRC, fragment_shader=FRAG_SRC)
    line_prog = ctx.program(vertex_shader=LINE_VERT, fragment_shader=LINE_FRAG)

    urdfpy_zero = _compute_raw_origin_fk()
    parts: list[tuple[moderngl.VertexArray, int, np.ndarray]] = []
    for stem, link_name in MESH_TO_LINK.items():
        stl_path = MESH_DIR / f"{stem}.stl"
        if not stl_path.exists():
            continue
        vertices, normals = load_binary_stl(stl_path)
        if vertices.shape[0] == 0:
            continue
        n = vertices.shape[0]
        model_mat = urdfpy_zero.get(link_name, np.eye(4, dtype=np.float64))
        colors = np.full((n, 3), (0.6, 0.6, 0.6), dtype=np.float32)
        data = np.hstack([vertices, colors, normals]).astype("f4")
        vbo = ctx.buffer(data.tobytes())
        vao = ctx.vertex_array(prog, [(vbo, "3f 3f 3f", "in_position", "in_color", "in_normal")])
        parts.append((vao, n, model_mat))

    line_vbo = ctx.buffer(reserve=6 * 4 * 4)
    line_vao = ctx.vertex_array(line_prog, [(line_vbo, "3f", "in_position")])

    LW, LH = 640, H
    RW, RH = W - LW, H // 2

    panels = [
        Panel(
            name="SIDE (YZ)",
            vp=(0, 0, LW, LH),
            eye_dir=np.array([-1, 0, 0], dtype=np.float64),
            up=np.array([0, 0, 1], dtype=np.float64),
            center=np.array([0, 1.5, 1.2], dtype=np.float64),
            half_size=2.5,
            axis_h=1,
            axis_v=2,
        ),
        Panel(
            name="TOP (XY)",
            vp=(LW, RH, RW, RH),
            eye_dir=np.array([0, 0, 1], dtype=np.float64),
            up=np.array([0, 1, 0], dtype=np.float64),
            center=np.array([0, 1.5, 0], dtype=np.float64),
            half_size=2.5,
            axis_h=0,
            axis_v=1,
        ),
        Panel(
            name="FRONT (XZ)",
            vp=(LW, 0, RW, RH),
            eye_dir=np.array([0, 1, 0], dtype=np.float64),
            up=np.array([0, 0, 1], dtype=np.float64),
            center=np.array([0, 0, 1.2], dtype=np.float64),
            half_size=2.5,
            axis_h=0,
            axis_v=2,
            flip_h=True,
        ),
    ]

    markers: dict[str, list[float]] = {}
    current_joint = 0
    last_panel_idx = 0
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 14)
    running = True
    dragging = False
    drag_panel: Panel | None = None
    last_mouse = (0, 0)

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    current_joint = ev.key - pygame.K_1
                    print(f"Selected: {JOINT_NAMES[current_joint]}")
                elif ev.key == pygame.K_s:
                    out = {k: [round(c, 6) for c in v] for k, v in markers.items()}
                    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
                    OUTPUT.write_text(json.dumps(out, indent=2))
                    print(f"Saved {len(out)} markers → {OUTPUT}")
                elif ev.key == pygame.K_r:
                    name = JOINT_NAMES[current_joint]
                    markers.pop(name, None)
                    print(f"Reset: {name}")
                elif ev.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                    name = JOINT_NAMES[current_joint]
                    if name not in markers:
                        markers[name] = [0.0, 0.0, 0.0]
                    step = 0.05 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 0.005
                    p = panels[last_panel_idx]
                    if ev.key == pygame.K_RIGHT:
                        markers[name][p.axis_h] += step
                    elif ev.key == pygame.K_LEFT:
                        markers[name][p.axis_h] -= step
                    elif ev.key == pygame.K_UP:
                        markers[name][p.axis_v] += step
                    elif ev.key == pygame.K_DOWN:
                        markers[name][p.axis_v] -= step
                    c = markers[name]
                    print(f"{name}: ({c[0]:.4f}, {c[1]:.4f}, {c[2]:.4f})")
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 1:
                    mx, my_pg = ev.pos
                    my_gl = H - 1 - my_pg
                    for pi, p in enumerate(panels):
                        vx, vy, vw, vh = p.vp
                        if vx <= mx < vx + vw and vy <= my_gl < vy + vh:
                            mvp = build_mvp(p)
                            ah, av, wh, wv = screen_to_world(p, mvp, mx, my_gl)
                            name = JOINT_NAMES[current_joint]
                            if name not in markers:
                                markers[name] = [0.0, 0.0, 0.0]
                            markers[name][ah] = round(wh, 6)
                            markers[name][av] = round(wv, 6)
                            last_panel_idx = pi
                            c = markers[name]
                            print(f"{name}: ({c[0]:.4f}, {c[1]:.4f}, {c[2]:.4f})  [from {p.name}]")
                            break
                elif ev.button in (4, 5):
                    mx, my_pg = ev.pos
                    my_gl = H - 1 - my_pg
                    for p in panels:
                        vx, vy, vw, vh = p.vp
                        if vx <= mx < vx + vw and vy <= my_gl < vy + vh:
                            if ev.button == 4:
                                p.half_size = max(0.3, p.half_size * 0.9)
                            else:
                                p.half_size = min(15.0, p.half_size * 1.1)
                            break
                elif ev.button == 2:
                    mx, my_pg = ev.pos
                    my_gl = H - 1 - my_pg
                    for p in panels:
                        vx, vy, vw, vh = p.vp
                        if vx <= mx < vx + vw and vy <= my_gl < vy + vh:
                            dragging = True
                            drag_panel = p
                            last_mouse = ev.pos
                            break
            elif ev.type == pygame.MOUSEBUTTONUP:
                if ev.button == 2:
                    dragging = False
                    drag_panel = None
            elif ev.type == pygame.MOUSEMOTION:
                if dragging and drag_panel is not None:
                    dx_px = ev.pos[0] - last_mouse[0]
                    dy_px = ev.pos[1] - last_mouse[1]
                    last_mouse = ev.pos
                    vw, vh = drag_panel.vp[2], drag_panel.vp[3]
                    aspect = vw / vh
                    world_per_px_h = (drag_panel.half_size * 2 * aspect) / vw
                    world_per_px_v = (drag_panel.half_size * 2) / vh
                    drag_panel.center[drag_panel.axis_h] -= dx_px * world_per_px_h
                    drag_panel.center[drag_panel.axis_v] += dy_px * world_per_px_v

        ctx.clear(0.12, 0.12, 0.15, 1.0)

        for pi, p in enumerate(panels):
            ctx.viewport = p.vp
            ctx.enable(moderngl.DEPTH_TEST)
            mvp = build_mvp(p)

            prog["alpha"].value = 1.0
            for vao, n, model_mat in parts:
                prog["mvp"].write(to_gl(mvp))
                prog["model"].write(to_gl(model_mat))
                vao.render(moderngl.TRIANGLES, vertices=n)

            ctx.disable(moderngl.DEPTH_TEST)

            name = JOINT_NAMES[current_joint]
            if name in markers:
                pos = markers[name]
                ch = make_crosshair_verts(pos, p)
                line_vbo.orphan(ch.nbytes)
                line_vbo.write(ch.tobytes())
                r, g, b = JOINT_COLORS_RGB[name]
                line_prog["mvp"].write(to_gl(mvp))
                line_prog["line_color"].value = (r, g, b)
                line_vao.render(moderngl.LINES, vertices=len(ch))

            for jn in JOINT_NAMES:
                if jn not in markers:
                    continue
                mp = markers[jn]
                r, g, b = JOINT_COLORS_RGB[jn]
                sz = 0.035 if jn != name else 0.05
                dot = _make_dot_verts(mp, p, sz)
                line_vbo.orphan(dot.nbytes)
                line_vbo.write(dot.tobytes())
                line_prog["mvp"].write(to_gl(mvp))
                line_prog["line_color"].value = (r, g, b)
                line_vao.render(moderngl.TRIANGLES, vertices=len(dot))

        ctx.viewport = (0, 0, W, H)
        ctx.disable(moderngl.DEPTH_TEST)
        _draw_hud(ctx, font, markers, current_joint, panels, last_panel_idx)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


def _make_dot_verts(pos: list[float], panel: Panel, size: float) -> np.ndarray:
    ah, av = panel.axis_h, panel.axis_v
    cx, cy = pos[ah], pos[av]
    third_axis = 3 - ah - av
    cz = pos[third_axis]
    segs = 12
    tris = []
    for i in range(segs):
        a1 = 2 * math.pi * i / segs
        a2 = 2 * math.pi * (i + 1) / segs
        p0 = [0.0, 0.0, 0.0]
        p1 = [0.0, 0.0, 0.0]
        p2 = [0.0, 0.0, 0.0]
        p0[ah] = cx
        p0[av] = cy
        p0[third_axis] = cz
        p1[ah] = cx + size * math.cos(a1)
        p1[av] = cy + size * math.sin(a1)
        p1[third_axis] = cz
        p2[ah] = cx + size * math.cos(a2)
        p2[av] = cy + size * math.sin(a2)
        p2[third_axis] = cz
        tris.extend([p0, p1, p2])
    return np.array(tris, dtype=np.float32)


def _draw_hud(
    ctx: moderngl.Context,
    font: pygame.font.Font,
    markers: dict[str, list[float]],
    current: int,
    panels: list[Panel],
    last_panel: int,
) -> None:
    hud_h = 130
    hud_w = 380
    surface = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 200))
    y = 6
    for i, name in enumerate(JOINT_NAMES):
        prefix = "▶ " if i == current else "  "
        pos = markers.get(name)
        coord = f"({pos[0]:+.4f}, {pos[1]:+.4f}, {pos[2]:+.4f})" if pos else "— click to set —"
        r, g, b = JOINT_COLORS_RGB[name]
        color = (int(r * 255), int(g * 255), int(b * 255))
        txt = font.render(f"{prefix}{i + 1}:{name:7s} {coord}", True, color)
        surface.blit(txt, (6, y))
        y += 22
    guide = font.render(
        f"Arrows=adjust  S=save  R=reset  Panel={panels[last_panel].name}", True, (180, 180, 180)
    )
    surface.blit(guide, (6, y + 4))

    raw = pygame.image.tobytes(surface, "RGBA", True)
    tex = ctx.texture((hud_w, hud_h), 4, raw)
    tex.use(0)

    hud_prog = ctx.program(
        vertex_shader="""
        #version 330
        in vec2 in_pos;
        in vec2 in_uv;
        out vec2 uv;
        void main() { gl_Position = vec4(in_pos, 0, 1); uv = in_uv; }
        """,
        fragment_shader="""
        #version 330
        in vec2 uv;
        uniform sampler2D tex;
        out vec4 fragColor;
        void main() { fragColor = texture(tex, uv); }
        """,
    )

    x0 = -1.0
    y0 = 1.0 - 2.0 * hud_h / H
    x1 = x0 + 2.0 * hud_w / W
    y1 = 1.0
    quad = np.array(
        [
            x0,
            y0,
            0,
            0,
            x1,
            y0,
            1,
            0,
            x1,
            y1,
            1,
            1,
            x0,
            y0,
            0,
            0,
            x1,
            y1,
            1,
            1,
            x0,
            y1,
            0,
            1,
        ],
        dtype=np.float32,
    )
    qvbo = ctx.buffer(quad.tobytes())
    qvao = ctx.vertex_array(hud_prog, [(qvbo, "2f 2f", "in_pos", "in_uv")])

    ctx.enable(moderngl.BLEND)
    ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
    hud_prog["tex"].value = 0
    qvao.render(moderngl.TRIANGLES)
    ctx.blend_func = moderngl.DEFAULT_BLENDING
    ctx.disable(moderngl.BLEND)

    tex.release()
    qvbo.release()
    qvao.release()
    hud_prog.release()


if __name__ == "__main__":
    main()
