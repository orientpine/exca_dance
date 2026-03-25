from __future__ import annotations

from typing import Callable, cast
from unittest.mock import MagicMock

from exca_dance.rendering.excavator_model import ExcavatorModel
from exca_dance.rendering.visual_cues import VisualCueRenderer


def _make_visual_cue_renderer() -> tuple[VisualCueRenderer, MagicMock, MagicMock]:
    renderer = MagicMock()
    renderer.width = 1920
    renderer.height = 1080

    fk = MagicMock()
    ghost_model = MagicMock()
    ghost_model._vbo = None
    ghost_model._vertex_count = 0

    model_class = cast(type[ExcavatorModel], MagicMock(return_value=ghost_model))
    cues = VisualCueRenderer(renderer, model_class, fk)
    return cues, renderer, ghost_model


def test_render_timeline_no_crash_empty_events() -> None:
    cues, renderer, _ = _make_visual_cue_renderer()
    draw_mock = MagicMock()
    setattr(cues, "_draw_highway_rect", draw_mock)

    cues.render_timeline(renderer, None, 120000.0)

    assert draw_mock.call_count == 3


def test_rebuild_ghost_glow_no_crash_empty_vbo() -> None:
    cues, _, _ = _make_visual_cue_renderer()
    rebuild = cast(Callable[[], None], getattr(cues, "_rebuild_ghost_glow"))

    rebuild()

    assert getattr(cues, "_ghost_glow_base") is None
