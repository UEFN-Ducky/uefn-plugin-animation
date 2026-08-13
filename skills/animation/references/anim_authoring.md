---
description: "Creating animations in UEFN — Control Rig in a Level Sequence then Bake Animation Sequence, Layered Control Rig additive overlays, Mixamo/FBX import, AnimSequence bone keys, Verse prop keyframes, blending and moving an actor mid-animation, plus animation design principles"
metadata:
  label: "Creating animations"
  default_enabled: false
  load_condition: "User wants to CREATE or IMPORT an animation (Control Rig, Mixamo, FBX, hand-keyed skeletal motion, moving platform, cutscene) rather than retarget an existing one"
---

# Creating animations — pick the route first

| Route | What moves | Where it runs | Tools |
|-------|-----------|---------------|-------|
| 1. Control Rig → bake | Skeleton bones | Editor authoring, output is an AnimSequence | Sequencer UI + `bake_sequence_to_anim` |
| 1b. **Layered** Control Rig → bake → additive | Bone **deltas** (player overlay) | AnimSequence with Additive Local Space | Sequencer UI + `set_anim_additive_type` |
| 2. FBX / Mixamo import | Skeleton bones | Imported AnimSequence | `import_asset` |
| 3. AnimSequence bone keys | Skeleton bones | Editor asset | `create_anim_sequence`, `set_anim_bone_keys` |
| 4. Verse `animation_controller` | Creative props (transform only) | Runtime, in game | Verse code only |
| 5. Level Sequence transform track | Any bound actor + cameras | Cinematic Sequence device | `create_level_sequence`, `add_transform_keys` |

`anim_author_capabilities({})` FIRST — UEFN builds vary; the probe reports
`level_sequence_route`, `anim_sequence_route`, `bake_sequence_route`, and
`additive_route`.

Whatever the route, an authored clip does nothing in game until something plays
it: `skill_read_subskill("animation", "runtime_playback")`. Player body clips:
`skill_read_subskill("animation", "player_animation")`.

## Route 1 — Control Rig in a Level Sequence, then bake

Authoring the rig itself is editor UI (no MCP tool drives Control Rig controls);
the bake at the end is scripted.

1. Content Drawer → right-click → **Cinematics → Level Sequence**. Open it,
   **Add Actor** → the target skeletal mesh (`create_level_sequence` +
   `add_sequence_binding` do the same thing headlessly).
2. On the actor track: **Control Rig → Control Rig Classes → FK Control Rig**.
   Turn **Animation Mode** on and **Game View off (G)** or the controls are invisible.
3. Select a control, move/rotate, key it (Enter or the key button).
4. Return to the start pose: Ctrl+C the first key, move the playhead to the end,
   Ctrl+V. Identical keys at two times = no motion between them.
5. Walk/run cycles: opposite arm with opposite leg; extremes at the ends, rest
   pose keys midway.
6. **Trim the playback range to the motion** — the bake covers the sequence
   range, so a 5 s range around a 1.5 s action bakes 3.5 s of nothing.
7. Bake:

```
bake_sequence_to_anim({"sequence_path": "/MyProject/Cinematics/LS_Wave",
    "actor_path": "FN_Mannequin",            # Outliner label of the bound actor
    "dest_folder": "/MyProject/Anims", "name": "AS_Wave"})
get_anim_sequence_info({"anim_path": "/MyProject/Anims/AS_Wave"})   # verify frames/bones
```

If the tool reports `available: false`, do the same thing in the editor:
right-click the actor track → **Bake Animation Sequence**. Either way the output
is a plain AnimSequence that shows up in Animation to Play, Animated Mesh
devices, AnimPresets, and Verse `@editable` slots.

**Editing an imported clip** (route 2) with Control Rig: right-click the
animation track → **Bake to Control Rig** → FK Control Rig with **Reduce Keys
enabled** — raw imports are key-dense and unusable without it. Then edit or
delete per-bone keys and bake back out.

### Route 1b — Layered Control Rig (additive player overlays)

For clips that should **layer on top of** Fortnite player locomotion (arm wave,
root scale giant/tiny), not replace the whole body:

1. Level Sequence → add **M_Medium_Base** (invisible mesh; bones are there).
2. **+ → Control Rig** → turn **Filter by Asset Skeleton OFF**, turn
   **Layered ON** → pick FX Control Rig or Body Rig.
3. Layered rigs store **deltas** (0 rotation / scale 1 = no change) and are
   non-destructive on top of another animation track.
4. Key everything first; move only the bones that should differ; bake
   (`bake_sequence_to_anim` or track → Bake Animation Sequence).
5. Flip additive so Verse overlays instead of replacing:

```
set_anim_additive_type({"anim_paths": ["/YourProject/Anims/AS_ArmUp"],
    "additive_type": "local_space"})
get_anim_sequence_info({"anim_path": "/YourProject/Anims/AS_ArmUp"})
```

Editor fallback: Asset Actions → Edit Selection in Property Matrix →
**Additive Anim Type → Local Space** → Save.

Play on the player with Verse `GetPlayAnimationController` — full device and
limits: `skill_read_subskill("animation", "player_animation")`.

## Route 2 — FBX / Mixamo import

- Mixamo export: **In Place checked**, **FBX With Skin**, **60 FPS**. Without
  In Place, root motion fights any Transform track you add later.
- First import: **Import All** creates the skeletal mesh plus the animation.
- More animations for a skeleton you already have: in the import dialog set the
  **target skeleton to the existing one** — otherwise you get a second, parallel
  skeleton and none of your clips interoperate.
- An imported clip is unusable on any other skeleton until retargeted:
  `skill_read_subskill("animation", "retargeting")`.

## Route 3 — AnimSequence bone keys (simple authored motion)

For waves, nods, idles, poses — directly on a skeleton, no Sequencer:

```
list_skeleton_bones({"skeletal_mesh_path": ".../SomeMesh"})        # exact bone names
create_anim_sequence({"skeletal_mesh_path": ".../SomeMesh",
    "dest_folder": "/MyProject/Anims", "name": "AS_Wave",
    "length_seconds": 1.5, "fps": 30})
set_anim_bone_keys({"anim_path": ".../AS_Wave",
    "bone": "Bip001-R-UpperArm", "keys": [
      {"time": 0.0, "rotation": [0,0,0]},
      {"time": 0.75, "rotation": [0,0,70]},
      {"time": 1.5, "rotation": [0,0,0]}]})
get_anim_sequence_info({"anim_path": ".../AS_Wave"})               # verify tracks
```

- Transforms are **bone-local** (relative to the parent bone) — key rotations on
  limb bones, not world positions.
- Sparse keys are fine: the tool resamples linearly to every frame (the raw
  engine call crashes on array-length mismatches; the tool guarantees safety).
- Complex full-body motion is still better retargeted or Control-Rig authored —
  hand-keying 20 bones rarely beats a converted clip.

## Route 4 — Verse prop animation (moving platforms, doors, hazards)

Fully code-authored at runtime, no editor assets, props only (transform, not
bones). Verify exact signatures via `search_verse_digest` / `get_verse_api`:

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

## Route 5 — Level Sequences (cutscenes, camera moves, choreography)

```
anim_author_capabilities({})                                       # probe
# FIRST: get_project_info() → content_root (e.g. /MyProject/)
create_level_sequence({"dest_folder": "/MyProject/Cinematics",
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
- **Playback is the Cinematic Sequence device** (see `runtime_playback`).

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

## Blending and moving during a clip

- Stack Animation tracks in Sequencer; drag the **top corner triangle of a clip**
  to crossfade instead of hard-cutting between them.
- Add a **Transform track** to move the actor while it animates. Key positions at
  the exact frames of contact events (takeoff, landing) — timing mismatch reads
  as foot sliding or teleporting.
- Physics-driven motion is NOT a Sequencer job (props pushed by Sequencer do not
  collide properly) — use the Prop Mover device instead.

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

## Pitfalls

| Symptom | Cause |
|---------|-------|
| Animation not offered on a mesh | Wrong skeleton — retarget it first |
| Baked clip has 3 s of nothing | Sequence playback range was not trimmed before baking |
| Imported Mixamo clip fights the Transform track | Exported without **In Place** |
| Control Rig track unusable after Bake to Control Rig | **Reduce Keys** was off — raw imports are key-dense |
| Limbs bend wrong after retarget | Retarget pose mismatch (A vs T) — fix the pose, not the chains |
| Authored animation never plays in game | No runtime trigger wired (`runtime_playback`) |
| Player overlay replaces walk instead of layering | Forgot Additive Local Space (`set_anim_additive_type`) or used a non-**Layered** Control Rig |
| Layered rig "edits" wipe the underlying dance | Filter/Layered toggles wrong — enable **Layered**, disable skeleton filter |
| Island fails to publish | Built on the experimental Verse Scene Graph animation API |
