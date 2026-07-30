---
description: "Step-by-step IK Rig + IK Retargeter workflow, the Biped-vs-Mannequin chain trap, explicit chains, and troubleshooting"
metadata:
  label: "Retargeting (step by step)"
  default_enabled: false
  load_condition: "Retargeting an animation, building an IK Rig/Retargeter, or chains/preset came back unknown or skipped"
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

`create_ik_rig` with `chain_preset="auto"` picks one of these from the bones.
Chain **names are identical** across presets so any source maps to any target.

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
`steps.chains_skipped` — read that; it usually means a naming variant (e.g.
`Bip001 Neck` with a space, or no `Bip001-Head`). Fix with `add_retarget_chains`.

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

Auto-map pairs chains by identical name. If it shows `auto_map_error` or the pose
is bad, the **retarget pose** (A-pose vs T-pose) needs aligning on the
`IKRetargeterController` (inspect with `describe_class`) — that's pose, not chains.

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
| `retarget_root not found` in steps | wrong method this build | `describe_class("IKRigController")`, use reported name via `execute_python` |
| Baked anim floats / T-poses | retarget pose mismatch | align source/target retarget pose on the retargeter |
| `batch retarget API differs` | UE changed the bake API | read `batch_operation_methods` in the response, drive via `execute_python` |
| Foot IK skates on MetaHuman | MH skeleton missing Mannequin IK virtual bones | Copy `ik_foot_root` / `ik_foot_l` / `ik_foot_r` (and hand IK equivalents if needed) from `SKM_Manny_Simple` onto the MH skeleton; re-save. Prefer Common `RTG_metahuman` / `IK_MetaHuman` for Mannequin→MH body clips. |

### MetaHuman ↔ Mannequin

Assembled MetaHumans ship (or share) Common assets **`RTG_metahuman`** and
**`IK_MetaHuman`**. Use those for Mannequin/FN → MH body locomotion when present
instead of reinventing chains. Full MH create/spawn path:
`skill_read_subskill("metahuman", "npc_spawn")`.

## Other anim editing (no retarget)

- **AnimSequence / Montage**: `AssetToolsHelpers.create_asset` + matching factory;
  edit with `AnimationLibrary`.
- **Notifies**: `AnimationLibrary.add_animation_notify_event(...)`.
- **Modifiers**: `AnimationModifierLibrary` — batch across a folder.

Finish with `save_asset`/`save_directory` then `save_current_level`.
