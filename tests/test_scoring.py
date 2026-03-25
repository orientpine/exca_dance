from __future__ import annotations

from exca_dance.core.models import Judgment
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


def test_combo_increments_on_hits_and_resets_on_miss() -> None:
    engine = ScoringEngine()
    engine.judge({}, 20.0)
    engine.judge({}, 20.0)
    assert engine.get_max_combo() == 2

    engine.judge({}, 121.0)
    assert engine.get_combo_multiplier() == 1


def test_combo_multiplier_progression_at_10_and_25_hits() -> None:
    engine = ScoringEngine()
    for _ in range(10):
        engine.judge({}, 20.0)
    assert engine.get_combo_multiplier() == 2

    for _ in range(15):
        engine.judge({}, 20.0)
    assert engine.get_combo_multiplier() == 3


def test_grade_s_at_95_percent_or_higher() -> None:
    engine = ScoringEngine()
    assert engine.get_grade(95, 100) == "S"
    assert engine.get_grade(190, 200) == "S"


def test_max_possible_score_for_100_events() -> None:
    engine = ScoringEngine()
    assert engine.get_max_possible_score(100) == 120000
