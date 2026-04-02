from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

VALID_MODES = ("virtual", "real")


class GameSettings:

    DEFAULT_MODE: str = "virtual"

    def __init__(self, filepath: str = "data/game_settings.json") -> None:
        self._filepath: Path = Path(filepath)
        self._mode: str = self.DEFAULT_MODE
        self.load()

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if value not in VALID_MODES:
            raise ValueError(f"Invalid mode {value!r}, must be one of {VALID_MODES}")
        self._mode = value

    def save(self) -> None:
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {"mode": self._mode}
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        if not self._filepath.exists():
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                raw = data.get("mode", self.DEFAULT_MODE)
                self._mode = raw if raw in VALID_MODES else self.DEFAULT_MODE
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("Game settings unreadable, using defaults: %s", exc)
