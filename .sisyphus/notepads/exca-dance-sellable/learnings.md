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
