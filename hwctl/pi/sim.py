"""Simulated Pi: GPIO pins wired straight into the world's circuit model."""

from __future__ import annotations

from hwctl.schemas import PinMode, PinState
from hwctl.world import World


class SimPi:
    """In-process PiAPI backend (v0.3 puts the same surface behind HTTP)."""

    def __init__(self, world: World) -> None:
        self.world = world

    def pins(self) -> list[PinState]:
        return self.world.pins()

    def set_mode(self, gpio: int, mode: PinMode) -> PinState:
        return self.world.set_pin_mode(gpio, mode)

    def set_level(self, gpio: int, level: int) -> PinState:
        return self.world.set_pin_level(gpio, level)

    def get_pin(self, gpio: int) -> PinState:
        return self.world.get_pin(gpio)
