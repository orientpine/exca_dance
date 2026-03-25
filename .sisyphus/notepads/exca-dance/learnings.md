# Spike Learnings — Pygame + ModernGL + Audio

## ✅ Validation Results

### Environment
- **Python**: 3.12.3
- **Pygame-CE**: 2.5.7 (SDL 2.32.10)
- **ModernGL**: Latest (installed via pip)
- **GL Renderer**: Mesa llvmpipe (LLVM 20.1.2) — software rendering on headless Ubuntu
- **GL Version**: 4.5 Compatibility Profile

### Three-Component Coexistence: CONFIRMED
1. **Pygame Display + OpenGL**: ✅ Works with `pygame.OPENGL | pygame.DOUBLEBUF` flags
2. **ModernGL Context**: ✅ Created successfully via `moderngl.create_context()` after Pygame init
3. **Audio Playback**: ✅ `pygame.mixer.music` plays WAV files (OGG generation requires ffmpeg)

### Performance
- **FPS**: 3800–4000 fps (software rendering, no vsync)
- **Stability**: 5-second run completed cleanly, exit code 0
- **Audio**: Loaded and played without blocking render loop

## Key Implementation Details

### Audio File Generation
- Generated 1-second 440Hz sine wave using numpy + wave module
- Attempted OGG conversion via ffmpeg (available on system)
- Fallback: WAV format works perfectly with `pygame.mixer.music.load()`
- **Note**: For production, pre-generate OGG files or use ffmpeg in build pipeline

### Headless Rendering
- Used `xvfb-run -a` for virtual display (no physical monitor needed)
- Set `SDL_AUDIODRIVER=dummy` for headless audio (prevents device errors)
- ModernGL renders to offscreen framebuffer without issues

### Shader Pipeline
- Vertex shader: 2D position + 3D color, rotation uniform
- Fragment shader: Simple passthrough color
- VAO/VBO: Triangle geometry with interleaved position+color
- Rotation: Time-based (elapsed seconds × 2.0 radians/sec)

## Guardrails Confirmed
- ❌ `pygame.mixer.music.get_pos()` NOT used (known drift bug)
- ✅ `time.perf_counter()` for timing (manual clock)
- ✅ No `Surface.blit()` in render loop (all OpenGL)
- ✅ No Ursina (Pygame loop conflict confirmed in plan)

## Next Steps (T2+)
- Extend spike to 3D excavator geometry (FK kinematics)
- Add 2D auxiliary views (top/side)
- Implement beat detection + scoring logic
- Load actual OGG music files (pre-generated)

## T2+ Scaffold Notes

- Editable install works in a local venv with `setuptools.build_meta` plus `package-dir = {"" = "src"}`.
- `pytest` in this environment needs `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` to avoid unrelated ROS launch plugins.
- Relative imports inside `src/exca_dance/core/` avoid type-stub warnings from the language server.
- Virtual bridge tests should verify actual import nodes instead of substring matches, because module docstrings may legally mention forbidden package names.
- Pyright reportMissingTypeStubs warnings may appear on typed package imports even when runtime behavior is correct.
