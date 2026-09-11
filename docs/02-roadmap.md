# Roadmap and milestone protocol

Each milestone ends with: tests green, a recording in `recordings/vX.Y.Z/`,
a `CHANGELOG.md` entry, a commit, an annotated git tag, a push. The protocol
is in `CLAUDE.md`; the script is `scripts/release_milestone.sh`.

Milestones are ordered so that every step is demoable on its own and the
hardware milestones only need adapters, never a rewrite.

## v0.1.0 - Sim core: light an LED from GPIO17  (hackathon target #1)

- `hwctl/schemas.py`, `hwctl/world`, `hwctl/circuit`, `hwctl/arm/sim.py`,
  `hwctl/pi/sim.py` (in-process, no HTTP yet), `hwctl/viz/render.py`,
  `hwctl/viz/record.py`.
- `configs/workspace.yaml` with the default harness and a tray of
  2x resistor_330, 2x led_red, jumpers.
- `scripts/demo_v0_1.py`: scripted sequence (no LLM) that picks a resistor,
  places it at rows 5-9, picks an LED, places it at rows 9-10, places a jumper
  from row 10 to the GND rail, sets GPIO17 high, and asserts the LED is on
  via `observe()`; then sets it low and asserts off.
- Recording: `recordings/v0.1.0/led-from-gpio17.gif`.
- Acceptance: `uv run pytest` green; the GIF shows the LED glow toggling.

## v0.2.0 - Claude in the loop  (hackathon target #2)

- `hwctl/mcp_server.py` exposing ArmAPI, PiAPI, CameraAPI, `workspace()`,
  `observe()`.
- `.mcp.json` so Claude Code / Claude Desktop can attach; a
  `.claude/agents/hardware-orchestrator.md` subagent with the system prompt.
- `scripts/orchestrate.py`: headless run with the Anthropic SDK tool runner
  (`claude-fable-5-1`, adaptive thinking, refusal fallbacks enabled) that
  takes a goal string, e.g. "make GPIO27 light a red LED", and produces the
  recording.
- Recording: the agent building the circuit from a one-line goal.
- Acceptance: the goal above succeeds from a clean workspace at least 3 of 3
  runs; command log saved with the recording.

## v0.3.0 - Services

- `hwctl/pi` becomes a FastAPI app with a Dockerfile; `pi.sim` talks to the
  world over HTTP. `docker compose up` runs pi + world/circuit + camera.
- Live web view (`hwctl/viz/web.py`): SSE stream of frames, command log.
- Acceptance: v0.2 orchestration works unchanged against the compose stack.

## v0.4.0 - Eyes only

- `observe()` removed from the MCP tool list. The orchestrator verifies through
  `camera_capture` (Claude reads the image) and `gpio_get`.
- Failure injection in `world`: placement tolerance, random 5 % drop on
  `open_gripper`, occasional `misaligned`. The agent must notice and retry.
- Acceptance: 10 runs of the v0.2 goal with 5 % failure injection; at least 8
  succeed; the recording shows one recovery.

## v0.5.0 - Toward a real machine

- Timed motion: feed rate, per-move duration, arm "busy" state, `wait()`.
- Cartridge rotation (0 / 90 degrees), `jumper_rail`.
- ArUco fiducials rendered at board corners; `hwctl/camera/cv.py` locates the
  board with OpenCV from a rendered image and reports LED states from pixel
  brightness; the sim renderer and the CV pipeline agree on all v0.1 circuits.
- Two more circuits in `tests/circuits/`: two LEDs on two GPIOs; LED with a
  button read on an input pin.

## v0.6.0 - First hardware: human arm  (first hardware milestone)

- `hwctl/arm/human.py`: prints instructions, waits for confirmation.
- `hwctl/pi/gpio.py`: gpiozero backend; same FastAPI app deployed to a real Pi
  with `scripts/deploy_pi.sh`.
- `hwctl/camera/cv.py` against a real overhead webcam.
- Acceptance: `HWCTL_BACKEND=human` and the v0.2 goal lights a real LED.
  Recording is a phone video plus the command log.

## v0.7.0 - Gantry adapter

- `hwctl/arm/gcode.py`: Marlin/GRBL over serial, homing, work-offset
  calibration from the fiducials, a Z lift and a gripper/vacuum GPIO.
- Bench test with the gantry moving over an empty board (dry run).

## v1.0.0 - Robot places the parts

- Real gantry, real tray, real Pi, real camera, same orchestrator.

## Done log

| version | date | recording | notes |
|---|---|---|---|
| | | | |
