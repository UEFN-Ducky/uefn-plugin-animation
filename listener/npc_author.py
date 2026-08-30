"""NPC content authoring: AnimPresets, character Blueprints, NPCCharacterDefinitions.

Fortnite's NPC content objects were the last hand-authoring hole in the toolchain:
an agent could write the Verse behavior and place the spawner, but a human still
had to click through the Content Browser to build the definition it spawns. These
handlers close that hole.

  READ    npc_author_capabilities, get_npc_definition_info, list_npc_definitions
  CREATE  create_anim_preset, create_character_blueprint,
          create_npc_character_definition, create_physics_asset_for_mesh
  CHANGE  set_anim_preset_slots, set_npc_definition_behavior,
          set_npc_definition_look, set_npc_spawner_definition

Shape of a working custom-mesh definition (verified against a shipped island, not
inferred from docs):

    type                = <instanced CharacterType_Custom_C>
    skeletal_mesh       = SKM_<Thing>
    character_blueprint = BP_<Thing>_C      (SkeletalMeshActor + one mesh component)
    anim_preset         = AP_<Thing>_C      (AnimPreset_BasicLocomotion)
    animation_bp        = None              (locomotion comes from the preset)
    behavior            = <instanced CharacterModifier_VerseBehavior_C>
                            .npc_behavior_script -> CDO of the Verse behavior class
    modifiers           = [ <CosmeticSpawn>, <Health> ]

``CharacterModifier_CosmeticSpawn`` is the part that makes a custom mesh spawn as
itself instead of as a Fortnite outfit. Two fields decide it and both must be set:
``character_look = CHARACTER_BLUEPRINT`` and ``character_movement =
ANIMATION_PRESET``. Leave ``character_parts`` empty — a populated part list drags
the Fortnite cosmetic path back in.

The modifier and character-type classes are Blueprints that ship inside the AI
Spawner playset (``/CRD_AISpawner/SpawnDefinitions/...``), so they are resolved
through the asset registry rather than hardcoded: the playset path has moved
between Fortnite releases, and a wrong hardcoded path fails as a null modifier
that only shows up as a T-posing NPC at runtime.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import unreal

from listener.dispatch import register
from listener.project_paths import pin_project_folder

# Classes this whole surface depends on. Reported by npc_author_capabilities so a
# build that lacks one fails with a readable answer instead of an AttributeError.
_REQUIRED = (
    "NPCCharacterDefinition",
    "NPCCharacterDefinitionFactory",
    "BlueprintFactory",
    "AnimPreset_BasicLocomotion",
    "AnimPreset_SingleAnimationData",
    "SkeletalMeshActor",
    "CharacterLook",
    "NPCCharacterMovement",
    "PhysicsAssetFactory",
)

_CHARACTER_TYPE_CUSTOM = "CharacterType_Custom"
_MOD_COSMETIC_SPAWN = "CharacterModifier_CosmeticSpawn"
_MOD_HEALTH = "CharacterModifier_Health"
_MOD_VERSE_BEHAVIOR = "CharacterModifier_VerseBehavior"
_AI_COMPANION_PROXY = "BP_FortPawnComponent_AICompanionProxy"

# The character-type and modifier classes are Blueprints inside Fortnite's own
# playsets. Known paths first (verified live), then a registry search, so a
# Fortnite release that moves a folder degrades to slow-but-correct instead of
# failing as a null modifier — which surfaces only as a T-posing NPC at runtime.
_KNOWN_CLASS_PATHS = {
    _CHARACTER_TYPE_CUSTOM: "/NPCDefault/Types/CharacterType_Custom.CharacterType_Custom_C",
    _MOD_COSMETIC_SPAWN: (
        "/CRD_AISpawner/SpawnDefinitions/Modifiers/CharacterModifier_CosmeticSpawn"
        ".CharacterModifier_CosmeticSpawn_C"
    ),
    _MOD_HEALTH: (
        "/CRD_AISpawner/SpawnDefinitions/Modifiers/CharacterModifier_Health"
        ".CharacterModifier_Health_C"
    ),
    _MOD_VERSE_BEHAVIOR: (
        "/CRD_AISpawner/SpawnDefinitions/Modifiers/CharacterModifier_VerseBehavior"
        ".CharacterModifier_VerseBehavior_C"
    ),
    _AI_COMPANION_PROXY: (
        "/CRD_AISpawner/Components/BP_FortPawnComponent_AICompanionProxy"
        ".BP_FortPawnComponent_AICompanionProxy_C"
    ),
}

_PRESET_SLOTS = ("idle", "move_forward", "move_backward", "move_left", "move_right")

# name -> resolved generated-class object path, filled on first use.
_CLASS_PATH_CACHE: Dict[str, str] = {}


# --- helpers ----------------------------------------------------------------


def _asset_tools():
    return unreal.AssetToolsHelpers.get_asset_tools()


def _capabilities() -> Dict[str, bool]:
    return {name: hasattr(unreal, name) for name in _REQUIRED}


def _require_capabilities() -> None:
    caps = _capabilities()
    missing = [k for k, v in caps.items() if not v]
    if missing:
        raise ValueError(
            "This UEFN build does not expose: %s. Run npc_author_capabilities for the full report."
            % ", ".join(missing)
        )


def _load_asset(path: str):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise ValueError("Asset not found: %s" % path)
    return asset


def _load_optional(path: str):
    if not (path or "").strip():
        return None
    return _load_asset(path.strip())


def _save(asset: Any) -> None:
    unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)


def _path_of(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    getter = getattr(obj, "get_path_name", None)
    return str(getter()) if callable(getter) else str(obj)


def _project_mount() -> str:
    """Leading mount of the open island, e.g. ``/catland``."""
    folder = pin_project_folder("", default_leaf="AI").replace("\\", "/")
    parts = [p for p in folder.split("/") if p]
    if not parts:
        raise ValueError("Could not resolve the project content mount.")
    return "/" + parts[0]


def _generated_class(blueprint_path: str):
    """Generated ``_C`` class for a Blueprint asset path."""
    path = blueprint_path.strip()
    if path.endswith("_C"):
        obj = unreal.load_object(None, path)
        if obj is not None:
            return obj
    if "." in path:
        path = path.split(".")[0]
    name = path.rstrip("/").split("/")[-1]
    obj = unreal.load_object(None, "%s.%s_C" % (path, name))
    if obj is None:
        raise ValueError("No generated class for Blueprint: %s" % blueprint_path)
    return obj


def _try_load_object(path: str):
    """``load_object`` only — never Asset Registry walks (those freeze/crash UEFN)."""
    if not (path or "").strip():
        return None
    try:
        return unreal.load_object(None, path)
    except Exception:
        return None


def _find_playset_class(asset_name: str):
    """Resolve a Fortnite playset Blueprint's generated class by known path.

    Never ``get_assets`` over BlueprintGeneratedClass — an unscoped (or even
    /CRD_AISpawner-recursive) registry walk on the game thread freezes/crashes
    UEFN. Known paths first; if those miss, copy the class off a project
    NPCCharacterDefinition. Place a Character Spawner if both fail.
    """
    cached = _CLASS_PATH_CACHE.get(asset_name)
    if cached:
        obj = _try_load_object(cached)
        if obj is not None:
            return obj

    known = _KNOWN_CLASS_PATHS.get(asset_name)
    if known:
        obj = _try_load_object(known)
        if obj is not None:
            _CLASS_PATH_CACHE[asset_name] = known
            return obj

    harvested = _harvest_class_from_existing(asset_name)
    if harvested is not None:
        return harvested

    raise ValueError(
        "Could not resolve '%s'. It ships in Fortnite's NPC playsets "
        "(/NPCDefault, /CRD_AISpawner) — place one Character Spawner device to "
        "mount them, then retry." % asset_name
    )


def _project_package_paths() -> List[str]:
    try:
        return [_project_mount()]
    except Exception:
        return []


def _harvest_class_from_existing(asset_name: str):
    """Last resort: copy the class off a definition already in THIS island.

    Scoped to the project mount — never scan Fortnite/NPCDefault globally.
    """
    roots = _project_package_paths()
    if not roots:
        return None
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    try:
        rows = registry.get_assets(
            unreal.ARFilter(
                class_names=["NPCCharacterDefinition"],
                recursive_classes=True,
                package_paths=roots,
                recursive_paths=True,
            )
        )
    except Exception:
        return None
    for row in rows:
        try:
            definition = unreal.EditorAssetLibrary.load_asset(
                str(row.get_editor_property("package_name"))
            )
        except Exception:
            continue
        if definition is None:
            continue
        candidates = []
        for field in ("type", "behavior"):
            try:
                candidates.append(definition.get_editor_property(field))
            except Exception:
                continue
        try:
            candidates.extend(definition.get_editor_property("modifiers") or [])
        except Exception:
            pass
        for obj in candidates:
            if obj is None:
                continue
            cls = obj.get_class()
            if cls.get_name() in ("%s_C" % asset_name, asset_name):
                _CLASS_PATH_CACHE[asset_name] = _path_of(cls) or ""
                return cls
    return None


def _new_subobject(cls, outer):
    """Instanced subobject owned by ``outer`` — how the Details panel stores these."""
    obj = unreal.new_object(cls, outer=outer)
    if obj is None:
        raise ValueError("Failed to instance %s" % _path_of(cls))
    return obj


def _compile(blueprint: Any) -> None:
    lib = getattr(unreal, "BlueprintEditorLibrary", None)
    fn = getattr(lib, "compile_blueprint", None) if lib is not None else None
    if callable(fn):
        fn(blueprint)


def _mesh_component_of(blueprint_path: str):
    """The default SkeletalMeshComponent on a SkeletalMeshActor Blueprint's CDO."""
    cdo = unreal.get_default_object(_generated_class(blueprint_path))
    comp = cdo.get_editor_property("skeletal_mesh_component")
    if comp is None:
        raise ValueError("No skeletal_mesh_component on %s" % blueprint_path)
    return cdo, comp


def _verse_behavior_cdo(behavior: str):
    """Accept a Verse class name, class path, or CDO path -> the behavior CDO object.

    A Verse behavior is referenced by its class default object, e.g.
    ``/catland/_Verse.Default__AI-CatReacts-cat_npc_behavior``. Every definition
    using that behavior points at the same shared CDO.
    """
    ref = (behavior or "").strip()
    if not ref:
        raise ValueError("behavior is required (Verse class name or CDO path).")

    candidates: List[str] = []
    if "Default__" in ref:
        candidates.append(ref)
    elif "/" in ref:
        pkg, _, cls = ref.rpartition(".")
        if pkg and cls:
            candidates.append("%s.Default__%s" % (pkg, cls))
        candidates.append(ref)
    else:
        candidates.append("%s/_Verse.Default__%s" % (_project_mount(), ref))

    for path in candidates:
        obj = unreal.load_object(None, path)
        if obj is not None:
            return obj
    raise ValueError(
        "Verse behavior not found: %s. Build Verse Code in UEFN first — the class "
        "only exists after a successful build." % behavior
    )


def _slot_struct(anim_path: str, play_rate: float):
    slot = unreal.AnimPreset_SingleAnimationData()
    anim = _load_optional(anim_path)
    if anim is not None:
        slot.set_editor_property("animation", anim)
    slot.set_editor_property("play_rate", float(play_rate))
    return slot


def _skeleton_of(asset: Any):
    try:
        return asset.get_editor_property("skeleton")
    except Exception:
        return None


# --- READ -------------------------------------------------------------------


def npc_author_capabilities() -> dict:
    """Cheap probe: hasattr + known-path load_object. Never Asset Registry walks."""
    caps = _capabilities()
    out: dict = {"ok": True, "capabilities": caps, "available": all(caps.values())}
    resolved = {}
    for name in (_CHARACTER_TYPE_CUSTOM, _MOD_COSMETIC_SPAWN, _MOD_HEALTH, _MOD_VERSE_BEHAVIOR):
        path = _KNOWN_CLASS_PATHS.get(name) or ""
        obj = _try_load_object(path)
        resolved[name] = _path_of(obj) if obj is not None else (
            "MISSING: playset not mounted — place one Character Spawner, then retry"
        )
    out["playset_classes"] = resolved
    out["preset_slots"] = list(_PRESET_SLOTS)
    if not out["available"]:
        out["hint"] = "Missing classes cannot be worked around from Python — report them."
    return out


def list_npc_definitions(limit: int = 50) -> dict:
    """List NPCCharacterDefinition assets in THIS island (project mount only)."""
    roots = _project_package_paths()
    if not roots:
        return {"ok": True, "count": 0, "definitions": []}
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    rows = registry.get_assets(
        unreal.ARFilter(
            class_names=["NPCCharacterDefinition"],
            recursive_classes=True,
            package_paths=roots,
            recursive_paths=True,
        )
    )
    paths = [str(r.get_editor_property("package_name")) for r in rows]
    return {"ok": True, "count": len(paths), "definitions": paths[: max(1, int(limit))]}


def get_npc_definition_info(asset_path: str) -> dict:
    """Read a definition's mesh/blueprint/preset/behavior and its modifier stack."""
    definition = _load_asset(asset_path)
    out: dict = {"ok": True, "asset_path": asset_path}

    for field in ("skeletal_mesh", "character_blueprint", "anim_preset", "animation_bp", "ik_retargeter"):
        try:
            out[field] = _path_of(definition.get_editor_property(field))
        except Exception:
            out[field] = None

    try:
        char_type = definition.get_editor_property("type")
        out["type"] = char_type.get_class().get_name() if char_type is not None else None
    except Exception:
        out["type"] = None

    try:
        out["character_parts"] = len(definition.get_editor_property("character_parts") or [])
        out["override_materials"] = len(definition.get_editor_property("override_materials") or [])
    except Exception:
        pass

    behavior = None
    try:
        behavior = definition.get_editor_property("behavior")
    except Exception:
        pass
    if behavior is not None:
        script = behavior.get_editor_property("npc_behavior_script")
        out["behavior"] = {
            "class": behavior.get_class().get_name(),
            "npc_behavior_script": _path_of(script),
        }
    else:
        out["behavior"] = None

    mods = []
    try:
        for mod in definition.get_editor_property("modifiers") or []:
            if mod is None:
                continue
            row = {"class": mod.get_class().get_name()}
            for field in ("character_look", "character_movement", "support_anim_preset",
                          "support_character_movement", "character_blueprint", "anim_preset"):
                try:
                    value = mod.get_editor_property(field)
                except Exception:
                    continue
                row[field] = _path_of(value) if hasattr(value, "get_path_name") else str(value)
            mods.append(row)
    except Exception:
        pass
    out["modifiers"] = mods

    # The two settings that decide custom mesh vs Fortnite outfit.
    cosmetic = next((m for m in mods if "CosmeticSpawn" in m.get("class", "")), None)
    out["spawns_custom_mesh"] = bool(
        cosmetic
        and "CHARACTER_BLUEPRINT" in str(cosmetic.get("character_look"))
        and "ANIMATION_PRESET" in str(cosmetic.get("character_movement"))
    )
    return out


# --- CREATE / CHANGE --------------------------------------------------------


def create_anim_preset(
    name: str,
    idle: str,
    walk: str = "",
    dest_folder: str = "",
    play_rate: float = 1.0,
    move_forward: str = "",
    move_backward: str = "",
    move_left: str = "",
    move_right: str = "",
) -> dict:
    """Create an AnimPreset_BasicLocomotion Blueprint and fill its five slots.

    ``walk`` fills all four move slots; per-direction arguments override it. NPC
    locomotion comes entirely from this preset, so there is no AnimBP to author.
    """
    _require_capabilities()
    folder = pin_project_folder(dest_folder, default_leaf="AI")
    unreal.EditorAssetLibrary.make_directory(folder)

    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.AnimPreset_BasicLocomotion)
    blueprint = _asset_tools().create_asset(name, folder, unreal.Blueprint, factory)
    if blueprint is None:
        raise ValueError("Failed to create AnimPreset Blueprint %s in %s" % (name, folder))
    _compile(blueprint)

    asset_path = "%s/%s" % (folder, name)
    result = set_anim_preset_slots(
        asset_path,
        idle=idle,
        walk=walk,
        play_rate=play_rate,
        move_forward=move_forward,
        move_backward=move_backward,
        move_left=move_left,
        move_right=move_right,
    )
    _save(blueprint)
    result.update({"created": True, "asset_path": asset_path, "class_path": "%s.%s_C" % (asset_path, name)})
    return result


def set_anim_preset_slots(
    asset_path: str,
    idle: str = "",
    walk: str = "",
    play_rate: float = 1.0,
    move_forward: str = "",
    move_backward: str = "",
    move_left: str = "",
    move_right: str = "",
) -> dict:
    """Set idle / move_* slots on an AnimPreset Blueprint. Empty names are left alone."""
    _require_capabilities()
    blueprint = _load_asset(asset_path)
    cdo = unreal.get_default_object(_generated_class(asset_path))

    wanted = {
        "idle": idle,
        "move_forward": move_forward or walk,
        "move_backward": move_backward or walk,
        "move_left": move_left or walk,
        "move_right": move_right or walk,
    }

    # A preset whose clips use a different Skeleton than the mesh is the single
    # most common cause of "NPC slides without animating" — check, don't guess.
    skeletons = {}
    applied = {}
    for slot, anim_path in wanted.items():
        if not (anim_path or "").strip():
            continue
        anim = _load_asset(anim_path)
        skeletons[slot] = _path_of(_skeleton_of(anim))
        cdo.set_editor_property(slot, _slot_struct(anim_path, play_rate))
        applied[slot] = anim_path

    _compile(blueprint)
    _save(blueprint)
    distinct = sorted({s for s in skeletons.values() if s})
    out = {
        "ok": True,
        "asset_path": asset_path,
        "slots": applied,
        "skeletons": distinct,
    }
    if len(distinct) > 1:
        out["warning"] = (
            "Clips span more than one Skeleton (%s). The NPC will not animate unless "
            "every clip shares the mesh's Skeleton." % ", ".join(distinct)
        )
    return out


def create_character_blueprint(
    name: str,
    skeletal_mesh_path: str,
    dest_folder: str = "",
    material_path: str = "",
    scale: float = 1.0,
) -> dict:
    """Create a SkeletalMeshActor Blueprint holding one mesh, material override and scale.

    This is how one mesh becomes many visually distinct characters: same mesh,
    same skeleton, same clips, one material-instance override each.
    """
    _require_capabilities()
    folder = pin_project_folder(dest_folder, default_leaf="AI")
    unreal.EditorAssetLibrary.make_directory(folder)

    mesh = _load_asset(skeletal_mesh_path)

    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.SkeletalMeshActor)
    blueprint = _asset_tools().create_asset(name, folder, unreal.Blueprint, factory)
    if blueprint is None:
        raise ValueError("Failed to create Blueprint %s in %s" % (name, folder))
    _compile(blueprint)

    asset_path = "%s/%s" % (folder, name)
    _cdo, comp = _mesh_component_of(asset_path)
    comp.set_editor_property("skeletal_mesh", mesh)
    # Locomotion is driven by the NPC AnimPreset, so the component must not carry
    # its own AnimBP — one would override the preset.
    comp.set_editor_property("anim_class", None)

    material = _load_optional(material_path)
    if material is not None:
        comp.set_editor_property("override_materials", [material])

    if float(scale) != 1.0:
        s = float(scale)
        comp.set_editor_property("relative_scale3d", unreal.Vector(s, s, s))

    _compile(blueprint)
    _save(blueprint)

    physics = None
    try:
        physics = _path_of(mesh.get_editor_property("physics_asset"))
    except Exception:
        pass
    out = {
        "ok": True,
        "created": True,
        "asset_path": asset_path,
        "class_path": "%s.%s_C" % (asset_path, name),
        "skeletal_mesh": skeletal_mesh_path,
        "material": material_path or None,
        "scale": float(scale),
        "physics_asset": physics,
    }
    if not physics:
        out["warning"] = (
            "%s has no Physics Asset. The NPC will T-pose and slide — run "
            "create_physics_asset_for_mesh first." % skeletal_mesh_path
        )
    return out


def create_npc_character_definition(
    name: str,
    skeletal_mesh_path: str,
    character_blueprint_path: str,
    anim_preset_path: str,
    behavior: str = "",
    dest_folder: str = "",
    max_health: float = 0.0,
) -> dict:
    """Create a complete custom-mesh NPCCharacterDefinition, ready for a spawner.

    Builds the full stack: CharacterType_Custom, the CosmeticSpawn modifier set to
    CHARACTER_BLUEPRINT + ANIMATION_PRESET, a Health modifier, and (if ``behavior``
    is given) the VerseBehavior modifier pointed at a compiled Verse behavior class.
    """
    _require_capabilities()
    folder = pin_project_folder(dest_folder, default_leaf="AI")
    unreal.EditorAssetLibrary.make_directory(folder)

    mesh = _load_asset(skeletal_mesh_path)
    bp_class = _generated_class(character_blueprint_path)
    preset_class = _generated_class(anim_preset_path)

    factory = unreal.NPCCharacterDefinitionFactory()
    definition = _asset_tools().create_asset(name, folder, unreal.NPCCharacterDefinition, factory)
    if definition is None:
        raise ValueError("Failed to create NPCCharacterDefinition %s in %s" % (name, folder))

    definition.set_editor_property("type", _new_subobject(_find_playset_class(_CHARACTER_TYPE_CUSTOM), definition))
    definition.set_editor_property("skeletal_mesh", mesh)
    definition.set_editor_property("character_blueprint", bp_class)
    definition.set_editor_property("anim_preset", preset_class)
    definition.set_editor_property("animation_bp", None)
    definition.set_editor_property("ik_retargeter", None)
    # Fortnite cosmetic parts must stay empty or they re-enter the outfit path.
    definition.set_editor_property("character_parts", [])
    definition.set_editor_property("override_materials", [])

    cosmetic = _new_subobject(_find_playset_class(_MOD_COSMETIC_SPAWN), definition)
    cosmetic.set_editor_property("character_look", unreal.CharacterLook.CHARACTER_BLUEPRINT)
    cosmetic.set_editor_property("character_movement", unreal.NPCCharacterMovement.ANIMATION_PRESET)
    cosmetic.set_editor_property("support_anim_preset", True)
    cosmetic.set_editor_property("support_character_movement", True)
    cosmetic.set_editor_property("character_blueprint", bp_class)
    cosmetic.set_editor_property("anim_preset", preset_class)
    try:
        cosmetic.set_editor_property(
            "ai_companion_proxy_to_apply", _find_playset_class(_AI_COMPANION_PROXY)
        )
    except Exception:
        pass  # optional; absent in some playset versions

    modifiers = [cosmetic]
    health = _new_subobject(_find_playset_class(_MOD_HEALTH), definition)
    if float(max_health) > 0.0:
        for field in ("max_health", "health", "MaxHealth"):
            try:
                health.set_editor_property(field, float(max_health))
                break
            except Exception:
                continue
    modifiers.append(health)
    definition.set_editor_property("modifiers", modifiers)

    behavior_result = None
    if (behavior or "").strip():
        behavior_result = _attach_behavior(definition, behavior)

    _save(definition)
    return {
        "ok": True,
        "created": True,
        "asset_path": "%s/%s" % (folder, name),
        "skeletal_mesh": skeletal_mesh_path,
        "character_blueprint": _path_of(bp_class),
        "anim_preset": _path_of(preset_class),
        "modifiers": [m.get_class().get_name() for m in modifiers],
        "behavior": behavior_result,
        "spawns_custom_mesh": True,
    }


def _attach_behavior(definition: Any, behavior: str) -> dict:
    cdo = _verse_behavior_cdo(behavior)
    modifier = definition.get_editor_property("behavior")
    if modifier is None:
        modifier = _new_subobject(_find_playset_class(_MOD_VERSE_BEHAVIOR), definition)
        definition.set_editor_property("behavior", modifier)
    modifier.set_editor_property("npc_behavior_script", cdo)
    return {"npc_behavior_script": _path_of(cdo)}


def set_npc_definition_behavior(asset_path: str, behavior: str) -> dict:
    """Point a definition's Verse behavior at a compiled npc_behavior class.

    Verse classes only exist after a successful Verse build, so this is a separate
    step from creating the definition: create the assets, build Verse, then attach.
    """
    _require_capabilities()
    definition = _load_asset(asset_path)
    result = _attach_behavior(definition, behavior)
    _save(definition)
    return {"ok": True, "asset_path": asset_path, **result}


def set_npc_definition_look(
    asset_path: str,
    character_blueprint_path: str = "",
    anim_preset_path: str = "",
    skeletal_mesh_path: str = "",
) -> dict:
    """Retarget an existing definition's mesh / character BP / preset.

    The cheap way to make a species variant: duplicate a working definition, then
    point it at a different character Blueprint.
    """
    _require_capabilities()
    definition = _load_asset(asset_path)
    changed = {}

    if (skeletal_mesh_path or "").strip():
        definition.set_editor_property("skeletal_mesh", _load_asset(skeletal_mesh_path))
        changed["skeletal_mesh"] = skeletal_mesh_path

    bp_class = _generated_class(character_blueprint_path) if (character_blueprint_path or "").strip() else None
    preset_class = _generated_class(anim_preset_path) if (anim_preset_path or "").strip() else None

    if bp_class is not None:
        definition.set_editor_property("character_blueprint", bp_class)
        changed["character_blueprint"] = _path_of(bp_class)
    if preset_class is not None:
        definition.set_editor_property("anim_preset", preset_class)
        changed["anim_preset"] = _path_of(preset_class)

    # The CosmeticSpawn modifier mirrors both fields; a definition whose modifier
    # still points at the old Blueprint spawns the old look.
    for mod in definition.get_editor_property("modifiers") or []:
        if mod is None or "CosmeticSpawn" not in mod.get_class().get_name():
            continue
        if bp_class is not None:
            mod.set_editor_property("character_blueprint", bp_class)
        if preset_class is not None:
            mod.set_editor_property("anim_preset", preset_class)
        changed["cosmetic_modifier_mirrored"] = True

    _save(definition)
    return {"ok": True, "asset_path": asset_path, "changed": changed}


def create_physics_asset_for_mesh(skeletal_mesh_path: str, name: str = "", dest_folder: str = "") -> dict:
    """Create and assign a Physics Asset for a skeletal mesh, if it has none.

    A skeletal mesh without a Physics Asset spawns as a T-pose that slides along
    the ground, which reads as an animation bug rather than a missing asset.
    """
    _require_capabilities()
    mesh = _load_asset(skeletal_mesh_path)
    existing = None
    try:
        existing = mesh.get_editor_property("physics_asset")
    except Exception:
        pass
    if existing is not None:
        return {"ok": True, "created": False, "physics_asset": _path_of(existing),
                "note": "Mesh already has a Physics Asset."}

    base = skeletal_mesh_path.split(".")[0]
    folder = pin_project_folder(dest_folder, default_leaf="") or base.rsplit("/", 1)[0]
    asset_name = (name or "").strip() or "PHYS_%s" % base.rsplit("/", 1)[-1].replace("SKM_", "").replace("SK_", "")

    factory = unreal.PhysicsAssetFactory()
    for field in ("target_skeletal_mesh", "skeletal_mesh"):
        try:
            factory.set_editor_property(field, mesh)
            break
        except Exception:
            continue
    physics = _asset_tools().create_asset(asset_name, folder, unreal.PhysicsAsset, factory)
    if physics is None:
        raise ValueError("Failed to create Physics Asset %s in %s" % (asset_name, folder))

    mesh.set_editor_property("physics_asset", physics)
    _save(physics)
    _save(mesh)
    return {
        "ok": True,
        "created": True,
        "physics_asset": "%s/%s" % (folder, asset_name),
        "skeletal_mesh": skeletal_mesh_path,
    }


_SPAWNER_DEF_FIELDS = (
    "NPCCharacterDefinition",
    "npc_character_definition",
    "CharacterDefinition",
    "character_definition",
    "AICharacterDefinition",
    "Definition",
    "definition",
)


def _try_set_definition(obj: Any, definition: Any) -> Optional[str]:
    for field in _SPAWNER_DEF_FIELDS:
        try:
            obj.set_editor_property(field, definition)
            return field
        except Exception:
            continue
    return None


def set_npc_spawner_definition(actor_path: str, definition_path: str) -> dict:
    """Assign an NPCCharacterDefinition to a placed Character Spawner.

    Never leave this for a human. Place the spawner with Epic PlaceDevice, then
    call this with the Outliner label.
    """
    from listener.lookup import require_actor
    from listener.save_coalesce import request_level_save

    actor = require_actor(actor_path)
    definition = _load_asset(definition_path)
    field = _try_set_definition(actor, definition)
    if field is None:
        try:
            comps = actor.get_components_by_class(unreal.ActorComponent) or []
        except Exception:
            comps = []
        for comp in comps:
            field = _try_set_definition(comp, definition)
            if field is not None:
                break
    if field is None:
        raise ValueError(
            "No NPCCharacterDefinition slot on %s. After PlaceDevice, call "
            "this with the Outliner label — do not ask a human to assign it."
            % actor_path
        )
    actor.modify()
    request_level_save()
    return {
        "ok": True,
        "actor": actor_path,
        "definition": definition_path,
        "property": field,
    }


register("npc_author_capabilities")(npc_author_capabilities)
register("list_npc_definitions")(list_npc_definitions)
register("get_npc_definition_info")(get_npc_definition_info)
register("create_anim_preset")(create_anim_preset)
register("set_anim_preset_slots")(set_anim_preset_slots)
register("create_character_blueprint")(create_character_blueprint)
register("create_npc_character_definition")(create_npc_character_definition)
register("set_npc_definition_behavior")(set_npc_definition_behavior)
register("set_npc_definition_look")(set_npc_definition_look)
register("create_physics_asset_for_mesh")(create_physics_asset_for_mesh)
register("set_npc_spawner_definition")(set_npc_spawner_definition)

try:  # Blueprint compiles and physics-asset builds are slow enough to throttle.
    from listener.tick import register_heavy

    for _cmd in (
        "create_anim_preset",
        "create_character_blueprint",
        "create_npc_character_definition",
        "create_physics_asset_for_mesh",
    ):
        register_heavy(_cmd)
except Exception:
    pass
