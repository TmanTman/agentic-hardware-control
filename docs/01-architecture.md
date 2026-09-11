# Architecture and interface contracts

This file is the contract between the agents working in parallel. Change it
deliberately, and tell the other agents when you do (see `docs/04-agents.md`).

## Layers

```
┌──────────────────────────────────────────────────────────────────┐
│  Hardware Orchestrator (Claude)                                  │
│  talks MCP to ->  hwctl-mcp  (tools: arm_*, gpio_*, camera_*,    │
│                              workspace_*)                        │
└───────────────┬───────────────────┬───────────────┬──────────────┘
                │ ArmAPI            │ PiAPI         │ CameraAPI
        ┌───────▼───────┐   ┌───────▼───────┐  ┌────▼─────────┐
        │ arm.sim       │   │ pi.sim (HTTP, │  │ camera.sim   │
        │ arm.gcode     │   │  in Docker)   │  │ camera.cv    │
        │ arm.human     │   │ pi.gpio (real)│  │              │
        └───────┬───────┘   └───────┬───────┘  └────┬─────────┘
                │ pick/place        │ pin levels     │ render
        ┌───────▼───────────────────▼────────────────▼─────────┐
        │ world  (breadboard, tray, cartridges, harness)         │
        │   -> netlist -> circuit.ngspice -> node voltages, LEDs │
        └────────────────────────────────────────────────────────┘
```

Rule: **nothing above the line may import anything below it** except through
the three device APIs. The orchestrator never reads world state or ngspice
output directly. (v0.1 has one temporary exception, `observe()`, see below.)

## Package layout

```
hwctl/
  schemas.py        # Pydantic models shared by everything (owned by sim-core)
  world/            # breadboard geometry, tray, cartridges, harness, placement physics
  circuit/          # netlist builder + ngspice runner (+ pure-python fallback solver)
  arm/              # ArmAPI protocol; sim, gcode, human backends
  pi/               # PiAPI protocol; FastAPI app; sim + gpio backends; Dockerfile
  camera/           # CameraAPI protocol; renderer (sim) + cv (real)
  viz/              # frame renderer (Pillow) + recording (GIF/MP4) + live web view
  mcp_server.py     # exposes the device APIs as MCP tools
  config.py         # BACKEND selection: sim | real | human
scripts/
  demo_v0_1.py      # scripted build used for the milestone recording
  release_milestone.sh
recordings/vX.Y.Z/  # gif + png frames + the command log that produced them
configs/
  workspace.yaml    # tray slots, board origin, harness map (the "known positions")
```

## Coordinate system

- Units: millimetres. Origin: bottom-left corner of the breadboard's hole grid.
  x runs along the board's long axis (rows), y across (columns a..j).
- Breadboard: standard 830-point, 63 rows x 10 columns (a-e, f-j), pitch
  2.54 mm, gap of 3 pitches between e and f, 2 power rails per side.
  Hole `(row, col)` centre = `(row_index * 2.54, y_of(col))`.
- Tray: a row of slots at fixed y beyond the board; each slot holds one
  cartridge of a known type. Slot centres are in `configs/workspace.yaml`.
- Nets are named by tie strip: `R{row}L` (a-e), `R{row}R` (f-j),
  `RAIL_T_POS`, `RAIL_T_NEG`, `RAIL_B_POS`, `RAIL_B_NEG`. GND is `RAIL_T_NEG`
  and `RAIL_B_NEG` in the default harness.

## Cartridges

A cartridge is a rigid carrier with N pins at fixed hole offsets. The arm holds
a cartridge by its centre; pin 0 is the reference pin.

| type | pins (row offset, col offset) | SPICE |
|---|---|---|
| `resistor_330` | (0,0), (4,0) | `R? n0 n1 330` |
| `resistor_1k`  | (0,0), (4,0) | `R? n0 n1 1k` |
| `led_red`      | (0,0)=anode, (1,0)=cathode | `D? n0 n1 LED_RED` |
| `jumper_N`     | (0,0), (N,0) for N in {2,3,4,5,6} | `R? n0 n1 0.01` |
| `jumper_rail`  | (0,0) then a rail hole | `R? n0 n1 0.01` |

Orientation is fixed (pins along the row axis) in v0.1. Rotation by 90 degrees
arrives in v0.5.

## Harness (Pi to breadboard, pre-wired)

Default `configs/workspace.yaml`:

| Pi pin | breadboard |
|---|---|
| 3V3 | `RAIL_T_POS` |
| GND | `RAIL_T_NEG`, `RAIL_B_NEG` |
| GPIO17 | row 5, col a (`R5L`) |
| GPIO27 | row 10, col a (`R10L`) |
| GPIO22 | row 15, col a (`R15L`) |
| GPIO23 | row 20, col a (`R20L`) |

The Pi's GPIO output is modelled as a 3.3 V (or 0 V) source with a 40 ohm
series resistance; an input pin reads HIGH when its node is above 1.8 V.

## Device APIs (the contract)

All three are Python `Protocol`s in their package's `__init__.py` and are
mirrored one-to-one as MCP tools. Return types are Pydantic models from
`hwctl/schemas.py`.

### ArmAPI

```
move_to(x_mm, y_mm)      -> ArmStatus     # XY move with lift up; error if lowered
lower()                  -> ArmStatus     # lift down (to tray or board contact)
raise_()                 -> ArmStatus
open_gripper()           -> ArmStatus     # releases held cartridge (inserts if pins over holes)
close_gripper()          -> ArmStatus     # grabs the cartridge under the gripper if any
status()                 -> ArmStatus     # {x, y, lifted, gripper, held: CartridgeRef|None}
```

Physics live in `world`, not in the arm. The arm backend calls
`world.try_pick(x, y)` and `world.try_place(cartridge, x, y)` and reports
what happened. A `PlaceResult` is `inserted`, `misaligned` (pins not over
holes, cartridge falls onto the board, no electrical contact), or `blocked`
(hole occupied). Sim v0.1 returns `inserted` whenever pins are within
`tolerance_mm` (default 0.5) of hole centres.

### PiAPI (HTTP, so the same service runs in Docker and on a real Pi)

```
GET  /pins                      -> [PinState]
POST /pins/{gpio}/mode  {mode}  -> PinState       # "out" | "in"
POST /pins/{gpio}/level {level} -> PinState       # 0 | 1 (outputs only)
GET  /pins/{gpio}               -> PinState       # inputs read the sampled level
POST /script  {python_source}   -> ScriptResult   # v0.2+: run a gpiozero script on the Pi
```

Backends: `sim` publishes pin levels to the world/circuit sim over HTTP;
`gpio` uses gpiozero on a real Pi. The container image is the same.

### CameraAPI

```
capture() -> Image (PNG bytes + capture metadata)
```

`camera.sim` renders the current world state (with LED brightness from ngspice)
at a configurable resolution, with ArUco fiducials drawn at the board corners
from v0.5 so the real CV pipeline can be developed against rendered images.

### Workspace (static, read-only)

```
workspace() -> Workspace   # board geometry, hole coordinates, tray slots, harness map
```

### observe() (temporary, v0.1 to v0.3 only)

`observe() -> {net: voltage, led_id: on|off}` straight from ngspice. Removed
from the MCP tool list at v0.4, when the orchestrator must use the camera.

## Circuit simulation

`world.netlist()` walks every inserted cartridge and every harness wire and
emits a SPICE deck; `circuit.ngspice.run_op(deck)` runs `ngspice -b` and
parses node voltages and branch currents. An LED is "on" when its forward
current exceeds 1 mA (brightness scaled 1-20 mA for rendering). Verified deck:

```
* GPIO17 -> 330R -> red LED -> GND
.model LED_RED D(IS=1e-18 N=1.8 RS=1 BV=5 CJO=10p)
Vgpio17 n_gpio17 0 DC 3.3
Rgpio17 n_gpio17 R5L 40
R1 R5L R9L 330
D1 R9L R12L LED_RED
Rj R12L 0 0.01
.control
op
print v(R5L) v(R9L) v(R12L) i(Vgpio17)
quit
.endc
.end
```

ngspice 42 gives 4.4 mA through the LED at 1.68 V forward. Floating nets get
a 1 Gohm tie to ground so `.op` always converges.

A pure-Python DC solver (resistors + a piecewise-linear diode) is kept as a
fallback so tests run where ngspice is missing; ngspice is the reference.

## Visualisation and recording

- `viz.render(world, circuit_result, arm_status) -> PIL.Image`, top-down,
  board + tray + arm crosshair + held cartridge + LED glow.
- `viz.Recorder` collects a frame after every device call and writes
  `recordings/vX.Y.Z/<name>.gif` (Pillow, no ffmpeg dependency) plus the
  frames and `commands.jsonl` so a recording can be replayed.
- A live web view (FastAPI + SSE + canvas) arrives at v0.3.

## Backend selection

`HWCTL_BACKEND=sim|real|human` (or `configs/backend.yaml`). `human` is the
bridge to first hardware: the arm backend prints "pick resistor from slot 3,
insert at rows 5-9 column c" and waits for a keypress, while the Pi and camera
are real. That is how v0.6 lights a real LED with no robot.
