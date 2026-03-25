from __future__ import annotations

from typing import cast

from exca_dance.core.constants import COMBO_THRESHOLDS, JUDGMENT_WINDOWS, SCORE_VALUES
from exca_dance.core.models import HitResult, JointName, Judgment


class ScoringEngine:
    def __init__(self) -> None:
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
        judgment = cast(Judgment, Judgment.MISS)
        tiers = cast(
            tuple[Judgment, Judgment, Judgment],
            (Judgment.PERFECT, Judgment.GREAT, Judgment.GOOD),
        )
        for tier in tiers:
            if timing_error_ms <= JUDGMENT_WINDOWS[tier]:
                judgment = tier
                break

        if angle_errors:
            avg_err = sum(angle_errors.values()) / len(angle_errors)
        else:
            avg_err = 0.0
        self.update_combo(judgment)
        combo_mult: int = self.get_combo_multiplier()

        angle_mult: float = max(0.1, 1.0 - (avg_err / 20.0))

        base: int = SCORE_VALUES[judgment]
        score = int(base * angle_mult * combo_mult)

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
        perfect_score = SCORE_VALUES[cast(Judgment, Judgment.PERFECT)]
        return perfect_score * 4 * num_events

    def get_grade(self, total: int, max_possible: int) -> str:
        if max_possible == 0:
            return "F"
        pct = total / max_possible * 100
        if pct >= 95:
            return "S"
        if pct >= 90:
            return "A"
        if pct >= 80:
            return "B"
        if pct >= 70:
            return "C"
        if pct >= 60:
            return "D"
        return "F"

    def get_judgment_counts(self) -> dict[Judgment, int]:
        return dict(self._judgments)
