"""Frame renderer (Pillow) + recording (GIF + command log)."""

from .record import Recorder
from .render import render

__all__ = ["Recorder", "render"]
