---
description: "Custom-mesh NPC pipeline — physics, AnimPreset, character Blueprint, NPCCharacterDefinition, spawner. Agent does every click. Never ask a human to hook anything up."
metadata:
  label: "NPC character definitions"
  default_enabled: false
  load_condition: "Building NPCCharacterDefinition assets, AnimPresets, restoring imported UE4 packs, custom quadrupeds/creatures, or wiring custom mesh NPCs to Verse behaviors"
---

# NPC character definitions — zero human clicks

**HARD:** never ask the user to create an AnimPreset, character Blueprint,
NPCCharacterDefinition, physics asset, or to assign a definition onto a
spawner, or to fill animation slots in Details. Those are all MCP tools.
If a tool errors, retry once, then use the closest listed alternative —
do not hand the job to a human.

Goal: a **spawnable custom-mesh NPC** with locomotion, reaction clips, and a
Verse `npc_behavior` **you write** for this island. The user says what the
creature should do. You find the tools and program it. No pasted example, no
Details homework.

Verse AI loops: `skill_read_subskill("verse", "sys_npc_ai")`.
Multi-species / play-dead / session registries: `skill_read_subskill("animation", "npc_ecosystem")`.
Retarget chains: `skill_read_subskill("animation", "retargeting")`.

```
imported mesh + Idle/Walk (+ react clips)
  → create_physics_asset_for_mesh          (if none — no physics = T-pose/slide)
  → create_anim_preset                     (idle + walk, same Skeleton)
  → create_character_blueprint             (one per visual variant / material)
  → duplicate react clips into the Verse module folder
  → verse_template_apply("npc_core") then customize behaviors next to duplicated clips
  → workspace_compile_verse
  → create_npc_character_definition + set_npc_definition_behavior
  → Epic PlaceDevice Character Spawner
  → set_npc_spawner_definition
  → wire_verse_device_ref on the spawn controller
```

After the listener is online, call `npc_author_capabilities({})` **alone**
(one editor tool that turn). If `available` is false, report the missing
classes — do not invent a Details-panel workaround. If the listener is
offline, STOP; write Verse with `workspace_*` and wait. Do not retry
`npc_author_*` while UEFN is down — that is what crashed the editor.

---

## 1. Restore prep (old Unreal 4 packs)

Imported marketplace / old-UE4 characters often arrive broken:

| Symptom | Cause | Fix |
|---------|-------|-----|
| Skeletal mesh has **null Skeleton** | Orphaned package refs after migrate | Assign a working Skeleton (`get_skeletal_mesh_info` → `set_object_property`) |
| AnimSequence has **empty data model** | FBX not reimported | FBX reimport onto the correct skeleton |
| Auto-Characterize spam / 0 chains | **Biped** `Bip001-*` vs Mannequin | Explicit chains — `retargeting` |
| NPC T-poses / slides | **No Physics Asset** | `create_physics_asset_for_mesh` |

Probe first: `get_skeletal_mesh_info`, `list_skeleton_bones`, `ik_retarget_capabilities`.

---

## 2. Physics (mandatory)

```
create_physics_asset_for_mesh({"skeletal_mesh_path": "<content_root>/…/SKM_Cat"})
```

No physics asset ⇒ the NPC T-poses and slides. The tool is a no-op if one exists.

---

## 3. AnimPreset (locomotion) — tool, not Content Browser

NPC locomotion comes from **`AnimPreset_BasicLocomotion`**. Do not author an AnimBP
(`animation_bp` stays null).

```
create_anim_preset({
  "name": "AP_Cat_Locomotion",
  "dest_folder": "<content_root>/AI",
  "idle": "<content_root>/…/AS_Cat_Idle",
  "walk": "<content_root>/…/AS_Cat_Walk",
  "play_rate": 1.0
})
```

`walk` fills move_forward / backward / left / right. All clips must share the
**same Skeleton** as the mesh. The tool warns if they do not.

---

## 4. Character Blueprint — the variant trick

Six "different cats" = one mesh + six material instances. Spawners use the
**NPCDef**, but CosmeticSpawn `CHARACTER_BLUEPRINT` needs this BP at runtime.

```
create_character_blueprint({
  "name": "BP_Cat_01",
  "dest_folder": "<content_root>/AI",
  "skeletal_mesh_path": "<content_root>/…/SKM_Cat",
  "material_path": "<content_root>/…/MI_Cat_01",
  "scale": 2.0
})
```

Tune `scale` to mesh bounds (a ~50 cm cat wants ~2×; a ~56 cm dog ~4×).
`anim_class` is forced null — locomotion is the preset.

---

## 5. Reaction clips in the Verse module folder

`@editable : animation_sequence` on an NPCDef **cannot** be set by
`set_verse_editable` (that stack is VerseDevice actors only). Do not ask a
human to fill Details.

**Do this instead:** duplicate the react clips into the **same folder as the
behavior `.verse` files**. After a Verse compile they appear in
`Assets.digest.verse` as same-module `animation_sequence` identifiers, and the
behavior references them by name. No Details panel.

```
duplicate_asset({"source": "…/AS_Cat_Attack_01", "destination_name": "AS_CatReact_Attack_01",
                 "destination_path": "<content_root>/AI/CatReacts"})
# repeat: Attack_02, Attack_03, Die, Dead, and the dog bite/play clip as AS_DogReact_Attack
```

Then write the behavior files in that folder (`workspace_write_file`). Name
clips and classes for **this** island. Do not apply the catland template
unless the user asked for cats+dog by that name.

---

## 6. `NPCCharacterDefinition` — tool, not duplicate-and-hope

```
create_npc_character_definition({
  "name": "NPCDef_Cat_01",
  "dest_folder": "<content_root>/AI",
  "skeletal_mesh_path": "…/SKM_Cat",
  "character_blueprint_path": "…/BP_Cat_01",
  "anim_preset_path": "…/AP_Cat_Locomotion",
  "behavior": ""
})
workspace_compile_verse()          # wait; WinError 10054 = build started, do not retry
set_npc_definition_behavior({
  "asset_path": "<content_root>/AI/NPCDef_Cat_01",
  "behavior": "cat_npc_behavior"   # or the CDO path after compile
})
```

What the tool actually writes (verified live, not guessed):

| Field | Value |
|-------|--------|
| `type` | instanced `CharacterType_Custom` |
| `skeletal_mesh` | the mesh |
| `character_blueprint` | `BP_*_C` |
| `anim_preset` | `AP_*_C` |
| `animation_bp` | null |
| `character_parts` | `[]` (populated parts re-enter the Fortnite outfit path) |
| `behavior.npc_behavior_script` | CDO of the Verse class — **only after** `set_npc_definition_behavior`. Fresh defs use DefaultBehavior (`kind=default`, script=null). That is success, not an error. |

CosmeticSpawn **must** be:

- `character_look = CHARACTER_BLUEPRINT`
- `character_movement = ANIMATION_PRESET`
- `support_anim_preset = true`, `support_character_movement = true`
- `character_blueprint` + `anim_preset` **mirrored** from the definition

That pair is what makes a custom quadruped spawn as itself instead of a
Fortnite skin. `create_npc_character_definition` sets it. Verify with
`get_npc_definition_info` → `spawns_custom_mesh: true`. Ignore
`behavior.kind=default` until you have compiled and called
`set_npc_definition_behavior`.

Variants: call `create_character_blueprint` + `create_npc_character_definition`
once per material, or `duplicate_asset` a finished def then
`set_npc_definition_look` to retarget the BP (mirrors CosmeticSpawn).

---

## 7. Place + assign the spawner — tool, not Details

1. Epic `unreal__call_tool` → `ValkyrieToolset.DeviceToolset` → `PlaceDevice`
   (Character Spawner / `npc_spawner_device`). Label + folder in that call
   (e.g. `Cat Spawner 01` in `NPCs/Cats`). One device per definition.
2. **Immediately:**

```
set_npc_spawner_definition({
  "actor_path": "Cat Spawner 01",
  "definition_path": "<content_root>/AI/NPCDef_Cat_01"
})
```

3. Place a VerseDevice running the spawn controller. **Compile first**
   (`workspace_compile_verse` succeeded — 10054 means wait, never retry). Then
   `get_verse_editables` — only wire when the field has a `mangled_name`.
   `wire_verse_device_ref` for scalar slots; `wire_verse_device_array` for
   arrays (`Triggers`, …) **one target per turn**. If the result is STALE
   REFLECTION, stop: the host already compiled + reloaded + retried once.
   Further `wire_*` calls cannot invent a hash. Poll `list_verse_types`, then
   re-inspect the **same** device and wire once. Never place a second copy of
   the device (same stale class; the existing one gets the hashes when the
   build lands). Never loop. Never ask the user to drag refs in Details.

Navmesh: spawners carry `AthenaAIRequiresNavigation`. If NPCs stand still they
have no navmesh — put them on walkable geometry.

---

## End-to-end checklist (new character / new island)

1. `get_project_info()` → `content_root`. Never write `/Game/...`.
2. Listener online, then `npc_author_capabilities` **alone** → `available: true`.
3. Physics on every skeletal mesh.
4. One `create_anim_preset` per species (idle+walk, same skeleton).
5. One `create_character_blueprint` per visual variant.
6. Duplicate react clips into the Verse module folder with the canonical names.
7. Write / apply the behavior files **in that folder**. `workspace_list_verse_errors` until clean.
8. `workspace_compile_verse` (do not retry on 10054).
9. `create_npc_character_definition` per variant, then `set_npc_definition_behavior`.
10. Place spawners → `set_npc_spawner_definition` each → wire the controller.
11. `save_current_level`, PIE.

If any step lacks a tool, **that is a bug in this skill** — do not invent a
"please click in Details" instruction.
