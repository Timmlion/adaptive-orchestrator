# Adaptive Orchestrator

A portable, file-based **Agent Board Protocol** for orchestrating complex multi-agent projects — planning, claiming, execution, review, integration, and a disposable static dashboard — across any agent harness.

Agents communicate through **task contracts, artifacts, runs, reviews, decisions, and claims** written as shared `.agent-board/` JSON files, rather than fragile conversational handoffs. The board is durable shared state any agent can join, resume, or hand off mid-project.

> This repository ships `adaptive-orchestrator` as a **Hermes-compatible skill**. The skill folder (`adaptive-orchestrator/`) is self-contained: drop it into your skills directory and use the scripts straight from a shell — no framework required.

---

## Why

Multi-agent projects fail when context lives in conversation history. The Agent Board Protocol makes state explicit and portable:

- **Resumable** — any agent can pick up a board and continue where work left off, without re-reading a chat log.
- **Harness-agnostic** — works with the same protocol whether agents run under Hermes, Claude Code, OpenCode, Codex, or a human.
- **Capability-aware** — tasks specify *required capabilities*, not model names; the runtime picks the smallest/cheapest model that meets the requirement.
- **Concurrent** — task claiming is lease-based; multiple workers proceed without a central lock.
- **Auditable** — runs and reviews are append-only with unique IDs; Git provides history, transport, and worktree isolation.

---

## How it works

The board lives in a directory named `.agent-board/`:

| Path | Purpose |
|---|---|
| `.agent-board/board.json` | Project metadata, departments, decision log. |
| `.agent-board/tasks/*.json` | Frozen task contracts after plan acceptance. |
| `.agent-board/claims/` | Worker leases (claim → release). |
| `.agent-board/runs/` | Append-only execution evidence and actual runtime/model. |
| `.agent-board/reviews/` | Append-only review findings (blocking vs non-blocking). |
| `.agent-board/state/` | Runtime facts that evolve during execution. |
| `.agent-board/dashboard/` | Disposable static HTML projection of board state. |

### Lifecycle

1. **Init** — `init_board.py` creates a valid board.
2. **Preflight** — verify harness/model/tool capabilities; record only what is verified.
3. **Plan** — planning council: proposals → cross-review → conflict resolution → red-team; freeze when the dependency DAG is valid.
4. **Contract** — materialize portable task contracts (capabilities, deps, acceptance criteria, verification).
5. **Validate** — `validate_board.py` before any execution.
6. **Claim** — workers claim tasks as leases, then execute at-least-once.
7. **Execute** — code-changing work goes in an isolated Git branch/worktree; record append-only run evidence.
8. **Review** — deterministic checks first, critic if policy requires; separate blocking from non-blocking.
9. **Integrate** — accepted work merged separately; cross-task verification; reconciliation tasks for conflicts.
10. **Dashboard** — `build_dashboard.py` renders a read-only projection (never a source of truth).

### Concurrency invariants

- Task contracts freeze after plan acceptance; runtime facts live in `state/`, `claims/`, `runs/`, `reviews/`.
- Runs and reviews are append-only with unique IDs.
- A valid claim is required before execution; competing claims block auto-integration until reconciled.
- Git is for history, transport, audit, and worktree isolation — never a distributed lock manager.
- No exactly-once execution is promised; duplicate/conflicting evidence is preserved.

---

## Quick start

```bash
# Initialize a board
python scripts/init_board.py --name "Project" --goal "Goal"

# Validate the board before doing anything
python scripts/validate_board.py

# Find work that is ready to execute
python scripts/list_ready_tasks.py

# Claim a task (lease) and mark a heartbeat
python scripts/claim_task.py TASK-0001 --runtime R --worker W --heartbeat

# Release after review, transition state, record evidence
python scripts/release_task.py TASK-0001 --runtime R
python scripts/transition_task.py TASK-0001 IN_PROGRESS --runtime R
python scripts/record_run.py TASK-0001 --runtime R --worker W --summary "..."

# Render the dashboard
python scripts/build_dashboard.py
```

---

## Repository layout

```
adaptive-orchestrator/
├── SKILL.md                    # Protocol overview + operating manual
├── agents/
│   └── openai.yaml             # Example agent declaration
├── references/                 # Detailed protocol guides
│   ├── claiming.md             #   Lease semantics
│   ├── execution.md            #   Append-only execution evidence
│   ├── git-protocol.md         #   Branch/worktree isolation
│   ├── integration.md          #   Cross-task reconciliation
│   ├── model-selection.md      #   Capability-aware model choice
│   ├── planning.md             #   Planning council + red-team
│   ├── preflight.md            #   Capability verification
│   ├── protocol.md             #   Board layout & state semantics
│   ├── reviewing.md            #   Deterministic checks + critic
│   ├── task-contract.md        #   Portable task contract format
│   └── schemas/                #   JSON schemas for board artifacts
│       ├── claim.schema.json
│       ├── project.schema.json
│       ├── review.schema.json
│       ├── run.schema.json
│       ├── state.schema.json
│       └── task.schema.json
└── scripts/                    # Reference CLI (Python stdlib, no deps)
    ├── init_board.py
    ├── validate_board.py
    ├── list_ready_tasks.py
    ├── claim_task.py
    ├── release_task.py
    ├── transition_task.py
    ├── record_run.py
    ├── build_dashboard.py
    └── boardlib.py             # Shared board operations
```

---

## Requirements

- Python 3.8+ (standard library only — no third-party dependencies)
- A `git` remote for transport/audit when executing code-changing tasks

---

## License

MIT — see [LICENSE](LICENSE).