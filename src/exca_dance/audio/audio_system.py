"""Audio system for Exca Dance.
Uses time.perf_counter() for song position tracking.
NEVER uses pygame.mixer.music position query — it drifts ~500ms/300s with MP3.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import wave
from pathlib import Path
from typing import cast

import numpy as np
import pygame

logger = logging.getLogger(__name__)

_SUPPORTED_MUSIC = {".ogg", ".wav"}
_SUPPORTED_SFX = {".wav"}
_AUDIO_CACHE_DIR: Path = Path("data/cache/audio")


class AudioSystem:
    """Manages BGM playback and SFX with precise timing via perf_counter."""

    def __init__(self, buffer_size: int = 512, volume_settings_path: str = "data/volume.json"):
        self._buffer_size: int = buffer_size
        self._initialized: bool = False
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
        self._volume_settings_path: Path = Path(volume_settings_path)
        self._init_mixer(buffer_size)
        self.load_volume_settings(str(self._volume_settings_path))

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

    def load_music_scaled(self, path: str, speed: float) -> None:
        """Load music with playback speed scaling via numpy WAV resampling.

        Speed > 1.0 = faster + higher pitch (chipmunk effect).
        Speed < 1.0 = slower + lower pitch.
        Pitch-preserving stretch would require librosa/ffmpeg; this uses
        simple linear interpolation to avoid heavy dependencies.

        Only WAV files can be scaled. OGG falls back to normal load with
        a warning. speed == 1.0 is a fast path to load_music().
        """
        if abs(speed - 1.0) < 1e-6:
            self.load_music(path)
            return

        ext = Path(path).suffix.lower()
        if ext not in _SUPPORTED_MUSIC:
            raise ValueError(f"Unsupported audio format '{ext}'. Use OGG or WAV.")
        if ext != ".wav":
            logger.warning(
                "Speed scaling requires WAV (got %s). Loading at normal speed.", ext
            )
            self.load_music(path)
            return

        src = Path(path)
        _AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = _AUDIO_CACHE_DIR / f"{src.stem}_{speed:.2f}x{src.suffix}"

        if not cache_path.exists():
            try:
                _resample_wav(str(src), str(cache_path), speed)
            except Exception as exc:
                logger.warning(
                    "WAV resampling failed (%s); loading at normal speed", exc
                )
                self.load_music(path)
                return

        if self._silent_mode:
            logger.warning("Silent mode: load_music_scaled ignored for %s", path)
            self._current_path = str(cache_path)
            return
        pygame.mixer.music.load(str(cache_path))
        self._current_path = str(cache_path)
        logger.debug("Loaded scaled music: %s (speed=%.2fx)", cache_path, speed)

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

    def get_bgm_volume(self) -> float:
        return self._volume

    def get_sfx_volume(self) -> float:
        return self._sfx_volume

    def set_bgm_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))
        if not self._silent_mode and self._initialized:
            pygame.mixer.music.set_volume(self._volume)

    def set_volume(self, volume: float) -> None:
        self.set_bgm_volume(volume)

    def set_sfx_volume(self, volume: float) -> None:
        self._sfx_volume = max(0.0, min(1.0, volume))
        for snd in self._sfx_cache.values():
            snd.set_volume(self._sfx_volume)

    def save_volume_settings(self, path: str) -> None:
        settings_path = Path(path)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"bgm": self._volume, "sfx": self._sfx_volume}
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_volume_settings(self, path: str) -> None:
        settings_path = Path(path)
        if not settings_path.exists():
            return
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = cast(dict[str, object], json.load(f))
            bgm = cast(float | int | str, data.get("bgm", self._volume))
            sfx = cast(float | int | str, data.get("sfx", self._sfx_volume))
            self.set_bgm_volume(float(bgm))
            self.set_sfx_volume(float(sfx))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Volume settings unreadable, using defaults: %s", exc)

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
            _ = self._sfx_cache[name].play()

    def destroy(self) -> None:
        if self._initialized and not self._silent_mode:
            # Stop all playback BEFORE quitting mixer — prevents hang when
            # audio backend (PipeWire/PulseAudio) is in a broken-pipe state.
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            try:
                pygame.mixer.stop()
            except Exception:
                pass
            self._quit_mixer_safe()
        self._sfx_cache.clear()

    def _quit_mixer_safe(self, timeout: float = 2.0) -> None:
        """Quit mixer with timeout — prevents indefinite hang on stuck audio backends."""
        t = threading.Thread(target=pygame.mixer.quit, daemon=True)
        t.start()
        t.join(timeout=timeout)
        if t.is_alive():
            logger.warning(
                "pygame.mixer.quit() timed out (%.1fs) — audio backend may be stuck", timeout
            )


_NUMPY_DTYPE_BY_SAMPWIDTH: dict[int, type] = {
    1: np.uint8,
    2: np.int16,
    4: np.int32,
}


def _resample_wav(src: str, dst: str, speed: float) -> None:
    """Resample a WAV file by speed factor using numpy linear interpolation.

    speed > 1.0 produces a shorter file (plays faster).
    speed < 1.0 produces a longer file (plays slower).
    Sample rate is preserved — pitch changes with speed (chipmunk effect).
    """
    with wave.open(src, "rb") as w_in:
        n_channels = w_in.getnchannels()
        sampwidth = w_in.getsampwidth()
        framerate = w_in.getframerate()
        n_frames = w_in.getnframes()
        raw = w_in.readframes(n_frames)

    dtype = _NUMPY_DTYPE_BY_SAMPWIDTH.get(sampwidth)
    if dtype is None:
        raise ValueError(f"Unsupported WAV sample width: {sampwidth}")

    samples = np.frombuffer(raw, dtype=dtype)
    if n_channels > 1:
        samples = samples.reshape(-1, n_channels)

    original_n = int(samples.shape[0])
    if original_n < 2:
        raise ValueError("WAV file too short to resample")

    new_n = max(2, int(round(original_n / speed)))
    old_x = np.arange(original_n, dtype=np.float64)
    new_x = np.linspace(0.0, float(original_n - 1), new_n, dtype=np.float64)

    if n_channels > 1:
        resampled = np.empty((new_n, n_channels), dtype=dtype)
        for ch in range(n_channels):
            interpolated = np.interp(new_x, old_x, samples[:, ch].astype(np.float64))
            resampled[:, ch] = np.asarray(interpolated, dtype=dtype)
    else:
        interpolated = np.interp(new_x, old_x, samples.astype(np.float64))
        resampled = np.asarray(interpolated, dtype=dtype)

    with wave.open(dst, "wb") as w_out:
        w_out.setnchannels(n_channels)
        w_out.setsampwidth(sampwidth)
        w_out.setframerate(framerate)
        w_out.writeframes(resampled.tobytes())
