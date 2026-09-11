"""Simulated camera: renders the current world snapshot to PNG bytes.

Does not import `hwctl.world` -- it is handed a zero-argument snapshot
callable so `hwctl.world` (or a test double) can supply state without this
module depending on it.
"""

from __future__ import annotations

import io
import time
from collections.abc import Callable

from hwctl.schemas import CartridgeSpec, Image, WorldSnapshot
from hwctl.viz.render import render


class SimCamera:
    """`CameraAPI` backend that renders `snapshot_fn()` on `capture()`."""

    def __init__(
        self,
        snapshot_fn: Callable[[], WorldSnapshot],
        cartridges: dict[str, CartridgeSpec],
        *,
        px_per_mm: float = 4.0,
    ) -> None:
        self.snapshot_fn = snapshot_fn
        self.cartridges = cartridges
        self.px_per_mm = px_per_mm

    def capture(self) -> Image:
        snap = self.snapshot_fn()
        img = render(snap, self.cartridges, px_per_mm=self.px_per_mm)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png = buf.getvalue()
        return Image(png=png, width=img.width, height=img.height, t=time.time(), note="sim")
