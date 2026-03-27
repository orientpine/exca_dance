from __future__ import annotations

import json
import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)


class CameraSettings:
    # Default values computed from existing hardcoded camera:
    # _EYE_3D = [6.0, -8.0, 5.0], _TARGET_3D = [2.0, 0.0, 1.5]
    # Relative: dx=4, dy=-8, dz=3.5
    # Radius = sqrt(16+64+12.25) ≈ 9.605
    # Elevation = atan2(3.5, sqrt(16+64)) ≈ 21.4°
    # Azimuth = atan2(-8, 4) ≈ -63.4° (math convention)
    DEFAULT_AZIMUTH: float = -63.4
    DEFAULT_ELEVATION: float = 21.4
    DEFAULT_RADIUS: float = 9.605

    def __init__(self, filepath: str = "data/camera.json") -> None:
        self._filepath: Path = Path(filepath)
        self._azimuth: float = self.DEFAULT_AZIMUTH
        self._elevation: float = self.DEFAULT_ELEVATION
        self._radius: float = self.DEFAULT_RADIUS
        self.load()

    @property
    def azimuth(self) -> float:
        return self._azimuth

    @azimuth.setter
    def azimuth(self, v: float) -> None:
        self._azimuth = v

    @property
    def elevation(self) -> float:
        return self._elevation

    @elevation.setter
    def elevation(self, v: float) -> None:
        self._elevation = max(-89.0, min(89.0, v))  # clamp to avoid gimbal lock

    @property
    def radius(self) -> float:
        return self._radius

    def compute_eye(
        self,
        target: tuple[float, float, float] = (2.0, 0.0, 1.5),
    ) -> tuple[float, float, float]:
        """Compute eye position from azimuth/elevation/radius relative to target."""
        az = math.radians(self._azimuth)
        el = math.radians(self._elevation)
        x = target[0] + self._radius * math.cos(el) * math.cos(az)
        y = target[1] + self._radius * math.cos(el) * math.sin(az)
        z = target[2] + self._radius * math.sin(el)
        return (x, y, z)

    def save(self) -> None:
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "azimuth": self._azimuth,
            "elevation": self._elevation,
            "radius": self._radius,
        }
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        if not self._filepath.exists():
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._azimuth = float(data.get("azimuth", self.DEFAULT_AZIMUTH))
                self._elevation = max(
                    -89.0,
                    min(89.0, float(data.get("elevation", self.DEFAULT_ELEVATION))),
                )
                self._radius = float(data.get("radius", self.DEFAULT_RADIUS))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("Camera settings unreadable, using defaults: %s", exc)

    def reset_to_defaults(self) -> None:
        self._azimuth = self.DEFAULT_AZIMUTH
        self._elevation = self.DEFAULT_ELEVATION
        self._radius = self.DEFAULT_RADIUS
