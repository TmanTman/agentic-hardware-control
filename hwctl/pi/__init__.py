"""PiAPI: GPIO control (docs/01-architecture.md).

v0.1 is in-process (`hwctl.pi.sim.SimPi`); v0.3 puts the same surface behind
FastAPI so the sim and a real Pi run the same container.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from hwctl.schemas import PinMode, PinState

__all__ = ["PiAPI", "PinMode", "PinState"]


@runtime_checkable
class PiAPI(Protocol):
    def pins(self) -> list[PinState]:
        """Every harness-connected GPIO."""
        ...

    def set_mode(self, gpio: int, mode: PinMode) -> PinState:
        """Make a pin an input or an output."""
        ...

    def set_level(self, gpio: int, level: int) -> PinState:
        """Drive an output pin 0 or 1."""
        ...

    def get_pin(self, gpio: int) -> PinState:
        """Read one pin; inputs report the sampled level."""
        ...
