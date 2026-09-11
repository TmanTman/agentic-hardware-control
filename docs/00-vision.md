# Vision: Claude builds hardware

**One sentence:** a Claude agent (the *Hardware Orchestrator*) drives a robot to
assemble a small electronic circuit on a breadboard wired to a Raspberry Pi,
then programs the Pi and verifies through a camera that the circuit works.

The project is built simulation-first. Every device the orchestrator can touch
has the **same interface in simulation and on real hardware**, so the agent is
pointed at real hardware by changing one config value, not by rewriting it.

## The cast

| Role | Simulated by | Real hardware |
|---|---|---|
| Hardware Orchestrator | Claude, through an MCP server | same |
| Robot arm (XY + lift + gripper) | `hwctl.arm.sim` | Cartesian gantry speaking G-code (see `docs/03-hardware.md`) |
| Raspberry Pi (device under test) | `hwctl.pi.sim` in a Docker container | the same HTTP service running on a real Pi with gpiozero |
| Breadboard + components + tray | `hwctl.world` (the physics of what actually happened) | reality |
| Circuit | ngspice, netlist derived from the world state | reality |
| Camera | renderer of the world state | overhead USB camera / Pi Camera |

The world model and ngspice are the *stand-in for reality*. They are never part
of the orchestrator's API; the orchestrator only sees arm, Pi, camera, and a
static description of the workspace (tray slots, hole coordinates, which GPIO
pins are pre-wired to which breadboard rows).

## Why simulation first

1. We want the agent behaviour, the interfaces, and the failure handling to be
   solid before any motor moves. The sim is the deliverable that keeps
   improving; hardware is the milestone that proves it was worth it.
2. A recorded, versioned simulation is a demo on its own. Every milestone
   produces a git tag and a recording (`recordings/vX.Y.Z/`).
3. The hardware design is chosen under harsh constraints (cheap, buildable in a
   weekend, sub-millimetre repeatable) so the simulation can be faithful to a
   real machine rather than to a fantasy one.

## Deliberate simplifications (v0.x)

- **Known positions.** Tray slot coordinates, breadboard hole coordinates and
  the Pi-to-breadboard harness are given to the agent as static data. No
  camera-based localisation until the roadmap says so.
- **Perfect arm.** `move_to(x, y)` arrives exactly. Tolerances, drift and
  dropped parts are injected later, on purpose, as roadmap items.
- **XY only.** Lift is binary (up / down). No height control.
- **Cartridges, not loose parts.** Every component sits on a rigid carrier with
  0.64 mm square pins at a fixed pitch. The robot never bends a lead.
- **Two component types plus jumpers.** Resistors, LEDs, rigid jumpers.
- **Build only.** No removal, no rework. Take parts from the tray, put them in
  the board.
- **Top-down 2D visualisation.**

## Success looks like

- v0.1: "Light an LED from GPIO17" is built and verified end-to-end in sim,
  with a GIF to prove it.
- v0.4: the orchestrator can only *see* the board through images, and still
  recovers from a mis-placed part.
- v0.6: the same orchestrator, pointed at a real Pi with a human standing in
  for the robot arm, lights a real LED.
- v1.0: a real gantry places the parts.
