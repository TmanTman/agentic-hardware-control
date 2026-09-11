"""World: breadboard geometry, tray, cartridges, harness, placement physics."""

from hwctl.world.geometry import col_at_offset, hole_offsets, nearest_hole, snap
from hwctl.world.netlist import build_deck
from hwctl.world.world import World

__all__ = ["World", "build_deck", "col_at_offset", "hole_offsets", "nearest_hole", "snap"]
