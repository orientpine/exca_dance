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

## T1 Render Math Notes

- `render_math.py` now isolates reusable geometry helpers from `_make_link_verts`: unit direction, direction-aligned rotation matrix, pure-position oriented-box vertex generation, and GL matrix validation.
- Degenerate link segments (`p1 == p2`) should return an empty `(0, 3)` float32 array instead of raising or producing NaN values.
- Rotation alignment is Z-up first with Y-up fallback when direction is near-parallel to up; this mirrors existing rendering convention while remaining numerically stable.
- For strict static checks in this repo, `typing.cast` around some NumPy scalar-returning expressions avoids `basedpyright reportAny` noise in math-heavy tests/utilities.
- Test evidence for task is saved at `.sisyphus/evidence/task-1-render-math-tests.txt` and includes both focused and full-suite pytest runs.

## Ghost Palette Notes

- Added a distinct violet/purple ghost palette in `rendering/theme.py` so target poses no longer blend with current joint colors.
- Raised `GHOST_ALPHA` to `0.55` and annotated class attributes to keep `basedpyright` diagnostics clean without changing color values.
#QW|
#TJ|## Pause Menu Q-Key Fix Notes
#KM|
#ZX|- In `GameplayScreen.handle_event()`, the PAUSED-state Q shortcut should call `game_loop.stop()` before returning `ScreenName.MAIN_MENU`; keep PLAYING-state Q behavior untouched.
#WV|- Updated pause overlay copy from `Q Quit` to `Q Main Menu` to match the actual action.
#HY|- Full pytest run completed with `54 passed` using `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -v --tb=short`.

## Song-End Transition Fix Notes (Task 2)

- `AudioSystem.is_playing()` now synchronizes `_is_playing` with real mixer state via `pygame.mixer.music.get_busy()` (non-silent mode), fixing stale true state after natural song completion.
- Added optional `song_duration_ms` support in `AudioSystem.play(...)` plus `_song_duration_ms`; in silent mode playback now auto-completes once perf-counter elapsed time reaches duration.
- `GameLoop` now records `_all_events_consumed_at_ms` and uses a 3-second fallback after all events are consumed to force `FINISHED` transition.
- `_all_events_consumed_at_ms` is reset in `start_song()` to avoid state leakage across songs.
- Evidence file: `.sisyphus/evidence/task-2-song-end.txt` (`54 passed`).

## Test & Lint Conventions (surveyed 2026-03-26)

### Test Run Command
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v
```
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` is REQUIRED to avoid ROS launch plugin conflicts (noted in learnings)
- README documents `pytest tests/ -v` but the env var is needed in this environment
- 56 tests collected across 6 test files

### Ruff Configuration (pyproject.toml)
- `line-length = 100`
- `target-version = "py310"`
- **No explicit `select` or `ignore` keys** — uses ruff defaults (E + F rules only)
- Active rule sets: E4xx, E7xx, E9xx (pycodestyle errors), F4xx–F9xx (pyflakes)
- No W (warnings), no I (isort), no N (pep8-naming), no ANN (annotations) enforced by ruff
- Run: `.venv/bin/ruff check src/ tests/`
- Format: `.venv/bin/ruff format src/ tests/`

### pytest Configuration
- **No `[tool.pytest.ini_options]`** in pyproject.toml — zero pytest config
- No custom markers defined anywhere (only `@pytest.mark.parametrize` used)
- No `conftest.py` fixtures — conftest.py is a 1-line docstring only
- `tmp_path` is the only fixture used (built-in pytest fixture for temp dirs)
- Test paths: `tests/` directory, flat structure, no subdirectories

### Test File Patterns
All test files follow these conventions:
1. `from __future__ import annotations` at top (all except test_ros2_interface.py)
2. Imports from `exca_dance.*` directly (editable install via `pip install -e ".[dev]"`)
3. Function names: `test_<what>_<condition>_<expected_result>()` — descriptive snake_case
4. No classes — all module-level test functions
5. Return type annotation `-> None` on all test functions (except test_ros2_interface.py)
6. `typing.cast` used in tests to satisfy basedpyright when NumPy returns ambiguous types

### Fixture Patterns
- `tmp_path: Path` — used for file I/O tests (leaderboard, beatmap, keybinding)
- `_valid_payload()` helper function pattern (not a fixture) — returns dict for beatmap tests
- No `@pytest.fixture` decorators anywhere in the test suite
- No mocking/patching used anywhere

### ModernGL / GL Testing
- **NO GL tests exist** — ModernGL is NOT tested in the test suite
- `test_render_math.py` tests pure-Python/NumPy geometry math (no GL context needed)
- GL rendering code (`renderer.py`, `excavator_model.py`, etc.) has zero test coverage
- Headless GL approach documented in learnings: `xvfb-run -a` + `SDL_AUDIODRIVER=dummy`
- `__main__.py` auto-sets `SDL_AUDIODRIVER=dummy` when no DISPLAY/WAYLAND_DISPLAY env var
- Mesa llvmpipe (software rendering) confirmed working on headless Ubuntu (GL 4.5)
- `moderngl.create_context()` called after `pygame.init()` with `pygame.OPENGL | pygame.DOUBLEBUF`
- If GL tests were needed: `xvfb-run -a PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v`

### Exception Testing Pattern
```python
with pytest.raises(ValueError):
    some_call(...)
```

### Parametrize Pattern
```python
@pytest.mark.parametrize("initials", ["", "ab", "abcd", "  ab  "])
def test_name(tmp_path, initials: str) -> None:
```

### AST-based Import Testing Pattern (test_ros2_interface.py)
```python
import ast
source = Path("/absolute/path/to/file.py").read_text()
tree = ast.parse(source)
imported_modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
assert "forbidden_module" not in imported_modules
```
