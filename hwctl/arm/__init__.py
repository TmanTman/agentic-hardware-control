"""ArmAPI: the pick-and-place contract (docs/01-architecture.md).

Backends: `sim` (this milestone), `gcode` (v0.7), `human` (v0.6). No call
raises across the API -- problems come back in `ArmStatus.error`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from hwctl.schemas import ArmStatus

__all__ = ["ArmAPI", "ArmStatus"]


@runtime_checkable
class ArmAPI(Protocol):
    def move_to(self, x_mm: float, y_mm: float) -> ArmStatus:
        """XY move; only legal while lifted."""
        ...

    def lower(self) -> ArmStatus:
        """Lift down, to tray or board contact."""
        ...

    def raise_(self) -> ArmStatus:
        """Lift up."""
        ...

    def open_gripper(self) -> ArmStatus:
        """Release the held cartridge; inserts it when its pins are over holes."""
        ...

    def close_gripper(self) -> ArmStatus:
        """Grab whatever cartridge is under the gripper, if any."""
        ...

    def status(self) -> ArmStatus:
        """Current pose, gripper and held cartridge."""
        ...
