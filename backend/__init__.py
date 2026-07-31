"""Animation — Store desktop plugin (gates core tool modules)."""

from __future__ import annotations


def register(api) -> None:
    """Import gated MCP tools onto the shared FastMCP instance."""
    import backend.tools.animation.animation_retarget  # noqa: F401
    import backend.tools.animation.sequencer  # noqa: F401
    api.log("animation tools registered")
