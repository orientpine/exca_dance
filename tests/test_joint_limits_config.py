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
