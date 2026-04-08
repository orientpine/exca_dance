from __future__ import annotations

import json
import logging
from pathlib import Path

from exca_dance.core.constants import JOINT_LIMITS
from exca_dance.core.models import JointName

logger = logging.getLogger(__name__)


class JointLimitsConfig:
    """Runtime source of truth for joint limits — supersedes constants.JOINT_LIMITS.

    Edits here affect BOTH virtual and real mode (clamping + safety gate).
    """

    DEFAULT_FILEPATH: str = "data/joint_limits.json"

    def __init__(self, filepath: str = DEFAULT_FILEPATH) -> None:
        self._filepath: Path = Path(filepath)
        self._limits: dict[JointName, tuple[float, float]] = {
            joint: (lo, hi) for joint, (lo, hi) in JOINT_LIMITS.items()
        }
        self.load()

    def get(self, joint: JointName) -> tuple[float, float]:
        return self._limits[joint]

    def get_min(self, joint: JointName) -> float:
        return self._limits[joint][0]

    def get_max(self, joint: JointName) -> float:
        return self._limits[joint][1]

    def set_min(self, joint: JointName, value: float) -> None:
        lo = float(value)
        _, hi = self._limits[joint]
        if lo > hi:
            raise ValueError(
                f"min {lo} must not exceed max {hi} for {joint.value}"
            )
        self._limits[joint] = (lo, hi)

    def set_max(self, joint: JointName, value: float) -> None:
        hi = float(value)
        lo, _ = self._limits[joint]
        if hi < lo:
            raise ValueError(
                f"max {hi} must not be below min {lo} for {joint.value}"
            )
        self._limits[joint] = (lo, hi)

    def reset_to_defaults(self) -> None:
        self._limits = {joint: (lo, hi) for joint, (lo, hi) in JOINT_LIMITS.items()}

    def is_default(self) -> bool:
        for joint, (lo, hi) in JOINT_LIMITS.items():
            cur_lo, cur_hi = self._limits[joint]
            if abs(cur_lo - lo) > 1e-9 or abs(cur_hi - hi) > 1e-9:
                return False
        return True

    def remap_target(self, joint: JointName, target: float) -> float:
        """Linearly remap a beatmap target angle from factory range to the user's configured range.

        Beatmaps are authored against `constants.JOINT_LIMITS` (the factory range).
        When the operator narrows or shifts a joint's range, this method preserves
        the proportional position of each target inside the new range so the
        choreography remains playable on the configured machine. Targets outside
        the factory range are clamped to the nearest endpoint before remapping.
        """
        factory_lo, factory_hi = JOINT_LIMITS[joint]
        user_lo, user_hi = self._limits[joint]
        span = factory_hi - factory_lo
        if span <= 0:
            return user_lo
        t = (target - factory_lo) / span
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        return user_lo + t * (user_hi - user_lo)

    def as_dict(self) -> dict[JointName, tuple[float, float]]:
        return dict(self._limits)

    def save(self) -> None:
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {
            joint.value: {"min": round(lo, 4), "max": round(hi, 4)}
            for joint, (lo, hi) in self._limits.items()
        }
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        if not self._filepath.exists():
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Joint limits file unreadable, using defaults: %s", exc)
            return
        if not isinstance(data, dict):
            return
        for joint in JointName:
            entry = data.get(joint.value)
            if not isinstance(entry, dict):
                continue
            try:
                raw_lo = entry.get("min")
                raw_hi = entry.get("max")
                if raw_lo is None or raw_hi is None:
                    continue
                lo = float(raw_lo)
                hi = float(raw_hi)
            except (TypeError, ValueError):
                continue
            if lo > hi:
                logger.warning(
                    "Skipping invalid limits for %s: min=%s > max=%s",
                    joint.value, lo, hi,
                )
                continue
            self._limits[joint] = (lo, hi)
