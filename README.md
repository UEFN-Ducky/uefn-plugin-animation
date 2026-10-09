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

## Next release: ship compiled

This plugin still ships its Python source on the Store. Its next release has to ship compiled and signed, the way Ducky Account and Roguelike do:

1. Give `scripts/release.py` and `scripts/build_zip.py` the compiled build from `uefn-plugin-account` (`build_compiled_zip`, upload by ticket, `--plain` only as an escape hatch).
2. Bump `version` and set `min_app_version` to `1.2.357` or newer (the Store keeps older apps from seeing it).
3. Publish, then check the download with the start-up license check (signature, id and version, compiled, team access), not only the signature.
4. A compiled build can't `importlib.reload` its own modules (Python raises SystemError), so reload only when running from source. Before publishing, install the source and compiled zips into a throwaway Ducky and check they register the same panel calls, tools and workflow nodes, and that those calls still work after the plugin reloads.

For this plugin:

- `listener/` runs in UEFN's own Python and stays readable source; only the Ducky-side backend compiles.

Remove this section once a compiled version is live.

## License

MIT. Copyright (c) 2026 Mindful Path Company, LLC. See [LICENSE](LICENSE).
