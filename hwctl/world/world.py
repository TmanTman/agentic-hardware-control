"""The physics: breadboard, tray, cartridges, harness, and the circuit it makes.

Nothing above the device APIs may import this module. The arm calls
`try_pick`/`try_place`; the Pi calls `set_pin_*`/`get_pin`; the camera and the
renderer call `snapshot()`.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from hwctl import circuit as circuit_pkg
from hwctl.schemas import (
    ArmStatus,
    CartridgeRef,
    CircuitResult,
    HoleRef,
    LedState,
    Observation,
    PickResult,
    PinState,
    PlacedCartridge,
    PlaceResult,
    TraySlot,
    Workspace,
    WorldSnapshot,
)
from hwctl.world.geometry import nearest_hole
from hwctl.world.netlist import build_deck, element_name

LED_ON_MA = 1.0
"""An LED counts as lit above 1 mA forward (docs/01-architecture.md)."""

Solver = Callable[[str], circuit_pkg.Solution]


class World:
    """Mutable ground truth. One instance per run."""

    def __init__(self, workspace: Workspace, solver: Solver | None = None) -> None:
        self.ws = workspace
        self._solver: Solver = solver or circuit_pkg.solve
        self._cache: dict[str, CircuitResult] = {}

        self._tray: list[TraySlot] = [slot.model_copy() for slot in workspace.tray]
        self._cartridges: list[PlacedCartridge] = [
            PlacedCartridge(
                ref=CartridgeRef(id=f"c{slot.id}", type=slot.cartridge),
                state="tray",
                x_mm=slot.x_mm,
                y_mm=slot.y_mm,
            )
            for slot in self._tray
            if slot.cartridge is not None
        ]
        self._occupied: dict[tuple[int, str], str] = {}
        self._slot_of: dict[str, int] = {f"c{slot.id}": slot.id for slot in self._tray}

        self._pins: dict[int, PinState] = {}
        for key, nets in workspace.harness.items():
            if key.upper().startswith("GPIO") and key[4:].isdigit():
                gpio = int(key[4:])
                self._pins[gpio] = PinState(
                    gpio=gpio, mode="in", level=0, net=nets[0] if nets else None
                )

    # ------------------------------------------------------------ inventory

    def cartridges(self) -> list[PlacedCartridge]:
        return [c.model_copy(deep=True) for c in self._cartridges]

    def tray(self) -> list[TraySlot]:
        return [s.model_copy() for s in self._tray]

    def find(self, cartridge_id: str) -> PlacedCartridge | None:
        for c in self._cartridges:
            if c.ref.id == cartridge_id:
                return c
        return None

    # ------------------------------------------------------------ geometry

    def nearest_hole(self, x_mm: float, y_mm: float) -> tuple[HoleRef, float] | None:
        """Nearest hole centre and distance in mm, or None if x is off the board."""
        return nearest_hole(self.ws, x_mm, y_mm)

    def _pin_holes(self, ref: CartridgeRef, x_mm: float, y_mm: float) -> list[HoleRef] | None:
        """Holes each pin would land in, or None if any pin misses by > tolerance."""
        spec = self.ws.cartridges[ref.type]
        p = self.ws.board.pitch_mm
        tol = self.ws.board.placement_tolerance_mm
        holes: list[HoleRef] = []
        for d_row, d_col in spec.pins:
            found = nearest_hole(self.ws, x_mm + d_row * p, y_mm + d_col * p)
            if found is None or found[1] > tol:
                return None
            holes.append(found[0])
        return holes

    # ------------------------------------------------------------ pick / place

    def try_pick(self, x_mm: float, y_mm: float) -> tuple[PickResult, CartridgeRef | None]:
        """Grab a tray or dropped cartridge whose pin 0 is under (x, y)."""
        tol = self.ws.board.placement_tolerance_mm
        for c in self._cartridges:
            if c.state not in ("tray", "dropped"):
                continue
            if abs(c.x_mm - x_mm) <= tol and abs(c.y_mm - y_mm) <= tol:
                if c.state == "tray":
                    slot_id = self._slot_of.get(c.ref.id)
                    for slot in self._tray:
                        if slot.id == slot_id:
                            slot.cartridge = None
                            break
                c.state = "held"
                c.pin0 = None
                c.pin_holes = []
                return "picked", c.ref.model_copy()
        return "empty", None

    def try_place(
        self, ref: CartridgeRef, x_mm: float, y_mm: float
    ) -> tuple[PlaceResult, list[HoleRef]]:
        """Insert the held cartridge with pin 0 at (x, y)."""
        c = self.find(ref.id)
        if c is None:
            return "misaligned", []

        holes = self._pin_holes(ref, x_mm, y_mm)
        if holes is None:
            c.state = "dropped"
            c.x_mm, c.y_mm = x_mm, y_mm
            c.pin0 = None
            c.pin_holes = []
            return "misaligned", []

        for h in holes:
            owner = self._occupied.get((h.row, h.col))
            if owner is not None and owner != ref.id:
                return "blocked", []

        hx, hy = self.ws.hole_xy(holes[0].row, holes[0].col)
        c.state = "inserted"
        c.x_mm, c.y_mm = hx, hy
        c.pin0 = holes[0]
        c.pin_holes = holes
        for h in holes:
            self._occupied[(h.row, h.col)] = ref.id
        return "inserted", holes

    def drop(self, ref: CartridgeRef, x_mm: float, y_mm: float) -> PlacedCartridge | None:
        """Release a held cartridge in the air: it lands where it is, unconnected."""
        c = self.find(ref.id)
        if c is None:
            return None
        c.state = "dropped"
        c.x_mm, c.y_mm = x_mm, y_mm
        c.pin0 = None
        c.pin_holes = []
        return c.model_copy(deep=True)

    def move_held(self, x_mm: float, y_mm: float) -> None:
        """Carry every held cartridge along with the gripper (keeps snapshots honest)."""
        for c in self._cartridges:
            if c.state == "held":
                c.x_mm, c.y_mm = x_mm, y_mm

    # ------------------------------------------------------------ pi pins

    def pins(self) -> list[PinState]:
        return [self.get_pin(g) for g in sorted(self._pins)]

    def get_pin(self, gpio: int) -> PinState:
        pin = self._pins[gpio]
        if pin.mode == "in" and pin.net:
            volts = self.solve().node_voltages.get(pin.net, 0.0)
            level = 1 if volts >= self.ws.gpio_model.input_threshold_v else 0
            return pin.model_copy(update={"level": level})
        return pin.model_copy()

    def set_pin_mode(self, gpio: int, mode: str) -> PinState:
        pin = self._pins[gpio]
        pin.mode = mode  # type: ignore[assignment]
        if mode == "in":
            pin.level = 0
        return self.get_pin(gpio)

    def set_pin_level(self, gpio: int, level: int) -> PinState:
        pin = self._pins[gpio]
        if pin.mode != "out":
            raise ValueError(f"GPIO{gpio} is an input; set_mode('out') first")
        pin.level = 1 if level else 0
        return self.get_pin(gpio)

    # ------------------------------------------------------------ circuit

    def netlist(self) -> str:
        """The SPICE deck for the current world state."""
        raw_pins = [self._pins[g].model_copy() for g in sorted(self._pins)]
        return build_deck(self.ws, self._cartridges, raw_pins)

    def solve(self) -> CircuitResult:
        """DC operating point, cached on the deck string."""
        deck = self.netlist()
        cached = self._cache.get(deck)
        if cached is not None:
            return cached

        backend, voltages, currents = self._solver(deck)
        led_ma: dict[str, float] = {}
        leds: dict[str, LedState] = {}
        for c in self._cartridges:
            if c.state != "inserted":
                continue
            spec = self.ws.cartridges[c.ref.type]
            name = element_name(spec.spice, c.ref.id)
            if not name.upper().startswith("D"):
                continue
            ma = max(0.0, currents.get(name.lower(), 0.0) * 1000.0)
            led_ma[c.ref.id] = ma
            leds[c.ref.id] = "on" if ma > LED_ON_MA else "off"

        result = CircuitResult(
            backend=backend,  # type: ignore[arg-type]
            node_voltages=voltages,
            led_currents_ma=led_ma,
            leds=leds,
            deck=deck,
        )
        self._cache[deck] = result
        return result

    def observe(self) -> Observation:
        """Temporary v0.1-v0.3 ground truth for the orchestrator."""
        r = self.solve()
        return Observation(nets=r.node_voltages, leds=r.leds, backend=r.backend)

    # ------------------------------------------------------------ viz

    def snapshot(self, arm: ArmStatus, caption: str = "") -> WorldSnapshot:
        return WorldSnapshot(
            board=self.ws.board,
            tray=self.tray(),
            cartridges=self.cartridges(),
            arm=arm,
            pins=self.pins(),
            circuit=self.solve(),
            t=time.time(),
            caption=caption,
        )
