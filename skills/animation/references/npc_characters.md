---
description: "NPC character pipeline — restore old UE4 skeletons/anims, retarget, AnimPreset_BasicLocomotion, NPCCharacterDefinition modifiers, and wire npc_spawner_device"
metadata:
  label: "NPC character definitions"
  default_enabled: false
  load_condition: "Building NPCCharacterDefinition assets, AnimPresets, restoring imported UE4 enemy packs, or wiring custom mesh NPCs to Verse behaviors"
---

# NPC character definitions — restore → retarget → definition → spawn

Goal: a **spawnable custom-mesh NPC** with locomotion, attack clips, and a Verse
`npc_behavior`. Agents should redo this for new characters **from skills alone**
(no project code). Verse AI loops live in `skill_read_subskill("verse", "sys_npc_ai")`.
Retarget chain math lives in `skill_read_subskill("animation", "retargeting")`.

```
imported UE4 pack
  → restore skeletons / empty anims
  → IK Rig + retarget bake → Animations_Restored/<Character>/
  → AnimPreset_BasicLocomotion (idle / run)
  → NPCCharacterDefinition (CharacterType_Custom + modifiers)
  → npc_spawner_device in level → spawn manager
```

---

## 1. Restore prep (old Unreal 4 packs)

Imported marketplace / old-UE4 characters often arrive broken:

| Symptom | Cause | Fix |
|---------|-------|-----|
| Skeletal mesh has **null Skeleton** | Orphaned package refs after migrate | Assign a working Skeleton of the same bone family (`get_skeletal_mesh_info` → set Skeleton on the mesh asset; save) |
| AnimSequence has **empty data model** | FBX not reimported / curves stripped | Prefer **FBX reimport** onto the correct skeleton; if sources missing, retarget from a sibling mesh that still has anims |
| Auto-Characterize spam / 0 chains | **Biped** `Bip001-*` bones vs Epic Mannequin names | Explicit chains — see `retargeting` (never the editor Auto button) |
| Two characters should share anims | Skeletons not marked compatible | Mark skeletons **compatible** when bone hierarchies match enough for retarget |

**Probe tools (always first):**

```
get_skeletal_mesh_info({"asset_path": ".../CharacterMesh"})   # bones, skeleton path, materials
get_asset_info({"asset_path": ".../SomeAnim"})                # class / sanity
list_skeleton_bones({"skeletal_mesh_path": "..."})            # preset_guess: biped | mannequin | unknown
ik_retarget_capabilities({})                                  # must be available before IK tools
```

Folder convention after bake (generic): keep originals; write retargeted clips under
`…/Animations_Restored/<CharacterName>/` so AnimPresets and Verse `@editable`
slots point at known-good assets.

---

## 2. Retarget animations

Follow the full **retargeting** reference. Short path:

1. `create_ik_rig_asset` source + target (or reuse existing IK_*).
2. `get_retarget_preset` + `set_retarget_root` + `add_retarget_chains` (Biped or Mannequin table).
3. `create_ik_retargeter_asset` + `auto_map_retarget_chains`.
4. `retarget_animation` with **all** needed anim paths in one batch (`suffix` optional).
5. `save_asset` / `save_directory` → `save_current_level`.

Reuse one retargeter for every clip on that source→target pair. If the result
floats or T-poses, fix the **retarget pose**, not chain names:
`create_retarget_pose` + `set_retarget_pose_bone_rotation` /
`set_retarget_pose_root_offset`, then re-bake one clip and look before batching
the rest (`retargeting` §3b).

---

## 3. AnimPreset (locomotion)

UEFN NPCs with custom meshes typically need an **`AnimPreset_BasicLocomotion`**
Blueprint (class `/Script/AnimPresetsRuntime.AnimPreset_BasicLocomotion`):

- Map **idle** and **run/walk** (and any preset slots your build exposes) to
  restored `AnimSequence` assets for that character.
- Name clearly: `AP_<Character>_Locomotion`.
- The character definition enables presets via `bSupportAnimPreset` and references
  this asset.
- **Same-skeleton rule:** every sequence on the preset (idle / run / MoveForward,
  etc.) must use the **same Skeleton**. Mixed skeletons → validation errors like
  “Invalid skeleton used in animation sequence for MoveForward”. Retarget all
  clips onto one skeleton before wiring the preset.

**Editor vs tools:** creating the Blueprint class instance and assigning sequence
slots is often **Content Browser / Details** work. Agents should:

- Document the required slot → anim mapping for the user / confirm after save.
- Verify with `get_asset_info` / `get_dependencies` that the preset soft-refs the
  restored anims.
- Never invent bone names — read them from `list_skeleton_bones`.

---

## 4. `NPCCharacterDefinition` asset

Class: `/Script/VerseFortniteAI.NPCCharacterDefinition`.

Typical composition observed in working custom NPCs:

### Character type

- **`CharacterType_Custom`** (path under CRD AI spawn definitions / types).
- Assign the **custom skeletal mesh** (the restored/compatible character mesh).
- The mesh needs a **physics asset** — without it, NPCs often spawn but
  **T-pose / slide without body anim**. Create or assign one on the skeletal mesh; save.
- Enable **`bSupportAnimPreset`** and point at the `AP_*_Locomotion` preset.

### Modifiers (common set)

| Modifier | Role |
|----------|------|
| `CharacterModifier_Health` | Max health / durability for the spawned NPC |
| `CharacterModifier_CosmeticSpawn` | Cosmetic / spawn presentation |
| `CharacterModifier_VerseBehavior` | Attaches a Verse `npc_behavior` **subclass**; exposes that class's `@editable` fields (attack anim, ranges, props) on the definition |

Fill Verse Behavior slots here — e.g. `AttackAnim` → a restored attack
`AnimSequence`. Those values are what the behavior reads at runtime; do not leave
them empty if combat depends on them.

Optional helper Blueprint actor (`BP_<Character>`) may hold a SkeletalMesh
component for editor preview — the **definition** is what the spawner uses.

**Honest tooling note:** creating `NPCCharacterDefinition` / modifier instances is
primarily an **editor asset authoring** step. MCP can inspect (`get_asset_info`,
`get_dependencies`, `search_assets`), duplicate/rename assets, and verify wiring —
do not claim a thin MCP tool "creates NPCDef from scratch" unless
`describe_class` / capabilities prove a create path. Prefer duplicate-an-existing
definition + retarget mesh/anims/behavior when automating.

---

## 5. Wire spawners

1. Place an **`npc_spawner_device`** (Character Spawner) per enemy type.
2. Assign the matching `NPCCharacterDefinition`.
3. Wire spawners into a Verse spawn manager (`sys_npc_ai` wave pattern):
   Spawned/Eliminated events, `MaxAlive`, `Spawn()`.
4. Confirm labels and `@editable` refs after compile/move (`find_devices`,
   `wire_verse_device_ref` when the manager is a Verse device).

---

## End-to-end checklist (new character)

1. **Inspect** mesh skeleton + sample anims (`get_skeletal_mesh_info`, empty-data check).
2. **Restore** null skeletons / mark compatible / FBX reimport if needed.
3. Confirm **physics asset** on the skeletal mesh.
4. **Retarget** locomotion + attack + death clips into `Animations_Restored/<Name>/`
   (all onto the **same** target skeleton).
5. **AnimPreset** idle/run → restored clips; save.
6. **NPCCharacterDefinition**: custom mesh + preset + Health + VerseBehavior + attack anim slots.
7. **Verse**: `npc_behavior` subclass (or reuse archetype) — `sys_npc_ai`.
8. **Level**: one spawner → spawn manager; PIE chase/attack/elim.
9. Persist: `save_asset` / `save_directory` / `save_current_level`.

### Cross-links

- Chains / Biped trap / bake: `retargeting`
- Hats/weapons on bones: `npc_items`
- Behavior loops / damage / projectiles: verse `sys_npc_ai`
- Wave devices only: verse `sys_spawning`
- **MetaHuman** create / UEFN Export / MH NPC spawn:
  `skill_read_subskill("metahuman", "assemble_uefn_export")` and
  `skill_read_subskill("metahuman", "npc_spawn")`
