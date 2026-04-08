from __future__ import annotations

import json
from typing import Any, cast

import pytest

from exca_dance.core.constants import JOINT_LIMITS
from exca_dance.core.joint_limits import JointLimitsConfig
from exca_dance.core.models import JointName


def test_default_matches_constants_when_file_missing() -> None:
    cfg = JointLimitsConfig(filepath="nonexistent/path/joint_limits.json")
    for joint, expected in JOINT_LIMITS.items():
        assert cfg.get(joint) == expected


def test_arm_default_uses_120_upper() -> None:
    cfg = JointLimitsConfig(filepath="nonexistent/path/joint_limits.json")
    assert cfg.get_max(JointName.ARM) == 120.0


def test_set_max_persists_via_save_load_roundtrip(tmp_path: Any) -> None:
    path = str(tmp_path / "limits.json")
    cfg = JointLimitsConfig(filepath=path)
    cfg.set_max(JointName.BUCKET, 30.0)
    cfg.save()

    cfg2 = JointLimitsConfig(filepath=path)
    assert cfg2.get_max(JointName.BUCKET) == 30.0


def test_set_min_above_max_raises() -> None:
    cfg = JointLimitsConfig(filepath="nonexistent/path/joint_limits.json")
    with pytest.raises(ValueError, match="must not exceed"):
        cfg.set_min(JointName.ARM, 200.0)


def test_set_max_below_min_raises() -> None:
    cfg = JointLimitsConfig(filepath="nonexistent/path/joint_limits.json")
    with pytest.raises(ValueError, match="must not be below"):
        cfg.set_max(JointName.ARM, -50.0)


def test_reset_to_defaults_restores_constants(tmp_path: Any) -> None:
    path = str(tmp_path / "limits.json")
    cfg = JointLimitsConfig(filepath=path)
    cfg.set_max(JointName.ARM, 90.0)
    cfg.set_min(JointName.SWING, -10.0)

    cfg.reset_to_defaults()

    for joint, expected in JOINT_LIMITS.items():
        assert cfg.get(joint) == expected


def test_load_skips_invalid_entries_and_keeps_defaults(tmp_path: Any) -> None:
    path = tmp_path / "limits.json"
    path.write_text(json.dumps({
        "arm": {"min": 999, "max": 0},
        "boom": {"min": -45.0, "max": 10.0},
    }))
    cfg = JointLimitsConfig(filepath=str(path))
    assert cfg.get(JointName.ARM) == JOINT_LIMITS[JointName.ARM]
    assert cfg.get(JointName.BOOM) == (-45.0, 10.0)


def test_load_corrupt_json_falls_back_to_defaults(tmp_path: Any) -> None:
    path = tmp_path / "limits.json"
    path.write_text("not valid json {{{")
    cfg = JointLimitsConfig(filepath=str(path))
    for joint, expected in JOINT_LIMITS.items():
        assert cfg.get(joint) == expected


def test_save_then_modify_in_memory_does_not_affect_persisted(tmp_path: Any) -> None:
    path = str(tmp_path / "limits.json")
    cfg = JointLimitsConfig(filepath=path)
    cfg.set_max(JointName.BUCKET, 25.0)
    cfg.save()

    cfg.set_max(JointName.BUCKET, 60.0)

    persisted = JointLimitsConfig(filepath=path)
    assert persisted.get_max(JointName.BUCKET) == 25.0


def test_game_loop_uses_joint_limits_config_for_virtual_clamping() -> None:
    from unittest.mock import MagicMock
    from exca_dance.core.game_loop import GameLoop, GameState

    cfg = JointLimitsConfig(filepath="nonexistent/path.json")
    cfg.set_max(JointName.ARM, 50.0)

    loop = cast(Any, GameLoop)(
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        mode="virtual",
        joint_limits=cfg,
    )
    loop._state = GameState.PLAYING
    loop._joint_angles[JointName.ARM] = 49.0
    cast(Any, loop)._get_input_velocities = lambda: {
        JointName.SWING: 0.0,
        JointName.BOOM: 0.0,
        JointName.ARM: 1.0,
        JointName.BUCKET: 0.0,
    }
    loop._update_joints(dt=10.0)
    assert loop.joint_angles[JointName.ARM] == 50.0


def test_remap_target_identity_when_user_range_equals_factory() -> None:
    cfg = JointLimitsConfig(filepath="nonexistent/path.json")
    for joint in JointName:
        lo, hi = JOINT_LIMITS[joint]
        mid = (lo + hi) / 2.0
        for sample in (lo, mid, hi):
            assert abs(cfg.remap_target(joint, sample) - sample) < 1e-9


def test_remap_target_compresses_to_narrower_user_range() -> None:
    cfg = JointLimitsConfig(filepath="nonexistent/path.json")
    cfg.set_min(JointName.BUCKET, -100.0)
    cfg.set_max(JointName.BUCKET, 30.0)

    factory_lo, factory_hi = JOINT_LIMITS[JointName.BUCKET]
    assert abs(cfg.remap_target(JointName.BUCKET, factory_lo) - (-100.0)) < 1e-9
    assert abs(cfg.remap_target(JointName.BUCKET, factory_hi) - 30.0) < 1e-9

    factory_mid = (factory_lo + factory_hi) / 2.0
    user_mid = (-100.0 + 30.0) / 2.0
    assert abs(cfg.remap_target(JointName.BUCKET, factory_mid) - user_mid) < 1e-9


def test_remap_target_preserves_proportional_position() -> None:
    cfg = JointLimitsConfig(filepath="nonexistent/path.json")
    cfg.set_min(JointName.ARM, 30.0)
    cfg.set_max(JointName.ARM, 90.0)

    factory_lo, factory_hi = JOINT_LIMITS[JointName.ARM]
    quarter = factory_lo + 0.25 * (factory_hi - factory_lo)
    expected_quarter = 30.0 + 0.25 * (90.0 - 30.0)
    assert abs(cfg.remap_target(JointName.ARM, quarter) - expected_quarter) < 1e-9


def test_remap_target_clamps_targets_outside_factory_range() -> None:
    cfg = JointLimitsConfig(filepath="nonexistent/path.json")
    cfg.set_min(JointName.BUCKET, -100.0)
    cfg.set_max(JointName.BUCKET, 30.0)

    factory_lo, factory_hi = JOINT_LIMITS[JointName.BUCKET]
    way_too_low = factory_lo - 50.0
    way_too_high = factory_hi + 50.0
    assert cfg.remap_target(JointName.BUCKET, way_too_low) == -100.0
    assert cfg.remap_target(JointName.BUCKET, way_too_high) == 30.0


def test_remap_target_handles_expanded_user_range() -> None:
    cfg = JointLimitsConfig(filepath="nonexistent/path.json")
    cfg.set_min(JointName.SWING, -360.0)
    cfg.set_max(JointName.SWING, 360.0)

    factory_lo, factory_hi = JOINT_LIMITS[JointName.SWING]
    factory_mid = (factory_lo + factory_hi) / 2.0
    assert abs(cfg.remap_target(JointName.SWING, factory_mid) - 0.0) < 1e-9
    assert abs(cfg.remap_target(JointName.SWING, factory_lo) - (-360.0)) < 1e-9
    assert abs(cfg.remap_target(JointName.SWING, factory_hi) - 360.0) < 1e-9


def test_game_loop_remaps_beatmap_targets_at_start_song() -> None:
    from unittest.mock import MagicMock
    from exca_dance.core.game_loop import GameLoop
    from exca_dance.core.models import BeatEvent

    cfg = JointLimitsConfig(filepath="nonexistent/path.json")
    cfg.set_min(JointName.BUCKET, -100.0)
    cfg.set_max(JointName.BUCKET, 30.0)

    factory_lo, factory_hi = JOINT_LIMITS[JointName.BUCKET]
    original_events = [
        BeatEvent(
            time_ms=1000,
            target_angles={JointName.BUCKET: factory_hi},
            duration_ms=400,
        ),
        BeatEvent(
            time_ms=2000,
            target_angles={JointName.BUCKET: factory_lo},
            duration_ms=400,
        ),
    ]
    beatmap = MagicMock()
    beatmap.events = original_events
    beatmap.audio_file = "dummy.wav"

    loop = cast(Any, GameLoop)(
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        mode="virtual",
        joint_limits=cfg,
    )
    loop.start_song(beatmap)

    assert len(loop._pending_events) == 2
    assert abs(loop._pending_events[0].target_angles[JointName.BUCKET] - 30.0) < 1e-9
    assert abs(loop._pending_events[1].target_angles[JointName.BUCKET] - (-100.0)) < 1e-9
    assert original_events[0].target_angles[JointName.BUCKET] == factory_hi


def test_remap_does_not_affect_unconfigured_joints_in_event() -> None:
    from unittest.mock import MagicMock
    from exca_dance.core.game_loop import GameLoop
    from exca_dance.core.models import BeatEvent

    cfg = JointLimitsConfig(filepath="nonexistent/path.json")
    cfg.set_max(JointName.ARM, 60.0)

    factory_arm_lo, factory_arm_hi = JOINT_LIMITS[JointName.ARM]
    expected_arm = 60.0
    factory_arm_mid = (factory_arm_lo + factory_arm_hi) / 2.0
    expected_arm_mid = factory_arm_lo + 0.5 * (60.0 - factory_arm_lo)

    events = [
        BeatEvent(
            time_ms=500,
            target_angles={
                JointName.ARM: factory_arm_hi,
                JointName.SWING: 45.0,
            },
            duration_ms=400,
        ),
        BeatEvent(
            time_ms=1000,
            target_angles={JointName.ARM: factory_arm_mid},
            duration_ms=400,
        ),
    ]

    loop = cast(Any, GameLoop)(
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        mode="virtual",
        joint_limits=cfg,
    )
    remapped = loop._remap_events_to_user_limits(events)

    assert abs(remapped[0].target_angles[JointName.ARM] - expected_arm) < 1e-9
    assert remapped[0].target_angles[JointName.SWING] == 45.0
    assert abs(remapped[1].target_angles[JointName.ARM] - expected_arm_mid) < 1e-9
