"""A Session wires the sim devices together and records every device call.

Used by the scripted demo, the MCP server, and the headless orchestrator so all
three produce the same `recordings/<version>/` layout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hwctl.arm.sim import SimArm
from hwctl.camera.sim import SimCamera
from hwctl.config import load_workspace
from hwctl.pi.sim import SimPi
from hwctl.schemas import Image, Observation, Workspace, WorldSnapshot
from hwctl.viz.record import Recorder
from hwctl.world import World


class Session:
    def __init__(
        self,
        workspace: Workspace | None = None,
        record_dir: str | Path | None = None,
        name: str = "run",
        *,
        fps: float = 2.0,
    ) -> None:
        self.ws = workspace or load_workspace()
        self.world = World(self.ws)
        self.arm = SimArm(self.world)
        self.pi = SimPi(self.world)
        self.camera = SimCamera(self.snapshot, self.ws.cartridges)
        self.recorder = Recorder(record_dir, name, fps=fps) if record_dir else None
        self._devices: dict[str, Any] = {"arm": self.arm, "pi": self.pi, "camera": self.camera}

    # ------------------------------------------------------------------ state

    def snapshot(self, caption: str = "") -> WorldSnapshot:
        return self.world.snapshot(self.arm.status(), caption)

    def observe(self) -> Observation:
        return self.world.observe()

    # ------------------------------------------------------------------ calls

    def call(self, device: str, method: str, **args: Any) -> Any:
        """Invoke `device.method(**args)`, record it with a frame, return the result."""
        if device == "observe":
            result = self.observe()
        elif device == "workspace":
            result = self.ws
        else:
            result = getattr(self._devices[device], method)(**args)
        if self.recorder is not None:
            arg_text = ", ".join(f"{k}={v}" for k, v in args.items())
            caption = f"{device}.{method}({arg_text})"
            snap = None if device == "workspace" else self.snapshot(caption)
            logged = result
            if isinstance(result, Image):
                logged = {"width": result.width, "height": result.height, "bytes": len(result.png)}
            elif isinstance(result, Workspace):
                logged = "workspace"
            self.recorder.record(device, method, args, logged, snap, self.ws.cartridges)
        return result

    def hold(self, caption: str, frames: int = 2) -> None:
        """Add a few identical frames so a state is visible in the GIF."""
        if self.recorder is not None:
            snap = self.snapshot(caption)
            for _ in range(frames):
                self.recorder.frame(snap, self.ws.cartridges)

    def close(self) -> Path | None:
        return self.recorder.close() if self.recorder is not None else None
