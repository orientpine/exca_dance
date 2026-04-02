"""Entry point for Exca Dance rhythm game."""

from __future__ import annotations
import argparse
from importlib import import_module
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import cast


def _setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _draw_fade_overlay(renderer, alpha: float) -> None:
    import moderngl
    import numpy as np

    if alpha <= 0.0:
        return

    ctx = renderer.ctx
    verts = np.array(
        [
            -1.0,
            -1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            -1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            -1.0,
            -1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            -1.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ],
        dtype="f4",
    )
    vbo = ctx.buffer(verts)
    prog = renderer.prog_solid
    vao = ctx.vertex_array(prog, [(vbo, "3f 3f", "in_position", "in_color")])

    identity = np.eye(4, dtype="f4")
    prog["mvp"].write(np.ascontiguousarray(identity).tobytes())
    prog["alpha"].value = alpha

    ctx.disable(moderngl.DEPTH_TEST)
    vao.render(moderngl.TRIANGLES)

    vao.release()
    vbo.release()
    prog["alpha"].value = 1.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exca Dance — Excavator Rhythm Game")
    parser.add_argument(
        "--mode",
        choices=["virtual", "real"],
        default="virtual",
        help="virtual: keyboard controls virtual excavator; real: ROS2 mode",
    )
    parser.add_argument("--windowed", action="store_true", help="Run in windowed mode (800x600)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args(argv)

    _setup_logging(args.debug)
    logger = logging.getLogger("exca_dance")
    logger.info("Exca Dance starting... mode=%s", args.mode)

    # Headless/CI: only force dummy audio when no display is available
    if (
        not os.environ.get("DISPLAY")
        and not os.environ.get("WAYLAND_DISPLAY")
        and sys.platform != "win32"
    ):
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    try:
        import pygame

        pygame.init()

        # Window setup
        from exca_dance.core.constants import TARGET_FPS

        if args.windowed:
            W, H = 800, 600
        else:
            display_info = pygame.display.Info()
            W, H = display_info.current_w, display_info.current_h

        # Renderer
        from exca_dance.rendering.renderer import GameRenderer

        renderer = GameRenderer(W, H, "Exca Dance", fullscreen=not args.windowed)

        # GL text renderer (prefer bundled D2Coding Nerd Font)
        from exca_dance.rendering.gl_text import GLTextRenderer

        bundled_font = Path("assets/fonts/D2CodingLigatureNerdFont-Regular.ttf")
        font_path = str(bundled_font) if bundled_font.exists() else None
        if font_path is None:
            logger.warning("Bundled D2Coding font not found, falling back to system default font")
        text_renderer = GLTextRenderer(renderer, font_path=font_path, font_size=20)

        # Audio
        from exca_dance.audio.audio_system import AudioSystem
        from exca_dance.core.models import Judgment

        audio = AudioSystem()
        hit_sounds = cast(
            dict[Judgment, pygame.mixer.Sound],
            {
                Judgment.PERFECT: pygame.mixer.Sound("assets/sounds/hit_perfect.wav"),
                Judgment.GREAT: pygame.mixer.Sound("assets/sounds/hit_great.wav"),
                Judgment.GOOD: pygame.mixer.Sound("assets/sounds/hit_good.wav"),
                Judgment.MISS: pygame.mixer.Sound("assets/sounds/hit_miss.wav"),
            },
        )

        # Core logic
        from exca_dance.core.kinematics import ExcavatorFK
        from exca_dance.core.scoring import ScoringEngine
        from exca_dance.core.keybinding import KeyBindingManager
        from exca_dance.core.leaderboard import LeaderboardManager
        from exca_dance.core.camera_settings import CameraSettings

        fk = ExcavatorFK()
        scoring = ScoringEngine()
        keybinding = KeyBindingManager()
        leaderboard = LeaderboardManager()
        camera_settings = CameraSettings()

        # Bridge
        from exca_dance.ros2_bridge import create_bridge

        bridge = create_bridge(args.mode)

        # 3D model + layout
        from exca_dance.rendering.excavator_model import ExcavatorModel
        from exca_dance.rendering.viewport_layout import GameViewportLayout

        excavator_model = ExcavatorModel(renderer, fk)
        viewport_layout = GameViewportLayout(renderer, W, H, camera_settings=camera_settings)

        # Game loop
        from exca_dance.core.game_loop import GameLoop

        game_loop = GameLoop(
            renderer, audio, fk, scoring, keybinding, bridge, viewport_layout, excavator_model,
            mode=args.mode,
        )

        # HUD + visual cues
        from exca_dance.ui.gameplay_hud import GameplayHUD
        from exca_dance.rendering.visual_cues import VisualCueRenderer
        from exca_dance.rendering.excavator_model import ExcavatorModel as ExcModel

        visual_cues = VisualCueRenderer(renderer, ExcModel, fk)
        from exca_dance.rendering.overlay_2d import Overlay2DRenderer

        overlay_2d = Overlay2DRenderer(renderer, fk)
        hud = GameplayHUD(renderer, text_renderer, audio, scoring, visual_cues)

        # Screens
        from exca_dance.core.game_state import GameStateManager, ScreenName
        from exca_dance.ui.screens.main_menu import MainMenuScreen
        from exca_dance.ui.screens.song_select import SongSelectScreen
        from exca_dance.ui.screens.gameplay_screen import GameplayScreen
        from exca_dance.ui.screens.results import ResultsScreen
        from exca_dance.ui.screens.leaderboard_screen import LeaderboardScreen
        from exca_dance.ui.screens.settings_screen import SettingsScreen
        from exca_dance.editor.editor_screen import PoseEditorScreen

        state_mgr = GameStateManager()
        state_mgr.register(
            ScreenName.MAIN_MENU,
            MainMenuScreen(
                renderer,
                text_renderer,
                args.mode.upper(),
                fk,
                ExcavatorModel,
            ),
        )
        state_mgr.register(
            ScreenName.SONG_SELECT, SongSelectScreen(renderer, text_renderer, leaderboard)
        )
        state_mgr.register(
            ScreenName.GAMEPLAY,
            GameplayScreen(
                renderer,
                text_renderer,
                game_loop,
                hud,
                visual_cues,
                viewport_layout,
                hit_sounds,
                overlay_2d=overlay_2d,
                camera_settings=camera_settings,
            ),
        )
        state_mgr.register(ScreenName.RESULTS, ResultsScreen(renderer, text_renderer))
        state_mgr.register(
            ScreenName.LEADERBOARD, LeaderboardScreen(renderer, text_renderer, leaderboard)
        )
        state_mgr.register(
            ScreenName.SETTINGS,
            SettingsScreen(
                renderer,
                text_renderer,
                keybinding,
                audio,
                camera_settings=camera_settings,
                fk=fk,
                excavator_model_class=ExcavatorModel,
            ),
        )
        tutorial_screen_class = import_module(
            "exca_dance.ui.screens.tutorial_screen"
        ).TutorialScreen
        state_mgr.register(ScreenName.TUTORIAL, tutorial_screen_class(renderer, text_renderer))
        state_mgr.register(
            ScreenName.EDITOR,
            PoseEditorScreen(renderer, text_renderer, audio, viewport_layout, excavator_model, fk),
        )
        state_mgr.transition_to(ScreenName.MAIN_MENU)

        # Main loop
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                    if state_mgr.get_current_state() == ScreenName.MAIN_MENU:
                        running = False
                state_mgr.handle_event(event)

            dt = clock.tick(TARGET_FPS) / 1000.0
            result = state_mgr.update(dt)
            if result == "quit":
                running = False

            renderer.begin_frame()
            state_mgr.render(renderer, text_renderer)
            if state_mgr.is_transitioning:
                _draw_fade_overlay(renderer, state_mgr.fade_alpha)
            renderer.end_frame()

        # Cleanup
        keybinding.save()
        camera_settings.save()
        audio.destroy()
        bridge.disconnect()
        visual_cues.destroy()
        excavator_model.destroy()
        renderer.destroy()
        pygame.quit()
        logger.info("Exca Dance exited cleanly")
        return 0

    except Exception as exc:
        log_path = Path("data/error.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            traceback.print_exc(file=f)
        print(f"Fatal error: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
