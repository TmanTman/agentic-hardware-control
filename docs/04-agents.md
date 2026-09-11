# Working as several agents

The hackathon runs with one person and several Claude Code terminals. This is
how they share the work without stepping on each other.

## Ground rules

1. `docs/01-architecture.md` and `hwctl/schemas.py` are the contract. Only the
   **sim-core** agent edits `schemas.py`; anyone who needs a change asks for it
   (leave a note in `docs/NOTES.md` under your agent name) and works against a
   stub until it lands.
2. One agent, one branch, one worktree: `git worktree add ../ahc-<role> -b
   <role>`. Merge into `main` through PRs; never rebase a shared branch.
3. Milestone releases are cut from `main` by whichever agent finishes the last
   acceptance item, following `CLAUDE.md`.
4. Every agent reads `CLAUDE.md` first. It tells them how to build, test,
   record and release.

## Roles for the hackathon day

| terminal | role | branch | owns | first task |
|---|---|---|---|---|
| 1 | **sim-core** | `sim-core` | `schemas.py`, `world/`, `circuit/`, `arm/sim.py`, `pi/sim.py`, `configs/` | v0.1 world + ngspice; `scripts/demo_v0_1.py` |
| 2 | **viz** | `viz` | `viz/`, `camera/sim.py`, `recordings/` | renderer + GIF recorder against `schemas.py`; later the web view |
| 3 | **orchestrator** | `orchestrator` | `mcp_server.py`, `.mcp.json`, `.claude/agents/`, `scripts/orchestrate.py` | MCP server over a fake backend, then swap in sim-core |
| 4 | **hardware** | `hardware` | `docs/03-hardware.md`, `arm/gcode.py`, `arm/human.py`, `pi/gpio.py`, `camera/cv.py`, `pi/Dockerfile` | BOM sanity check, then the human-arm backend and Pi deploy script |

Sequencing on the day:

1. sim-core lands `schemas.py` within the first hour and pushes it; everyone
   else rebases onto it.
2. viz and orchestrator work against `schemas.py` and a hand-written fake
   world until sim-core's v0.1 demo runs.
3. v0.1.0 release. viz records it.
4. orchestrator wires the MCP server to the real sim; v0.2.0 release.
5. Remaining time goes to v0.3 (services) or v0.4 (eyes only), whichever the
   demo needs more.

## Prompts to start each terminal

Each terminal gets the same opening line, then its role:

> Read `CLAUDE.md`, `docs/00-vision.md`, `docs/01-architecture.md`,
> `docs/02-roadmap.md`, `docs/04-agents.md`. You are the **<role>** agent.
> Work on branch `<branch>` in a worktree. Build the items listed for your role
> for the current milestone. Do not edit files owned by other roles; leave
> requests in `docs/NOTES.md`.

## Token budget

The hackathon budget is $100 of Claude Fable 5.1 (`claude-fable-5-1`), priced
at $10 per million input tokens and $50 per million output tokens, with cached
input at $0.25 per million. Spend it on the orchestrator demo, not on building
the sim:

- Build the sim with whatever Claude Code plan the terminals run on.
- An orchestrator run is ~20-40 tool calls; with prompt caching and small tool
  results it costs well under a dollar. Camera images cost roughly 1.5k tokens
  each at 1000 px, so the v0.4 agent should capture on demand, not per step.
- Keep the MCP tool results terse (status structs, not prose) and the system
  prompt stable so the cache prefix holds.
