from __future__ import annotations

from typing import Callable, cast
from unittest.mock import MagicMock

from exca_dance.rendering.excavator_model import ExcavatorModel
from exca_dance.rendering.visual_cues import VisualCueRenderer


import numpy as np


def _make_visual_cue_renderer() -> tuple[VisualCueRenderer, MagicMock, MagicMock]:
    renderer = MagicMock()
    # Mock buffer needs a valid .size for pre-allocated VBO size checks
    mock_buffer = MagicMock()
    mock_buffer.size = 999999
    renderer.ctx.buffer.return_value = mock_buffer
    renderer.width = 1920
    renderer.height = 1080

    fk = MagicMock()
    ghost_model = MagicMock()
    ghost_model._vbo = None
    ghost_model._vertex_count = 0
    ghost_model.get_transformed_vertices.return_value = np.empty((0, 9), dtype=np.float32)

    model_class = cast(type[ExcavatorModel], MagicMock(return_value=ghost_model))
    cues = VisualCueRenderer(renderer, model_class, fk)
    return cues, renderer, ghost_model


def test_render_timeline_no_crash_empty_events() -> None:
    cues, renderer, _ = _make_visual_cue_renderer()

    # Should not crash with no events — timeline uses batched VBOs now
    cues.render_timeline(renderer, None, 120000.0)


def test_rebuild_outline_cache_no_crash_empty_vbo() -> None:
    cues, _, _ = _make_visual_cue_renderer()
    rebuild = cast(Callable[[], None], getattr(cues, "_rebuild_outline_cache"))

    rebuild()

    assert getattr(cues, "_outline_vertex_count") == 0


def test_ghost_angles_independent_of_player_input() -> None:
    """Ghost model must NOT move when player changes non-target joints.

    Regression test: previously, ghost_angles started from current_angles,
    so joints not specified in the beat event tracked the player's movements.
    """
    from exca_dance.core.models import BeatEvent, JointName

    cues, _, ghost_model = _make_visual_cue_renderer()

    # Target event only specifies BOOM=45.0
    event = BeatEvent(time_ms=1000, target_angles={JointName.BOOM: 45.0})

    # Player has moved SWING to 90.0 and ARM to -30.0
    player_angles = {
        JointName.SWING: 90.0,
        JointName.BOOM: 10.0,
        JointName.ARM: -30.0,
        JointName.BUCKET: 50.0,
    }

    cues.update(
        current_time_ms=500.0,
        current_angles=player_angles,
        upcoming_events=[event],
    )

    # Ghost model must have been updated
    ghost_model.update.assert_called_once()
    actual_ghost_angles = ghost_model.update.call_args[0][0]

    # Ghost BOOM must be the target value
    assert actual_ghost_angles[JointName.BOOM] == 45.0
    # Ghost joints NOT in the target must be 0.0 (default), NOT the player's angles
    assert actual_ghost_angles[JointName.SWING] == 0.0, (
        f"Ghost SWING should be 0.0 (default), got {actual_ghost_angles[JointName.SWING]}"
    )
    assert actual_ghost_angles[JointName.ARM] == 0.0, (
        f"Ghost ARM should be 0.0 (default), got {actual_ghost_angles[JointName.ARM]}"
    )
    assert actual_ghost_angles[JointName.BUCKET] == 0.0, (
        f"Ghost BUCKET should be 0.0 (default), got {actual_ghost_angles[JointName.BUCKET]}"
    )


def test_ghost_unspecified_joints_use_default_not_player() -> None:
    """When only some joints are targeted, others must stay at default (0.0).

    Verifies: changing player angles between frames does not alter the ghost
    for joints not in the beat event's target_angles.
    """
    from exca_dance.core.models import BeatEvent, JointName

    cues, _, ghost_model = _make_visual_cue_renderer()

    event = BeatEvent(
        time_ms=2000,
        target_angles={JointName.BOOM: 30.0, JointName.ARM: -20.0},
    )

    # Frame 1: player at home position
    angles_frame1 = {j: 0.0 for j in JointName}
    cues.update(800.0, angles_frame1, [event])
    ghost_model.update.assert_called_once()
    ghost_angles_1 = ghost_model.update.call_args[0][0]

    # Frame 2: player moved SWING and BUCKET significantly
    ghost_model.reset_mock()
    # Force ghost update by resetting prev cache
    cues._prev_ghost_angles = None
    angles_frame2 = {
        JointName.SWING: 120.0,
        JointName.BOOM: 5.0,
        JointName.ARM: 15.0,
        JointName.BUCKET: 180.0,
    }
    cues.update(900.0, angles_frame2, [event])
    ghost_model.update.assert_called_once()
    ghost_angles_2 = ghost_model.update.call_args[0][0]

    # Ghost target joints must match event targets, not player
    assert ghost_angles_2[JointName.BOOM] == 30.0
    assert ghost_angles_2[JointName.ARM] == -20.0

    # Ghost non-target joints must be identical between frames
    # (both 0.0 — default) regardless of player movement
    assert ghost_angles_1[JointName.SWING] == ghost_angles_2[JointName.SWING] == 0.0
    assert ghost_angles_1[JointName.BUCKET] == ghost_angles_2[JointName.BUCKET] == 0.0


def test_ghost_does_not_update_when_target_angles_unchanged() -> None:
    """Ghost model should not rebuild when target angles haven't changed,
    even if player angles have changed.
    """
    from exca_dance.core.models import BeatEvent, JointName

    cues, _, ghost_model = _make_visual_cue_renderer()

    event = BeatEvent(time_ms=3000, target_angles={JointName.BOOM: 45.0})

    # Frame 1: initial update
    cues.update(1500.0, {j: 0.0 for j in JointName}, [event])
    assert ghost_model.update.call_count == 1

    # Frame 2: player moves, but target hasn't changed
    cues.update(
        1516.0,
        {JointName.SWING: 90.0, JointName.BOOM: 20.0, JointName.ARM: -10.0, JointName.BUCKET: 30.0},
        [event],
    )
    # Ghost should NOT have been updated again (angles unchanged)
    assert ghost_model.update.call_count == 1
