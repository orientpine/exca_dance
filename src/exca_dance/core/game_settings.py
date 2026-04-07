from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

VALID_MODES = ("virtual", "real")
SPEED_MIN: float = 0.5
SPEED_MAX: float = 2.0


class GameSettings:

    DEFAULT_MODE: str = "virtual"
    DEFAULT_PLAYBACK_SPEED: float = 1.0

    def __init__(self, filepath: str = "data/game_settings.json") -> None:
        self._filepath: Path = Path(filepath)
        self._mode: str = self.DEFAULT_MODE
        self._playback_speed: float = self.DEFAULT_PLAYBACK_SPEED
        self.load()

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if value not in VALID_MODES:
            raise ValueError(f"Invalid mode {value!r}, must be one of {VALID_MODES}")
        self._mode = value

    @property
    def playback_speed(self) -> float:
        return self._playback_speed

    @playback_speed.setter
    def playback_speed(self, value: float) -> None:
        v = float(value)
        if not (SPEED_MIN <= v <= SPEED_MAX):
            raise ValueError(
                f"Playback speed must be in [{SPEED_MIN}, {SPEED_MAX}], got {v}"
            )
        self._playback_speed = round(v, 2)

    def save(self) -> None:
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {"mode": self._mode, "playback_speed": self._playback_speed}
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        if not self._filepath.exists():
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                raw_mode = data.get("mode", self.DEFAULT_MODE)
                self._mode = raw_mode if raw_mode in VALID_MODES else self.DEFAULT_MODE
                raw_speed = data.get("playback_speed", self.DEFAULT_PLAYBACK_SPEED)
                try:
                    speed_val = float(raw_speed)
                    if SPEED_MIN <= speed_val <= SPEED_MAX:
                        self._playback_speed = round(speed_val, 2)
                except (TypeError, ValueError):
                    pass
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("Game settings unreadable, using defaults: %s", exc)
