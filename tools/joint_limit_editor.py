#!/usr/bin/env python3
"""Joint limit editor — 3-panel orthographic excavator viewer.

Controls:
  1/2/3/4           - select joint (swing/boom/arm/bucket)
  Left/Right        - rotate selected joint ±2.0°
  Shift+Left/Right  - fine rotate ±0.5°
  M                 - set current angle as MIN for selected joint
  N                 - set current angle as MAX for selected joint
  G                 - ghost toggle (off -> min -> max -> both -> off)
  S                 - save limits to tools/joint_limits.json
  L                 - load limits from tools/joint_limits.json
  R                 - reset selected joint limits to JOINT_LIMITS defaults
  Home              - reset all current angles to 0°
  Scroll            - zoom panel under cursor
  Middle-drag       - pan panel
  ESC               - quit
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import moderngl
import numpy as np
import pygame

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from exca_dance.rendering.stl_loader import load_binary_stl  # noqa: E402
from exca_dance.rendering.urdf_kin import (
    MESH_TO_LINK,
    compute_link_transforms,
    compute_mesh_corrections,
)  # noqa: E402

MESH_DIR = ROOT / "assets" / "meshes" / "collision"
LIMITS_PATH = ROOT / "tools" / "joint_limits.json"

W, H = 1280, 900
JOINT_NAMES = ["swing", "boom", "arm", "bucket"]

GHOST_OFF = 0
GHOST_MIN = 1
GHOST_MAX = 2
GHOST_BOTH = 3

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
uniform vec3 tint;
out vec4 fragColor;
void main() {
    vec3 ld = normalize(vec3(0.3, -0.5, 0.8));
    float d = max(dot(normalize(v_normal), ld), 0.0);
    fragColor = vec4(v_color * tint * (0.35 + 0.65 * d), alpha);
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

HUD_VERT = """
#version 330
in vec2 in_pos;
in vec2 in_uv;
out vec2 uv;
void main() {
    gl_Position = vec4(in_pos, 0, 1);
    uv = in_uv;
}
"""

HUD_FRAG = """
#version 330
in vec2 uv;
uniform sampler2D tex;
out vec4 fragColor;
void main() {
    fragColor = texture(tex, uv);
}
"""


@dataclass
class Panel:
    name: str
    vp: tuple[int, int, int, int]
    eye_dir: np.ndarray
    up: np.ndarray
    center: np.ndarray
    half_size: float
    axis_h: int
    axis_v: int


@dataclass
class MeshPart:
    vao: moderngl.VertexArray
    vertex_count: int
    link_name: str


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
    fwd = target - eye
    fwd = fwd / np.linalg.norm(fwd)
    side = np.cross(fwd, up)
    side_norm = np.linalg.norm(side)
    if side_norm < 1e-9:
        side = np.cross(fwd, np.array([1.0, 0.0, 0.0], dtype=np.float64))
        side_norm = np.linalg.norm(side)
    side = side / side_norm
    up2 = np.cross(side, fwd)

    view = np.eye(4, dtype=np.float64)
    view[0, :3] = side
    view[1, :3] = up2
    view[2, :3] = -fwd
    view[0, 3] = -np.dot(side, eye)
    view[1, 3] = -np.dot(up2, eye)
    view[2, 3] = np.dot(fwd, eye)
    return view


def to_gl(mat: np.ndarray) -> bytes:
    return np.ascontiguousarray(mat.astype("f4").T).tobytes()


def build_mvp(panel: Panel) -> np.ndarray:
    aspect = panel.vp[2] / panel.vp[3]
    half = panel.half_size
    proj = ortho(-half * aspect, half * aspect, -half, half, -50.0, 50.0)
    eye = panel.center + panel.eye_dir * 20.0
    view = look_at(eye, panel.center, panel.up)
    return proj @ view


def _default_limits_map(joint_limits: object) -> dict[str, dict[str, float]]:
    limits_dict = cast(dict[object, tuple[float, float]], joint_limits)
    defaults: dict[str, dict[str, float]] = {}
    for joint, (mn, mx) in limits_dict.items():
        name = cast(str, getattr(joint, "value"))
        defaults[name] = {"min": float(mn), "max": float(mx)}
    return defaults


def _copy_limits(limits: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    return {name: {"min": vals["min"], "max": vals["max"]} for name, vals in limits.items()}


def load_limits(limits: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    if not LIMITS_PATH.exists():
        return _copy_limits(limits)

    raw_obj = json.loads(LIMITS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw_obj, dict):
        return _copy_limits(limits)
    raw: dict[str, object] = raw_obj
    loaded = _copy_limits(limits)
    for joint in JOINT_NAMES:
        if joint not in raw:
            continue
        item = raw[joint]
        if not isinstance(item, dict):
            continue
        item_dict = cast(dict[str, object], item)
        raw_min = item_dict.get("min")
        raw_max = item_dict.get("max")
        if not isinstance(raw_min, (int, float, str)):
            continue
        if not isinstance(raw_max, (int, float, str)):
            continue
        try:
            mn = float(raw_min)
            mx = float(raw_max)
        except (KeyError, TypeError, ValueError):
            continue
        loaded[joint]["min"] = mn
        loaded[joint]["max"] = mx
    return loaded


def save_limits(limits: dict[str, dict[str, float]]) -> None:
    out = {
        name: {"min": round(vals["min"], 6), "max": round(vals["max"], 6)}
        for name, vals in limits.items()
    }
    LIMITS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIMITS_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")


def _build_ghost_angles(
    current: dict[str, float],
    limits: dict[str, dict[str, float]],
    selected_joint: str,
    key: str,
) -> dict[str, float]:
    out = dict(current)
    out[selected_joint] = limits[selected_joint][key]
    return out


def _render_model(
    prog: moderngl.Program,
    parts: list[MeshPart],
    mvp: np.ndarray,
    link_transforms: dict[str, np.ndarray],
    corrections: dict[str, np.ndarray],
    alpha: float,
    tint: tuple[float, float, float],
) -> None:
    cast(moderngl.Uniform, prog["mvp"]).write(to_gl(mvp))
    cast(moderngl.Uniform, prog["alpha"]).value = alpha
    cast(moderngl.Uniform, prog["tint"]).value = tint
    for part in parts:
        link_t = link_transforms.get(part.link_name)
        if link_t is None:
            continue
        corr = corrections.get(part.link_name)
        if corr is None:
            corr = np.eye(4, dtype=np.float64)
        model = link_t @ corr
        cast(moderngl.Uniform, prog["model"]).write(to_gl(model))
        part.vao.render(moderngl.TRIANGLES, vertices=part.vertex_count)


def _draw_hud(
    ctx: moderngl.Context,
    hud_prog: moderngl.Program,
    hud_vao: moderngl.VertexArray,
    font: pygame.font.Font,
    selected_idx: int,
    current_angles: dict[str, float],
    limits: dict[str, dict[str, float]],
    ghost_mode: int,
) -> None:
    hud_w, hud_h = 640, 180
    surface = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
    _ = surface.fill((0, 0, 0, 210))

    ghost_txt = {
        GHOST_OFF: "off",
        GHOST_MIN: "min",
        GHOST_MAX: "max",
        GHOST_BOTH: "both",
    }[ghost_mode]

    y = 8
    for i, name in enumerate(JOINT_NAMES):
        marker = "▶" if i == selected_idx else " "
        angle = current_angles[name]
        mn = limits[name]["min"]
        mx = limits[name]["max"]
        line = f"{marker} {i + 1}:{name:7s}  angle:{angle:+6.1f}°  min:{mn:+6.1f}°  max:{mx:+6.1f}°"
        color = (80, 255, 120) if i == selected_idx else (220, 220, 220)
        _ = surface.blit(font.render(line, True, color), (10, y))
        y += 26

    guide = "←/→=rotate  Shift=0.5°  M=min  N=max  G=ghost"
    guide2 = f"S=save  L=load  R=reset limits  Home=angles 0°  Ghost:{ghost_txt}"
    _ = surface.blit(font.render(guide, True, (180, 180, 180)), (10, y + 8))
    _ = surface.blit(font.render(guide2, True, (180, 180, 180)), (10, y + 34))

    raw = pygame.image.tobytes(surface, "RGBA", True)
    tex = ctx.texture((hud_w, hud_h), 4, raw)
    tex.use(0)

    ctx.enable(moderngl.BLEND)
    ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
    cast(moderngl.Uniform, hud_prog["tex"]).value = 0
    hud_vao.render(moderngl.TRIANGLES)
    ctx.blend_func = cast(tuple[int, int], cast(object, moderngl.DEFAULT_BLENDING))
    ctx.disable(moderngl.BLEND)
    tex.release()


def main() -> None:
    from exca_dance.core.constants import JOINT_LIMITS
    from exca_dance.core.models import JointName

    def to_joint_angle_map(angles: dict[str, float]) -> dict[JointName, float]:
        return cast(
            dict[JointName, float],
            {
                JointName.SWING: angles["swing"],
                JointName.BOOM: angles["boom"],
                JointName.ARM: angles["arm"],
                JointName.BUCKET: angles["bucket"],
            },
        )

    pygame.init()
    _ = pygame.display.set_mode((W, H), pygame.OPENGL | pygame.DOUBLEBUF)
    _ = pygame.display.set_caption("Joint Limit Editor — 3-Panel Ortho")

    ctx = moderngl.create_context()
    prog = ctx.program(vertex_shader=VERT_SRC, fragment_shader=FRAG_SRC)

    hud_prog = ctx.program(vertex_shader=HUD_VERT, fragment_shader=HUD_FRAG)
    hud_w, hud_h = 640, 180
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
    hud_vbo = ctx.buffer(quad.tobytes())
    hud_vao = ctx.vertex_array(hud_prog, [(hud_vbo, "2f 2f", "in_pos", "in_uv")])

    mesh_corrections = compute_mesh_corrections()
    parts: list[MeshPart] = []
    for stem, link_name in MESH_TO_LINK.items():
        stl_path = MESH_DIR / f"{stem}.stl"
        if not stl_path.exists():
            continue
        vertices, normals = load_binary_stl(stl_path)
        if vertices.shape[0] == 0:
            continue

        count = int(vertices.shape[0])
        colors = np.full((count, 3), 0.70, dtype=np.float32)
        packed = np.hstack([vertices, colors, normals]).astype("f4")
        vbo = ctx.buffer(packed.tobytes())
        vao = ctx.vertex_array(prog, [(vbo, "3f 3f 3f", "in_position", "in_color", "in_normal")])
        parts.append(MeshPart(vao=vao, vertex_count=count, link_name=link_name))

    panels = [
        Panel(
            name="SIDE (YZ)",
            vp=(0, 0, 640, 900),
            eye_dir=np.array([-1.0, 0.0, 0.0], dtype=np.float64),
            up=np.array([0.0, 0.0, 1.0], dtype=np.float64),
            center=np.array([0.0, 1.5, 1.2], dtype=np.float64),
            half_size=2.5,
            axis_h=1,
            axis_v=2,
        ),
        Panel(
            name="TOP (XY)",
            vp=(640, 450, 640, 450),
            eye_dir=np.array([0.0, 0.0, 1.0], dtype=np.float64),
            up=np.array([0.0, 1.0, 0.0], dtype=np.float64),
            center=np.array([0.0, 1.5, 0.0], dtype=np.float64),
            half_size=2.5,
            axis_h=0,
            axis_v=1,
        ),
        Panel(
            name="FRONT (XZ)",
            vp=(640, 0, 640, 450),
            eye_dir=np.array([0.0, 1.0, 0.0], dtype=np.float64),
            up=np.array([0.0, 0.0, 1.0], dtype=np.float64),
            center=np.array([0.0, 0.0, 1.2], dtype=np.float64),
            half_size=2.5,
            axis_h=0,
            axis_v=2,
        ),
    ]

    default_limits = _default_limits_map(JOINT_LIMITS)
    limits = load_limits(default_limits)

    current_angles: dict[str, float] = {name: 0.0 for name in JOINT_NAMES}
    selected_idx = 0
    ghost_mode = GHOST_BOTH

    font = pygame.font.SysFont("monospace", 22)
    clock = pygame.time.Clock()
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
                    selected_idx = ev.key - pygame.K_1
                elif ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    step = 0.5 if (pygame.key.get_mods() & pygame.KMOD_SHIFT) else 2.0
                    if ev.key == pygame.K_LEFT:
                        step = -step
                    selected_name = JOINT_NAMES[selected_idx]
                    current_angles[selected_name] += step
                elif ev.key == pygame.K_m:
                    selected_name = JOINT_NAMES[selected_idx]
                    limits[selected_name]["min"] = current_angles[selected_name]
                elif ev.key == pygame.K_n:
                    selected_name = JOINT_NAMES[selected_idx]
                    limits[selected_name]["max"] = current_angles[selected_name]
                elif ev.key == pygame.K_g:
                    ghost_mode = (ghost_mode + 1) % 4
                elif ev.key == pygame.K_s:
                    save_limits(limits)
                elif ev.key == pygame.K_l:
                    limits = load_limits(default_limits)
                elif ev.key == pygame.K_r:
                    selected_name = JOINT_NAMES[selected_idx]
                    limits[selected_name]["min"] = default_limits[selected_name]["min"]
                    limits[selected_name]["max"] = default_limits[selected_name]["max"]
                elif ev.key == pygame.K_HOME:
                    for joint_name in JOINT_NAMES:
                        current_angles[joint_name] = 0.0
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button in (4, 5):
                    mx, my_pg = ev.pos
                    my_gl = H - 1 - my_pg
                    for panel in panels:
                        vx, vy, vw, vh = panel.vp
                        if vx <= mx < vx + vw and vy <= my_gl < vy + vh:
                            if ev.button == 4:
                                panel.half_size = max(0.3, panel.half_size * 0.9)
                            else:
                                panel.half_size = min(15.0, panel.half_size * 1.1)
                            break
                elif ev.button == 2:
                    mx, my_pg = ev.pos
                    my_gl = H - 1 - my_pg
                    for panel in panels:
                        vx, vy, vw, vh = panel.vp
                        if vx <= mx < vx + vw and vy <= my_gl < vy + vh:
                            dragging = True
                            drag_panel = panel
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

        selected_name = JOINT_NAMES[selected_idx]
        angle_map = to_joint_angle_map(current_angles)
        link_transforms_main = compute_link_transforms(angle_map)

        render_min = ghost_mode in (GHOST_MIN, GHOST_BOTH)
        render_max = ghost_mode in (GHOST_MAX, GHOST_BOTH)
        link_transforms_min: dict[str, np.ndarray] | None = None
        link_transforms_max: dict[str, np.ndarray] | None = None

        if render_min:
            min_angles = _build_ghost_angles(current_angles, limits, selected_name, "min")
            link_transforms_min = compute_link_transforms(to_joint_angle_map(min_angles))
        if render_max:
            max_angles = _build_ghost_angles(current_angles, limits, selected_name, "max")
            link_transforms_max = compute_link_transforms(to_joint_angle_map(max_angles))

        ctx.clear(0.08, 0.08, 0.11, 1.0)

        for panel in panels:
            ctx.viewport = panel.vp
            mvp = build_mvp(panel)
            ctx.enable(moderngl.DEPTH_TEST)

            _render_model(
                prog,
                parts,
                mvp,
                link_transforms_main,
                mesh_corrections,
                alpha=1.0,
                tint=(1.0, 1.0, 1.0),
            )

            if render_min and link_transforms_min is not None:
                ctx.enable(moderngl.BLEND)
                ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
                _render_model(
                    prog,
                    parts,
                    mvp,
                    link_transforms_min,
                    mesh_corrections,
                    alpha=0.25,
                    tint=(1.0, 0.3, 0.3),
                )
                ctx.blend_func = cast(tuple[int, int], cast(object, moderngl.DEFAULT_BLENDING))
                ctx.disable(moderngl.BLEND)

            if render_max and link_transforms_max is not None:
                ctx.enable(moderngl.BLEND)
                ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
                _render_model(
                    prog,
                    parts,
                    mvp,
                    link_transforms_max,
                    mesh_corrections,
                    alpha=0.25,
                    tint=(0.3, 1.0, 0.3),
                )
                ctx.blend_func = cast(tuple[int, int], cast(object, moderngl.DEFAULT_BLENDING))
                ctx.disable(moderngl.BLEND)

            ctx.disable(moderngl.DEPTH_TEST)

        ctx.viewport = (0, 0, W, H)
        _draw_hud(ctx, hud_prog, hud_vao, font, selected_idx, current_angles, limits, ghost_mode)

        _ = pygame.display.flip()
        _ = clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
