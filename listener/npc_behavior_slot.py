"""NPC definition behavior slot — DefaultBehavior has no npc_behavior_script."""

from __future__ import annotations


def verse_behavior_class(class_name: str | None) -> bool:
    return "VerseBehavior" in (class_name or "")


def must_replace_behavior_modifier(class_name: str | None) -> bool:
    """True when the slot is empty or stock DefaultBehavior (cannot hold a Verse CDO)."""
    return not verse_behavior_class(class_name)


def behavior_slot_info(class_name: str | None, script_path: str | None = None) -> dict:
    name = class_name or ""
    if not name:
        return {"class": None, "kind": "none", "npc_behavior_script": None}
    if verse_behavior_class(name):
        return {"class": name, "kind": "verse", "npc_behavior_script": script_path}
    kind = "default" if "DefaultBehavior" in name else "other"
    return {"class": name, "kind": kind, "npc_behavior_script": None}
