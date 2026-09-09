---
description: "Items/props on NPCs — create or find the item mesh, socket the skeleton, attach, verify, iterate; runtime-NPC caveats and the grant-vs-attach distinction"
metadata:
  label: "Items on NPCs"
  default_enabled: false
  load_condition: "Putting an item, prop, weapon, hat, or accessory on an NPC or any skeletal character"
---

**Tool order (HARD):** 1) Official UEFN MCP first (`ducky_get_status` → `epic_mcp_online` → nested `unreal__*`). 2) Ducky listener second. 3) `execute_python` LAST — never a placement path, even if Epic and listener failed. Map: `skill_read_subskill("uefn", "epic_mcp")`.

# Items on NPCs — the golden path

Goal: a visible item (hat, weapon, backpack, turban, …) riding a character's
skeleton so it moves with the bone. This is **editor-time content setup** with
thin MCP tools — one operation per call, verify between steps, never blind.

```
search_assets(search="hat", limit=20)                              # 1 FIND the item mesh
get_skeletal_mesh_info(asset_path=".../NPC_Mesh")                  # 2 READ bones + existing sockets
add_skeleton_socket(asset_path=".../NPC_Mesh",
    bone_name="head", socket_name="HatSocket",
    location=[0, 0, 12])                                           # 3 CHANGE (saves the Skeleton asset)
spawn_actor(asset_path=".../SM_Hat")                               # 4 the item as its own actor
attach_actor(child_path="SM_Hat", parent_path="NPC_Actor",
    socket="HatSocket", rule="snap_to_target")                     # 5 snap onto the socket
get_actor_bone_transform(actor_path="NPC_Actor",
    socket_or_bone="HatSocket")                                    # 6 VERIFY placement
add_skeleton_socket(..., update_existing=true,
    location=[0, 2, 14], rotation=[0, -5, 0])                      # 7 iterate the fit
save_current_level()                                               # 8 persist
```

## 1. Getting the item mesh

- **It already exists**: `search_assets` / `list_assets` — prefer PROJECT
  assets; `get_asset_info` for bounds so you can size the socket offset.
- **It needs creating**: import FBX/glTF via `import_asset` (details, LODs,
  collision: the **modeling** pack). Author items with the origin at the
  grip/contact point — then the socket offset stays near zero.
- **Scale**: verify with `get_asset_info` bounds vs the character's
  `get_skeletal_mesh_info` bounds BEFORE attaching; a 10× hat is the classic
  first-try failure.

## 2. Choosing bone + socket

- Read real bone names from `get_skeletal_mesh_info` — **never guess**. Epic
  Mannequin uses `head`, `hand_r`, `spine_03`…; 3ds Max Biped uses
  `Bip001-Head`, `Bip001-R-Hand`… Same item, different skeleton, different name.
- Reuse an existing socket when one fits (`list_skeleton_sockets`); weapons
  often already have `weapon_r` style sockets.
- Name sockets for the item slot (`HatSocket`, `BackpackSocket`), not the item.

## 3. Attach semantics

- `rule: "snap_to_target"` → item jumps exactly onto the socket (the normal case).
- No `rule` → keeps world position (re-parent without moving — for props
  already placed correctly).
- `list_actor_components` shows how the character actor is built when the
  attach lands on the wrong component.

## Runtime-spawned NPCs (spawner devices / NPC character definitions)

Sockets live on the **Skeleton asset**, so every mesh sharing that skeleton —
including NPCs spawned at runtime from a definition — has the socket. But
editor `attach_actor` only affects actors placed in the level. For items on
runtime NPCs:

- **Content setup first**: if the NPC definition's mesh can include the item
  (merged mesh or costume part), that beats runtime attachment.
- **Verse**: query the digests for the real API before writing anything —
  `search_verse_digest({"query": "attach"})` / `get_verse_api`. Do not invent
  attach APIs; if the digest has none, the known fallback is a
  `creative_prop` that follows the character (spawn + `MoveTo`/teleport on a
  tick loop) — accept the one-frame lag or reconsider content setup.

## Attach vs grant — different asks

- "Put a sword **on his back**" = this file (visible cosmetic attach).
- "Give the NPC a weapon **to use**" = inventory: Item Granter / NPC
  definition equipment — that's device wiring (**uefn** pack golden paths),
  not sockets.

## Hard safety rules

- **Never** construct `unreal.SkeletalMeshSocket()` or touch
  `SubobjectDataSubsystem` via `execute_python` — native crash, kills the
  whole editor. The thin tools exist because of that crash.
- `add_skeleton_socket` already saves the Skeleton asset; still finish with
  `save_current_level` so the placed actors persist.
- `remove_skeleton_socket` needs approval — the socket is shared by every
  mesh on that skeleton, so removal can strip other characters' items.
