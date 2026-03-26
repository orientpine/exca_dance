from __future__ import annotations

from pathlib import Path

from exca_dance.audio.audio_system import AudioSystem


def test_set_and_get_bgm_volume() -> None:
    audio = AudioSystem()
    audio.set_bgm_volume(0.5)
    assert abs(audio.get_bgm_volume() - 0.5) < 0.01


def test_volume_save_load_roundtrip(tmp_path: Path) -> None:
    audio = AudioSystem()
    audio.set_bgm_volume(0.7)
    audio.set_sfx_volume(0.3)
    path = str(tmp_path / "volume.json")
    audio.save_volume_settings(path)

    audio2 = AudioSystem()
    audio2.load_volume_settings(path)

    assert abs(audio2.get_bgm_volume() - 0.7) < 0.01
    assert abs(audio2.get_sfx_volume() - 0.3) < 0.01
