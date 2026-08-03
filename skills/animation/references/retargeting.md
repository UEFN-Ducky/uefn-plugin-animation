---
description: "Step-by-step IK Rig + IK Retargeter workflow, the Biped-vs-Mannequin chain trap, explicit chains, retarget-pose (A-pose vs T-pose) fixes, and troubleshooting"
metadata:
  label: "Retargeting (step by step)"
  default_enabled: false
  load_condition: "Retargeting an animation, building an IK Rig/Retargeter, fixing a bad retarget pose, or chains/preset came back unknown or skipped"
---

# IK Rig retargeting — the manual stages

`retarget_animation_pipeline` runs all of this in one call. Do it by hand when a
stage fails, a preset is `unknown`, or you're reusing rigs across many anims.

## The chain trap (read first)

Retargeting maps **chains** (Spine, LeftArm…) source→target. Chains are made of
named bones. The engine's **Auto Characterize** button only recognises **Epic
Mannequin** names (`pelvis`, `spine_01`, `upperarm_l`, `thigh_l`…). If the
skeleton was imported from **3ds Max Biped**, its bones are `Bip001-Pelvis`,
`Bip001-L-UpperArm`, `Bip001-L-Thigh`… — auto-characterize matches nothing and
you get a rig with zero chains (the "was not found in this skeleton, but is used
by UE4 Mannequin" spam). So we add chains **explicitly**.

Always start by reading the actual names:

```
# FIRST: get_project_info() → content_root (e.g. /VideoTest/)
list_skeleton_bones({"skeletal_mesh_path": "/VideoTest/Corpse/Corpse_Sword"})
# -> {"preset_guess": "biped", "bones": ["Bip001-Pelvis","Bip001-Spine",...]}
```

## Restoring old UE4 packs (before chains)

Imported UE4 / marketplace character packs often need **asset repair** before
any IK Rig will work. Full NPC pipeline (AnimPreset + character definition):
`skill_read_subskill("animation", "npc_characters")`.

| Symptom | Fix |
|---------|-----|
| Skeletal mesh **Skeleton is None** | Reassign a working Skeleton of the same bone family; save the mesh |
| AnimSequence **empty data model** | Reimport FBX onto the correct skeleton; if sources are gone, retarget from a sibling mesh that still has curves |
| Characters should share / retarget anims | Mark skeletons **compatible** when hierarchies match |
| Then 0 chains / Mannequin spam | You hit the Biped trap above — explicit `add_retarget_chains`, not Auto Characterize |

Probe with `get_skeletal_mesh_info` and `get_asset_info` first. Bake restored
clips into a clear folder (e.g. `Animations_Restored/<Character>/`) so presets
and Verse `@editable` slots do not point at broken originals.

## Preset chain tables

`create_ik_rig_asset` returns a `preset_guess` from the bone names; pass that name
to `get_retarget_preset` and feed its `chains` to `add_retarget_chains`
(`retarget_animation_pipeline` does the same automatically via
`source_preset` / `target_preset = "auto"`). Chain **names are identical** across
presets so any source maps to any target.

**Biped** (root `Bip001-Pelvis`) — validated on Corpse_Sword:

| Chain | Start | End |
|-------|-------|-----|
| Spine | Bip001-Spine | Bip001-Spine2 |
| Head | Bip001-Neck | Bip001-Head |
| LeftArm | Bip001-L-UpperArm | Bip001-L-Hand |
| RightArm | Bip001-R-UpperArm | Bip001-R-Hand |
| LeftLeg | Bip001-L-Thigh | Bip001-L-Foot |
| RightLeg | Bip001-R-Thigh | Bip001-R-Foot |
| LeftClavicle | Bip001-L-Clavicle | Bip001-L-Clavicle |
| RightClavicle | Bip001-R-Clavicle | Bip001-R-Clavicle |

**Mannequin** (root `pelvis`): Spine `spine_01→spine_03`, Head `neck_01→head`,
LeftArm `upperarm_l→hand_l`, RightArm `upperarm_r→hand_r`, LeftLeg
`thigh_l→foot_l`, RightLeg `thigh_r→foot_r`, clavicles `clavicle_*`.

Any chain whose start/end bone isn't in the skeleton is **skipped** and listed in
the `skipped` array of the `add_retarget_chains` response (with the reason) — read
that; it usually means a naming variant (e.g. `Bip001 Neck` with a space, or no
`Bip001-Head`). Fix the names and re-add with `replace_existing: true`.

## 1 & 2. Source and target IK Rigs (create + change primitives)

```
create_ik_rig_asset({"skeletal_mesh_path": "/VideoTest/Corpse/Corpse_Sword",
  "dest_folder": "/VideoTest/Retargeting", "name": "IK_Corpse"})   # -> preset_guess: "biped"
get_retarget_preset({"name": "biped"})            # -> {root, chains}
set_retarget_root({"ik_rig_path": "/VideoTest/Retargeting/IK_Corpse", "bone": "Bip001-Pelvis"})
add_retarget_chains({"ik_rig_path": "/VideoTest/Retargeting/IK_Corpse", "chains": [ ...preset chains... ]})
```

Repeat for the target (`IK_Archer`). If `preset_guess` is `unknown` (custom
skeleton), map bones yourself from `list_skeleton_bones` and pass them straight to
`add_retarget_chains`:

```
add_retarget_chains({"ik_rig_path": ".../IK_Custom", "replace_existing": true,
  "chains": [{"name":"Spine","start":"spine_a","end":"spine_d"},
             {"name":"LeftArm","start":"arm_l","end":"wrist_l"}, ...]})
```

Verify any rig with `get_ik_rig_info(ik_rig_path)`; fix one limb with
`remove_retarget_chains` + `add_retarget_chains`.

## 3. IK Retargeter (create + change primitives)

```
create_ik_retargeter_asset({"source_ik_rig_path": "/VideoTest/Retargeting/IK_Corpse",
  "target_ik_rig_path": "/VideoTest/Retargeting/IK_Archer",
  "dest_folder": "/VideoTest/Retargeting", "name": "RTG_Corpse_to_Archer"})
auto_map_retarget_chains({"ik_retargeter_path": "/VideoTest/Retargeting/RTG_Corpse_to_Archer"})
```

Auto-map pairs chains by identical name.

## 3b. Retarget pose (A-pose vs T-pose) — when the result looks wrong

If chains map fine but the baked result floats, twists, or holds the arms at the
wrong angle, the two skeletons' **rest poses** disagree. Fix the pose on the
retargeter — never rebuild chains for it, and never copy bones between skeletons.

```
get_retarget_pose_info({"ik_retargeter_path": ".../RTG_Corpse_to_Archer"})
# -> {"poses": ["Default"], "current_pose_offsets": {...}}
create_retarget_pose({"ik_retargeter_path": ".../RTG_Corpse_to_Archer",
    "name": "MatchSource"})                       # created on the target side, selected
set_retarget_pose_bone_rotation({"ik_retargeter_path": ".../RTG_Corpse_to_Archer",
    "bone": "upperarm_l", "rotation": [0, 0, -45]})   # [pitch,yaw,roll] degrees
set_retarget_pose_bone_rotation({"ik_retargeter_path": "...",
    "bone": "upperarm_r", "rotation": [0, 0, 45]})
set_retarget_pose_root_offset({"ik_retargeter_path": "...", "offset": [0, 0, -4]})
retarget_animation({...})                         # re-bake, look, adjust
```

- `source_or_target` defaults to `"target"`; pass `"source"` to edit the other side.
- Rotations are offsets from the rest pose, so ±45° on each upper arm turns a
  T-pose into an A-pose (and vice versa).
- Iterate: pose → re-bake one clip → inspect → adjust. Only batch the rest once
  the single clip looks right.
- `set_current_retarget_pose` switches between poses you have already made
  (e.g. one per source character).

## 4. Bake the animation

```
retarget_animation({"ik_retargeter_path": "/VideoTest/Retargeting/RTG_Corpse_to_Archer",
  "source_mesh_path": "/VideoTest/Corpse/Corpse_Sword", "target_mesh_path": "/VideoTest/Archer/Archer",
  "anim_paths": ["/VideoTest/Corpse/Corpse_Alert_Attack_Fast2"], "suffix": "_Retargeted"})
```

Pass every anim path in `anim_paths` to batch a whole folder through one retargeter.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 0 chains / "used by UE4 Mannequin" spam | Biped skeleton + engine auto button | `get_retarget_preset("biped")` → `add_retarget_chains` — don't use the editor auto button |
| `preset_guess: unknown` | custom bone names | `list_skeleton_bones`, then pass explicit `chains` to `add_retarget_chains` |
| chain in `chains_skipped` | start/end bone name variant | correct it, `add_retarget_chains(..., replace_existing=true)` |
| `create_asset returned None` | bad `dest_folder` or name clash | check folder / pick a new name |
| `set_retarget_root not found` | wrong method this build | read `controller_methods` in the response; the tools self-report what exists |
| Baked anim floats / T-poses / arms wrong | retarget pose mismatch | §3b — `create_retarget_pose` + `set_retarget_pose_bone_rotation`, then re-bake |
| Feet skate or sink | root height / rest-pose offset | `set_retarget_pose_root_offset` on the target side |
| `batch retarget API differs` | UE changed the bake API | read `batch_operation_methods` in the response and adapt |

### MetaHuman ↔ Mannequin

Assembled MetaHumans ship (or share) Common assets **`RTG_metahuman`** and
**`IK_MetaHuman`**. Use those for Mannequin/FN → MH body locomotion when present
instead of reinventing chains, and correct any remaining pose difference with the
retarget-pose tools in §3b. Full MH create/spawn path:
`skill_read_subskill("metahuman", "npc_spawn")`.

## Not the UEFN path

Montages, `AnimationLibrary` notifies, `AnimationModifierLibrary`, and
AnimBlueprint editing are full-Unreal APIs — don't drive them through
`execute_python` here. Author in Sequencer and bake
(`skill_read_subskill("animation", "anim_authoring")`); play through a device or
AnimPreset (`skill_read_subskill("animation", "runtime_playback")`).

Finish with `save_asset`/`save_directory` then `save_current_level`.
