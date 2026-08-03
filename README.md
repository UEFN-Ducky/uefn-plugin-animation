# UEFN Animation

The whole UEFN skeletal-animation surface: IK retargeting with retarget-pose
(A-pose vs T-pose) fixes, skeleton sockets, Level Sequence / AnimSequence
authoring, Bake Animation Sequence, and Animated Mesh device playback. Bundles
the animation skill.

Desktop plugin for [UEFN-Ducky](https://github.com/UEFN-Ducky/UEFN-Ducky) (`animation`).
Install or update from **Settings → Store** in the app — do not install from a zip by hand.

## Layout

| Folder | What it is |
|--------|------------|
| `backend/` | MCP tools (`api.tool` → `api.listener`) |
| `listener/` | Unreal Python handlers, overlaid into `listener/plugins/animation/` on enable |
| `skills/animation/` | The skill + references the agent reads |

Both halves ship together, so tools and handlers update through the Store
without an app release. Requires app ≥ 1.0.655 (plugin listener overlay).

## Build

```bash
py scripts/build_zip.py
py backend/test_tools.py      # tool/manifest/listener wiring check
```

Writes `deploy/animation-1.1.0.ducky-plugin.zip` (scripts/ and deploy/ are not packed).
