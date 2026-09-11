# CLAUDE.md - agent operating instructions

This repo builds a simulation-first system in which a Claude "Hardware
Orchestrator" drives a robot to assemble circuits on a breadboard wired to a
Raspberry Pi. Read `docs/00-vision.md` (why), `docs/01-architecture.md`
(interfaces, the contract), `docs/02-roadmap.md` (what next), and
`docs/04-agents.md` (who does what) before writing code.

## Build and test

- Python 3.11, managed with `uv`. `uv sync` installs; `uv run pytest` tests.
- ngspice is required for the reference circuit backend
  (`apt-get install ngspice`, or `brew install ngspice`). Tests that need it are
  marked `@pytest.mark.ngspice` and skip when it is absent.
- Lint: `uv run ruff check . && uv run ruff format --check .`

## Conventions

- Pydantic models for anything crossing a boundary; they live in
  `hwctl/schemas.py` and are owned by the sim-core role.
- Devices (arm, pi, camera) are Protocols with interchangeable backends
  selected by `HWCTL_BACKEND`. Nothing above the device APIs imports `world`
  or `circuit`.
- Millimetres everywhere. Nets are named by tie strip (`R5L`, `RAIL_T_NEG`).
- Keep tool results terse; the orchestrator's context is the budget.

## Milestone loop (do this, in order, every time a milestone's acceptance criteria pass)

1. Confirm the milestone's acceptance list in `docs/02-roadmap.md` is fully
   met. Run `uv run pytest` and the lint. Both green.
2. Produce the recording: `uv run python scripts/demo_<milestone>.py --record
   recordings/vX.Y.Z/`. It must write at least one `.gif` and a
   `commands.jsonl`. Keep the GIF under 5 MB (downscale or subsample frames).
3. Add a `CHANGELOG.md` entry for vX.Y.Z (date, what shipped, recording path).
   Fill the row in the "Done log" table at the bottom of `docs/02-roadmap.md`.
4. Commit: `release: vX.Y.Z - <milestone title>`.
5. Tag and push: `scripts/release_milestone.sh vX.Y.Z` (annotated tag, pushes
   branch and tag).
6. Start the next milestone in the roadmap. Do not skip ahead; do not cut a
   tag with red tests or without a recording.

Versions follow the roadmap. If you ship something worth tagging between
milestones, use a patch bump (v0.1.1) and add it to the changelog.

## Recordings

`recordings/vX.Y.Z/` holds the GIF, the frames it was made from (optional),
and `commands.jsonl` (one device call per line with the resulting status) so a
run can be replayed. Commit them; they are the demo.

## Git

- Work on your role's branch (see `docs/04-agents.md`); PRs into `main`.
- Never force-push a shared branch. Never rewrite tags.
