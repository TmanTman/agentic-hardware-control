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

## Coordinator mode (one agent, whole roadmap)

The four-terminal split above exists to let one human drive four terminals on
the day. When a single autonomous agent builds the project, use this mode
instead. It trades wall-clock parallelism for zero coordination overhead.

### Rules that change

- One agent owns **all** roles. Work on branch `coordinator` (a worktree is
  optional). Merge into `main` by PR, or fast-forward `main` yourself if no one
  else is committing.
- The `schemas.py` ownership rule collapses to: keep
  `docs/01-architecture.md` and `hwctl/schemas.py` in sync in the same commit.
- `docs/NOTES.md` is unused. There is nobody to leave a note for.
- Milestones are done **in roadmap order**, one at a time, through the loop in
  `CLAUDE.md`. The roadmap is a dependency chain (v0.2 needs v0.1's sim, v0.3
  wraps v0.2, v0.4 removes a tool from v0.2), so parallel milestones do not
  work.

### Subagents: when to spawn one

| use | agent kind | why |
|---|---|---|
| Acceptance review before every release | fresh agent, read-only | The coordinator believes its own work is done. A fresh context reads the milestone's acceptance list in `docs/02-roadmap.md` and checks it against the repo and test output. Release only when it passes. |
| v0.5 workstreams (timed motion, rotation, CV pipeline, extra circuits) | forks, in parallel | The only milestone with independent items. Forks inherit the contract context; fresh agents would re-derive it. |
| Research side quests (ngspice output format, Marlin serial protocol) | fresh agent | Only the findings need to come back. |

Do not spawn subagents for ordinary milestone work; the context that matters
(the contract, the current world model) is in the coordinator's head and a
subagent starts without it.

### Dynamic workflows: not for the build

Claude Code's dynamic workflows (`ultracode`, or "create a dynamic workflow")
run tens to hundreds of parallel subagents from a generated orchestration
script. They are built for codebase-wide audits, thousand-file migrations and
adversarial verification, and they cost substantially more tokens than a
normal session. This project is a few thousand lines with a serial roadmap;
there is nothing to fan out. Do not use them to build milestones. The one
defensible use is an adversarial verification pass on the v0.4 orchestrator
(failure injection, recovery) before v0.6 commits to real hardware, and only
if budget allows.

### Stop gates

Stop and report to the human at each of these. Do not improvise around them.

| gate | when | what the human decides |
|---|---|---|
| API spend | v0.2.0 acceptance (3 orchestrator runs) and v0.4.0 acceptance (10 runs with camera images) | Whether to spend from the $100 budget now. `ANTHROPIC_API_KEY` must be set; if it is not, stop here. |
| Docker | v0.3.0 | Docker Desktop must be running. Ask before starting it. |
| Release push | every `scripts/release_milestone.sh` | It pushes a branch and an annotated tag to `origin`; tags are never rewritten. v0.1.0 may be pushed unattended. Ask before each later one. |
| Real hardware | v0.6.0 | Hard stop. Everything from here needs a person at the bench. |

Everything else (installing `ngspice`, editing any file, running tests,
committing on `coordinator`) needs no confirmation.

### Prompt to start the coordinator

> Read `CLAUDE.md`, `docs/00-vision.md`, `docs/01-architecture.md`,
> `docs/02-roadmap.md`, `docs/04-agents.md`. You are the **Coordinator**
> (see "Coordinator mode" in `docs/04-agents.md`): you own every role, on
> branch `coordinator`. Execute the roadmap from v0.1.0 onward through the
> milestone loop in `CLAUDE.md`. Before each release, spawn a fresh read-only
> subagent to check the acceptance list independently. Stop and report at
> every stop gate.

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
