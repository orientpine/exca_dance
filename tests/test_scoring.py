from __future__ import annotations

from typing import cast

from exca_dance.core.models import JointName, Judgment
from exca_dance.core.scoring import ScoringEngine


def test_perfect_judgment_at_20ms() -> None:
    engine = ScoringEngine()
    result = engine.judge({}, 20.0)
    assert result.judgment == Judgment.PERFECT


def test_perfect_judgment_at_35ms_boundary() -> None:
    engine = ScoringEngine()
    result = engine.judge({}, 35.0)
    assert result.judgment == Judgment.PERFECT


def test_great_judgment_at_36ms() -> None:
    engine = ScoringEngine()
    result = engine.judge({}, 36.0)
    assert result.judgment == Judgment.GREAT


def test_great_judgment_at_70ms_boundary() -> None:
    engine = ScoringEngine()
    result = engine.judge({}, 70.0)
    assert result.judgment == Judgment.GREAT


def test_good_judgment_at_71ms() -> None:
    engine = ScoringEngine()
    result = engine.judge({}, 71.0)
    assert result.judgment == Judgment.GOOD


def test_miss_judgment_at_121ms_score_zero() -> None:
    engine = ScoringEngine()
    result = engine.judge({}, 121.0)
    assert result.judgment == Judgment.MISS
    assert result.score == 0


def test_easy_difficulty_perfect_at_45ms() -> None:
    engine = ScoringEngine(difficulty="EASY")
    angle_errors: dict[JointName, float] = {cast(JointName, JointName.BOOM): 0.0}
    result = engine.judge(angle_errors, 45.0)
    assert result.judgment == Judgment.PERFECT


def test_hard_difficulty_great_at_30ms() -> None:
    engine = ScoringEngine(difficulty="HARD")
    angle_errors: dict[JointName, float] = {cast(JointName, JointName.BOOM): 0.0}
    result = engine.judge(angle_errors, 30.0)
    assert result.judgment == Judgment.GREAT


def test_angle_accuracy_scaling_uses_20_degree_floor() -> None:
    engine = ScoringEngine()
    boom = cast(JointName, JointName.BOOM)
    angle_errors: dict[JointName, float] = {boom: 0.0}

    angle_errors[boom] = 0.0
    assert engine.judge(angle_errors, 20.0).score == 300

    angle_errors[boom] = 10.0
    assert engine.judge(angle_errors, 20.0).score == 150

    angle_errors[boom] = 20.0
    assert engine.judge(angle_errors, 20.0).score == 30


def test_combo_increments_on_hits_and_resets_on_miss() -> None:
    engine = ScoringEngine()
    _ = engine.judge({}, 20.0)
    _ = engine.judge({}, 20.0)
    assert engine.get_max_combo() == 2

    _ = engine.judge({}, 121.0)
    assert engine.get_combo_multiplier() == 1


def test_combo_multiplier_progression_at_10_and_25_hits() -> None:
    engine = ScoringEngine()
    for _ in range(10):
        _ = engine.judge({}, 20.0)
    assert engine.get_combo_multiplier() == 2

    for _ in range(15):
        _ = engine.judge({}, 20.0)
    assert engine.get_combo_multiplier() == 3


def test_combo_multiplier_applies_on_current_hit() -> None:
    engine = ScoringEngine()

    for _ in range(9):
        assert engine.judge({}, 20.0).score == 300

    assert engine.judge({}, 20.0).score == 600


def test_grade_s_at_95_percent_or_higher() -> None:
    engine = ScoringEngine()
    assert engine.get_grade(95, 100) == "S"
    assert engine.get_grade(190, 200) == "S"


def test_max_possible_score_for_100_events() -> None:
    engine = ScoringEngine()
    assert engine.get_max_possible_score(100) == 120000


def test_angle_accuracy_downgrades_perfect_to_great() -> None:
    engine = ScoringEngine()
    angle_errors = {cast(JointName, JointName.BOOM): 8.0}
    result = engine.judge(angle_errors, 0.0)
    assert result.judgment == Judgment.GREAT


def test_angle_accuracy_downgrades_perfect_to_good() -> None:
    engine = ScoringEngine()
    angle_errors = {cast(JointName, JointName.BOOM): 15.0}
    result = engine.judge(angle_errors, 0.0)
    assert result.judgment == Judgment.GOOD


def test_angle_accuracy_causes_miss_at_high_error() -> None:
    engine = ScoringEngine()
    angle_errors = {cast(JointName, JointName.BOOM): 30.0}
    result = engine.judge(angle_errors, 0.0)
    assert result.judgment == Judgment.MISS
    assert result.score == 0
    assert result.score == 0


def test_small_angle_error_keeps_perfect() -> None:
    engine = ScoringEngine()
    angle_errors = {cast(JointName, JointName.BOOM): 3.0}
    result = engine.judge(angle_errors, 0.0)
    assert result.judgment == Judgment.PERFECT


def test_combined_timing_and_angle_picks_worse() -> None:
    engine = ScoringEngine()
    angle_errors = {cast(JointName, JointName.BOOM): 15.0}
    result = engine.judge(angle_errors, 50.0)
    assert result.judgment == Judgment.GOOD


def test_empty_angle_errors_keeps_timing_judgment() -> None:
    engine = ScoringEngine()
    result = engine.judge({}, 0.0)
    assert result.judgment == Judgment.PERFECT


def test_angle_thresholds_vary_by_difficulty() -> None:
    easy_engine = ScoringEngine(difficulty="EASY")
    hard_engine = ScoringEngine(difficulty="HARD")
    angle_errors = {cast(JointName, JointName.BOOM): 6.0}
    assert easy_engine.judge(angle_errors, 0.0).judgment == Judgment.PERFECT
    assert hard_engine.judge(angle_errors, 0.0).judgment == Judgment.GREAT
