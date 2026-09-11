# Changelog

Milestone entries look like `## [vX.Y.Z] - YYYY-MM-DD - title`, followed by
what shipped and the recording path. `scripts/release_milestone.sh` checks for
the heading.

## [Unreleased]

## [v0.1.0] - 2026-09-12 - Sim core: light an LED from GPIO17

- `hwctl/schemas.py`: the shared Pydantic contract (workspace, arm, pi, camera,
  circuit, world snapshot, command log).
- `hwctl/world`: breadboard geometry, tray, cartridges, pick/place physics with
  0.5 mm tolerance, netlist builder.
- `hwctl/circuit`: ngspice runner plus a pure-Python Newton MNA fallback
  (`HWCTL_SOLVER=python`); they agree to 0.05 % on the reference LED deck.
- `hwctl/arm/sim.py`, `hwctl/pi/sim.py`: in-process ArmAPI / PiAPI backends.
- `hwctl/viz`: top-down Pillow renderer, `Recorder` (GIF + `commands.jsonl`),
  `hwctl/camera/sim.py`.
- `hwctl/session.py`: wires the devices together and records every call.
- `scripts/demo_v0_1.py`: scripted build, asserts the LED toggles via `observe()`.
- Recording: `recordings/v0.1.0/led-from-gpio17.gif`.

## [v0.0.0] - 2026-09-11 - Project charter

- Vision, architecture contract, roadmap, hardware design, agent roles,
  milestone protocol.
