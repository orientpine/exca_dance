# Decisions — gameplay-screen-overhaul

## Execution Plan
- Wave 1 (6 tasks parallel): T1, T2, T3, T4, T5, T6
- Wave 2 (3 tasks, after Wave 1): T7, T8, T9
- Wave 3 (1 task, after Wave 2): T10
- Final Wave: F1, F2, F3, F4 parallel

## Key Architectural Decisions
- Ghost outline: use existing `prog_additive` (NO new shaders)
- Wireframe: full triangle edges (not just box edges)
- 2D overlay: straight line segments + text labels (NO arc tessellation)
- Pulse animation: CPU-side sin() with time.perf_counter()
- Z-fighting prevention: disable depth test for outline pass
- Line width: 1.0 only (Mesa/llvmpipe limitation)
- Hit sounds: pygame.mixer.Sound.play() directly
- Scope: 1920×1080 fullscreen only; windowed mode unchanged
