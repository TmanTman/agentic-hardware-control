"""Workspace loading and backend selection.

`configs/workspace.yaml` is the single source of truth for the "known
positions" (board geometry, harness, tray, cartridge specs). This module turns
it into the `Workspace` pydantic model from `hwctl.schemas`.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from hwctl.schemas import BoardGeometry, CartridgeSpec, GpioModel, TraySlot, Workspace

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = REPO_ROOT / "configs" / "workspace.yaml"


def backend() -> str:
    """Device backend selector: sim | real | human."""
    return os.environ.get("HWCTL_BACKEND", "sim")


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]  # type: ignore[union-attr]


def load_workspace(path: str | Path | None = None) -> Workspace:
    """Load and normalise `configs/workspace.yaml` (or another path)."""
    p = Path(path) if path is not None else DEFAULT_WORKSPACE
    raw = yaml.safe_load(p.read_text())

    board = BoardGeometry(**raw["board"])
    gpio_model = GpioModel(**raw.get("gpio_model", {}))

    # yaml allows `GPIO17: R5L` as well as `GND: [A, B]`; normalise to lists.
    harness = {k: _as_list(v) for k, v in raw.get("harness", {}).items()}

    tray_raw = raw.get("tray", {}) or {}
    tray_y = float(tray_raw.get("y_mm", 0.0))
    tray = [
        TraySlot(
            id=int(s["id"]),
            x_mm=float(s["x_mm"]),
            y_mm=float(s.get("y_mm", tray_y)),
            cartridge=s.get("cartridge"),
        )
        for s in tray_raw.get("slots", [])
    ]

    cartridges = {
        name: CartridgeSpec(
            type=name,
            pins=[tuple(pin) for pin in spec["pins"]],  # type: ignore[misc]
            spice=spec["spice"],
            pin_names=spec.get("pin_names"),
        )
        for name, spec in raw.get("cartridges", {}).items()
    }

    return Workspace(
        board=board,
        harness=harness,
        gpio_model=gpio_model,
        tray=tray,
        cartridges=cartridges,
        spice_models=list(raw.get("spice_models", [])),
    )
