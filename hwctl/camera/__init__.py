"""CameraAPI protocol. Mirrored one-to-one as an MCP tool (`camera_capture`).

Backends: `hwctl.camera.sim` (renders the world snapshot), `hwctl.camera.cv`
(v0.5+, real overhead camera). See `docs/01-architecture.md`.
"""

from __future__ import annotations

from typing import Protocol

from hwctl.schemas import Image


class CameraAPI(Protocol):
    def capture(self) -> Image:
        """Capture one frame. PNG bytes + capture metadata."""
        ...
