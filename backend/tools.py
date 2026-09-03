"""Animation MCP tools — retargeting, authoring, playback, and custom-mesh NPCs.

Every tool is a thin pass-through to a listener command shipped in this same
plugin (``listener/``), so the whole animation surface updates through the Store
without an app release.
"""

from __future__ import annotations

import json
from typing import Any, Optional

PLUGIN_ID = "animation"

_INTENT = (
    r"\b(anim|animation|animate|retarget|ik\s*rig|ik\s*retargeter|retarget\s*pose|skeleton|skeletal|"
    r"socket|bone|sequencer|level\s*sequence|anim\s*sequence|animated\s*mesh|control\s*rig|mixamo|"
    r"additive|player\s*anim|npc|npc\s*def|character\s*definition|anim\s*preset|animpreset|"
    r"character\s*blueprint|cosmetic\s*spawn|creature|animal|pet|quadruped|ecosystem)\b"
)

# Bake / retarget round-trips walk every frame of every clip — the default bridge
# timeout is sized for interactive edits, not for these.
_BAKE_TIMEOUT = 600.0

# Blueprint compiles and physics-asset generation run on the game thread.
_NPC_AUTHOR_TIMEOUT = 300.0


def _json(api: Any, command: str, params: dict[str, Any], *, pretty: bool = False, timeout: Optional[float] = None) -> str:
    if timeout is None:
        result = api.listener(command, params)
    else:
        try:
            result = api.listener(command, params, timeout=timeout)
        except TypeError:  # host predates the timeout argument
            result = api.listener(command, params)
    if pretty:
        return json.dumps(result, indent=2, ensure_ascii=False, default=str)
    return json.dumps(result, ensure_ascii=False, default=str)


def register_tools(api: Any) -> None:
    # --- retargeting: READ -------------------------------------------------

    @api.tool(intent=_INTENT)
    def ik_retarget_capabilities(pretty: bool = False) -> str:
        """Report whether this UEFN build exposes the IK Rig / retarget API (call first)."""
        return _json(api, "ik_retarget_capabilities", {}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def list_skeleton_bones(skeletal_mesh_path: str, pretty: bool = False) -> str:
        """List a skeletal mesh's bone names and guess its chain preset (biped/mannequin)."""
        return _json(api, "list_skeleton_bones", {"skeletal_mesh_path": skeletal_mesh_path}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def get_retarget_preset(name: str = "", pretty: bool = False) -> str:
        """Return a retarget chain preset's root + chains; empty name lists all presets."""
        return _json(api, "get_retarget_preset", {"name": name}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def get_ik_rig_info(ik_rig_path: str, pretty: bool = False) -> str:
        """Read an IK Rig's retarget root and chains."""
        return _json(api, "get_ik_rig_info", {"ik_rig_path": ik_rig_path}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def get_ik_retargeter_info(ik_retargeter_path: str, pretty: bool = False) -> str:
        """Read an IK Retargeter's source/target rigs."""
        return _json(api, "get_ik_retargeter_info", {"ik_retargeter_path": ik_retargeter_path}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def get_skeletal_mesh_info(asset_path: str, pretty: bool = False) -> str:
        """One-call skeletal mesh inspection: skeleton, bones, sockets, materials, LODs, bounds."""
        return _json(api, "get_skeletal_mesh_info", {"asset_path": asset_path}, pretty=pretty)

    # --- retargeting: CREATE / CHANGE --------------------------------------

    @api.tool(intent=_INTENT)
    def create_ik_rig_asset(skeletal_mesh_path: str, dest_folder: str = "", name: str = "", pretty: bool = False) -> str:
        """Create an IK Rig asset and bind its skeletal mesh (omit dest_folder to auto-pin)."""
        return _json(
            api,
            "create_ik_rig_asset",
            {"skeletal_mesh_path": skeletal_mesh_path, "dest_folder": dest_folder, "name": name},
            pretty=pretty,
        )

    @api.tool(intent=_INTENT)
    def create_ik_retargeter_asset(
        source_ik_rig_path: str,
        target_ik_rig_path: str,
        dest_folder: str = "",
        name: str = "",
        pretty: bool = False,
    ) -> str:
        """Create an IK Retargeter and bind source + target IK Rigs."""
        return _json(
            api,
            "create_ik_retargeter_asset",
            {
                "source_ik_rig_path": source_ik_rig_path,
                "target_ik_rig_path": target_ik_rig_path,
                "dest_folder": dest_folder,
                "name": name,
            },
            pretty=pretty,
        )

    @api.tool(intent=_INTENT)
    def set_retarget_root(ik_rig_path: str, bone: str, pretty: bool = False) -> str:
        """Set an IK Rig's retarget root (pelvis/hips bone)."""
        return _json(api, "set_retarget_root", {"ik_rig_path": ik_rig_path, "bone": bone}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def add_retarget_chains(
        ik_rig_path: str, chains: list[dict], replace_existing: bool = False, pretty: bool = False
    ) -> str:
        """Add or replace retarget chains on an IK Rig (never the editor Auto Characterize button)."""
        return _json(
            api,
            "add_retarget_chains",
            {"ik_rig_path": ik_rig_path, "chains": chains, "replace_existing": replace_existing},
            pretty=pretty,
        )

    @api.tool(intent=_INTENT)
    def remove_retarget_chains(ik_rig_path: str, names: list[str], pretty: bool = False) -> str:
        """Remove named retarget chains from an IK Rig."""
        return _json(api, "remove_retarget_chains", {"ik_rig_path": ik_rig_path, "names": names}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def auto_map_retarget_chains(ik_retargeter_path: str, pretty: bool = False) -> str:
        """Auto-map source→target chains on an IK Retargeter (pairs by identical name)."""
        return _json(api, "auto_map_retarget_chains", {"ik_retargeter_path": ik_retargeter_path}, pretty=pretty)

    # --- retarget pose (A-pose vs T-pose) ----------------------------------

    @api.tool(intent=_INTENT)
    def get_retarget_pose_info(ik_retargeter_path: str, source_or_target: str = "target", pretty: bool = False) -> str:
        """List retarget poses on one side of an IK Retargeter, plus the current pose's edits."""
        return _json(
            api,
            "get_retarget_pose_info",
            {"ik_retargeter_path": ik_retargeter_path, "source_or_target": source_or_target},
            pretty=pretty,
        )

    @api.tool(intent=_INTENT)
    def create_retarget_pose(
        ik_retargeter_path: str,
        name: str,
        source_or_target: str = "target",
        set_current: bool = True,
        pretty: bool = False,
    ) -> str:
        """Add a named retarget pose to one side of an IK Retargeter (and select it)."""
        return _json(
            api,
            "create_retarget_pose",
            {
                "ik_retargeter_path": ik_retargeter_path,
                "name": name,
                "source_or_target": source_or_target,
                "set_current": set_current,
            },
            pretty=pretty,
        )

    @api.tool(intent=_INTENT)
    def set_current_retarget_pose(
        ik_retargeter_path: str, name: str, source_or_target: str = "target", pretty: bool = False
    ) -> str:
        """Select which retarget pose one side of an IK Retargeter uses."""
        return _json(
            api,
            "set_current_retarget_pose",
            {"ik_retargeter_path": ik_retargeter_path, "name": name, "source_or_target": source_or_target},
            pretty=pretty,
        )

    @api.tool(intent=_INTENT)
    def set_retarget_pose_bone_rotation(
        ik_retargeter_path: str,
        bone: str,
        rotation: list[float],
        source_or_target: str = "target",
        pretty: bool = False,
    ) -> str:
        """Rotate one bone in the current retarget pose — the A-pose vs T-pose fix.

        rotation=[pitch,yaw,roll] degrees, offset from the rest pose (e.g. swing the
        upper arms down so a T-posed target matches an A-posed source). Fix the pose,
        then re-run retarget_animation — never copy bones between skeletons.
        """
        return _json(
            api,
            "set_retarget_pose_bone_rotation",
            {
                "ik_retargeter_path": ik_retargeter_path,
                "bone": bone,
                "rotation": rotation,
                "source_or_target": source_or_target,
            },
            pretty=pretty,
        )

    @api.tool(intent=_INTENT)
    def set_retarget_pose_root_offset(
        ik_retargeter_path: str, offset: list[float], source_or_target: str = "target", pretty: bool = False
    ) -> str:
        """Translate the root in the current retarget pose (height / ground alignment)."""
        return _json(
            api,
            "set_retarget_pose_root_offset",
            {"ik_retargeter_path": ik_retargeter_path, "offset": offset, "source_or_target": source_or_target},
            pretty=pretty,
        )

    # --- retargeting: BAKE -------------------------------------------------

    @api.tool(intent=_INTENT)
    def retarget_animation(
        ik_retargeter_path: str,
        source_mesh_path: str,
        target_mesh_path: str,
        anim_paths: list[str],
        prefix: str = "",
        suffix: str = "_Retargeted",
        pretty: bool = False,
    ) -> str:
        """Bake source AnimSequences onto the target skeleton via an IK Retargeter (batch)."""
        return _json(
            api,
            "retarget_animation",
            {
                "ik_retargeter_path": ik_retargeter_path,
                "source_mesh_path": source_mesh_path,
                "target_mesh_path": target_mesh_path,
                "anim_paths": anim_paths,
                "prefix": prefix,
                "suffix": suffix,
            },
            pretty=pretty,
            timeout=_BAKE_TIMEOUT,
        )

    @api.tool(intent=_INTENT)
    def retarget_animation_pipeline(
        source_mesh_path: str,
        target_mesh_path: str,
        anim_path: str,
        dest_folder: str = "",
        source_preset: str = "auto",
        target_preset: str = "auto",
        suffix: str = "_Retargeted",
        pretty: bool = False,
    ) -> str:
        """Chain IK rig + retargeter + bake for a single animation (plain case only)."""
        return _json(
            api,
            "retarget_animation_pipeline",
            {
                "source_mesh_path": source_mesh_path,
                "target_mesh_path": target_mesh_path,
                "anim_path": anim_path,
                "dest_folder": dest_folder,
                "source_preset": source_preset,
                "target_preset": target_preset,
                "suffix": suffix,
            },
            pretty=pretty,
            timeout=_BAKE_TIMEOUT,
        )

    # --- skeleton sockets ---------------------------------------------------

    @api.tool(intent=_INTENT)
    def list_skeleton_sockets(asset_path: str, pretty: bool = False) -> str:
        """List sockets on a Skeleton (pass a Skeleton or SkeletalMesh path)."""
        return _json(api, "list_skeleton_sockets", {"asset_path": asset_path}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def add_skeleton_socket(
        asset_path: str,
        bone_name: str,
        socket_name: str,
        location: Optional[list[float]] = None,
        rotation: Optional[list[float]] = None,
        update_existing: bool = False,
        pretty: bool = False,
    ) -> str:
        """Add a socket to a Skeleton under bone_name — NEVER build sockets via execute_python.

        asset_path may be the Skeleton or its SkeletalMesh. location=[x,y,z],
        rotation=[pitch,yaw,roll] relative to the bone. update_existing=true re-fits
        an existing socket. Attach afterwards via attach_actor(rule="snap_to_target").
        """
        return _json(
            api,
            "add_skeleton_socket",
            {
                "asset_path": asset_path,
                "bone_name": bone_name,
                "socket_name": socket_name,
                "location": location,
                "rotation": rotation,
                "update_existing": update_existing,
            },
            pretty=pretty,
        )

    @api.tool(intent=_INTENT)
    def remove_skeleton_socket(asset_path: str, socket_name: str, pretty: bool = False) -> str:
        """Remove a named socket from a Skeleton (pass a Skeleton or SkeletalMesh path)."""
        return _json(api, "remove_skeleton_socket", {"asset_path": asset_path, "socket_name": socket_name}, pretty=pretty)

    # --- authoring: Level Sequence / AnimSequence ---------------------------

    @api.tool(intent=_INTENT)
    def anim_author_capabilities(pretty: bool = False) -> str:
        """Report which authoring routes this UEFN build exposes: level sequence, anim sequence, bake."""
        return _json(api, "anim_author_capabilities", {}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def create_level_sequence(
        dest_folder: str = "", name: str = "", fps: int = 30, length_seconds: float = 5.0, pretty: bool = False
    ) -> str:
        """Create a LevelSequence asset; play it in game via a Cinematic Sequence device."""
        return _json(
            api,
            "create_level_sequence",
            {"dest_folder": dest_folder, "name": name, "fps": fps, "length_seconds": length_seconds},
            pretty=pretty,
        )

    @api.tool(intent=_INTENT)
    def add_sequence_binding(sequence_path: str, actor_path: str, pretty: bool = False) -> str:
        """Bind a placed level actor into a LevelSequence; returns the binding name."""
        return _json(
            api, "add_sequence_binding", {"sequence_path": sequence_path, "actor_path": actor_path}, pretty=pretty
        )

    @api.tool(intent=_INTENT)
    def add_transform_keys(sequence_path: str, binding_name: str, keys: list[dict], pretty: bool = False) -> str:
        """Key a sequence binding's transform. keys=[{time(s), location?[x,y,z], rotation?[roll,pitch,yaw]deg, scale?[x,y,z], interp?(auto|linear|constant)}]. Auto-extends the section range."""
        return _json(
            api,
            "add_transform_keys",
            {"sequence_path": sequence_path, "binding_name": binding_name, "keys": keys},
            pretty=pretty,
        )

    @api.tool(intent=_INTENT)
    def get_sequence_info(sequence_path: str, pretty: bool = False) -> str:
        """Read a LevelSequence's playback range, bindings, tracks, and key counts."""
        return _json(api, "get_sequence_info", {"sequence_path": sequence_path}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def create_anim_sequence(
        skeletal_mesh_path: str,
        dest_folder: str = "",
        name: str = "",
        length_seconds: float = 1.0,
        fps: int = 30,
        pretty: bool = False,
    ) -> str:
        """Create an empty AnimSequence bound to a skeletal mesh's skeleton (then set_anim_bone_keys)."""
        return _json(
            api,
            "create_anim_sequence",
            {
                "skeletal_mesh_path": skeletal_mesh_path,
                "dest_folder": dest_folder,
                "name": name,
                "length_seconds": length_seconds,
                "fps": fps,
            },
            pretty=pretty,
        )

    @api.tool(intent=_INTENT)
    def set_anim_bone_keys(anim_path: str, bone: str, keys: list[dict], pretty: bool = False) -> str:
        """Key one bone's BONE-LOCAL transform. keys=[{time(s), location?, rotation?[roll,pitch,yaw]deg, scale?}]; sparse keys are resampled to every frame (crash-safe arrays)."""
        return _json(api, "set_anim_bone_keys", {"anim_path": anim_path, "bone": bone, "keys": keys}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def get_anim_sequence_info(anim_path: str, pretty: bool = False) -> str:
        """Read an AnimSequence's length, fps, tracked bones, and additive settings."""
        return _json(api, "get_anim_sequence_info", {"anim_path": anim_path}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def set_anim_additive_type(
        anim_paths: list[str],
        additive_type: str = "local_space",
        ref_pose_type: str = "",
        ref_pose_anim: str = "",
        pretty: bool = False,
    ) -> str:
        """Set AdditiveAnimType on AnimSequence(s) — scripts the Property Matrix Local Space flip.

        Use ``local_space`` so a clip overlays Fortnite player locomotion when played
        via Verse GetPlayAnimationController. Without this flag the same Verse call
        fully overrides body animation. Falls back to the Property Matrix UI path if
        the enum is not exposed on this UEFN build.
        """
        return _json(
            api,
            "set_anim_additive_type",
            {
                "anim_paths": anim_paths,
                "additive_type": additive_type,
                "ref_pose_type": ref_pose_type,
                "ref_pose_anim": ref_pose_anim,
            },
            pretty=pretty,
            timeout=_BAKE_TIMEOUT,
        )

    @api.tool(intent=_INTENT)
    def bake_sequence_to_anim(
        sequence_path: str,
        actor_path: str,
        dest_folder: str = "",
        name: str = "",
        binding_name: str = "",
        pretty: bool = False,
    ) -> str:
        """Bake a bound skeletal actor's Level Sequence motion into an AnimSequence asset.

        The scripted form of the editor's right-click actor track → Bake Animation
        Sequence: Control Rig keys, anim tracks, and blends are sampled over the
        sequence's playback range (trim it first). The result plays on an Animated
        Mesh device, an AnimPreset, or a Verse @editable slot.
        """
        return _json(
            api,
            "bake_sequence_to_anim",
            {
                "sequence_path": sequence_path,
                "actor_path": actor_path,
                "dest_folder": dest_folder,
                "name": name,
                "binding_name": binding_name,
            },
            pretty=pretty,
            timeout=_BAKE_TIMEOUT,
        )

    # --- runtime playback: Animated Mesh device -----------------------------

    @api.tool(intent=_INTENT)
    def animated_mesh_capabilities(pretty: bool = False) -> str:
        """Find the Animated Mesh device asset to place, plus any already in the level."""
        return _json(api, "animated_mesh_capabilities", {}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def configure_animated_mesh(
        actor_path: str,
        skeletal_mesh_path: str = "",
        anim_path: str = "",
        loop: Optional[bool] = None,
        play_rate: Optional[float] = None,
        save_level: bool = False,
        pretty: bool = False,
    ) -> str:
        """Set mesh / animation / loop / play rate on a placed Animated Mesh device.

        actor_path is the Outliner label. The animation must belong to the SAME
        skeleton as the mesh — retarget first if it does not. Omitted arguments are
        left alone; trigger playback with Direct Event Binding (Play Animation).
        """
        return _json(
            api,
            "configure_animated_mesh",
            {
                "actor_path": actor_path,
                "skeletal_mesh_path": skeletal_mesh_path,
                "anim_path": anim_path,
                "loop": loop,
                "play_rate": play_rate,
                "save_level": save_level,
            },
            pretty=pretty,
        )

    # --- custom-mesh NPCs: definitions, presets, character Blueprints -------
    #
    # A custom creature needs four assets an agent previously could not create:
    # a Physics Asset, an AnimPreset, a character Blueprint, and the
    # NPCCharacterDefinition tying them together. Build order:
    #
    #   create_physics_asset_for_mesh -> create_anim_preset ->
    #   create_character_blueprint (one per variant) ->
    #   create_npc_character_definition -> Verse build ->
    #   set_npc_definition_behavior

    @api.tool(intent=_INTENT)
    def npc_author_capabilities(pretty: bool = False) -> str:
        """Cheap probe: hasattr + known-path load. Never scans Fortnite Blueprints."""
        return _json(api, "npc_author_capabilities", {}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def list_npc_definitions(limit: int = 50, pretty: bool = False) -> str:
        """List the project's NPCCharacterDefinition assets."""
        return _json(api, "list_npc_definitions", {"limit": limit}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def get_npc_definition_info(asset_path: str, pretty: bool = False) -> str:
        """Read a definition's mesh/blueprint/preset/behavior + modifiers, and whether it spawns a custom mesh."""
        return _json(api, "get_npc_definition_info", {"asset_path": asset_path}, pretty=pretty)

    @api.tool(intent=_INTENT)
    def create_physics_asset_for_mesh(
        skeletal_mesh_path: str,
        name: str = "",
        dest_folder: str = "",
        pretty: bool = False,
    ) -> str:
        """Create + assign a Physics Asset for a skeletal mesh that has none.

        A skeletal mesh with no Physics Asset spawns as a T-pose that slides along
        the ground — it reads as an animation bug but it is a missing asset.
        """
        return _json(
            api,
            "create_physics_asset_for_mesh",
            {"skeletal_mesh_path": skeletal_mesh_path, "name": name, "dest_folder": dest_folder},
            pretty=pretty,
            timeout=_NPC_AUTHOR_TIMEOUT,
        )

    @api.tool(intent=_INTENT)
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
        pretty: bool = False,
    ) -> str:
        """Create an AnimPreset_BasicLocomotion Blueprint; `walk` fills all four move slots.

        NPC locomotion comes entirely from this preset — do not author an AnimBP.
        Every clip must share the mesh's Skeleton or the NPC slides without animating.
        """
        return _json(
            api,
            "create_anim_preset",
            {
                "name": name,
                "idle": idle,
                "walk": walk,
                "dest_folder": dest_folder,
                "play_rate": play_rate,
                "move_forward": move_forward,
                "move_backward": move_backward,
                "move_left": move_left,
                "move_right": move_right,
            },
            pretty=pretty,
            timeout=_NPC_AUTHOR_TIMEOUT,
        )

    @api.tool(intent=_INTENT)
    def set_anim_preset_slots(
        asset_path: str,
        idle: str = "",
        walk: str = "",
        play_rate: float = 1.0,
        move_forward: str = "",
        move_backward: str = "",
        move_left: str = "",
        move_right: str = "",
        pretty: bool = False,
    ) -> str:
        """Set idle / move_* slots on an existing AnimPreset Blueprint (empty names untouched)."""
        return _json(
            api,
            "set_anim_preset_slots",
            {
                "asset_path": asset_path,
                "idle": idle,
                "walk": walk,
                "play_rate": play_rate,
                "move_forward": move_forward,
                "move_backward": move_backward,
                "move_left": move_left,
                "move_right": move_right,
            },
            pretty=pretty,
            timeout=_NPC_AUTHOR_TIMEOUT,
        )

    @api.tool(intent=_INTENT)
    def create_character_blueprint(
        name: str,
        skeletal_mesh_path: str,
        dest_folder: str = "",
        material_path: str = "",
        scale: float = 1.0,
        pretty: bool = False,
    ) -> str:
        """Create a SkeletalMeshActor Blueprint with one mesh + material override + scale.

        This is how one mesh becomes many visually distinct characters: same mesh,
        same skeleton, same clips, a different material instance per variant.
        """
        return _json(
            api,
            "create_character_blueprint",
            {
                "name": name,
                "skeletal_mesh_path": skeletal_mesh_path,
                "dest_folder": dest_folder,
                "material_path": material_path,
                "scale": scale,
            },
            pretty=pretty,
            timeout=_NPC_AUTHOR_TIMEOUT,
        )

    @api.tool(intent=_INTENT)
    def create_npc_character_definition(
        name: str,
        skeletal_mesh_path: str,
        character_blueprint_path: str,
        anim_preset_path: str,
        behavior: str = "",
        dest_folder: str = "",
        max_health: float = 0.0,
        pretty: bool = False,
    ) -> str:
        """Create a complete custom-mesh NPCCharacterDefinition ready to assign to a spawner.

        Builds CharacterType_Custom, the CosmeticSpawn modifier (CHARACTER_BLUEPRINT
        + ANIMATION_PRESET, which is what makes a custom mesh spawn instead of a
        Fortnite outfit), and Health. Attaches `behavior` when the Verse class is
        already compiled; otherwise build Verse then set_npc_definition_behavior.
        """
        return _json(
            api,
            "create_npc_character_definition",
            {
                "name": name,
                "skeletal_mesh_path": skeletal_mesh_path,
                "character_blueprint_path": character_blueprint_path,
                "anim_preset_path": anim_preset_path,
                "behavior": behavior,
                "dest_folder": dest_folder,
                "max_health": max_health,
            },
            pretty=pretty,
            timeout=_NPC_AUTHOR_TIMEOUT,
        )

    @api.tool(intent=_INTENT)
    def set_npc_definition_behavior(asset_path: str, behavior: str, pretty: bool = False) -> str:
        """Point a definition at a compiled Verse npc_behavior class (class name or CDO path).

        Verse classes only exist after a successful Verse build, so this is a
        separate step: create the assets, build Verse, then attach.
        """
        return _json(
            api,
            "set_npc_definition_behavior",
            {"asset_path": asset_path, "behavior": behavior},
            pretty=pretty,
        )

    @api.tool(intent=_INTENT)
    def set_npc_definition_look(
        asset_path: str,
        character_blueprint_path: str = "",
        anim_preset_path: str = "",
        skeletal_mesh_path: str = "",
        pretty: bool = False,
    ) -> str:
        """Retarget a definition's mesh / character BP / preset, mirroring the CosmeticSpawn modifier."""
        return _json(
            api,
            "set_npc_definition_look",
            {
                "asset_path": asset_path,
                "character_blueprint_path": character_blueprint_path,
                "anim_preset_path": anim_preset_path,
                "skeletal_mesh_path": skeletal_mesh_path,
            },
            pretty=pretty,
            timeout=_NPC_AUTHOR_TIMEOUT,
        )

    @api.tool(intent=_INTENT)
    def set_npc_spawner_definition(actor_path: str, definition_path: str, pretty: bool = False) -> str:
        """Assign an NPCCharacterDefinition to a placed Character Spawner (Outliner label). Never ask a human."""
        return _json(
            api,
            "set_npc_spawner_definition",
            {"actor_path": actor_path, "definition_path": definition_path},
            pretty=pretty,
        )
