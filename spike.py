#!/usr/bin/env python3
"""
Spike: Validate Pygame + ModernGL + Audio coexistence.
Tests: GL context creation, rendering loop, audio playback.
"""

import os
import sys
import time
import struct
import wave
import math
import numpy as np

# Set dummy audio driver for headless environments
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import moderngl


def create_test_ogg():
    """Generate a 1-second test OGG file (440Hz sine wave)."""
    ogg_path = "/tmp/test_spike.ogg"
    wav_path = "/tmp/test_spike.wav"

    # Generate WAV first (OGG generation requires external tools)
    sample_rate = 44100
    duration = 1
    frequency = 440
    samples = int(sample_rate * duration)

    # Generate sine wave
    t = np.linspace(0, duration, samples, False)
    wave_data = np.sin(2 * np.pi * frequency * t) * 32767 * 0.3
    wave_data = wave_data.astype(np.int16)

    # Write WAV
    with wave.open(wav_path, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(wave_data.tobytes())

    # Try to convert to OGG using ffmpeg if available
    ret = os.system(f"ffmpeg -i {wav_path} -q:a 9 {ogg_path} -y 2>/dev/null")
    if ret == 0 and os.path.exists(ogg_path):
        return ogg_path

    # Fallback: use WAV
    return wav_path


def main():
    """Run spike validation."""
    print("[SPIKE] Starting Pygame + ModernGL + Audio validation...")

    # 1. Initialize Pygame with OpenGL
    pygame.init()
    print("[SPIKE] Pygame initialized")

    # 2. Create display with OpenGL flags
    width, height = 800, 600
    flags = pygame.OPENGL | pygame.DOUBLEBUF
    display = pygame.display.set_mode((width, height), flags)
    pygame.display.set_caption("Spike: Pygame + ModernGL + Audio")
    print("[SPIKE] Display created (800x600, OpenGL)")

    # 3. Create ModernGL context
    ctx = moderngl.create_context()
    print(f"[SPIKE] ModernGL context created: {ctx.info}")

    # 4. Create simple shaders
    vertex_shader = """
    #version 330
    in vec2 position;
    in vec3 color;
    out vec3 frag_color;
    uniform float rotation;
    
    void main() {
        float c = cos(rotation);
        float s = sin(rotation);
        vec2 rotated = vec2(
            position.x * c - position.y * s,
            position.x * s + position.y * c
        );
        gl_Position = vec4(rotated, 0.0, 1.0);
        frag_color = color;
    }
    """

    fragment_shader = """
    #version 330
    in vec3 frag_color;
    out vec4 out_color;
    
    void main() {
        out_color = vec4(frag_color, 1.0);
    }
    """

    program = ctx.program(vertex_shader=vertex_shader, fragment_shader=fragment_shader)
    print("[SPIKE] Shaders compiled")

    # 5. Create triangle geometry
    vertices = np.array(
        [
            -0.5,
            -0.5,
            1.0,
            0.0,
            0.0,
            0.5,
            -0.5,
            0.0,
            1.0,
            0.0,
            0.0,
            0.5,
            0.0,
            0.0,
            1.0,
        ],
        dtype="f4",
    )

    vbo = ctx.buffer(vertices)
    vao = ctx.vertex_array(program, [(vbo, "2f 3f", "position", "color")])
    print("[SPIKE] Geometry created")

    # 6. Load audio
    audio_file = create_test_ogg()
    pygame.mixer.init()
    pygame.mixer.music.load(audio_file)
    print(f"[SPIKE] Audio loaded: {audio_file}")

    # 7. Run loop for 5 seconds
    pygame.mixer.music.play()
    print("[SPIKE] Audio playback started")

    start_time = time.perf_counter()
    frame_count = 0
    last_fps_time = start_time

    running = True
    while running:
        current_time = time.perf_counter()
        elapsed = current_time - start_time

        # Exit after 5 seconds
        if elapsed > 5.0:
            running = False

        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Render
        ctx.clear(0.1, 0.1, 0.1)
        rotation = elapsed * 2.0  # Rotate based on time
        program["rotation"].value = rotation
        vao.render()

        pygame.display.flip()
        frame_count += 1

        # Print FPS every second
        if current_time - last_fps_time >= 1.0:
            fps = frame_count / (current_time - last_fps_time)
            print(f"[SPIKE] FPS: {fps:.1f}")
            frame_count = 0
            last_fps_time = current_time

    # 8. Cleanup
    pygame.mixer.music.stop()
    pygame.quit()
    print("[SPIKE] Cleanup complete")
    print("[SPIKE] SUCCESS: All three components validated")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[SPIKE] FAILED: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
