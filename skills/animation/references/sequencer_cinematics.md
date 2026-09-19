---
description: "Level Sequence cinematics — cine camera, cuts, spawnables vs possessables, Cinematic Sequence device wiring, multi-actor choreography, Verse play"
metadata:
  label: "Sequencer cinematics"
  default_enabled: false
  load_condition: "User wants a cutscene, cinematic, camera sequence, Level Sequence with cameras, Cinematic Sequence device, multi-actor choreography, or camera cuts"
---

# Sequencer cinematics (UEFN)

Deep-dive for **Level Sequences** used as cutscenes / camera moves. Basics of
transform keys live in `anim_authoring` — load this when cameras, devices, or
multi-actor shots are involved.

Always `anim_author_capabilities({})` first. Tool availability varies by UEFN build.

## Routes reminder

| Need | Route |
|------|-------|
| Prop slide / door | Verse `animation_controller` or Sequence transform keys |
| Camera cutscene | Level Sequence + **Cinematic Sequence device** |
| Skeletal acting | AnimSequence / retargeted clips on bindings |

## Create sequence + bind actors

```
anim_author_capabilities({})
# FIRST: get_project_info() → content_root (e.g. /MyProject/)
create_level_sequence({"dest_folder": "/MyProject/Cinematics",
    "name": "LS_Intro", "fps": 30, "length_seconds": 8})
add_sequence_binding({"sequence_path": ".../LS_Intro",
    "actor_path": "GateProp"})
add_transform_keys({"sequence_path": ".../LS_Intro",
    "binding_name": "GateProp", "keys": [
      {"time": 0.0, "location": [0,0,0], "interp": "auto"},
      {"time": 2.0, "location": [0,0,384], "interp": "auto"}]})
get_sequence_info({"sequence_path": ".../LS_Intro"})
```

- `rotation` = `[roll, pitch, yaw]` degrees; `time` in seconds.
- Keep sequences **under ~30 s**; chain shorts with fades.
- Verify keys with `get_sequence_info` — don't assume.

## Cameras

1. Place or spawn a camera actor the project allows (Cine Camera when available —
   `list_actor_classes` / `search_assets`; don't invent paths).
2. `add_sequence_binding` the camera.
3. Key transform (and focal length via `execute_python` / property tracks when thin
   tools don't expose lens — `uefn_editor_python_hints` + `describe_class` first).
4. Camera **Cut** track: switch active camera over time — may require
   `execute_python` on the Level Sequence API when no thin tool exists.

Shot discipline (also leveldesign `cinematic_composition`):

- Eye-height establish (~170 uu) before hero close-up.
- Hold 3–5 frames on the money pose; ease into moves.
- One idea per shot; cut on action.

## Spawnables vs possessables

| Kind | Meaning in practice |
|------|---------------------|
| **Possessable** | Sequence drives an actor **already in the level** (usual UEFN path for props/cameras you placed) |
| **Spawnable** | Sequence spawns its own instance for the shot — useful for one-off cine props; cleanup/state rules differ |

Prefer possessables for island props that must match gameplay state. If spawnable
APIs aren't exposed in your build, place actors and bind them (possessable).

## Cinematic Sequence device

Playback is **not** "press play in Sequencer" for players — it's the device:

1. Place **Cinematic Sequence** device (`get_all_actors(label_filter=…)` (or Epic `DeviceToolset`) / Creative device list).
2. Set Sequence asset to `LS_Intro` (Epic `DeviceToolset` `GetDeviceProperties` →
   Epic `DeviceToolset` `SetDeviceProperty` — use real field names from inspect).
3. **Auto Start off** unless intentional; one authoritative trigger (Verse or wire).
4. Ending camera shots: prefer **Pause at end** over Stop (stuck-camera bugs).
5. Props that should stay where the anim ended: When Finished → **Keep State**.

Verse: trigger the device's play function after `search_verse_digest` /
`get_verse_api` for the exact API — don't guess event names.

## Multi-actor choreography

1. Block shot list (times + who moves).
2. Bind each actor + camera.
3. Key transforms sparsely; ease arrivals.
4. `get_sequence_info` after each bind batch.
5. PIE with 2+ players when possible — join-in-progress / camera contention
   won't show in a solo editor scrub.
6. `save_asset` on the sequence → `save_current_level()`.

## Failure table

| Symptom | Fix |
|---------|-----|
| Nothing plays in game | Device not wired / Auto Start off with no trigger |
| Double playback | Two triggers overlapping |
| Stuck camera | Pause-at-end; restore player control explicitly |
| Keys missing | Outside section range; re-add keys via tool |
| Actor doesn't move | Wrong binding / wrong actor_path label |
| Capabilities false | Fall back to Verse prop anim or FBX anim path |

## Don'ts

- Don't build a 3-minute single sequence — split.
- Don't animate everything in the level — only what the shot needs.
- Don't skip `anim_author_capabilities`.
- Don't use Stop-at-end for camera sequences when Pause is available.

## Related

- Transform / Verse / AnimSequence basics → `anim_authoring`
- Shot framing in the level → leveldesign `cinematic_composition`
- Lighting the shot → leveldesign `lighting`
- NPC acting → `npc_characters`, `retargeting`
