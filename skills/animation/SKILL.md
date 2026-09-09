---
source_plugin_id: animation
name: animation
description: "Create, import, retarget, bake, and PLAY custom skeletal animations in UEFN — Control Rig / Level Sequence authoring, Mixamo & FBX import, IK Rig + IK Retargeter with retarget-pose fixes, bake to AnimSequence, Animated Mesh device playback, player GetPlayAnimationController (full override + additive overlay), NPC AnimPresets, and skeleton sockets"
license: MIT
metadata:
  label: UEFN Animation
  version: 23
  managed_by: uefn-ducky
  author: UEFN-Ducky
  copyright: Copyright 2026 Mindful Path Company, LLC
  allow_redistribute: true
---

# UEFN skeletal animation

**Tool order (HARD):** 1) Official UEFN MCP first — `ducky_get_status`; when `epic_mcp_online` use nested `unreal__*` (`unreal__list_toolsets` → `unreal__describe_toolset` → `unreal__call_tool`; 5+ ops → ProgrammaticToolset `execute_tool_script`). 2) Ducky listener second (Epic-offline gaps + Ducky-only tools listed in this skill). 3) `execute_python` LAST — never a placement/layout path, even if Epic and listener already failed. Never spawn, move, or assign materials. Map: `skill_read_subskill("uefn", "epic_mcp")`.

**CRITICAL — editor mutations are SERIAL:** one heavy MCP call (`spawn_actor`,
`set_actor_*`, `save_current_level`, bake/retarget tools, `npc_author_*`,
`create_physics_asset_for_mesh`, `create_anim_preset`, `create_character_blueprint`,
`create_npc_character_definition`, `duplicate_asset`) → wait → next. Never
parallel or same-turn multi spawn/wire/save — freezes UEFN. A single tool may
accept many `anim_paths` in **one** call (serial MCP, not parallel tools).
Details: `skill_read_subskill("uefn", "batch_commands")`.

`npc_author_capabilities` is a cheap `hasattr` + known-path `load_object`. If the
listener is offline, STOP — do not retry it. Never fire it in the same turn as
other listener/editor tools.

**NPCDef reads vs Verse behavior (HARD):** `create_npc_character_definition`
leaves stock `CharacterModifier_DefaultBehavior`. That class has **no**
`npc_behavior_script`. `get_npc_definition_info` is a read that must succeed
anyway (`behavior.kind` = `default`, script = null). Never treat that as a
tool failure and never retry the same read. Attach Verse only after
`workspace_compile_verse` via `set_npc_definition_behavior` (it **replaces**
DefaultBehavior with VerseBehavior). Wire spawn-controller `@editable` arrays
(`Triggers`, spawners, …) only after that same successful compile — STALE
REFLECTION means no hash yet; the host already retries once, so do not hammer
`wire_verse_*`.

UEFN is not full Unreal: AnimBlueprints, Montages, `AnimationLibrary`, and
animation modifiers are not the path here. Authoring happens in Sequencer, the
result is always an **AnimSequence**, and playback is a **device, an AnimPreset,
or Verse** — never "press Play in Sequencer".

## The facts that decide everything

- **Only skeletal meshes animate.** Static meshes must be converted first. Stock
  rig: FN Mannequin (Content Browser → Fortnite → search "FN"). Player body:
  **M_Medium_Base**.
- **Animations are skeleton-specific.** A clip authored for skeleton A is not
  even offered on skeleton B until it is **retargeted**.
- **Skeletal mesh actors expose Animation to Play** with Looping, Playing,
  Initial Position, Play Rate — fine for editor preview, not a runtime trigger.
- **Authoring ≠ playback.** Sequencer/Control Rig author; at runtime an Animated
  Mesh device, a Cinematic Sequence device, an NPC AnimPreset, or Verse
  (`GetPlayAnimationController` on the player / NPC) plays it.
- Animation sets count against island memory — bake what you ship, not the pack.

## Pick the route

| Goal | Route | Tools |
|------|-------|-------|
| Hand-author body motion | Control Rig in a Level Sequence → bake | editor UI + `bake_sequence_to_anim` |
| Bring in a Mixamo / FBX clip | Import onto the target skeleton | `import_asset` (see `anim_authoring`) |
| Same clip on a different skeleton | IK Rig + IK Retargeter + bake | `create_ik_rig_asset` … `retarget_animation` |
| Simple wave / nod / idle / pose | AnimSequence bone keys | `create_anim_sequence`, `set_anim_bone_keys` |
| Move a prop (platform, door) | Verse `animation_controller` | Verse only, no assets |
| Cutscene / camera choreography | Level Sequence + Cinematic Sequence device | `create_level_sequence`, `add_transform_keys` |
| Play a clip in game on a mesh | **Animated Mesh device** | `animated_mesh_capabilities`, `configure_animated_mesh` |
| Play a clip on the **PLAYER** character | Verse `GetPlayAnimationController` (+ optional additive) | Verse + `set_anim_additive_type` |
| NPC locomotion / attacks / custom creatures | AnimPreset + NPCCharacterDefinition **via tools** | `npc_characters`, `npc_ecosystem` |

Probe first (one listener tool per turn, only while the listener is online):
`ik_retarget_capabilities({})` / `anim_author_capabilities({})` /
`npc_author_capabilities({})`. If the listener is offline, STOP — do not retry
those. NPC authoring never falls back to asking a human to click Details.

## The tools (flat MCP tools)

| Kind | Tools |
|------|-------|
| **PROBE** | `ik_retarget_capabilities`, `anim_author_capabilities`, `animated_mesh_capabilities`, `npc_author_capabilities` |
| **READ** | `list_skeleton_bones`, `get_retarget_preset`, `get_ik_rig_info`, `get_ik_retargeter_info`, `get_retarget_pose_info`, `get_sequence_info`, `get_anim_sequence_info`, `get_skeletal_mesh_info`, `list_skeleton_sockets`, `list_npc_definitions`, `get_npc_definition_info` |
| **CREATE** | `create_ik_rig_asset`, `create_ik_retargeter_asset`, `create_retarget_pose`, `create_level_sequence`, `create_anim_sequence`, `create_physics_asset_for_mesh`, `create_anim_preset`, `create_character_blueprint`, `create_npc_character_definition` |
| **CHANGE** | `set_retarget_root`, `add_retarget_chains`, `remove_retarget_chains`, `auto_map_retarget_chains`, `set_current_retarget_pose`, `set_retarget_pose_bone_rotation`, `set_retarget_pose_root_offset`, `add_sequence_binding`, `add_transform_keys`, `set_anim_bone_keys`, `set_anim_additive_type`, `add_skeleton_socket`, `remove_skeleton_socket`, `set_anim_preset_slots`, `set_npc_definition_behavior`, `set_npc_definition_look`, `set_npc_spawner_definition` |
| **BAKE** | `retarget_animation`, `bake_sequence_to_anim` |
| **PLAY** | `configure_animated_mesh` |
| **COMPOSE** | `retarget_animation_pipeline` (convenience only) |

They are small composable primitives — read one thing, create one thing, change
one thing — so you chain them for the task at hand. Don't reach for the
all-in-one pipeline unless the case is the plain one.

## Retarget: the normal chain

```
# FIRST: get_project_info() → content_root (e.g. /MyProject/)
ik_retarget_capabilities({})                                  # PROBE
create_ik_rig_asset({"skeletal_mesh_path": ".../SourceMesh",
    "dest_folder": "/MyProject/Retargeting", "name": "IK_Source"})        # -> preset_guess: "biped"
get_retarget_preset({"name": "biped"})                        # READ -> root + chains
set_retarget_root({"ik_rig_path": ".../IK_Source", "bone": "Bip001-Pelvis"})
add_retarget_chains({"ik_rig_path": ".../IK_Source", "chains": [ ...preset... ]})
# repeat CREATE + CHANGE for the target mesh (IK_Target) ...
create_ik_retargeter_asset({"source_ik_rig_path": ".../IK_Source",
    "target_ik_rig_path": ".../IK_Target", "dest_folder": "/MyProject/Retargeting",
    "name": "RTG_Source_to_Target"})
auto_map_retarget_chains({"ik_retargeter_path": ".../RTG_Source_to_Target"})
retarget_animation({"ik_retargeter_path": ".../RTG_Source_to_Target",
    "source_mesh_path": ".../SourceMesh", "target_mesh_path": ".../TargetMesh",
    "anim_paths": [".../SomeAnimSequence"]})                              # BAKE (batch)
save_current_level()
```

**Rest poses differ (A-pose vs T-pose)?** That is a *pose* problem, not a chain
problem, and the fix is on the retargeter — never copy bones between skeletons:

```
get_retarget_pose_info({"ik_retargeter_path": ".../RTG_Source_to_Target"})
create_retarget_pose({"ik_retargeter_path": "...", "name": "MatchSource"})
set_retarget_pose_bone_rotation({"ik_retargeter_path": "...",
    "bone": "upperarm_l", "rotation": [0, 0, -45]})   # [pitch,yaw,roll] deg, target side
retarget_animation({...})                             # re-bake and look again
```

Because the primitives are separate you can also reuse an existing rig and just
call `add_retarget_chains`; verify with `get_ik_rig_info`; batch many anims in one
`retarget_animation`; or `remove_retarget_chains` + re-add to fix one limb.

## Author → bake → play (the Control Rig path)

1. Level Sequence + FK Control Rig on the actor, key the controls (editor UI —
   Animation Mode on, Game View off).
2. Trim the sequence playback range to the motion; the bake covers that range.
3. `bake_sequence_to_anim({"sequence_path": "...", "actor_path": "MyMannequin",
   "dest_folder": "/MyProject/Anims", "name": "AS_Wave"})` — the scripted form of
   right-click track → **Bake Animation Sequence**.
4. Play it: `animated_mesh_capabilities({})` → `spawn_actor` the device →
   `configure_animated_mesh({"actor_path": "AnimMesh_Statue",
   "skeletal_mesh_path": "...", "anim_path": ".../AS_Wave", "loop": true})`.

Full step-by-step, Mixamo import settings, blending, and moving an actor while it
animates: `skill_read_subskill("animation", "anim_authoring")`.

## Play a clip on the PLAYER character

Players are not Animated Mesh devices. Use Verse:

```
Agent.GetFortCharacter[] → FortCharacter.GetPlayAnimationController[]
→ AnimController.Play(Clip, ?BlendInTime := …, ?BlendOutTime := …)
→ hold the play_animation_instance (Await / Stop)
```

- **Full override** (dances, cutscene poses): leave Additive Anim Type = No Additive.
- **Overlay on Fortnite locomotion** (arm wave, giant/tiny scale): author with a
  **Layered** Control Rig on `M_Medium_Base`, bake, then
  `set_anim_additive_type({"anim_paths": ["…"], "additive_type": "local_space"})`
  (Property Matrix → Local Space if the tool is unavailable).

Optional: `PutInStasis` / `ReleaseFromStasis`, `TeleportTo` for framed beats.
Full device, additive authoring, and limits:
`skill_read_subskill("animation", "player_animation")`.

## Skeleton sockets (attach props to bones)

To hang a prop (hat, weapon, accessory) on a skeleton bone, create a socket with
the dedicated tools — **never** via `execute_python` (`unreal.SkeletalMeshSocket()`
direct construction is a native crash that kills the whole editor, and Blueprint
SCS/component surgery is blocked for the same reason).

```
get_skeletal_mesh_info({"asset_path": ".../SomeMesh"})            # bones+sockets+materials+bounds
add_skeleton_socket({"asset_path": ".../SomeMesh",
    "bone_name": "Bip001-Head", "socket_name": "HatSocket",
    "location": [0, 0, 12]})                                      # saves the Skeleton asset
spawn_actor({"asset_path": ".../SomeHatMesh"})
attach_actor({"child_path": "SomeHat", "parent_path": "SomeCharacter",
    "socket": "HatSocket", "rule": "snap_to_target"})
get_actor_bone_transform({"actor_path": "SomeCharacter",
    "socket_or_bone": "HatSocket"})                               # verify placement
add_skeleton_socket({..., "update_existing": true, "location": [0, 2, 14]})
save_current_level()
```

Sockets live on the **Skeleton asset**, shared by every mesh using that skeleton —
including runtime-spawned NPCs. Editor `attach_actor` only affects placed actors;
runtime NPCs need the attachment done by gameplay, but the socket is already there.
Full items-on-NPCs workflow: `skill_read_subskill("animation", "npc_items")`.

## Hard rules

- **Engine "Auto Characterize" only knows Epic Mannequin bone names**
  (`pelvis`, `spine_01`, `upperarm_l`…). A 3ds Max Biped skeleton uses `Bip001-*`,
  so it matches nothing and makes ZERO chains — the #1 retarget failure. Use
  `get_retarget_preset` + `add_retarget_chains` instead of the engine auto button.
- **Every tool self-reports.** On a method miss it returns the members that ARE on
  the class (`controller_methods`, `batch_operation_methods`) — read that and adapt;
  don't retry blindly.
- **Source and target chain names must match exactly** (`Spine`, `LeftArm`, …) or
  `auto_map_retarget_chains` can't pair them. The presets guarantee this.
- **Paths use the project mount** from `get_project_info().content_root`
  (e.g. `/MyProject/Retargeting`) — never invent `/Game/...` for new assets.
  Omit `dest_folder` / pass empty to let the listener auto-pin.
- **Never publish on Verse `PlaySkeletalAnimation`** (experimental Scene Graph
  animation): islands using it cannot be published, and enabling the flag renames
  legacy `animation_sequence` assets with an `_asset` postfix, breaking existing
  Verse compilation. Ship the Animated Mesh device / AnimPreset / player
  `GetPlayAnimationController` instead.
- **Player anim controller resets** if the player emotes or fires a weapon —
  design around it (`AllowEmotes := false` in stasis, short clips, or accept the
  pop). Root/bone **scale overlays are visual only**; hitboxes do not follow.
- **Do not use full-Unreal animation APIs** via `execute_python` — Montages,
  `AnimationLibrary` notifies, `AnimationModifierLibrary`, AnimBlueprint editing
  and Control Rig graph surgery are not the UEFN path.

## FBX fallback (retarget API not available)

If `ik_retarget_capabilities` reports `available: false`: `export_asset` the source
AnimSequence to FBX, then `import_asset` it back onto the **target** skeletal mesh
(Interchange remaps by bone name). Lossy for very different proportions.

## After ANY animation asset change

`save_asset` / `save_directory` → `save_current_level()`.

## Reference files

Tags: [yours]=you created, [store]=Store, [shipped]=bundled, [plugin]=plugin.

Load with MCP `skill_read_subskill("animation", "<id>")` when needed. Do **not** use the IDE Read/open-file tool on `~/.claude/skills`, `~/.cursor/skills`, or `references/*.md` paths (outside the project workspace — permission prompts / always errors).

- `anim_authoring` [plugin] — Control Rig authoring + Bake Animation Sequence, Mixamo/FBX import settings, Layered Control Rig additive overlays, AnimSequence bone keys, Verse prop keyframes, blending and moving an actor mid-animation, plus animation design principles
  Load when: Creating or importing an animation (Control Rig, Mixamo, FBX, hand-keyed motion) rather than retargeting an existing one
- `player_animation` [plugin] — Play clips on the PLAYER via `GetPlayAnimationController` — full override vs Additive Local Space overlay, Layered Control Rig authoring, stasis/teleport, Assets digest, emote/fire reset and hitbox limits
  Load when: Playing a custom animation on the player character, additive/overlay player anims, giant/tiny player, weapon inspect, or melee on the player
- `runtime_playback` [plugin] — Making an animation actually play in game: Animated Mesh device, Cinematic Sequence device, NPC AnimPresets, player anim controller, and why the Verse Scene Graph API is not publishable
  Load when: An animation exists but nothing plays it, or choosing between device / preset / Verse playback
- `retargeting` [plugin] — Step-by-step IK Rig + IK Retargeter workflow, the Biped-vs-Mannequin chain trap, retarget-pose (A-pose vs T-pose) fixes, and troubleshooting
  Load when: Retargeting an animation, building an IK Rig/Retargeter, or chains/preset came back unknown or skipped
- `npc_characters` [plugin] — Custom-mesh NPC pipeline: physics, AnimPreset, character Blueprint, NPCCharacterDefinition, spawner assign. Agent does every click.
  Load when: Building NPCCharacterDefinition assets, AnimPresets, restoring imported UE4 packs, custom quadrupeds/creatures, or wiring custom mesh NPCs to Verse behaviors
- `npc_ecosystem` [plugin] — Multi-species NPC patterns (session registries, FSMs, play-dead). Default: `verse_template_apply("npc_core")` then customize; `npc_ecosystem` is the optional cat+dog example.
  Load when: Building two-species or NPC-to-NPC ecosystems (cats/dogs/creatures that see each other), play-dead, downed registries, or autonomous wander/follow/flee/hunt
- `npc_items` [plugin] — Items/props on NPCs — create or find the item mesh, socket the skeleton, attach, verify, iterate; runtime-NPC caveats and the grant-vs-attach distinction
  Load when: Putting an item, prop, weapon, hat, or accessory on an NPC or any skeletal character
- `sequencer_cinematics` [plugin] — Level Sequence cinematics — cine camera, cuts, spawnables vs possessables, Cinematic Sequence device wiring, multi-actor choreography
  Load when: User wants a cutscene, cinematic, camera sequence, Cinematic Sequence device, or multi-actor choreography

**MetaHuman NPCs** (Creator / Mesh to MH / UEFN Export assemble / MH-specific
physics + spawn): install the MetaHuman Store plugin, then
`skill_read_subskill("metahuman", "npc_spawn")` (and pack core for create/assemble).
