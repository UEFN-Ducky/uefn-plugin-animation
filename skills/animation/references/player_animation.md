---
description: "Play custom AnimSequences on the PLAYER character via fort_character.GetPlayAnimationController — full override or additive overlay (Layered Control Rig + AdditiveAnimType Local Space), with stasis, teleport, blend times, and hard limits"
metadata:
  label: "Player animation"
  default_enabled: false
  load_condition: "Playing a custom animation on the player character, additive/overlay player anims, GetPlayAnimationController, Layered Control Rig, AdditiveAnimType Local Space, player stasis during a clip, giant/tiny player, weapon inspect, or melee on the player"
---

# Player animation — anim controller + additive overlay

> **Snippets here are fragments.** The `using` block in this file's first code
> block applies to all of them — copy those imports (or start from the matching
> `verse_template_apply` pack) when pasting into a real `.verse` file.

Players are not Animated Mesh devices. As of the Play Animation Controller
shipping for players, you play clips through Verse on `fort_character` — no
player reference prop, no chair device.

Confirm signatures with `search_verse_digest` / `get_verse_api` before shipping —
names evolve. Module: `/Fortnite.com/Animation/PlayAnimation`.

## Full override vs additive overlay

Same Verse call either way. The **only** difference is the AnimSequence asset:

| Clip setting | What the player sees |
|--------------|----------------------|
| Additive Anim Type = **No Additive** (default) | Clip **replaces** Fortnite body animation |
| Additive Anim Type = **Local Space** | Clip **layers on top of** Fortnite locomotion (arms, scale, deltas) |

Flip it with MCP:

```
set_anim_additive_type({"anim_paths": ["/YourProject/Anims/AS_ArmUp"],
    "additive_type": "local_space"})
get_anim_sequence_info({"anim_path": "/YourProject/Anims/AS_ArmUp"})   # verify additive_anim_type
```

Editor fallback (Property Matrix exposes a field the Details panel hides):
Content Drawer → select AnimSequence(s) → right-click → **Asset Actions →
Edit Selection in Property Matrix** → **Additive Anim Type → Local Space** → Save.

Without that flip, an "arm wave" clip still overrides the whole body.

## The Verse device (override or additive)

```verse
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/Diagnostics }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Animation/PlayAnimation }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /Fortnite.com/Playspaces }
using { /Verse.org/Assets }

# Clip identifier comes from Assets.digest after a successful Verse compile.
# Path Content/Animations/SillyDance1 → Animations.SillyDance1 (project mount).
player_anim_device := class(creative_device):

    @editable
    Trigger : trigger_device = trigger_device{}

    # Point this at your retargeted / baked AnimSequence in Details.
    @editable
    Clip : animation_sequence = external {}

    OnBegin<override>()<suspends>:void =
        Trigger.TriggeredEvent.Subscribe(OnTriggered)

    OnTriggered(MaybeAgent : ?agent):void =
        if (Agent := MaybeAgent?):
            spawn{ PlayOnAgent(Agent) }

    PlayOnAgent(Agent : agent)<suspends>:void =
        if:
            FortCharacter := Agent.GetFortCharacter[]
            AnimController := FortCharacter.GetPlayAnimationController[]
        then:
            # Hold the INSTANCE — do not re-fetch the controller to Stop.
            Instance := AnimController.Play(
                Clip,
                ?BlendInTime := 0.25,
                ?BlendOutTime := 0.25,
                ?PlayRate := 1.0
                # ?PlayCount := 1.0
                # ?StartPositionSeconds := 0.0
            )
            Result := Instance.Await()   # Completed | Interrupted | Error
            # Or: Instance.Stop() after Sleep(...), or PlayAndAwait(Clip, ...)
```

`Play` returns `play_animation_instance` immediately. Prefer `Instance.Await()` /
`PlayAndAwait` over "Sleep then re-get controller and Stop" — the instance is
the handle for `Stop`, `IsPlaying[]`, `CompletedEvent`, `InterruptedEvent`,
`BlendedInEvent`, `BlendingOutEvent`.

Optional named args on `Play` / `PlayAndAwait`:

| Arg | Meaning |
|-----|---------|
| `?BlendInTime` / `?BlendOutTime` | Seconds — snappy clips still want a short blend |
| `?PlayRate` | Speed; useful if you scale playback with movement |
| `?PlayCount` | How many times to play |
| `?StartPositionSeconds` | Start mid-clip |

Place the device, wire the trigger in Details, launch a session, walk onto the
trigger. Compile Verse first or the Assets digest identifier / `@editable`
`animation_sequence` slot will look broken.

## Stasis (freeze the player for the clip)

For dances / cutscenes where the player must not walk away:

```verse
PlayOnAgent(Agent : agent)<suspends>:void =
    if:
        FortCharacter := Agent.GetFortCharacter[]
        AnimController := FortCharacter.GetPlayAnimationController[]
    then:
        FortCharacter.PutInStasis(
            stasis_args{
                AllowEmotes := false
                AllowTurning := false
                AllowFalling := false
            }
        )
        Instance := AnimController.Play(Clip, ?BlendInTime := 0.25, ?BlendOutTime := 0.25)
        Instance.Await()
        # Always release on every exit path (Await returns on Interrupted/Error too).
        FortCharacter.ReleaseFromStasis()
```

Verse has no `defer`. If you `race` the play against a cancel event, call
`ReleaseFromStasis()` in **every** branch that leaves the freeze, or the player
stays locked.

## Teleport (frame the player for a cutscene)

```verse
@editable
TeleportLocation : vector3 = vector3{}

@editable
YawDegrees : float = 0.0
@editable
PitchDegrees : float = 0.0
@editable
RollDegrees : float = 0.0

# Inside PlayOnAgent, before Play:
if (FortCharacter.TeleportTo[TeleportLocation, MakeRotationFromYawPitchRollDegrees(YawDegrees, PitchDegrees, RollDegrees)]):
```

`TeleportTo` is `<decides>` — put it in an `if`. Place the XYZ carefully (under
the floor is a common first-try miss). Useful with stasis + a full-override clip
for scripted beats.

## Assets digest — why the clip name is "undefined"

Every AnimSequence under your project Content is exposed to Verse through
`Assets.digest.verse` after a **successful** Verse compile:

1. Clip lives under a Content folder (e.g. `Animations/SillyDance1`).
2. `using { /Verse.org/Assets }` in the device file.
3. Fix any Verse errors, then compile — the identifier appears
   (`Animations.SillyDance1` or whatever the folder path maps to).
4. Or skip the bare identifier and assign the clip on an
   `@editable Clip : animation_sequence` in the device Details panel.

A broken Verse build is the usual reason the name never shows up.

## Authoring an additive overlay (Layered Control Rig)

Pipeline:

1. Content Drawer → **Cinematics → Level Sequence**. Open it.
2. Place / find **M_Medium_Base** (Fortnite player skeleton — invisible mesh,
   bones are there). Add it to the sequence (Add → track for that skeletal mesh).
3. Optional: delete the default Animation track.
4. **+ → Control Rig**. Turn **Filter by Asset Skeleton OFF**, turn
   **Layered ON**, then pick **FX Control Rig** (bones visible) or **Body Rig**.
5. Layered Control Rigs are **naturally additive** and non-destructive: values
   are deltas from the underlying pose. Rotation/translation **0** and scale
   **1** mean "no change". Editing a layered rig on top of a dance clip does
   not rewrite the dance.
6. Key everything at the start. Move **only** the bones you want to overlay
   (e.g. raise an arm for a wave, scale root for giant/tiny). Key the return.
7. Right-click the skeleton track → **Bake Animation Sequence**. Save.
8. Flip additive: `set_anim_additive_type({"anim_paths": [".../AS_ArmUp"],
   "additive_type": "local_space"})` (or Property Matrix → Local Space).
9. Play with the Verse device above — Fortnite walk/run continues underneath.

### Giant / tiny / horror proportions

Same pipeline: key **root** (or pelvis / arms / head) **scale** on the layered
rig, bake, set Local Space, play. Visual only — see Limits.

### Getting Fortnite Control Rigs into a project

Open / create an **Animation template** project → Content Drawer → **Fortnite**
folder → migrate the Control Rig assets into your island project. Makes Body /
FX layered rigs available without hunting.

### Mixamo / FBX full-body clips (usually override)

1. Mixamo: mannequin + clip, download (In Place if you will add a Transform
   track later).
2. Import onto the Mixamo skeleton; **Retarget Animations** → source Mixamo,
   target **M_Medium_Base** → export.
3. Play via the Verse device. Leave Additive = No Additive for a full dance
   takeover; set Local Space only if the clip was authored as a delta overlay.

Retarget details: `skill_read_subskill("animation", "retargeting")`.

## Hard limits (do not paper over these)

- **No per-bone weight blending** between your clip and Fortnite's. You cannot
  say "this bone 100% custom, that bone 100% Fortnite" — wait for Scene Graph
  skeletal editing / mover work.
- **Emoting or firing a weapon resets** the anim controller back to default
  Fortnite animations. Design around it (stasis with `AllowEmotes := false`,
  short clips, or accept the reset).
- **Root / bone scale is visual only.** Hitboxes do not grow or shrink with a
  giant/tiny overlay.
- **Without Local Space**, the clip fully overrides locomotion — that is
  correct for dances, wrong for arm overlays.
- Confirm `GetPlayAnimationController` on this build before promising the
  feature — it was guards/NPCs only for a long time; players are recent.

## Use cases this unlocks

Weapon inspect, melee / punch, immersive interact poses, giant/tiny power-ups,
horror silhouette twists, short emote-like moments without the Emote wheel —
all on the real player character while (for additive) they keep walking.

## Failure table

| Symptom | Cause |
|---------|-------|
| Clip replaces walk instead of overlaying | Additive Anim Type still No Additive — run `set_anim_additive_type` / Property Matrix Local Space |
| Verse can't see the clip name | Assets digest stale — fix Verse errors, compile |
| `GetPlayAnimationController` fails | No `fort_character`, or build predates player support — confirm digest |
| Player stuck after clip | Forgot `ReleaseFromStasis` on an Interrupted / Error / race exit |
| Overlay snaps off mid-play | Player emoted or fired — controller reset (known limit) |
| Giant/tiny looks right but collisions wrong | Scale is visual only — hitboxes unchanged |
| Layered rig edits overwrite the dance | Used a non-layered Control Rig — enable **Layered** when adding the rig |
| Property Matrix / tool can't set additive | UEFN build missing the enum — `anim_author_capabilities` → `additive_route`; use the UI hint in the tool response |
