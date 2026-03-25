from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from exca_dance.core.models import LeaderboardEntry

logger = logging.getLogger(__name__)


class LeaderboardManager:
    def __init__(self, filepath: str = "data/leaderboard.json"):
        self._filepath: Path = Path(filepath)
        self._entries: list[LeaderboardEntry] = []
        self.load()

    def add_entry(self, initials: str, score: int, song_title: str) -> LeaderboardEntry:
        initials = initials.strip().upper()
        if len(initials) != 3:
            raise ValueError(f"Initials must be exactly 3 characters, got: '{initials}'")
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = LeaderboardEntry(
            initials=initials, score=score, song_title=song_title, timestamp=timestamp
        )
        self._entries.append(entry)
        self.save()
        return entry

    def get_top_scores(self, limit: int = 10, song: str | None = None) -> list[LeaderboardEntry]:
        entries = self._entries
        if song is not None:
            entries = [e for e in entries if e.song_title == song]
        return sorted(entries, key=lambda e: e.score, reverse=True)[:limit]

    def save(self) -> None:
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "initials": e.initials,
                "score": e.score,
                "song_title": e.song_title,
                "timestamp": e.timestamp,
            }
            for e in self._entries
        ]
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        if not self._filepath.exists():
            self._entries = []
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                raw_data = cast(object, json.load(f))
            if not isinstance(raw_data, list):
                raise KeyError("Leaderboard data must be a list")
            entries_data = cast(list[object], raw_data)
            entries: list[LeaderboardEntry] = []
            for item in entries_data:
                if not isinstance(item, dict):
                    raise KeyError("Leaderboard entry must be an object")
                entry = cast(dict[str, object], item)
                initials = entry.get("initials")
                score = entry.get("score")
                song_title = entry.get("song_title")
                timestamp = entry.get("timestamp", "")
                if (
                    not isinstance(initials, str)
                    or not isinstance(score, int)
                    or not isinstance(song_title, str)
                ):
                    raise KeyError("Leaderboard entry has invalid field types")
                if not isinstance(timestamp, str):
                    raise KeyError("Leaderboard entry has invalid timestamp type")
                entries.append(
                    LeaderboardEntry(
                        initials=initials,
                        score=score,
                        song_title=song_title,
                        timestamp=timestamp,
                    )
                )
            self._entries = entries
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Leaderboard file corrupted, resetting: %s", exc)
            self._entries = []

    def clear(self) -> None:
        self._entries = []
        if self._filepath.exists():
            self._filepath.unlink()
