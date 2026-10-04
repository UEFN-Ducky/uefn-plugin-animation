"""The listener overlay imports the way the host loads it: as ``listener.plugins.animation``.

Deploy copies ``listener/`` into the host's ``listener/plugins/animation/``. A
plugin-local module imported as ``listener.<name>`` resolves against the HOST
package, fails, and takes every animation command down with it — the host only
logs ``plugin listener load failed (animation)``.
"""

from __future__ import annotations

import importlib
import shutil
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_OVERLAY = Path(__file__).resolve().parents[1] / "listener"


def _stub(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


@pytest.fixture
def host(tmp_path, monkeypatch):
    """A minimal host ``listener`` package with the overlay deployed under plugins/."""
    pkg = tmp_path / "listener"
    shutil.copytree(_OVERLAY, pkg / "plugins" / "animation", ignore=shutil.ignore_patterns("__pycache__"))
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "plugins" / "__init__.py").write_text("", encoding="utf-8")

    registered: list[str] = []

    def register(name):
        def deco(fn):
            registered.append(name)
            return fn

        return deco

    for name in [m for m in sys.modules if m == "listener" or m.startswith("listener.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "unreal", MagicMock(name="unreal"))
    # Host modules the overlay is allowed to import as ``listener.<name>``.
    for name, attrs in {
        "listener.dispatch": {"register": register},
        "listener.project_paths": {"pin_project_folder": lambda *a, **k: None},
        "listener.save_coalesce": {"request_level_save": lambda: None},
        "listener.serialize": {"rotator_pyr": lambda *a, **k: None},
        "listener.tick": {"register_heavy": lambda name: None},
        "listener.lookup": {"require_actor": lambda *a, **k: None},
    }.items():
        monkeypatch.setitem(sys.modules, name, _stub(name, **attrs))
    monkeypatch.syspath_prepend(str(tmp_path))
    return registered


def test_overlay_imports_as_host_plugin_package(host):
    importlib.import_module("listener.plugins.animation")
    assert "set_npc_definition_behavior" in host  # npc_author
    assert "configure_animated_mesh" in host  # animated_mesh
