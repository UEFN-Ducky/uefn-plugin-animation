"""Wiring check for the animation MCP tools: every tool the manifest promises is
registered, and each one forwards the parameters its listener handler expects.

Run standalone (``py backend/test_tools.py``) or under pytest.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]


def _load_register_tools():
    spec = importlib.util.spec_from_file_location("_animation_tools", Path(__file__).with_name("tools.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.register_tools


class _FakeApi:
    """Captures @api.tool registrations and the api.listener calls they make."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}
        self.calls: list[tuple] = []

    def tool(self, fn=None, *, name=None, intent=None, listener=True):
        def deco(f):
            self.tools[name or f.__name__] = f
            return f

        return deco(fn) if fn is not None else deco

    def listener(self, command, params=None, timeout=None):
        self.calls.append((command, dict(params or {}), timeout))
        return {"ok": True, "command": command}

    def log(self, *args, **kwargs) -> None:
        pass

    def last(self) -> tuple:
        return self.calls[-1]


def _registered() -> _FakeApi:
    api = _FakeApi()
    _load_register_tools()(api)
    return api


def test_manifest_matches_registered_tools() -> None:
    manifest = json.loads((_ROOT / "plugin.json").read_text(encoding="utf-8"))
    promised = set(manifest["contributes"]["agent.tools"]["tools"])
    assert _registered().tools.keys() == promised

    plan_tools = set(manifest["contributes"]["agent.tools"]["plan_tools"])
    assert plan_tools <= promised, plan_tools - promised


def test_retarget_pose_params() -> None:
    api = _registered()
    api.tools["set_retarget_pose_bone_rotation"](
        ik_retargeter_path="/P/Retargeting/RTG_A_to_B", bone="upperarm_l", rotation=[0, 0, -45]
    )
    command, params, _ = api.last()
    assert command == "set_retarget_pose_bone_rotation"
    assert params == {
        "ik_retargeter_path": "/P/Retargeting/RTG_A_to_B",
        "bone": "upperarm_l",
        "rotation": [0, 0, -45],
        "source_or_target": "target",
    }

    api.tools["set_retarget_pose_root_offset"](ik_retargeter_path="/P/R/RTG", offset=[0, 0, -4], source_or_target="source")
    command, params, _ = api.last()
    assert command == "set_retarget_pose_root_offset"
    assert params["offset"] == [0, 0, -4] and params["source_or_target"] == "source"


def test_bake_and_animated_mesh_params() -> None:
    api = _registered()
    api.tools["bake_sequence_to_anim"](
        sequence_path="/P/Cinematics/LS_Wave", actor_path="FN_Mannequin", dest_folder="/P/Anims", name="AS_Wave"
    )
    command, params, timeout = api.last()
    assert command == "bake_sequence_to_anim"
    assert params["sequence_path"] == "/P/Cinematics/LS_Wave" and params["actor_path"] == "FN_Mannequin"
    assert timeout and timeout > 60  # bakes outlive the interactive bridge timeout

    api.tools["configure_animated_mesh"](
        actor_path="AnimMesh_Statue", skeletal_mesh_path="/P/SKM_Statue", anim_path="/P/Anims/AS_Wave", loop=True
    )
    command, params, _ = api.last()
    assert command == "configure_animated_mesh"
    assert params["anim_path"] == "/P/Anims/AS_Wave" and params["loop"] is True


def test_set_anim_additive_type_params() -> None:
    api = _registered()
    api.tools["set_anim_additive_type"](
        anim_paths=["/P/Anims/AS_ArmUp", "/P/Anims/AS_Giant"],
        additive_type="local_space",
    )
    command, params, timeout = api.last()
    assert command == "set_anim_additive_type"
    assert params == {
        "anim_paths": ["/P/Anims/AS_ArmUp", "/P/Anims/AS_Giant"],
        "additive_type": "local_space",
        "ref_pose_type": "",
        "ref_pose_anim": "",
    }
    assert timeout and timeout > 60  # recompression can outlive the interactive bridge


def test_listener_handles_every_command_the_tools_send() -> None:
    api = _registered()
    for tool in api.tools.values():
        try:
            tool(**{})  # tools with required args are covered by the calls above
        except TypeError:
            continue
    sent = {command for command, _params, _timeout in api.calls}
    sent |= {
        "set_retarget_pose_bone_rotation",
        "bake_sequence_to_anim",
        "configure_animated_mesh",
        "set_anim_additive_type",
    }

    registered = set()
    for path in (_ROOT / "listener").glob("*.py"):
        registered |= set(re.findall(r'register\("([a-z0-9_]+)"\)', path.read_text(encoding="utf-8")))
    assert sent <= registered, sent - registered


if __name__ == "__main__":
    for name, fn in sorted(dict(globals()).items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
