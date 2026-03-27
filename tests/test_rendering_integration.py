"""Integration tests for rendering subsystem wiring.

These tests verify that the public API contracts between rendering modules
are satisfied — specifically the methods that VisualCueRenderer expects
on ExcavatorModel.  Pure-mock unit tests cannot catch these because they
never instantiate the real class.

No GL context is needed — we only inspect the class definition, not call
the methods.
"""

from __future__ import annotations

import inspect


def test_excavator_model_has_get_transformed_vertices() -> None:
    """VisualCueRenderer._rebuild_outline_cache calls this method."""
    from exca_dance.rendering.excavator_model import ExcavatorModel

    assert hasattr(ExcavatorModel, "get_transformed_vertices"), (
        "ExcavatorModel must have get_transformed_vertices() — "
        "required by VisualCueRenderer._rebuild_outline_cache"
    )
    sig = inspect.signature(ExcavatorModel.get_transformed_vertices)
    # Only 'self' parameter — no args required
    params = [p for p in sig.parameters if p != "self"]
    assert params == [], f"Expected no params besides self, got {params}"


def test_excavator_model_has_render_glow() -> None:
    """VisualCueRenderer.render_ghost calls this for additive glow pass."""
    from exca_dance.rendering.excavator_model import ExcavatorModel

    assert hasattr(ExcavatorModel, "render_glow"), (
        "ExcavatorModel must have render_glow() — required by VisualCueRenderer.render_ghost"
    )
    sig = inspect.signature(ExcavatorModel.render_glow)
    params = list(sig.parameters.keys())
    assert "alpha" in params, "render_glow must accept 'alpha' parameter"


def test_excavator_model_has_render_3d() -> None:
    """Core render method used by viewport_layout and visual_cues."""
    from exca_dance.rendering.excavator_model import ExcavatorModel

    assert hasattr(ExcavatorModel, "render_3d")
    sig = inspect.signature(ExcavatorModel.render_3d)
    params = list(sig.parameters.keys())
    assert "mvp" in params, "render_3d must accept 'mvp' parameter"
    assert "alpha" in params, "render_3d must accept 'alpha' parameter"


def test_excavator_model_has_update() -> None:
    """GameLoop and VisualCueRenderer call update(joint_angles)."""
    from exca_dance.rendering.excavator_model import ExcavatorModel

    assert hasattr(ExcavatorModel, "update")
    sig = inspect.signature(ExcavatorModel.update)
    params = [p for p in sig.parameters if p != "self"]
    assert len(params) >= 1, "update must accept joint_angles parameter"


def test_visual_cues_renderer_importable() -> None:
    """Verify VisualCueRenderer can be imported alongside ExcavatorModel."""
    from exca_dance.rendering.excavator_model import ExcavatorModel
    from exca_dance.rendering.visual_cues import VisualCueRenderer

    # Both classes must be importable without error
    assert VisualCueRenderer is not None
    assert ExcavatorModel is not None


def test_renderer_prog_additive_has_alpha_mult_uniform_in_source() -> None:
    """visual_cues.render_outline sets prog_additive['alpha_mult'].

    Verify the shader source contains the uniform declaration so it
    won't fail at runtime.
    """
    import ast
    from pathlib import Path

    renderer_path = (
        Path(__file__).resolve().parent.parent / "src" / "exca_dance" / "rendering" / "renderer.py"
    )
    source = renderer_path.read_text()
    tree = ast.parse(source)

    # Find the string literal containing the additive fragment shader
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "alpha_mult" in node.value and "uniform" in node.value:
                found = True
                break

    assert found, (
        "prog_additive fragment shader must declare 'uniform float alpha_mult' — "
        "required by VisualCueRenderer.render_outline"
    )
