# Issues — exca-dance-sellable

## [2026-03-25] Session: ses_2da417907ffea6NBkr8D3UF94B
### Known Bugs (from plan audit)
- **TOCTOU in gameplay_screen.py:66-68**: `get_upcoming_events(500)` called twice — Task 1-3 fixes this
- ghost glow VBO format mismatch (Task 1-2 — already fixed in overhaul plan)
