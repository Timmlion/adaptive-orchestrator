---
name: adaptive-orchestrator
description: Orchestrate complex multi-agent projects through a portable file-based Agent Board Protocol. Use for autonomous or supervised planning and execution, resuming shared projects, coordinating specialized leaders/workers/critics/humans across agent harnesses, capability-aware model selection, concurrent task claiming, review, Git-isolated implementation, integration, and a disposable static dashboard backed by shared .agent-board JSON files.
---
# Adaptive Orchestrator
Use `.agent-board/` as durable shared state. Agents communicate through task contracts, artifacts, runs, reviews, decisions, and claims rather than conversational handoffs.

## Modes
- **autonomously create**: plan, execute, review, integrate, finish; stop only for genuine human-only blockers.
- **plan and loop me in for acceptance**: finish planning/red-team, materialize board/dashboard, request approval, then execute.
- **resume**: validate the existing board, run current-harness preflight, recover stale work conservatively, continue; never re-plan from scratch.

## Protocol
1. Locate a valid shared board or initialize one with `scripts/init_board.py`. Never create a private copy when a canonical board exists.
2. Run preflight before planning/claiming. Record only verified harness, model, tool, vision, subagent and parallelism capabilities; write unknown when unverifiable. Read `references/preflight.md`.
3. Appoint one Program Director. Create the smallest set of departments that can deliver the goal.
4. Run planning council rounds: proposals, affected-domain cross-review, blocking-conflict resolution, independent red-team. Freeze only when no blocking objections/critical unknowns remain and the dependency DAG is valid. Read `references/planning.md`.
5. Materialize portable task contracts. Specify required capabilities, tools, dependencies, context, acceptance criteria and verification, not concrete model names. Read `references/task-contract.md`.
6. Validate with `scripts/validate_board.py` before execution.
7. Query READY work with `scripts/list_ready_tasks.py`. Filter hard requirements, then choose the smallest/cheapest model expected to meet required quality. Unknown never satisfies a hard requirement. Read `references/model-selection.md`.
8. Claim before agent execution with `scripts/claim_task.py`. Treat claims as leases and execution as at-least-once. Read `references/claiming.md`.
9. Build minimal worker context: task, parent goal, direct dependencies, relevant decisions/files, latest blocking review feedback. Never dump the whole board by default.
10. Execute code-changing work in an isolated Git branch/worktree when possible. Record append-only run evidence and actual runtime/model. Read `references/execution.md` and `references/git-protocol.md`.
11. Review deterministic checks first, then critic if policy requires it. Critics judge frozen acceptance criteria, explicit constraints, regressions and correctness/safety defects. Separate blocking from non-blocking findings. Read `references/reviewing.md`.
12. Bound retries: two worker revisions, one stronger/different suitable model, then leader, then Director for re-plan/human/cancel.
13. Integrate accepted work separately and run cross-task/system verification. Create reconciliation tasks for semantic conflicts. Read `references/integration.md`.
14. Generate `dashboard/index.html` with `scripts/build_dashboard.py`. UI is a disposable projection, never source of truth.

## Concurrency invariants
- Freeze `tasks/*.json` after plan acceptance; runtime facts belong in `state/`, `claims/`, `runs/`, `reviews/`.
- Keep runs/reviews append-only and use unique IDs.
- Require a valid claim before execution. Competing claims block automatic integration until reconciled.
- Use Git for history, transport, audit and worktree isolation, never as a distributed lock manager.
- Do not promise exactly-once execution. Preserve duplicate/conflicting evidence.

## Commands
`python scripts/init_board.py --name "Project" --goal "Goal"`
`python scripts/validate_board.py`
`python scripts/list_ready_tasks.py`
`python scripts/claim_task.py TASK-0001 --runtime R --worker W`
`python scripts/claim_task.py TASK-0001 --runtime R --worker W --heartbeat`
`python scripts/release_task.py TASK-0001 --runtime R`
`python scripts/transition_task.py TASK-0001 IN_PROGRESS --runtime R`
`python scripts/record_run.py TASK-0001 --runtime R --worker W --summary "..."`
`python scripts/build_dashboard.py`

Read `references/protocol.md` for layout/state semantics. Schemas are in `references/schemas/`.
