from __future__ import annotations

from typing import cast

from exca_dance.core.constants import COMBO_THRESHOLDS, SCORE_VALUES
from exca_dance.core.models import HitResult, JointName, Judgment


def _window_set(perfect: float, great: float, good: float) -> dict[Judgment, float]:
    windows: dict[Judgment, float] = {}
    windows[cast(Judgment, Judgment.PERFECT)] = perfect
    windows[cast(Judgment, Judgment.GREAT)] = great
    windows[cast(Judgment, Judgment.GOOD)] = good
    return windows


_WINDOWS: dict[str, dict[Judgment, float]] = {
    "EASY": _window_set(50.0, 100.0, 170.0),
    "NORMAL": _window_set(35.0, 70.0, 120.0),
    "HARD": _window_set(25.0, 50.0, 90.0),
}

_JUDGMENT_RANK: dict[Judgment, int] = {
    cast(Judgment, Judgment.PERFECT): 0,
    cast(Judgment, Judgment.GREAT): 1,
    cast(Judgment, Judgment.GOOD): 2,
    cast(Judgment, Judgment.MISS): 3,
}


class ScoringEngine:
    _ANGLE_THRESHOLDS: dict[str, dict[Judgment, float]] = {
        "EASY": _window_set(8.0, 18.0, 35.0),
        "NORMAL": _window_set(5.0, 12.0, 25.0),
        "HARD": _window_set(3.0, 8.0, 18.0),
    }

    def __init__(self, difficulty: str = "NORMAL") -> None:
        normalized = difficulty.upper()
        self._difficulty: str = normalized if normalized in _WINDOWS else "NORMAL"
        self._windows: dict[Judgment, float] = _WINDOWS[self._difficulty]
        self._angle_thresholds: dict[Judgment, float] = self._ANGLE_THRESHOLDS[self._difficulty]
        self._total_score: int = 0
        self._combo: int = 0
        self._judgments: dict[Judgment, int] = {j: 0 for j in Judgment}
        self._max_combo: int = 0
        self.reset()

    def reset(self) -> None:
        self._total_score = 0
        self._combo = 0
        self._judgments = {j: 0 for j in Judgment}
        self._max_combo = 0

    def judge(self, angle_errors: dict[JointName, float], timing_error_ms: float) -> HitResult:
        timing_judgment = cast(Judgment, Judgment.MISS)
        tiers = cast(
            tuple[Judgment, Judgment, Judgment],
            (Judgment.PERFECT, Judgment.GREAT, Judgment.GOOD),
        )
        for tier in tiers:
            if timing_error_ms <= self._windows[tier]:
                timing_judgment = tier
                break

        if angle_errors:
            avg_err = sum(angle_errors.values()) / len(angle_errors)
        else:
            avg_err = 0.0

        if angle_errors:
            angle_judgment = cast(Judgment, Judgment.MISS)
            for tier in tiers:
                if avg_err <= self._angle_thresholds[tier]:
                    angle_judgment = tier
                    break
            judgment = (
                timing_judgment
                if _JUDGMENT_RANK[timing_judgment] >= _JUDGMENT_RANK[angle_judgment]
                else angle_judgment
            )
        else:
            judgment = timing_judgment

        self.update_combo(judgment)
        combo_mult: int = self.get_combo_multiplier()

        angle_mult: float = max(0.1, 1.0 - (avg_err / 20.0))

        base: int = SCORE_VALUES[timing_judgment]
        score = int(base * angle_mult * combo_mult)
        if judgment == Judgment.MISS:
            score = 0

        self._total_score += score
        self._judgments[judgment] += 1
        avg_err_val = sum(angle_errors.values()) / len(angle_errors) if angle_errors else 0.0
        return HitResult(
            judgment=judgment,
            score=score,
            angle_error=avg_err_val,
            timing_error_ms=timing_error_ms,
        )

    def update_combo(self, judgment: Judgment) -> None:
        if judgment == Judgment.MISS:
            self._combo = 0
        else:
            self._combo += 1
            self._max_combo = max(self._max_combo, self._combo)

    def get_combo_multiplier(self) -> int:
        mult = 1
        for threshold, m in sorted(COMBO_THRESHOLDS.items()):
            if self._combo >= threshold:
                mult = m
        return mult

    def get_total_score(self) -> int:
        return self._total_score

    def get_max_combo(self) -> int:
        return self._max_combo

    def get_max_possible_score(self, num_events: int) -> int:
        perfect_score: int = SCORE_VALUES[cast(Judgment, Judgment.PERFECT)]
        total = 0
        combo = 0
        for _ in range(num_events):
            combo += 1
            mult = 1
            for threshold, m in sorted(COMBO_THRESHOLDS.items()):
                if combo >= threshold:
                    mult = m
            total += perfect_score * mult
        return total

    def get_grade(self, total: int, max_possible: int) -> str:
        if max_possible == 0:
            return "C"
        pct = total / max_possible * 100
        if pct >= 95:
            return "S"
        if pct >= 85:
            return "A"
        if pct >= 70:
            return "B"
        return "C"

    def get_judgment_counts(self) -> dict[Judgment, int]:
        return dict(self._judgments)
