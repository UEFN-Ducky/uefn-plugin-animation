"""Animated Mesh device helpers — the publishable way to play an animation at runtime.

A Level Sequence needs a Cinematic Sequence device and a Verse
``PlaySkeletalAnimation`` needs an experimental (unpublishable) flag. The plain
UEFN answer for "this mesh plays this animation in game" is the **Animated Mesh
device**: place it, point it at a SkeletalMesh + AnimSequence, set Loop and Play
Rate, then drive it with Direct Event Binding (Play / Pause / Play Reverse).

``animated_mesh_capabilities`` finds the device asset to place;
``configure_animated_mesh`` fills its fields on a placed actor. Placement itself
is the existing ``spawn_actor`` tool — no new spawn path here.

The device's exact property names differ per Fortnite release, so the setter
tries the known aliases and, on a miss, RETURNS the actor's real option keys
instead of guessing wrong.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import unreal

from listener import lookup
from listener.dispatch import register
from listener.save_coalesce import request_level_save

# Where Epic ships the device. Devices/ first (small), whole Creative tree as fallback.
_DEVICE_PATHS = ("/Game/Creative/Devices", "/Game/Creative")
_DEVICE_MATCH = ("animatedmesh", "animated_mesh")

# field -> property-name aliases across Fortnite releases (first hit wins).
_FIELD_ALIASES: Dict[str, tuple] = {
    "skeletal_mesh": ("SkeletalMesh", "AnimatedMesh", "SkeletalMeshAsset", "Mesh"),
    "animation": ("Animation", "AnimationToPlay", "AnimationSequence", "AnimSequence", "AnimationAsset"),
    "loop": ("Loop", "Looping", "LoopAnimation", "bLoop"),
    "play_rate": ("PlayRate", "AnimationPlayRate", "PlaybackSpeed", "PlaybackRate"),
}


def _is_animated_mesh_class(name: str) -> bool:
    compact = name.lower().replace(" ", "").replace("_", "")
    return "animatedmesh" in compact


def _search_device_assets() -> List[dict]:
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    for path in _DEVICE_PATHS:
        try:
            found = registry.get_assets(
                unreal.ARFilter(package_paths=[path], recursive_paths=True)
            )
        except Exception:
            continue
        rows = []
        for data in found or []:
            try:
                name = str(data.asset_name)
            except Exception:
                continue
            low = name.lower()
            if not any(m in low.replace("_", "") or m in low for m in _DEVICE_MATCH):
                continue
            try:
                rows.append({"name": name, "path": str(data.package_name)})
            except Exception:
                continue
        if rows:
            return rows[:20]
    return []


def animated_mesh_capabilities() -> dict:
    """Find the Animated Mesh device asset to place, plus any already in the level."""
    assets = _search_device_assets()
    placed = []
    try:
        for actor in lookup.actor_list():
            if _is_animated_mesh_class(actor.get_class().get_name()):
                placed.append({"label": actor.get_actor_label(), "class": actor.get_class().get_name()})
    except Exception:
        pass
    return {
        "ok": True,
        "available": bool(assets or placed),
        "device_assets": assets,
        "placed": placed,
        "notes": [
            "Place with spawn_actor(asset_path='<device path>_C'), then set_actor_label + set_actor_folder.",
            "Fill fields with configure_animated_mesh (skeletal mesh, animation, loop, play rate).",
            "Runtime control is Direct Event Binding: Play Animation / Pause Animation / Play Reverse Animation.",
            "The animation must belong to the SAME skeleton as the mesh — retarget first if it does not.",
        ]
        + ([] if assets else ["Device asset not found by search — browse Content Browser > Fortnite > Devices > Animated Mesh."]),
    }


def _resolve_field(actor: Any, field: str):
    """(property_key, current_value) for the first alias this build exposes."""
    for key in _FIELD_ALIASES[field]:
        try:
            return key, actor.get_editor_property(key)
        except Exception:
            continue
    return None, None


def _coerce(field: str, value: Any):
    if field in ("skeletal_mesh", "animation"):
        asset = unreal.EditorAssetLibrary.load_asset(str(value))
        if asset is None:
            raise ValueError(f"Asset not found: {value}")
        return asset
    if field == "loop":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes")
    return float(value)


def configure_animated_mesh(
    actor_path: str,
    skeletal_mesh_path: str = "",
    anim_path: str = "",
    loop: Optional[bool] = None,
    play_rate: Optional[float] = None,
    save_level: bool = False,
) -> dict:
    """Set mesh / animation / loop / play rate on a placed Animated Mesh device.

    ``actor_path`` is the Outliner label of the placed device. Asset paths are
    loaded and assigned as object references (plain set_device_settings only
    coerces primitives, so it cannot do this). Omitted arguments are left alone.
    """
    actor = lookup.require_actor(actor_path)
    requested: Dict[str, Any] = {}
    if (skeletal_mesh_path or "").strip():
        requested["skeletal_mesh"] = skeletal_mesh_path.strip()
    if (anim_path or "").strip():
        requested["animation"] = anim_path.strip()
    if loop is not None:
        requested["loop"] = loop
    if play_rate is not None:
        requested["play_rate"] = play_rate
    if not requested:
        return {"ok": False, "error": "nothing to set — pass skeletal_mesh_path, anim_path, loop, or play_rate"}

    results: Dict[str, dict] = {}
    with unreal.ScopedEditorTransaction("Configure Animated Mesh"):
        for field, raw in requested.items():
            key, before = _resolve_field(actor, field)
            if key is None:
                results[field] = {"ok": False, "error": f"no property found (tried {list(_FIELD_ALIASES[field])})"}
                continue
            try:
                actor.set_editor_property(key, _coerce(field, raw))
                actor.modify()
                results[field] = {"ok": True, "property": key, "before": str(before), "set": str(raw)}
            except Exception as e:
                results[field] = {"ok": False, "property": key, "error": str(e)}

    lookup.invalidate()
    if save_level:
        request_level_save()

    out: dict = {
        "ok": all(r.get("ok") for r in results.values()),
        "label": actor.get_actor_label(),
        "class": actor.get_class().get_name(),
        "results": results,
    }
    if not out["ok"]:
        # Self-describing miss: hand back the device's real option keys to retry with.
        try:
            from listener.device_editor import get_device_settings

            settings = get_device_settings(actor_path)
            out["device_option_keys"] = sorted(settings.get("settings", {}).keys())
        except Exception as e:
            out["device_option_keys_error"] = str(e)
        out["hint"] = "Set unmatched fields with set_creative_device_fields using a key from device_option_keys."
    return out


register("animated_mesh_capabilities")(animated_mesh_capabilities)
register("configure_animated_mesh")(configure_animated_mesh)

try:  # older hosts have no plugin heavy-command opt-in
    from listener.tick import register_heavy

    register_heavy("configure_animated_mesh")
except Exception:
    pass
