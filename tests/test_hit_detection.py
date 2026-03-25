from __future__ import annotations

from unittest.mock import MagicMock

from exca_dance.core.hit_detection import JudgmentDisplay
from exca_dance.core.models import Judgment


def test_flash_alpha_positive_after_perfect() -> None:
    disp = JudgmentDisplay()
    hit = MagicMock()
    hit.judgment = Judgment.PERFECT
    hit.score = 300

    disp.trigger(hit, combo=1)

    _color, alpha = disp.current_flash
    assert alpha > 0.0


def test_flash_color_red_after_miss() -> None:
    disp = JudgmentDisplay()
    hit = MagicMock()
    hit.judgment = Judgment.MISS
    hit.score = 0

    disp.trigger(hit, combo=0)

    color, _alpha = disp.current_flash
    assert color == (1.0, 0.1, 0.1)
