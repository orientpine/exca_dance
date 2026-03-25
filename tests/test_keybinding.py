from __future__ import annotations

from pathlib import Path

from exca_dance.core.constants import DEFAULT_KEY_BINDINGS
from exca_dance.core.keybinding import KeyBindingManager
from exca_dance.core.models import JointName


def test_default_bindings_exist_for_all_joints(tmp_path: Path) -> None:
    manager = KeyBindingManager(filepath=str(tmp_path / "settings.json"))

    for joint in JointName:
        assert manager.get_binding(joint) == DEFAULT_KEY_BINDINGS[joint]


def test_get_joint_for_positive_key_returns_joint_and_direction(tmp_path: Path) -> None:
    manager = KeyBindingManager(filepath=str(tmp_path / "settings.json"))
    joint = JointName.SWING
    positive_key, _ = manager.get_binding(joint)

    assert manager.get_joint_for_key(positive_key) == (joint, 1)


def test_get_joint_for_negative_key_returns_joint_and_direction(tmp_path: Path) -> None:
    manager = KeyBindingManager(filepath=str(tmp_path / "settings.json"))
    joint = JointName.BOOM
    _, negative_key = manager.get_binding(joint)

    assert manager.get_joint_for_key(negative_key) == (joint, -1)


def test_get_joint_for_unknown_key_returns_none(tmp_path: Path) -> None:
    manager = KeyBindingManager(filepath=str(tmp_path / "settings.json"))

    assert manager.get_joint_for_key(9999) is None


def test_set_binding_roundtrip_updates_binding(tmp_path: Path) -> None:
    manager = KeyBindingManager(filepath=str(tmp_path / "settings.json"))

    manager.set_binding(JointName.ARM, 120, 121)

    assert manager.get_binding(JointName.ARM) == (120, 121)
    assert manager.get_joint_for_key(120) == (JointName.ARM, 1)
    assert manager.get_joint_for_key(121) == (JointName.ARM, -1)


def test_save_and_reload_persists_custom_binding(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    manager = KeyBindingManager(filepath=str(settings_file))
    manager.set_binding(JointName.BUCKET, 120, 121)
    manager.save()

    reloaded = KeyBindingManager(filepath=str(settings_file))

    assert reloaded.get_binding(JointName.BUCKET) == (120, 121)


def test_reset_to_defaults_restores_original_bindings(tmp_path: Path) -> None:
    manager = KeyBindingManager(filepath=str(tmp_path / "settings.json"))
    original = dict(DEFAULT_KEY_BINDINGS)

    manager.set_binding(JointName.SWING, 1, 2)
    manager.reset_to_defaults()

    for joint, binding in original.items():
        assert manager.get_binding(joint) == binding
