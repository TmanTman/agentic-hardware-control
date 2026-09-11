"""Simulated arm: perfect motion, all physics delegated to `World`."""

from __future__ import annotations

from hwctl.schemas import ArmStatus, CartridgeRef
from hwctl.world import World


class SimArm:
    """A flawless pick-and-place head over the simulated workspace."""

    def __init__(self, world: World) -> None:
        self.world = world
        self.x_mm = 0.0
        self.y_mm = 0.0
        self.lifted = True
        self.gripper = "open"
        self.held: CartridgeRef | None = None

    # ------------------------------------------------------------ helpers

    def _status(self, event: str | None = None, error: str | None = None) -> ArmStatus:
        return ArmStatus(
            x_mm=self.x_mm,
            y_mm=self.y_mm,
            lifted=self.lifted,
            gripper=self.gripper,  # type: ignore[arg-type]
            held=self.held.model_copy() if self.held else None,
            event=event,  # type: ignore[arg-type]
            error=error,
        )

    # ------------------------------------------------------------ ArmAPI

    def move_to(self, x_mm: float, y_mm: float) -> ArmStatus:
        if not self.lifted:
            return self._status(error="lower: raise before moving")
        self.x_mm, self.y_mm = float(x_mm), float(y_mm)
        self.world.move_held(self.x_mm, self.y_mm)
        return self._status(event="moved")

    def lower(self) -> ArmStatus:
        self.lifted = False
        return self._status(event="lowered")

    def raise_(self) -> ArmStatus:
        self.lifted = True
        return self._status(event="raised")

    def close_gripper(self) -> ArmStatus:
        self.gripper = "closed"
        if self.lifted or self.held is not None:
            return self._status()
        result, ref = self.world.try_pick(self.x_mm, self.y_mm)
        if result == "picked" and ref is not None:
            self.held = ref
            self.world.move_held(self.x_mm, self.y_mm)
            return self._status(event="picked")
        return self._status(event="empty")

    def open_gripper(self) -> ArmStatus:
        if self.held is None:
            self.gripper = "open"
            return self._status()

        if self.lifted:
            ref, self.held = self.held, None
            self.gripper = "open"
            self.world.drop(ref, self.x_mm, self.y_mm)
            return self._status(event="dropped")

        ref = self.held
        result, _holes = self.world.try_place(ref, self.x_mm, self.y_mm)
        if result == "blocked":
            return self._status(event="blocked", error="blocked: a hole is already occupied")
        self.held = None
        self.gripper = "open"
        if result == "misaligned":
            return self._status(event="misaligned", error="misaligned: pins are not over holes")
        return self._status(event="inserted")

    def status(self) -> ArmStatus:
        return self._status()
