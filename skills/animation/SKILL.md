---
source_plugin_id: animation
name: animation
description: "Retarget animations between skeletal meshes, CREATE custom animations (Verse prop keyframes, Level Sequences, AnimSequence bone keys), and attach items/props to NPC skeletons in UEFN — composable IK Rig / IK Retargeter, sequencer, and socket tools, plus an FBX fallback"
license: All Rights Reserved
metadata:
  label: UEFN Animation
  version: 13
  managed_by: uefn-ducky
  author: UEFN-Ducky
  copyright: Copyright 2026 UEFN-Ducky
  allow_redistribute: false
---

# UEFN Animation — retarget, edit, and CREATE

Two capability families: **retargeting** (convert an animation authored for
one skeletal mesh onto another skeleton — this file) and **authoring** (create
new animations: Verse prop keyframes, Level Sequences for the Cinematic
Sequence device, AnimSequence bone keys — see the **Creating animations**
reference; probe with `anim_author_capabilities`).

The tools are **small composable primitives** — read one thing, create one
thing, change one thing — so you chain them for the task at hand. Don't reach for
the all-in-one pipeline unless the case is the plain one.

## The tools (flat MCP tools)

| Kind | Tools |
|------|-------|
| **READ** | `ik_retarget_capabilities`, `list_skeleton_bones`, `get_retarget_preset`, `get_ik_rig_info`, `get_ik_retargeter_info`, `list_skeleton_sockets` |
| **CREATE** | `create_ik_rig_asset`, `create_ik_retargeter_asset` |
| **CHANGE** | `set_retarget_root`, `add_retarget_chains`, `remove_retarget_chains`, `auto_map_retarget_chains`, `add_skeleton_socket`, `remove_skeleton_socket` |
| **BAKE** | `retarget_animation` |
| **COMPOSE** | `retarget_animation_pipeline` (convenience only) |

Always `ik_retarget_capabilities({})` first. If `available` is false,
skip these and use the **FBX fallback** below.

## Skeleton sockets (attach props to bones)

To hang a prop (hat, weapon, accessory) on a skeleton bone, create a socket with
the dedicated tools — **never** via `execute_python` (`unreal.SkeletalMeshSocket()`
direct construction is a native crash that kills the whole editor, and Blueprint
SCS/component surgery is blocked for the same reason).

The full chain, all thin tools:

```
get_skeletal_mesh_info({"asset_path": ".../SomeMesh"})            # READ: bones+sockets+materials+bounds in one call
add_skeleton_socket({"asset_path": ".../SomeMesh",
    "bone_name": "Bip001-Head", "socket_name": "HatSocket",
    "location": [0, 0, 12]})                                      # CHANGE (saves the Skeleton asset)
spawn_actor({"asset_path": ".../SomeHatMesh"})                    # the prop as its own actor
attach_actor({"child_path": "SomeHat", "parent_path": "SomeCharacter",
    "socket": "HatSocket", "rule": "snap_to_target"})             # snaps onto the socket
get_actor_bone_transform({"actor_path": "SomeCharacter",
    "socket_or_bone": "HatSocket"})                               # READ: verify placement
add_skeleton_socket({..., "update_existing": true,
    "location": [0, 2, 14]})                                      # iterate the fit
save_current_level()
```

Also: `list_actor_components` shows how a placed actor is built (never probe
Blueprint CDOs via execute_python); `remove_skeleton_socket` cleans up;
`attach_actor` without `rule` keeps world position (re-parent without moving).

Notes: sockets live on the **Skeleton asset**, shared by every mesh using that
skeleton — including runtime-spawned characters (NPC definitions). Editor
`attach_actor` only affects actors placed in the level; runtime-spawned NPCs
need the attachment done by gameplay (Verse) or content setup, but the socket
itself is already there for them.

For the full items-on-NPCs workflow — finding/creating the item mesh, sizing
it, bone/socket naming across skeleton types, runtime-NPC options, and the
attach-vs-grant distinction —
`skill_read_subskill("animation", "npc_items")`.

For **custom NPC characters** (restore old UE4 packs → retarget → AnimPreset →
`NPCCharacterDefinition` → spawner):
`skill_read_subskill("animation", "npc_characters")`. Verse AI loops:
`skill_read_subskill("verse", "sys_npc_ai")`.

## Chain the primitives (the normal path)

```
# FIRST: get_project_info() → content_root (e.g. /VideoTest/)
ik_retarget_capabilities({})                                  # READ
create_ik_rig_asset({"skeletal_mesh_path": ".../SourceMesh",
    "dest_folder": "/VideoTest/Retargeting", "name": "IK_Source"})        # CREATE -> preset_guess: "biped"
get_retarget_preset({"name": "biped"})                        # READ -> root + chains
set_retarget_root({"ik_rig_path": ".../IK_Source", "bone": "Bip001-Pelvis"})   # CHANGE
add_retarget_chains({"ik_rig_path": ".../IK_Source", "chains": [ ...preset... ]}) # CHANGE
# repeat CREATE + CHANGE for the target mesh (IK_Target) ...
create_ik_retargeter_asset({"source_ik_rig_path": ".../IK_Source",
    "target_ik_rig_path": ".../IK_Target", "dest_folder": "/VideoTest/Retargeting",
    "name": "RTG_Source_to_Target"})                                      # CREATE
auto_map_retarget_chains({"ik_retargeter_path": ".../RTG_Source_to_Target"})     # CHANGE
retarget_animation({"ik_retargeter_path": ".../RTG_Source_to_Target",
    "source_mesh_path": ".../SourceMesh", "target_mesh_path": ".../TargetMesh",
    "anim_paths": [".../SomeAnimSequence"]})                              # BAKE
save_current_level()
```

Because they're separate, you can also: reuse an existing rig and just call
`add_retarget_chains`; `get_ik_rig_info` to verify chains; batch many anims in one
`retarget_animation`; or `remove_retarget_chains` + re-add to fix one limb.

## Convenience wrapper (plain case only)

```
retarget_animation_pipeline({"source_mesh_path": ".../SourceMesh",
    "target_mesh_path": ".../TargetMesh", "anim_path": ".../SomeAnimSequence"})
```

It just chains the primitives above with `preset:"auto"`. Read its
`report.*.chains.skipped` — if a preset is `unknown`, fall back to the primitives
and `skill_read_subskill("animation", "retargeting")`.

## Hard rules

- **Engine "Auto Characterize" only knows Epic Mannequin bone names**
  (`pelvis`, `spine_01`, `upperarm_l`…). A 3ds Max Biped skeleton uses `Bip001-*`,
  so it matches nothing and makes ZERO chains — the #1 retarget failure. Use
  `get_retarget_preset` + `add_retarget_chains` instead of the engine auto button.
- **Every tool self-reports.** On a method miss it returns the members that ARE on
  the class (`controller_methods`, `batch_operation_methods`) — read that and adapt
  via `execute_python`; don't retry blindly.
- **Source and target chain names must match exactly** (`Spine`, `LeftArm`, …) or
  `auto_map_retarget_chains` can't pair them. The presets guarantee this.
- **Paths use the project mount** from `get_project_info().content_root`
  (e.g. `/VideoTest/Retargeting`) — never invent `/Game/...` for new assets.
  Omit `dest_folder` / pass empty to let the listener auto-pin.

## FBX fallback (API not available)

If `ik_retarget_capabilities` reports `available: false`: `export_asset` the source
AnimSequence to FBX, then `import_asset` it back onto the **target** skeletal mesh
(Interchange remaps by bone name). Lossy for very different proportions.

## After ANY animation asset change

`save_asset` / `save_directory` → `save_current_level()`.

## Reference files

- `references/retargeting.md` — IK Rig + IK Retargeter step-by-step, Biped trap, UE4 pack restore prep
  Load when: Retargeting an animation, building an IK Rig/Retargeter, or chains/preset came back unknown or skipped
- `references/anim_authoring.md` — Creating Level Sequences / AnimSequence bone keys / Verse prop keyframes
  Load when: Authoring a new animation (not retargeting an existing one)
- `references/sequencer_cinematics.md` — Cameras, cuts, Cinematic Sequence device, multi-actor choreography
  Load when: Cutscenes, cine cameras, device playback, or multi-actor Level Sequences
- `references/npc_items.md` — Items/props on NPCs — sockets, attach, verify
  Load when: Putting an item, prop, weapon, hat, or accessory on an NPC or skeletal character
- `references/npc_characters.md` — Restore UE4 skeletons → retarget → AnimPreset → NPCCharacterDefinition → spawner
  Load when: Building NPCCharacterDefinition assets, AnimPresets, restoring imported UE4 enemy packs, or wiring custom mesh NPCs to Verse behaviors

**MetaHuman NPCs** (Creator / Mesh to MH / UEFN Export assemble / MH-specific
physics + spawn): install the MetaHuman Store plugin, then
`skill_read_subskill("metahuman", "npc_spawn")` (and pack core for create/assemble).
