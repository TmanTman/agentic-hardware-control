"""Pydantic models shared by every layer. Owned by the sim-core role.

Everything that crosses a boundary (device API return values, MCP tool results,
renderer input, command log lines) is one of these. Keep them terse: the
orchestrator's context window is the budget.

Coordinates are millimetres. Origin is the centre of hole (row 1, col a);
x runs along the rows (row r is at x = (r - 1) * pitch), y across the columns
(column c is at y = column_offset[c] * pitch; rails have negative / large
offsets). The arm position is the position of the held cartridge's pin 0.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- primitives

Gripper = Literal["open", "closed"]
PinMode = Literal["in", "out"]
PlaceResult = Literal["inserted", "misaligned", "blocked"]
PickResult = Literal["picked", "empty"]
CartridgeState = Literal["tray", "held", "inserted", "dropped"]
LedState = Literal["on", "off"]
Device = Literal["arm", "pi", "camera", "observe", "workspace"]


class HoleRef(BaseModel):
    """A breadboard hole. `col` is a column letter (a..j) or a rail name."""

    row: int
    col: str


class CartridgeRef(BaseModel):
    """Identity of one physical cartridge (e.g. the second 330R in the tray)."""

    id: str
    type: str


# ---------------------------------------------------------------- workspace (static)


class CartridgeSpec(BaseModel):
    """Geometry and SPICE template for a cartridge type."""

    type: str
    pins: list[tuple[int, int]] = Field(description="(row, col) hole offsets from pin 0")
    spice: str = Field(description="template with {id} {n0} {n1} ... placeholders")
    pin_names: list[str] | None = None


class TraySlot(BaseModel):
    id: int
    x_mm: float
    y_mm: float
    cartridge: str | None = Field(description="cartridge type, or None once taken")


class BoardGeometry(BaseModel):
    type: str = "breadboard_830"
    rows: int = 63
    pitch_mm: float = 2.54
    columns: dict[str, int] = Field(description="column letter -> y offset in pitches")
    rails: dict[str, int] = Field(description="rail net -> y offset in pitches")
    placement_tolerance_mm: float = 0.5


class GpioModel(BaseModel):
    high_v: float = 3.3
    series_ohm: float = 40.0
    input_threshold_v: float = 1.8


class Workspace(BaseModel):
    """The 'known positions' the orchestrator gets from workspace()."""

    board: BoardGeometry
    harness: dict[str, list[str]] = Field(description="Pi pin -> nets it is wired to")
    gpio_model: GpioModel
    tray: list[TraySlot]
    cartridges: dict[str, CartridgeSpec]
    spice_models: list[str] = []
    notes: str = (
        "Units mm. Origin = hole (1,a). x = (row-1)*pitch along rows; "
        "y = column_offset*pitch across columns. Arm position = held cartridge pin 0. "
        "Nets: R{row}L for cols a-e, R{row}R for f-j, RAIL_* for rails."
    )

    def hole_xy(self, row: int, col: str) -> tuple[float, float]:
        """Centre of a hole. `col` is a column letter or a rail net name."""
        p = self.board.pitch_mm
        if col in self.board.columns:
            return ((row - 1) * p, self.board.columns[col] * p)
        if col in self.board.rails:
            return ((row - 1) * p, self.board.rails[col] * p)
        raise KeyError(f"unknown column or rail: {col}")

    def net_of(self, row: int, col: str) -> str:
        if col in self.board.rails:
            return col
        off = self.board.columns[col]
        return f"R{row}L" if off <= self.board.columns["e"] else f"R{row}R"


# ---------------------------------------------------------------- arm


class ArmStatus(BaseModel):
    """Returned by every ArmAPI call."""

    x_mm: float
    y_mm: float
    lifted: bool
    gripper: Gripper
    held: CartridgeRef | None = None
    event: PlaceResult | PickResult | Literal["moved", "lowered", "raised", "dropped"] | None = None
    error: str | None = None


# ---------------------------------------------------------------- pi


class PinState(BaseModel):
    gpio: int
    mode: PinMode
    level: int = Field(description="0 or 1; for inputs, the sampled level")
    net: str | None = Field(default=None, description="breadboard net from the harness")


class ScriptResult(BaseModel):
    """v0.2+: result of running a gpiozero script on the Pi."""

    ok: bool
    stdout: str = ""
    stderr: str = ""


# ---------------------------------------------------------------- camera


class Image(BaseModel):
    png: bytes
    width: int
    height: int
    t: float = Field(description="capture time, seconds since epoch")
    note: str = ""


# ---------------------------------------------------------------- circuit / observe


class CircuitResult(BaseModel):
    """Output of one DC operating-point solve of the current world."""

    backend: Literal["ngspice", "python"]
    node_voltages: dict[str, float] = Field(description="net -> volts")
    led_currents_ma: dict[str, float] = Field(description="cartridge id -> forward mA")
    leds: dict[str, LedState] = Field(description="cartridge id -> on (>1 mA) / off")
    deck: str = Field(default="", description="the SPICE deck that was solved")

    def brightness(self, cartridge_id: str) -> float:
        """0..1 for rendering: 1 mA -> 0.05, 20 mA -> 1.0."""
        i = self.led_currents_ma.get(cartridge_id, 0.0)
        return max(0.0, min(1.0, i / 20.0))


class Observation(BaseModel):
    """observe(): temporary (v0.1-v0.3) ground truth straight from the circuit sim."""

    nets: dict[str, float]
    leds: dict[str, LedState]
    backend: str


# ---------------------------------------------------------------- world snapshot (for viz)


class PlacedCartridge(BaseModel):
    """Where one cartridge is right now, for rendering and for the circuit."""

    ref: CartridgeRef
    state: CartridgeState
    x_mm: float = Field(description="pin 0 x (tray slot, gripper, or board position)")
    y_mm: float
    pin0: HoleRef | None = Field(default=None, description="set when inserted")
    pin_holes: list[HoleRef] = Field(default_factory=list, description="all pins when inserted")


class WorldSnapshot(BaseModel):
    """Everything the renderer needs. Produced by world.snapshot(); consumed by viz."""

    board: BoardGeometry
    tray: list[TraySlot]
    cartridges: list[PlacedCartridge]
    arm: ArmStatus
    pins: list[PinState]
    circuit: CircuitResult | None = None
    t: float = 0.0
    caption: str = ""


# ---------------------------------------------------------------- recording


class CommandRecord(BaseModel):
    """One line of recordings/vX.Y.Z/commands.jsonl."""

    seq: int
    t: float
    device: Device
    call: str
    args: dict[str, Any] = {}
    result: dict[str, Any] | str | None = None
    frame: str | None = Field(default=None, description="frame filename, if one was captured")
