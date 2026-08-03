"""Animation — Store desktop plugin.

Owns its MCP tools (``tools.py``) and the Unreal Python handlers they call
(``listener/``), so retargeting / authoring / playback ship through the Store
instead of an app release.
"""

from __future__ import annotations

from typing import Any


def register(api: Any) -> None:
    from .tools import register_tools

    register_tools(api)
    api.log("animation tools registered")
