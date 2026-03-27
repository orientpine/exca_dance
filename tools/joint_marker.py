#!/usr/bin/env python3
"""Joint position marker tool.

Renders the ix35e excavator STL meshes in a 3D viewport.
Click on the model to place joint markers. Saves coordinates to JSON.

Controls:
  Left-click     — place/move current joint marker on model surface
  1/2/3/4        — select joint: 1=swing, 2=boom, 3=arm, 4=bucket
  Scroll         — zoom in/out
  Middle-drag    — orbit camera
  S              — save markers to joint_markers.json
  R              — reset current marker
  ESC            — quit
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import moderngl
import numpy as np
import pygame

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from exca_dance.rendering.stl_loader import load_binary_stl  # noqa: E402
from exca_dance.rendering.urdf_kin import (  # noqa: E402
    MESH_TO_LINK,
    _compute_raw_origin_fk,
)

MESH_DIR = ROOT / "assets" / "meshes" / "collision"
OUTPUT = ROOT / "tools" / "joint_markers.json"
W, H = 1280, 900

JOINT_NAMES = ["swing", "boom", "arm", "bucket"]
JOINT_COLORS = {
    "swing": (0.0, 1.0, 0.0),
    "boom": (1.0, 0.4, 0.0),
    "arm": (1.0, 0.8, 0.0),
    "bucket": (0.0, 0.8, 1.0),
}

VERT_SHADER = """
#version 330
in vec3 in_position;
in vec3 in_color;
in vec3 in_normal;
uniform mat4 mvp;
uniform mat4 model;
out vec3 v_color;
out vec3 v_normal;
out vec3 v_pos;
void main() {
    vec4 world = model * vec4(in_position, 1.0);
    gl_Position = mvp * world;
    v_pos = world.xyz;
    v_color = in_color;
    v_normal = mat3(model) * in_normal;
}
"""

FRAG_SHADER = """
#version 330
in vec3 v_color;
in vec3 v_normal;
in vec3 v_pos;
uniform float alpha;
out vec4 fragColor;
void main() {
    vec3 light_dir = normalize(vec3(0.3, -0.5, 0.8));
    float diff = max(dot(normalize(v_normal), light_dir), 0.0);
    vec3 lit = v_color * (0.35 + 0.65 * diff);
    fragColor = vec4(lit, alpha);
}
"""

ID_VERT = """
#version 330
in vec3 in_position;
uniform mat4 mvp;
uniform mat4 model;
out vec3 v_world;
void main() {
    vec4 world = model * vec4(in_position, 1.0);
    gl_Position = mvp * world;
    v_world = world.xyz;
}
"""

ID_FRAG = """
#version 330
in vec3 v_world;
out vec4 fragColor;
void main() {
    fragColor = vec4(v_world, 1.0);
}
"""

MARKER_VERT = """
#version 330
in vec3 in_position;
uniform mat4 mvp;
uniform vec3 marker_pos;
uniform float marker_scale;
uniform vec3 marker_color;
out vec3 v_color;
void main() {
    vec3 world = in_position * marker_scale + marker_pos;
    gl_Position = mvp * vec4(world, 1.0);
    v_color = marker_color;
}
"""

MARKER_FRAG = """
#version 330
in vec3 v_color;
out vec4 fragColor;
void main() {
    fragColor = vec4(v_color, 1.0);
}
"""


def make_sphere_verts(subdivisions: int = 2) -> np.ndarray:
    """Icosphere vertices for marker rendering."""
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    verts = [
        (-1, phi, 0),
        (1, phi, 0),
        (-1, -phi, 0),
        (1, -phi, 0),
        (0, -1, phi),
        (0, 1, phi),
        (0, -1, -phi),
        (0, 1, -phi),
        (phi, 0, -1),
        (phi, 0, 1),
        (-phi, 0, -1),
        (-phi, 0, 1),
    ]
    verts = [np.array(v, dtype=np.float32) / np.linalg.norm(v) for v in verts]
    faces = [
        (0, 11, 5),
        (0, 5, 1),
        (0, 1, 7),
        (0, 7, 10),
        (0, 10, 11),
        (1, 5, 9),
        (5, 11, 4),
        (11, 10, 2),
        (10, 7, 6),
        (7, 1, 8),
        (3, 9, 4),
        (3, 4, 2),
        (3, 2, 6),
        (3, 6, 8),
        (3, 8, 9),
        (4, 9, 5),
        (2, 4, 11),
        (6, 2, 10),
        (8, 6, 7),
        (9, 8, 1),
    ]
    for _ in range(subdivisions):
        mid_cache: dict[tuple[int, int], int] = {}
        new_faces = []
        for i0, i1, i2 in faces:
            a = _midpoint(verts, mid_cache, i0, i1)
            b = _midpoint(verts, mid_cache, i1, i2)
            c = _midpoint(verts, mid_cache, i2, i0)
            new_faces.extend([(i0, a, c), (i1, b, a), (i2, c, b), (a, b, c)])
        faces = new_faces
    result = []
    for i0, i1, i2 in faces:
        result.extend([verts[i0], verts[i1], verts[i2]])
    return np.array(result, dtype=np.float32)


def _midpoint(
    verts: list[np.ndarray],
    cache: dict[tuple[int, int], int],
    i0: int,
    i1: int,
) -> int:
    key = (min(i0, i1), max(i0, i1))
    if key in cache:
        return cache[key]
    mid = (verts[i0] + verts[i1]) / 2.0
    mid = mid / np.linalg.norm(mid)
    idx = len(verts)
    verts.append(mid)
    cache[key] = idx
    return idx


def perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / math.tan(math.radians(fov_deg) / 2.0)
    m = np.zeros((4, 4), dtype=np.float64)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = 2 * far * near / (near - far)
    m[3, 2] = -1
    return m


def look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    f = target - eye
    f = f / np.linalg.norm(f)
    s = np.cross(f, up)
    s = s / np.linalg.norm(s)
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


def main() -> None:
    pygame.init()
    pygame.display.set_mode((W, H), pygame.OPENGL | pygame.DOUBLEBUF)
    pygame.display.set_caption("Joint Marker Tool — ix35e")
    ctx = moderngl.create_context()
    ctx.enable(moderngl.DEPTH_TEST)

    prog = ctx.program(vertex_shader=VERT_SHADER, fragment_shader=FRAG_SHADER)
    id_prog = ctx.program(vertex_shader=ID_VERT, fragment_shader=ID_FRAG)
    marker_prog = ctx.program(vertex_shader=MARKER_VERT, fragment_shader=MARKER_FRAG)

    # Load meshes
    urdfpy_zero = _compute_raw_origin_fk()
    parts: list[tuple[moderngl.VertexArray, moderngl.VertexArray, int, np.ndarray]] = []

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
        id_vao = ctx.vertex_array(
            id_prog, [(vbo, "3f 24x", "in_position")]
        )
        parts.append((vao, id_vao, n, model_mat))

    # Marker sphere
    sphere = make_sphere_verts(2)
    sphere_vbo = ctx.buffer(sphere.tobytes())
    sphere_vao = ctx.vertex_array(marker_prog, [(sphere_vbo, "3f", "in_position")])
    sphere_count = len(sphere)

    # ID-pick framebuffer (world-pos encoded as RGB float)
    id_tex = ctx.texture((W, H), 4, dtype="f4")
    id_depth = ctx.depth_renderbuffer((W, H))
    id_fbo = ctx.framebuffer(color_attachments=[id_tex], depth_attachment=id_depth)

    # Camera
    cam_dist = 6.0
    cam_azimuth = -60.0
    cam_elevation = 25.0
    cam_target = np.array([0.0, 1.5, 1.0], dtype=np.float64)

    # State
    markers: dict[str, list[float] | None] = {j: None for j in JOINT_NAMES}
    current_joint = 0
    dragging = False
    last_mouse = (0, 0)

    clock = pygame.time.Clock()
    running = True

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
                    out = {k: v for k, v in markers.items() if v is not None}
                    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
                    OUTPUT.write_text(json.dumps(out, indent=2))
                    print(f"Saved {len(out)} markers to {OUTPUT}")
                elif ev.key == pygame.K_r:
                    markers[JOINT_NAMES[current_joint]] = None
                    print(f"Reset: {JOINT_NAMES[current_joint]}")
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 1:
                    # Pick world position
                    mx, my = ev.pos
                    gy = H - 1 - my
                    id_fbo.use()
                    ctx.clear(0, 0, 0, 0)
                    eye = _cam_eye(cam_dist, cam_azimuth, cam_elevation, cam_target)
                    mvp = perspective(45, W / H, 0.1, 100) @ look_at(
                        eye, cam_target, np.array([0, 0, 1.0])
                    )
                    for vao, id_vao, n, model_mat in parts:
                        id_prog["mvp"].write(to_gl(mvp))
                        id_prog["model"].write(to_gl(model_mat))
                        id_vao.render(moderngl.TRIANGLES, vertices=n)
                    pixel = id_fbo.read(viewport=(mx, gy, 1, 1), components=4, dtype="f4")
                    world_pos = np.frombuffer(pixel, dtype=np.float32)[:3]
                    if np.any(world_pos != 0):
                        name = JOINT_NAMES[current_joint]
                        markers[name] = [round(float(x), 6) for x in world_pos]
                        print(f"{name}: {markers[name]}")
                elif ev.button == 2:
                    dragging = True
                    last_mouse = ev.pos
                elif ev.button == 4:
                    cam_dist = max(1.0, cam_dist - 0.5)
                elif ev.button == 5:
                    cam_dist = min(30.0, cam_dist + 0.5)
            elif ev.type == pygame.MOUSEBUTTONUP:
                if ev.button == 2:
                    dragging = False
            elif ev.type == pygame.MOUSEMOTION:
                if dragging:
                    dx = ev.pos[0] - last_mouse[0]
                    dy = ev.pos[1] - last_mouse[1]
                    cam_azimuth += dx * 0.3
                    cam_elevation = max(-89, min(89, cam_elevation + dy * 0.3))
                    last_mouse = ev.pos

        # Render
        ctx.screen.use()
        ctx.clear(0.08, 0.08, 0.12, 1.0)
        eye = _cam_eye(cam_dist, cam_azimuth, cam_elevation, cam_target)
        mvp = perspective(45, W / H, 0.1, 100) @ look_at(eye, cam_target, np.array([0, 0, 1.0]))

        prog["alpha"].value = 1.0
        for vao, _, n, model_mat in parts:
            prog["mvp"].write(to_gl(mvp))
            prog["model"].write(to_gl(model_mat))
            vao.render(moderngl.TRIANGLES, vertices=n)

        # Draw markers
        ctx.disable(moderngl.DEPTH_TEST)
        for i, name in enumerate(JOINT_NAMES):
            pos = markers[name]
            if pos is None:
                continue
            r, g, b = JOINT_COLORS[name]
            scale = 0.04 if i != current_joint else 0.06
            marker_prog["mvp"].write(to_gl(mvp))
            marker_prog["marker_pos"].value = tuple(pos)
            marker_prog["marker_scale"].value = scale
            marker_prog["marker_color"].value = (r, g, b)
            sphere_vao.render(moderngl.TRIANGLES, vertices=sphere_count)
        ctx.enable(moderngl.DEPTH_TEST)

        # HUD text
        _draw_hud(markers, current_joint)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


def _cam_eye(dist: float, az: float, el: float, target: np.ndarray) -> np.ndarray:
    az_r = math.radians(az)
    el_r = math.radians(el)
    x = dist * math.cos(el_r) * math.cos(az_r)
    y = dist * math.cos(el_r) * math.sin(az_r)
    z = dist * math.sin(el_r)
    return target + np.array([x, y, z], dtype=np.float64)


def _draw_hud(markers: dict[str, list[float] | None], current: int) -> None:
    overlay = pygame.Surface((320, 160), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    font = pygame.font.SysFont("monospace", 16)
    y = 8
    for i, name in enumerate(JOINT_NAMES):
        prefix = "▶ " if i == current else "  "
        pos = markers[name]
        coord = f"({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f})" if pos else "— not set —"
        r, g, b = JOINT_COLORS[name]
        color = (int(r * 255), int(g * 255), int(b * 255))
        text = font.render(f"{prefix}{i + 1}:{name:7s} {coord}", True, color)
        overlay.blit(text, (8, y))
        y += 32
    guide = font.render("Click=place  1-4=select  S=save  R=reset", True, (200, 200, 200))
    overlay.blit(guide, (8, y + 8))

    # Blit overlay via pygame (this is a tool, not game rendering)
    screen = pygame.display.get_surface()
    screen_data = pygame.image.tostring(overlay, "RGBA", True)
    # Use raw pixel copy to screen
    raw = np.frombuffer(screen_data, dtype=np.uint8).reshape(160, 320, 4)
    # We need to draw this without blit - use pygame's display directly
    # Actually for a tool, pygame blit onto an offscreen surface then upload is fine
    # But since we're in GL mode, let's just print to console instead
    pass


if __name__ == "__main__":
    main()
