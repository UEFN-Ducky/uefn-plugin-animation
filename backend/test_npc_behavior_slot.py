"""DefaultBehavior has no npc_behavior_script — info must not fail, attach must replace."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SLOT = Path(__file__).resolve().parents[1] / "listener" / "npc_behavior_slot.py"


def _load():
    spec = importlib.util.spec_from_file_location("npc_behavior_slot", _SLOT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_default_behavior_is_readable_not_verse() -> None:
    slot = _load()
    info = slot.behavior_slot_info("CharacterModifier_DefaultBehavior_C")
    assert info["kind"] == "default"
    assert info["npc_behavior_script"] is None
    assert slot.must_replace_behavior_modifier(info["class"]) is True


def test_verse_behavior_keeps_script() -> None:
    slot = _load()
    info = slot.behavior_slot_info(
        "CharacterModifier_VerseBehavior_C", "/_Verse/…/guard_behavior"
    )
    assert info["kind"] == "verse"
    assert info["npc_behavior_script"] == "/_Verse/…/guard_behavior"
    assert slot.must_replace_behavior_modifier(info["class"]) is False


def test_empty_slot_needs_verse_modifier() -> None:
    slot = _load()
    assert slot.must_replace_behavior_modifier(None) is True
    assert slot.behavior_slot_info(None)["kind"] == "none"


if __name__ == "__main__":
    test_default_behavior_is_readable_not_verse()
    test_verse_behavior_keeps_script()
    test_empty_slot_needs_verse_modifier()
    print("ok")
