from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from exca_dance.audio.audio_system import _resample_wav
from exca_dance.core.game_loop import _scale_events
from exca_dance.core.models import BeatEvent, JointName


def test_scale_events_identity_at_1x() -> None:
    events = [
        BeatEvent(time_ms=1000, target_angles={JointName.BOOM: 10.0}, duration_ms=500),
        BeatEvent(time_ms=5000, target_angles={JointName.ARM: -20.0}, duration_ms=750),
    ]
    scaled = _scale_events(events, 1.0)
    assert scaled[0].time_ms == 1000
    assert scaled[0].duration_ms == 500
    assert scaled[1].time_ms == 5000
    assert scaled[1].duration_ms == 750


def test_scale_events_half_speed_doubles_times() -> None:
    events = [
        BeatEvent(time_ms=1000, target_angles={JointName.BOOM: 10.0}, duration_ms=500),
        BeatEvent(time_ms=10000, target_angles={JointName.ARM: -20.0}, duration_ms=800),
    ]
    scaled = _scale_events(events, 0.5)
    assert scaled[0].time_ms == 2000
    assert scaled[0].duration_ms == 1000
    assert scaled[1].time_ms == 20000
    assert scaled[1].duration_ms == 1600


def test_scale_events_double_speed_halves_times() -> None:
    events = [
        BeatEvent(time_ms=2000, target_angles={JointName.BOOM: 10.0}, duration_ms=1000),
        BeatEvent(time_ms=10000, target_angles={JointName.ARM: -20.0}, duration_ms=500),
    ]
    scaled = _scale_events(events, 2.0)
    assert scaled[0].time_ms == 1000
    assert scaled[0].duration_ms == 500
    assert scaled[1].time_ms == 5000
    assert scaled[1].duration_ms == 250


def test_scale_events_preserves_target_angles() -> None:
    targets = {JointName.BOOM: 10.0, JointName.ARM: -20.0}
    events = [BeatEvent(time_ms=1000, target_angles=targets, duration_ms=500)]
    scaled = _scale_events(events, 1.5)
    assert scaled[0].target_angles == targets
    assert scaled[0].target_angles is not targets


def test_scale_events_minimum_duration_one() -> None:
    events = [BeatEvent(time_ms=1000, target_angles={}, duration_ms=1)]
    scaled = _scale_events(events, 2.0)
    assert scaled[0].duration_ms == 1


def _write_test_wav(path: Path, n_samples: int = 1000, n_channels: int = 2) -> None:
    framerate = 44100
    sampwidth = 2
    t = np.arange(n_samples) / framerate
    tone = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
    if n_channels == 2:
        interleaved = np.empty(n_samples * 2, dtype=np.int16)
        interleaved[0::2] = tone
        interleaved[1::2] = tone
        data = interleaved.tobytes()
    else:
        data = tone.tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(n_channels)
        w.setsampwidth(sampwidth)
        w.setframerate(framerate)
        w.writeframes(data)


def test_resample_wav_double_speed_halves_samples(tmp_path: Path) -> None:
    src = tmp_path / "src.wav"
    dst = tmp_path / "dst.wav"
    _write_test_wav(src, n_samples=1000, n_channels=2)

    _resample_wav(str(src), str(dst), speed=2.0)

    with wave.open(str(dst), "rb") as w:
        assert w.getnchannels() == 2
        assert w.getsampwidth() == 2
        assert w.getframerate() == 44100
        assert w.getnframes() == 500


def test_resample_wav_half_speed_doubles_samples(tmp_path: Path) -> None:
    src = tmp_path / "src.wav"
    dst = tmp_path / "dst.wav"
    _write_test_wav(src, n_samples=1000, n_channels=2)

    _resample_wav(str(src), str(dst), speed=0.5)

    with wave.open(str(dst), "rb") as w:
        assert w.getnframes() == 2000


def test_resample_wav_mono(tmp_path: Path) -> None:
    src = tmp_path / "src.wav"
    dst = tmp_path / "dst.wav"
    _write_test_wav(src, n_samples=500, n_channels=1)

    _resample_wav(str(src), str(dst), speed=1.5)

    with wave.open(str(dst), "rb") as w:
        assert w.getnchannels() == 1
        expected = int(round(500 / 1.5))
        assert w.getnframes() == expected


def test_resample_wav_rejects_too_short(tmp_path: Path) -> None:
    src = tmp_path / "tiny.wav"
    dst = tmp_path / "dst.wav"
    with wave.open(str(src), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(np.array([0], dtype=np.int16).tobytes())

    with pytest.raises(ValueError, match="too short"):
        _resample_wav(str(src), str(dst), speed=2.0)
