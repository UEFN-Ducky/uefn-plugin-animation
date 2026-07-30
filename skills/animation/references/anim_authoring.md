---
description: "Creating custom animations in UEFN — three routes: Verse animation_controller keyframes on props (runtime), Level Sequence tools + Cinematic Sequence device (cutscenes/choreography), and AnimSequence bone keyframes (skeletal motion) — plus animation design principles"
metadata:
  label: "Creating animations"
  default_enabled: false
  load_condition: "User wants to CREATE/author an animation (moving platform, door, cutscene, camera move, custom skeletal motion) rather than retarget an existing one"
---

# Creating animations — pick the route first

| Route | What moves | Where it runs | Tools |
|-------|-----------|---------------|-------|
| 1. Verse `animation_controller` | Creative props (transform only) | Runtime, in game | Verse code only |
| 2. Level Sequence | Any bound actor + cameras | Editor-authored, played by Cinematic Sequence device | `create_level_sequence`, `add_sequence_binding`, `add_transform_keys` |
| 3. AnimSequence bone keys | Skeleton bones | Editor asset, played on skeletal meshes | `create_anim_sequence`, `set_anim_bone_keys` |

For routes 2–3, `anim_author_capabilities({})` FIRST — UEFN builds vary in what
they expose; the probe says which routes are live.

## Route 1 — Verse prop animation (moving platforms, doors, hazards)

Fully code-authored at runtime, no editor assets. The API (verify exact
signatures via `search_verse_digest` / `get_verse_api`):

```verse
if (AC := MyProp.GetAnimationController[]):
    Keyframes : []keyframe_delta = array:
        keyframe_delta:
            DeltaLocation := vector3{ X := 512.0, Y := 0.0, Z := 0.0 }  # cm, ADDITIVE
            DeltaRotation := MakeRotationFromYawPitchRollDegrees(90.0, 0.0, 0.0)  # relative
            DeltaScale := vector3{ X := 1.0, Y := 1.0, Z := 1.0 }  # MULTIPLICATIVE (1 = unchanged)
            Time := 0.5           # seconds for THIS segment
            Interpolation := EaseOut
    AC.SetAnimation(Keyframes, ?Mode := animation_mode.OneShot)
    AC.Play()
```

Rules that bite:

- **Deltas, not targets**: each keyframe is relative to the previous frame's
  end. Scale is multiplicative — to pulse 0.8x and back, the second key needs
  `1.0/0.8`.
- **Loop mode requires a closed path**: deltas must sum back to the start
  (net translation zero, net rotation zero) or the prop drifts each cycle.
  `PingPong` sidesteps this by playing in reverse.
- **Check state before SetAnimation**: only call it when `AC.GetState()` is
  `AnimationNotSet` or `Stopped` — re-setting mid-play errors.
- Interpolation: `Linear`, `EaseIn`, `EaseOut`, `EaseInOut`, or custom cubic
  bezier params. Linear looks robotic — default to eased.

## Route 2 — Level Sequences (cutscenes, camera moves, choreography)

```
anim_author_capabilities({})                                       # probe
# FIRST: get_project_info() → content_root (e.g. /VideoTest/)
create_level_sequence({"dest_folder": "/VideoTest/Cinematics",
    "name": "LS_Intro", "fps": 30, "length_seconds": 8})
add_sequence_binding({"sequence_path": ".../LS_Intro",
    "actor_path": "GateProp"})                                     # -> binding_name
add_transform_keys({"sequence_path": ".../LS_Intro",
    "binding_name": "GateProp", "keys": [
      {"time": 0.0, "location": [0,0,0], "interp": "auto"},
      {"time": 2.0, "location": [0,0,384], "interp": "auto"}]})
get_sequence_info({"sequence_path": ".../LS_Intro"})               # verify keys landed
```

- `rotation` is `[roll, pitch, yaw]` degrees (transform channel order);
  `time` is seconds; omit a property to leave its channels unkeyed.
- The tool auto-extends the section range over all keys — the raw engine
  silently drops keys outside the range, so don't hand-edit ranges downward.
- **Playback is the Cinematic Sequence device**: place one, set its Sequence
  to the asset, wire/trigger it (Verse or a trigger device).

Cinematic device best practices (community-validated):

- Keep each sequence **under ~30 s**; chain several short sequences with fades
  rather than one long one.
- **Auto Start off**, one authoritative trigger (Verse or a single device
  wire) — overlapping triggers cause double playback and camera contention.
- Prop must stay where the animation ends? Track properties → When Finished →
  **Keep State**.
- Ending a camera sequence: prefer **Pause at end over Stop** — Stop has
  known stuck-camera bugs; restore player control explicitly.
- Animate ONLY what the shot needs; verify in a live session with 2+ players
  (state divergence and join-in-progress bugs don't show in editor preview).

## Route 3 — AnimSequence bone keys (custom skeletal motion)

For simple authored motion — waves, nods, idles, poses — directly on a
skeleton:

```
anim_author_capabilities({})                                       # probe
list_skeleton_bones({"skeletal_mesh_path": ".../SomeMesh"})        # exact bone names
create_anim_sequence({"skeletal_mesh_path": ".../SomeMesh",
    "dest_folder": "/VideoTest/Anims", "name": "AS_Wave",
    "length_seconds": 1.5, "fps": 30})
set_anim_bone_keys({"anim_path": ".../AS_Wave",
    "bone": "Bip001-R-UpperArm", "keys": [
      {"time": 0.0, "rotation": [0,0,0]},
      {"time": 0.75, "rotation": [0,0,70]},
      {"time": 1.5, "rotation": [0,0,0]}]})
get_anim_sequence_info({"anim_path": ".../AS_Wave"})               # verify tracks
```

- Transforms are **bone-local** (relative to the parent bone) — key rotations
  on limb bones, not world positions.
- Sparse keys are fine: the tool resamples linearly to every frame (the raw
  engine call crashes on array-length mismatches; the tool guarantees safety).
- Complex full-body motion is still better retargeted from an existing anim
  (see retargeting) — hand-keying 20 bones rarely beats a converted clip.

## Animation design principles (any route)

- **Ease everything.** Linear in/out reads mechanical; EaseOut for arrivals,
  EaseIn for departures, EaseInOut for continuous motion.
- **Anticipation → action → settle.** A door that pauses 0.2 s, opens fast,
  and overshoots 5% before settling feels alive; a constant-speed door feels
  like placeholder.
- **Think in frames at 30 fps**: snappy actions 6–10 frames (0.2–0.33 s),
  standard moves 15–30, dramatic reveals 60+. Sub-0.15 s motion is invisible.
- **Arcs over lines**: natural motion curves; add a mid keyframe off the
  straight path for throws, swings, hops.
- **Hold poses.** Motion reads at the holds, not during movement — give key
  poses 3–5 frames of stillness.
- Loops need identical first/last poses AND matched velocity through the seam
  (mirror the easing on both ends).
