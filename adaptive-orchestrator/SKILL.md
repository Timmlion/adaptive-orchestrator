---
name: adaptive-orchestrator
description: Use when starting, resuming, or coordinating a complex project through a shared file-based agent board, including model-aware planning and a live JSON dashboard.
---
# Adaptive Orchestrator

`.agent-board/` is durable shared state. Task contracts, claims, runs, reviews, and decisions are JSON. Conversation and the dashboard are not sources of truth.

## Entry and model preflight

1. Look for `.agent-board/` in the project folder.
2. For a new board, ask exactly: **What are we building?** Then **Discover selectable models** from the harness context, native model list, or API. Ask the user about models only when discovery is uncertain or unavailable.
3. Ask the user to select the allowed pool. Save it as `allowed_models`.
4. **research every selected model** in an independent pass. Use official model cards or docs first; use current benchmark evidence only as support. Record links, retrieval timestamps, confidence, known and unknown facts, roles, quality tier, and relative cost. Never infer an unknown fact.
5. Present the assessment and get user confirmation before `scripts/record_preflight.py` persists `model_policy`.
6. For an existing board, validate and inspect it. Refresh and confirm missing or stale model policy before any new claim. Do not ask for the goal again.

Also record verified harness tools and capabilities. Ask whether execution is `autopilot` or `ask`. For `ask`, record `CEO`, `manager`, or `full_control`. Ask whether multi-harness coordination is needed; it is off by default.

`autopilot` shows a concise summary and continues when there are no blockers. An `ask` policy at **CEO** requires the explicit word `start` before the first claim. No policy overrides a human-only blocker, a destructive or out-of-scope action, or consent required for cross-harness takeover.

## Plan approval gate

1. Run planning, affected-domain review, conflict resolution, and an independent red-team. See `references/planning.md`.
2. Freeze portable task contracts with role, complexity, and capability requirements. Do not bind a task to a concrete model. See `references/task-contract.md`.
3. Run `python3 scripts/plan_work.py --runtime <runtime>`. It validates the model policy and routes every task.
4. **capability gaps**, invalid policy, or an incomplete route block the plan and require user resolution.
5. **No claim before this gate**: do not call `find_work.py` or `claim_task.py` until the frozen plan passes.

Route each task in this order: `allowed_models` → verified model capabilities → role → sufficient quality → cheapest relative cost. Record the actual model only in run evidence. Give critics fresh context; run deterministic tests first; for high-risk work prefer a stronger or diverse model family.

## Execution

After the gate passes, use `scripts/find_work.py --runtime <runtime>`. It may return `ask_to_take_over`; explain it and obtain explicit user approval before a cross-harness claim. Claim before execution, keep worker context narrow, record runtime/model/run evidence, review against frozen criteria, and integrate accepted work separately.

## Dashboard

Always run `scripts/build_dashboard.py` after plan freeze. Dashboard assets are disposable and never write board JSON. When a **browser preview** is verified, serve loopback with `scripts/serve_dashboard.py --board .agent-board` and open or offer its URL. If browser preview fails, print the URL and give the same concise briefing in chat. Browser failure never blocks the text briefing or work.

## Invariants

- Task contracts freeze after plan approval; runtime facts belong in state, claims, runs, and reviews.
- Unknown or malformed facts never meet a hard requirement.
- Runs and reviews are append-only. Claims are leases, not distributed locks.
- Git is for history and isolated worktrees, never locking.

## Commands

```sh
python3 scripts/init_board.py --name "Project" --goal "Goal" --autonomy autopilot
python3 scripts/record_preflight.py --json '{...}'
python3 scripts/plan_work.py --runtime <runtime>
python3 scripts/validate_board.py
python3 scripts/find_work.py --runtime <runtime>
python3 scripts/claim_task.py TASK-0001 --runtime <runtime> --worker W
python3 scripts/build_dashboard.py
python3 scripts/serve_dashboard.py --board .agent-board
```

Read `references/preflight.md`, `references/model-selection.md`, and `references/protocol.md` for the detailed rules.
