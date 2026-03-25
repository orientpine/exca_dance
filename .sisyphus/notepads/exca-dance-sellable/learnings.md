# Learnings — exca-dance-sellable

## [2026-03-25] Session: ses_2da417907ffea6NBkr8D3UF94B
### Project Setup
- Working directory: /home/cha/Documents/exca_dance_sellable
- Plan file: /home/cha/Documents/exca_dance/.sisyphus/plans/exca-dance-sellable.md
- venv: .venv (created fresh)
- Baseline: 56 tests pass, 0 failures
- Test command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest tests/ -v`
- Linter: `.venv/bin/ruff check src/ tests/`

### Architecture
- No .venv existed initially — needed to create: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`
- VBO layout: 9 floats/vertex (pos 3f + color 3f + normal 3f) for prog_solid
- prog_additive: 7 floats/vertex (pos 3f + color 4f)
- All screens duck-typed: on_enter, handle_event, update, render
- time.perf_counter() for timing — never pygame clock
- Angles in degrees throughout (radians only in kinematics.py)

## [2026-03-26] Session: gameplay_screen TOCTOU fix
### Regression Notes
- Cached `get_upcoming_events(500)` in a local `_upcoming` variable before indexing, removing the race between repeated calls.
- Added `tests/test_gameplay_screen.py` with `unittest.mock.MagicMock` coverage for `GameplayScreen.update()` when upcoming events are empty.
- Full suite result: 57 passed.

## [2026-03-26] Session: judgment flash + combo milestone polish
### UI Feedback Patterns
- `JudgmentDisplay` now owns transient screen-flash state (`flash_alpha`, `flash_color`, `flash_start`, `flash_duration`) and exposes it via `current_flash` so HUD can render overlays without duplicating timing logic.
- PERFECT/MISS flash specs implemented as short-lived effects: PERFECT uses white `(1.0, 1.0, 1.0)` at 0.15 for 50ms, MISS uses red `(1.0, 0.1, 0.1)` at 0.08 for 30ms.
- Judgment label pop animation is cleanly handled in `render()` with a 0.3s ease-out style scale transition from 1.5× base size to base size.
- `_draw_rect_2d` in `GameplayHUD` accepts an `alpha` kwarg, allowing full-screen flash overlays through existing `prog_solid` path (no new shader needed).
- Combo milestone emphasis at exact combo values `(10, 25, 50)` uses `NEON_PINK` and a larger scale for stronger progression feedback.
- Added `tests/test_hit_detection.py` with MagicMock-only coverage for PERFECT flash alpha and MISS flash color; full suite result: 59 passed.

## [2026-03-26] Session: fade-to-black screen transition system
### Transition Architecture
- `GameStateManager.transition_to()` now queues `_pending_screen`/`_pending_kwargs` and enters a fade-out state instead of switching screens immediately.
- Screen swap plus delayed `on_enter(**kwargs)` happens exactly at fade peak (`_fade_alpha == 1.0`), then manager enters fade-in and clears pending transition data.
- Fade timing is symmetric (`_fade_duration = 0.3` each phase) and exposed via `is_transitioning` and `fade_alpha` properties for render-layer overlay usage.

### Rendering Pattern
- Fullscreen fade overlay in `__main__.py` reuses `renderer.prog_solid` with a `"3f 3f"` VBO layout, identity MVP, and per-frame alpha uniform updates.
- Overlay draw is injected after `state_mgr.render(...)` and before `renderer.end_frame()` so it fades all screens uniformly without touching individual screen implementations.

### Test Strategy
- Added focused state-manager tests (`tests/test_game_state.py`) that advance time in deterministic `0.01s` steps to validate transition start (`is_transitioning=True`) and completion (`False` after total fade budget).
