from __future__ import annotations

import inspect
from typing import Any, cast

from exca_dance.rendering.renderer import GameRenderer


def test_bloom_enabled_defaults_false() -> None:
    init_source = inspect.getsource(GameRenderer.__init__)
    assert "self._bloom_enabled = False" in init_source


def test_bloom_enabled_toggle() -> None:
    prop = GameRenderer.__dict__.get("bloom_enabled")
    assert prop is not None
    assert isinstance(prop, property)
    assert prop.fset is not None

    renderer = object.__new__(GameRenderer)
    renderer._bloom_enabled = False
    renderer._scene_fbo = cast(Any, object())

    renderer.bloom_enabled = True
    assert renderer.bloom_enabled is True

    renderer.bloom_enabled = False
    assert renderer.bloom_enabled is False
