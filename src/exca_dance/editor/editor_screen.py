"""Pose editor: timeline + event placement + angle editing + save/load."""

from __future__ import annotations
import os
import pygame
from typing import cast
from exca_dance.core.models import JointName, BeatEvent, BeatMap
from exca_dance.core.beatmap import load_beatmap, save_beatmap
from exca_dance.core.constants import DEFAULT_JOINT_ANGLES, JOINT_ANGULAR_VELOCITY, JOINT_LIMITS
from exca_dance.rendering.theme import NeonTheme
from exca_dance.core.game_state import ScreenName


class PoseEditorScreen:
    """
    In-game pose editor:
    - Timeline at bottom (scrollable, beat markers)
    - Excavator preview (top area)
    - N: new event at cursor
    - Delete: remove selected event
    - Space: play/pause preview
    - Ctrl+S: save, Ctrl+O: load, Ctrl+N: new
    """

    def __init__(
        self, renderer, text_renderer, audio, viewport_layout, excavator_model, fk
    ) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._audio = audio
        self._layout = viewport_layout
        self._model = excavator_model
        self._fk = fk

        self._beatmap: BeatMap | None = None
        self._events: list[BeatEvent] = []
        self._selected_idx: int = -1
        self._cursor_ms: float = 0.0
        self._playing: bool = False
        self._joint_angles: dict[JointName, float] = dict(DEFAULT_JOINT_ANGLES)
        self._held_keys: set[int] = set()
        self._filepath: str = ""
        self._status_msg: str = "Ctrl+N: New  Ctrl+O: Load  Ctrl+S: Save"

    def on_enter(self, **kwargs) -> None:
        self._playing = False
        self._cursor_ms = 0.0
        self._held_keys.clear()

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            self._held_keys.add(event.key)
            ctrl = pygame.key.get_mods() & pygame.KMOD_CTRL
            shift = pygame.key.get_mods() & pygame.KMOD_SHIFT

            if event.key == pygame.K_ESCAPE:
                self._audio.stop()
                return ScreenName.MAIN_MENU

            elif ctrl and event.key == pygame.K_n:
                self._new_beatmap()
            elif ctrl and event.key == pygame.K_s:
                self._save()
            elif ctrl and event.key == pygame.K_o:
                self._load_dialog()
            elif event.key == pygame.K_SPACE:
                self._toggle_play()
            elif event.key == pygame.K_n and not ctrl:
                self._add_event()
            elif event.key == pygame.K_DELETE:
                self._delete_selected()
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                if shift:
                    self._held_keys.add(event.key)
                else:
                    self._held_keys.discard(event.key)
                    delta = -500 if event.key == pygame.K_LEFT else 500
                    self._cursor_ms = max(0.0, self._cursor_ms + delta)
            elif event.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
                if self._selected_idx >= 0 and self._selected_idx < len(self._events):
                    ev = self._events[self._selected_idx]
                    delta = -50 if event.key == pygame.K_LEFTBRACKET else 50
                    new_dur = max(100, ev.duration_ms + delta)
                    self._events[self._selected_idx] = BeatEvent(
                        ev.time_ms, ev.target_angles, new_dur
                    )

        elif event.type == pygame.KEYUP:
            self._held_keys.discard(event.key)

        return None

    def _new_beatmap(self) -> None:
        self._beatmap = BeatMap(
            title="New Song", artist="", bpm=120.0, offset_ms=0, audio_file="", events=[]
        )
        self._events = []
        self._selected_idx = -1
        self._cursor_ms = 0.0
        self._status_msg = "New beat map created"

    def _add_event(self) -> None:
        target = dict(self._joint_angles)
        ev = BeatEvent(time_ms=int(self._cursor_ms), target_angles=target, duration_ms=500)
        self._events.append(ev)
        self._events.sort(key=lambda e: e.time_ms)
        self._selected_idx = next(
            i for i, e in enumerate(self._events) if e.time_ms == int(self._cursor_ms)
        )
        self._status_msg = f"Event added at {self._cursor_ms:.0f}ms"

    def _delete_selected(self) -> None:
        if 0 <= self._selected_idx < len(self._events):
            self._events.pop(self._selected_idx)
            self._selected_idx = min(self._selected_idx, len(self._events) - 1)
            self._status_msg = "Event deleted"

    def _toggle_play(self) -> None:
        if self._playing:
            self._audio.pause()
            self._playing = False
        else:
            if (
                self._beatmap
                and self._beatmap.audio_file
                and os.path.isfile(self._beatmap.audio_file)
            ):
                self._audio.load_music(self._beatmap.audio_file)
                self._audio.play()
            self._playing = True

    def _save(self) -> None:
        if self._beatmap is None:
            self._status_msg = "No beat map to save"
            return
        bm = BeatMap(
            title=self._beatmap.title,
            artist=self._beatmap.artist,
            bpm=self._beatmap.bpm,
            offset_ms=self._beatmap.offset_ms,
            audio_file=self._beatmap.audio_file,
            events=list(self._events),
        )
        path = self._filepath or f"assets/beatmaps/{bm.title.replace(' ', '_').lower()}.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        save_beatmap(bm, path)
        self._filepath = path
        self._status_msg = f"Saved: {path}"

    def _load_dialog(self) -> None:
        # Simple: load first available beatmap
        for fname in sorted(os.listdir("assets/beatmaps")):
            if fname.endswith(".json"):
                path = os.path.join("assets/beatmaps", fname)
                try:
                    bm = load_beatmap(path)
                    self._beatmap = bm
                    self._events = list(bm.events)
                    self._filepath = path
                    self._status_msg = f"Loaded: {path}"
                    return
                except Exception as e:
                    self._status_msg = f"Load error: {e}"

    def update(self, dt: float):
        if self._playing:
            self._cursor_ms = self._audio.get_position_ms()

        # Update joint angles from held keys
        for key in self._held_keys:
            # Use default WASD-like mapping for editor
            key_map: dict[int, tuple[JointName, int]] = {
                pygame.K_w: (cast(JointName, JointName.BOOM), 1),
                pygame.K_s: (cast(JointName, JointName.BOOM), -1),
                pygame.K_a: (cast(JointName, JointName.SWING), -1),
                pygame.K_d: (cast(JointName, JointName.SWING), 1),
                pygame.K_UP: (cast(JointName, JointName.ARM), 1),
                pygame.K_DOWN: (cast(JointName, JointName.ARM), -1),
                pygame.K_LEFT: (cast(JointName, JointName.BUCKET), -1),
                pygame.K_RIGHT: (cast(JointName, JointName.BUCKET), 1),
            }
            if key in key_map:
                jname, direction = key_map[key]
                lo, hi = JOINT_LIMITS[jname]
                self._joint_angles[jname] = max(
                    lo, min(hi, self._joint_angles[jname] + direction * JOINT_ANGULAR_VELOCITY * dt)
                )

        # Update selected event angles if editing
        if self._selected_idx >= 0 and self._selected_idx < len(self._events):
            ev = self._events[self._selected_idx]
            self._events[self._selected_idx] = BeatEvent(
                ev.time_ms, dict(self._joint_angles), ev.duration_ms
            )

        self._model.update(self._joint_angles)
        return None

    def render(self, renderer, text_renderer) -> None:
        # Render excavator
        self._layout.render_all(self._model, self._joint_angles)

        if text_renderer is None:
            return
        W, H = renderer.width, renderer.height

        # Title bar
        title = self._beatmap.title if self._beatmap else "No Beat Map"
        text_renderer.render(
            f"EDITOR: {title}",
            W // 2,
            20,
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=1.2,
            align="center",
        )

        # Timeline (bottom strip)
        tl_y = H - 120
        text_renderer.render(
            f"Time: {self._cursor_ms / 1000:.2f}s",
            20,
            tl_y,
            color=NeonTheme.TEXT_WHITE.as_tuple(),
            scale=0.9,
        )

        # Event markers
        for i, ev in enumerate(self._events):
            color = NeonTheme.NEON_PINK if i == self._selected_idx else NeonTheme.NEON_GREEN
            text_renderer.render(
                f"●{ev.time_ms / 1000:.1f}s",
                20 + i * 80,
                tl_y + 25,
                color=color.as_tuple(),
                scale=0.75,
            )

        # Joint angles
        jnames = list(JointName)
        for i, jname in enumerate(jnames):
            angle = self._joint_angles.get(jname, 0.0)
            text_renderer.render(
                f"{jname.value}: {angle:+.1f}°",
                W - 200,
                60 + i * 30,
                color=NeonTheme.TEXT_WHITE.as_tuple(),
                scale=0.85,
            )

        # Status
        text_renderer.render(
            self._status_msg,
            W // 2,
            H - 30,
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=0.85,
            align="center",
        )
        text_renderer.render(
            "N:Add  Del:Remove  Space:Play  Ctrl+S:Save  ESC:Back",
            W // 2,
            H - 55,
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=0.75,
            align="center",
        )
