from __future__ import annotations

import inspect

from exca_dance.rendering.viewport_layout import GameViewportLayout


def test_render_gameplay_background_method_exists() -> None:
    assert hasattr(GameViewportLayout, "render_gameplay_background")


def test_render_gameplay_background_callable() -> None:
    sig = inspect.signature(GameViewportLayout.render_gameplay_background)
    params = list(sig.parameters.keys())
    assert "self" in params
    assert "beat_phase" in params
