from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import cast

from exca_dance.core.constants import DEFAULT_KEY_BINDINGS
from exca_dance.core.models import JointName

logger = logging.getLogger(__name__)


class KeyBindingManager:
    def __init__(self, filepath: str = "data/settings.json"):
        self._filepath: Path = Path(filepath)
        self._bindings: dict[JointName, tuple[int, int]] = dict(DEFAULT_KEY_BINDINGS)
        self.load()

    def get_binding(self, joint: JointName) -> tuple[int, int]:
        return self._bindings[joint]

    def set_binding(self, joint: JointName, positive_key: int, negative_key: int) -> None:
        for j, (pk, nk) in self._bindings.items():
            if j == joint:
                continue
            if positive_key in (pk, nk) or negative_key in (pk, nk):
                logger.warning("Key conflict detected for joint %s", joint)
        self._bindings[joint] = (positive_key, negative_key)

    def get_joint_for_key(self, key: int) -> tuple[JointName, int] | None:
        for joint, (pk, nk) in self._bindings.items():
            if key == pk:
                return (joint, 1)
            if key == nk:
                return (joint, -1)
        return None

    def save(self) -> None:
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "key_bindings": {
                j.value: {"positive": pk, "negative": nk} for j, (pk, nk) in self._bindings.items()
            }
        }
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        if not self._filepath.exists():
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = cast(dict[str, object], json.load(f))
            bindings_data = data.get("key_bindings")
            if not isinstance(bindings_data, dict):
                return
            for jname_str, keys in bindings_data.items():
                try:
                    if not isinstance(jname_str, str) or not isinstance(keys, dict):
                        raise KeyError
                    keys_data = cast(dict[str, object], keys)
                    positive = keys_data.get("positive")
                    negative = keys_data.get("negative")
                    if positive is None or negative is None:
                        raise KeyError
                    positive_key = int(str(positive))
                    negative_key = int(str(negative))
                    jname = JointName(jname_str)
                    self._bindings[jname] = (positive_key, negative_key)
                except (TypeError, ValueError, KeyError):
                    pass
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Settings file unreadable, using defaults: %s", exc)

    def reset_to_defaults(self) -> None:
        self._bindings = dict(DEFAULT_KEY_BINDINGS)
