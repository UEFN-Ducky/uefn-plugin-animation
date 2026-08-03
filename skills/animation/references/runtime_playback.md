---
description: "Making an animation actually play in game — Animated Mesh device, Cinematic Sequence device, NPC AnimPresets, player GetPlayAnimationController, editor-only Animation to Play, and why the Verse Scene Graph animation API is not publishable"
metadata:
  label: "Runtime playback"
  default_enabled: false
  load_condition: "An animation asset exists but nothing plays it in game, or choosing between Animated Mesh device / Cinematic Sequence device / AnimPreset / Verse playback"
---

# Playing an animation in game

Authoring produces an AnimSequence. Nothing plays it until you place something
that does. Pick by what is animating:

| What animates | Play it with | Publishable |
|---------------|--------------|-------------|
| A skeletal mesh prop / statue / set piece | **Animated Mesh device** | Yes |
| The **player** character (body clip / overlay) | Verse `GetPlayAnimationController` | Yes |
| A camera cutscene / scripted moment | **Cinematic Sequence device** | Yes |
| An NPC's locomotion + attacks | **AnimPreset + NPCCharacterDefinition** | Yes |
| A Creative prop's transform (platform, door) | Verse `animation_controller` | Yes |
| Editor preview only | Skeletal mesh actor's **Animation to Play** | n/a — not a runtime trigger |
| Scene Graph entities | Verse `PlaySkeletalAnimation` | **No — experimental** |

## Animated Mesh device (the default answer)

```
animated_mesh_capabilities({})            # find the device asset + any already placed
spawn_actor({"asset_path": "/Game/Creative/.../AnimatedMesh_C"})
set_actor_label({...})  set_actor_folder({...})        # organize as you place
configure_animated_mesh({"actor_path": "AnimMesh_Statue",
    "skeletal_mesh_path": "/VideoTest/Characters/SKM_Statue",
    "anim_path": "/VideoTest/Anims/AS_Wave",
    "loop": true, "play_rate": 1.0})
save_current_level()
```

- The animation must belong to the **same skeleton** as the mesh. If it does not,
  it will not be offered — retarget first (`retargeting`).
- Defaults: Loop **true**, Play Rate **1.0**.
- Runtime control is **Direct Event Binding**: Play Animation, Pause Animation,
  Play Reverse Animation — wire those from a trigger device or Verse.
- Device memory scales with the animation sets it references. Point it at baked
  clips you ship, not at a whole imported pack.
- If `configure_animated_mesh` reports a field it could not match, it returns the
  device's real option keys — set those with `set_creative_device_fields`.

## Player character — GetPlayAnimationController

Players are not Animated Mesh devices. From Verse on `fort_character`:

```
GetPlayAnimationController[] → Play(Clip, ?BlendInTime, ?BlendOutTime, …)
→ hold play_animation_instance (Await / Stop)
```

Same Verse call for full-body override (dance) or additive overlay (arm wave /
giant scale). Overlay requires the clip's **Additive Anim Type = Local Space**
(`set_anim_additive_type` or Property Matrix). Optional stasis + teleport for
cutscene framing. Emoting or firing resets the controller; scale is visual-only.

Full device, Layered Control Rig authoring, Assets digest, and limits:
`skill_read_subskill("animation", "player_animation")`.

## Cinematic Sequence device

For Level Sequences (cameras, choreography, scripted moments). Place the device,
set its Sequence to the asset, keep **Auto Start off** and use one authoritative
trigger. Full wiring, camera cuts, and the stuck-camera/Pause-vs-Stop rules:
`skill_read_subskill("animation", "sequencer_cinematics")`.

## NPC AnimPresets

Spawned NPCs do not read an Animated Mesh device — their clips come from an
`AnimPreset_BasicLocomotion` referenced by the `NPCCharacterDefinition`, plus
attack/reaction clips driven from Verse `npc_behavior`. Every sequence on a
preset must use the **same skeleton**. Full pipeline:
`skill_read_subskill("animation", "npc_characters")`; Verse AI loops:
`skill_read_subskill("verse", "sys_npc_ai")`.

## Animation to Play (editor field, not a trigger)

A skeletal mesh actor exposes Animation to Play with Looping, Playing, Initial
Position, and Play Rate. It is useful to eyeball a clip on a mesh in the editor.
It is not a gameplay trigger and gives you no Play/Pause events — ship the device.

## Verse Scene Graph animation — do not publish

`Entity.PlaySkeletalAnimation[...]` (Project Settings → Experimental → Scene
Graph Animation, UEFN v41+) is experimental:

- Islands using it **cannot be published**.
- Enabling the flag renames legacy `animation_sequence` assets with an `_asset`
  postfix, which **breaks existing Verse compilation**.
- Each animation asset becomes a Verse class named by its path
  (`Character/Animations/Idle` → `Character.Animations.Idle`), and the entity
  needs a `mesh_component` referencing a skeletal mesh.
- The returned handle eases out (`EaseOut(false)` uses the play-time window,
  `Cancel()` removes instantly and can pop a frame).

Use it only for experiments you will not ship. For anything published, the
Animated Mesh device, the Cinematic Sequence device, an AnimPreset, or player
`GetPlayAnimationController`.

## Failure table

| Symptom | Cause |
|---------|-------|
| Animation dropdown does not offer your clip | Clip belongs to another skeleton — retarget |
| Device placed but nothing happens | No trigger wired (Direct Event Binding / Verse), or Auto Start off with no caller |
| Plays twice | Two triggers bound to the same device |
| Plays in editor, not in session | You set Animation to Play instead of using a device |
| Player clip overrides walk instead of overlaying | Additive Anim Type still No Additive — see `player_animation` |
| Island fails validation / cannot publish | Built on the experimental Scene Graph animation API |
| Memory warnings | Device references a whole animation pack — trim to baked clips |
