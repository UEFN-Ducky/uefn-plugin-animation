---
description: "Multi-species NPC ecosystems — session registries, FSMs, play-dead/downed, same-module clips. Agent writes original Verse. Zero human wiring."
metadata:
  label: "NPC ecosystems (multi-species)"
  default_enabled: false
  load_condition: "Building two-species or NPC-to-NPC ecosystems (cats/dogs/creatures that see each other), play-dead, downed registries, or autonomous wander/follow/flee/hunt"
---

# Multi-species NPC ecosystems

You **write** the Verse for *this* island. The user names the fantasy
("cats flee a dog, play dead on catch"). You load this file, invent class
names that fit the project, and program it. Do not paste a 700-line example
into chat. Do not ask the user to hook anything.

Asset authoring (mesh → preset → BP → NPCDef → spawner) is
`skill_read_subskill("animation", "npc_characters")`.
Behavior skeleton APIs: `skill_read_subskill("verse", "sys_npc_ai")`.

Default: `verse_template_apply("npc_core")` → `Verse/NPCCore/`, then customize
class names and swap Sleep fallbacks for `Play(AS_…)`. Do not invent a parallel
prey/hunter folder. Do not `verse_template_apply("npc_ecosystem")` unless the
user asked for that exact cat+dog pack.

---

## What to build (you invent the names)

Two (or more) species in one Verse module folder. Each NPC self-registers in
`OnBegin` into a `weak_map(session, []agent)` and unregisters in `OnEnd`.
Typical loop: wander → notice player → notice peer → notice the other species →
on catch, play a one-shot then mark downed so the hunter picks someone else.
No device graph between species — the handshake is the session registries.

Place behaviors **next to duplicated react clips** so clip ids compile as
same-module `animation_sequence`. You pick the filenames (`AS_<Species>React_*`).
`duplicate_asset` them there **before** the first compile.

---

## Same-module clips (you write the references)

`set_verse_editable` cannot reach NPCDef VerseBehavior slots. Do not ask a
human to fill Details.

Duplicate Idle/Attack/Die clips into the behavior folder, then in the class
**you author** reference those identifiers directly (`Play(AS_MyReact_Die, …)`).
If the pack has no bite clip, duplicate an excited/play idle under a name you
choose.

---

## Session registries (pattern — you type it)

```
var ActivePreyAgents : weak_map(session, []agent) = map{}
var ActiveHunterAgents : weak_map(session, []agent) = map{}
var DownedAgents : weak_map(session, []agent) = map{}
var DownedUntilTimes : weak_map(session, []float) = map{}
```

Session maps only. Never this pattern on persist `weak_map(player, …)`.

Downed state is two parallel arrays. Rebuild both and re-`set`.

### `no_rollback effect not allowed`

Do not read a `weak_map` inside `<transacts>`. Fetch arrays in a `void` context,
pass them into a pure checker:

```
IsDownedInLists<public>(Agent, Now, Agents, Untils)<transacts> : logic = …
DownedAgents := GetDownedAgents()
DownedUntils := GetDownedUntilTimes()
Downed := IsDownedInLists(Other, Now, DownedAgents, DownedUntils)
```

---

## FSM + pre-emption (pattern — you write the states)

`race{}` the action with `WaitWhileState(X)` that polls `CurrentState` (~0.15 s).
That pre-empts `NavigateTo` without cancellation plumbing.

`StateLocked` on one-shots (flee / greet / play-dead) so the sense loop cannot
stomp mid-clip.

`OnBegin` must succeed the full `if:` chain (`GetAgent`, `GetFortCharacter`,
`GetNavigatable`, `GetFocusInterface`, `GetPlayAnimationController`) or the NPC
never registers. `OnEnd` unregisters.

Anti-bugs worth keeping when you write hunt/flee:

1. Flee without jump spam.
2. After a catch, hunt **excluding** the one you just downed. The caught NPC
   ignores hunters briefly so it does not flee-spam.

---

## Spawn controller (you write it)

A `creative_device` with `@editable` `npc_spawner_device` slots. Spawn on begin
after a player exists (retry if `GetPlayers()` is empty). Wire with
`wire_verse_device_ref` after compile — you, not Details.

Give the hunter runway (~1500–2000 units from the prey cluster).

---

## Traps

| Symptom | Cause | Fix |
|---------|-------|-----|
| T-pose / slide | no Physics Asset | `create_physics_asset_for_mesh` |
| Fortnite skin | CosmeticSpawn ≠ `CHARACTER_BLUEPRINT` | `create_npc_character_definition` |
| Moves, no anim | not `ANIMATION_PRESET` / mixed Skeleton | preset + modifier |
| `no_rollback effect not allowed` | `weak_map` inside `<transacts>` | fetch lists first |
| Clip id will not compile | asset not in this module folder | `duplicate_asset` next to `.verse` |
| Species never see each other | `OnBegin` if-chain failed / no navmesh | walkable geo + physics |
| Asking the user to hook anims | **hard-rule violation** | you write the refs |

Never tell the user to open Details. Never paste someone else's island as the
deliverable — program this one.
