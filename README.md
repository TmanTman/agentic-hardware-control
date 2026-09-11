# agentic-hardware-control

Claude builds hardware. A Claude *Hardware Orchestrator* drives a robot arm to
assemble circuits on a breadboard wired to a Raspberry Pi, programs the Pi,
and verifies the result through a camera. Built simulation-first: every device
has the same interface in sim and on real hardware.

- `docs/00-vision.md` - the idea and the deliberate simplifications
- `docs/01-architecture.md` - layers, coordinate system, the device API contract
- `docs/02-roadmap.md` - milestones v0.1 to v1.0 with acceptance criteria
- `docs/03-hardware.md` - the constrained real-hardware design and BOM
- `docs/04-agents.md` - how several Claude Code terminals split the work
- `CLAUDE.md` - operating instructions for the agents (build, test, record, tag)

## Quick start

```
uv sync
apt-get install ngspice     # or brew install ngspice
uv run pytest
```

Milestone recordings live in `recordings/vX.Y.Z/`.
