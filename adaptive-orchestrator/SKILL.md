---
name: adaptive-orchestrator
description: Use when starting, resuming, or coordinating a complex project through a shared file-based agent board, including optional multi-harness work allocation and a live JSON project dashboard.
---
# Adaptive Orchestrator

`.agent-board/` is durable shared state. Agents exchange task contracts, claims, runs, reviews and decisions through JSON files; conversation and the dashboard are never sources of truth.

## Entry decision

1. Look for `.agent-board/` in the project folder.
2. If it is absent, ask exactly: **What are we building?** Then ask only the preflight questions needed for that goal. Initialize the board with `scripts/init_board.py` and persist verified current-runtime facts with `scripts/record_preflight.py`.
3. If it exists, do not ask for the goal again. Run `scripts/validate_board.py`, inspect project/task/state/claim/run/review JSON, and report completed work, blockers and the next available work. Record a fresh current-harness preflight when facts changed or are missing.
4. Ensure the live panel exists with `scripts/build_dashboard.py`; start it through `scripts/serve_dashboard.py` when the user wants to view it.

## Adaptive preflight

Ask sequentially after the goal. Record only verified abilities; use `unknown` when verification is unavailable.

- Identify the current harness, selectable models, tools and capabilities.
- Ask whether execution is `autopilot` or `ask`.
- For `ask`, ask for the decision threshold: `CEO` (strategy, scope, risk, release), `manager` (also material implementation/integration trade-offs), or `full_control` (including small execution decisions).
- Ask whether multi-harness coordination is needed. Default to a single harness and allocate across its verified models.
- If multi-harness is enabled, gather each known harness, its verified capabilities and intended purpose or load-balancing role. These are preferences, not proof of current availability.

`autopilot` proceeds without ordinary approval, but never overrides a human-only blocker, a destructive/out-of-scope action, or explicit consent required for cross-harness task takeover.

## Planning and execution

1. Appoint one Program Director and the smallest useful departments.
2. Run proposal, affected-domain review, blocking-conflict resolution and independent red-team; freeze only with a valid dependency DAG and no critical unknowns. Read `references/planning.md`.
3. Materialize portable task contracts. Put hard capabilities/tools in `requirements`; put only an optional runtime preference in `execution.preferred_runtime`. Never bind a contract to a concrete model. Read `references/task-contract.md`.
4. Validate the board with `scripts/validate_board.py`.
5. Ask `scripts/find_work.py --runtime <runtime>` for work. It first returns compatible READY work preferred for this runtime. If none exists but a compatible task prefers another harness, it returns `ask_to_take_over` with the reason. Explain that proposal and wait for explicit user approval before invoking `scripts/claim_task.py`; do not automatically take it over.
6. Claim before execution, use the narrowest useful worker context, record actual runtime/model/run evidence, then review against frozen criteria. Read `references/claiming.md`, `references/execution.md` and `references/reviewing.md`.
7. Integrate accepted work separately and perform cross-task verification. Read `references/integration.md`.

## Dashboard

Run `scripts/build_dashboard.py` whenever `dashboard/index.html` or `dashboard/app.js` is absent. Those disposable assets contain no board data and never write JSON.

Run `scripts/serve_dashboard.py --board .agent-board`; it exposes a loopback-only, read-only `/api/board` projection constructed from current JSON files on each request. `app.js` refreshes it periodically. A missing or malformed JSON record must be shown as diagnostics, not silently repaired by the panel.

## Invariants

- Freeze `tasks/*.json` after plan acceptance; runtime facts belong in `state/`, `claims/`, `runs/` and `reviews/`.
- Runs and reviews are append-only. Claims are leases, not distributed locks; preserve conflicting evidence.
- Unknown or malformed environment facts never satisfy hard requirements.
- An active claim blocks automatic work selection. Expired or malformed claims require reconciliation; do not silently reclaim them.
- Git is for history and isolated worktrees, never locking.

## Commands

```sh
python3 scripts/init_board.py --name "Project" --goal "Goal" --autonomy autopilot
python3 scripts/record_preflight.py --json '{...}'
python3 scripts/validate_board.py
python3 scripts/find_work.py --runtime R
python3 scripts/claim_task.py TASK-0001 --runtime R --worker W
python3 scripts/build_dashboard.py
python3 scripts/serve_dashboard.py --board .agent-board
```

Read `references/protocol.md` for layout/state semantics and `references/schemas/` for JSON contracts.
