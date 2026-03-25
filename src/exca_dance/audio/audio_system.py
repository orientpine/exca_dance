"""Audio system for Exca Dance.
Uses time.perf_counter() for song position tracking.
NEVER uses pygame.mixer.music position query — it drifts ~500ms/300s with MP3.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pygame

logger = logging.getLogger(__name__)

_SUPPORTED_MUSIC = {".ogg", ".wav"}
_SUPPORTED_SFX = {".wav"}


class AudioSystem:
    """Manages BGM playback and SFX with precise timing via perf_counter."""

    def __init__(self, buffer_size: int = 512):
        self._buffer_size = buffer_size
        self._initialized = False
        self._start_time: float = 0.0
        self._pause_start: float = 0.0
        self._accumulated_pause: float = 0.0
        self._is_playing: bool = False
        self._is_paused: bool = False
        self._volume: float = 1.0
        self._sfx_volume: float = 1.0
        self._sfx_cache: dict[str, pygame.mixer.Sound] = {}
        self._current_path: str | None = None
        self._song_duration_ms: float | None = None
        self._silent_mode: bool = False
        self._init_mixer(buffer_size)

    def _init_mixer(self, buffer_size: int) -> None:
        try:
            pygame.mixer.pre_init(44100, -16, 2, buffer_size)
            pygame.mixer.init()
            self._initialized = True
        except pygame.error as exc:
            logger.warning("Audio device unavailable, running in silent mode: %s", exc)
            self._silent_mode = True

    def load_music(self, path: str) -> None:
        """Load an OGG (or WAV) music file. Raises ValueError for unsupported formats."""
        ext = Path(path).suffix.lower()
        if ext not in _SUPPORTED_MUSIC:
            raise ValueError(f"Unsupported audio format '{ext}'. Use OGG or WAV.")
        if self._silent_mode:
            logger.warning("Silent mode: load_music ignored for %s", path)
            self._current_path = path
            return
        pygame.mixer.music.load(path)
        self._current_path = path
        logger.debug("Loaded music: %s", path)

    def play(self, song_duration_ms: float | None = None) -> None:
        """Start/restart playback from beginning."""
        self._song_duration_ms = song_duration_ms
        if self._silent_mode:
            self._start_time = time.perf_counter()
            self._accumulated_pause = 0.0
            self._is_playing = True
            self._is_paused = False
            return
        pygame.mixer.music.set_volume(self._volume)
        pygame.mixer.music.play()
        self._start_time = time.perf_counter()
        self._accumulated_pause = 0.0
        self._is_playing = True
        self._is_paused = False

    def pause(self) -> None:
        if self._is_playing and not self._is_paused:
            if not self._silent_mode:
                pygame.mixer.music.pause()
            self._pause_start = time.perf_counter()
            self._is_paused = True

    def resume(self) -> None:
        if self._is_paused:
            if not self._silent_mode:
                pygame.mixer.music.unpause()
            self._accumulated_pause += time.perf_counter() - self._pause_start
            self._is_paused = False

    def stop(self) -> None:
        if not self._silent_mode:
            pygame.mixer.music.stop()
        self._is_playing = False
        self._is_paused = False

    def get_position_ms(self) -> float:
        """
        Return current song position in milliseconds using perf_counter.
        Returns 0 if not playing.
        NEVER calls pygame.mixer.music position query.
        """
        if not self._is_playing:
            return 0.0
        elapsed = time.perf_counter() - self._start_time - self._accumulated_pause
        if self._is_paused:
            elapsed -= time.perf_counter() - self._pause_start
        return max(0.0, elapsed * 1000.0)

    def is_playing(self) -> bool:
        if not self._is_playing or self._is_paused:
            return False

        if self._silent_mode:
            if self._song_duration_ms is not None:
                elapsed_ms = (
                    time.perf_counter() - self._start_time - self._accumulated_pause
                ) * 1000.0
                if elapsed_ms >= self._song_duration_ms:
                    self._is_playing = False
                    return False
            return True

        if not pygame.mixer.music.get_busy():
            self._is_playing = False
            return False
        return True

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))
        if not self._silent_mode and self._initialized:
            pygame.mixer.music.set_volume(self._volume)

    def set_sfx_volume(self, volume: float) -> None:
        self._sfx_volume = max(0.0, min(1.0, volume))
        for snd in self._sfx_cache.values():
            snd.set_volume(self._sfx_volume)

    def load_sfx(self, name: str, path: str) -> None:
        """Load a WAV sound effect."""
        if self._silent_mode or not self._initialized:
            return
        ext = Path(path).suffix.lower()
        if ext not in _SUPPORTED_SFX:
            raise ValueError(f"SFX must be WAV, got: {ext}")
        self._sfx_cache[name] = pygame.mixer.Sound(path)
        self._sfx_cache[name].set_volume(self._sfx_volume)

    def play_sfx(self, name: str) -> None:
        if name in self._sfx_cache:
            self._sfx_cache[name].play()

    def destroy(self) -> None:
        if self._initialized and not self._silent_mode:
            pygame.mixer.quit()
        self._sfx_cache.clear()
