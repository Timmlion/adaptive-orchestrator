# Adaptive Orchestrator

A portable, file-based Agent Board Protocol for complex multi-agent work. Durable state lives in `.agent-board/` JSON files. The dashboard and conversation are views, not sources of truth.

The self-contained skill is in `adaptive-orchestrator/`. Install that folder in a supported skill directory, or run its scripts from this repository.

## Lifecycle

1. **New board** — ask exactly “What are we building?” Then discover selectable models from harness context, native model list, or API. Ask the user about models only when discovery is uncertain or unavailable.
2. **Model policy** — the user chooses the allowed pool. Research every selected model independently: official docs or cards first, current benchmarks as supporting evidence. Record source links, timestamps, confidence, known and unknown facts, roles, quality tier, and relative cost. Never infer unknown facts. Present the assessment and get confirmation before persisting `model_policy`.
3. **Existing board** — do not ask for the goal again. Refresh and confirm missing or stale model policy before a new claim.
4. **Plan** — create portable contracts with role, complexity, and capability requirements. Do not name a concrete model in a task.
5. **Plan gate** — run `plan_work.py`. Capability gaps, invalid policy, or an unroutable task block work and require user resolution. No claim happens before the gate passes.
6. **Dashboard** — after plan freeze, always build the disposable dashboard assets. If browser preview works, serve loopback and open or offer its URL. Otherwise print the URL and give the same short briefing in chat. A browser failure never blocks text or execution.
7. **Execute** — select, claim, run, test, review, and integrate. Actual model selection is append-only run evidence, not a task-contract field.

## Model-aware routing

`plan_work.py` routes every frozen task in this exact order:

1. allowed-model allowlist;
2. verified model capabilities;
3. requested role;
4. sufficient quality tier;
5. cheapest relative cost.

Unknown facts never satisfy hard requirements. Give critics fresh context. Run deterministic tests first. For high-risk work, prefer a stronger or diverse model family when the confirmed policy permits it.

## Control modes

- `autopilot` shows a concise summary and continues only when there are no blockers.
- `ask / CEO` needs explicit `start` before the first claim.
- `ask / manager` also asks about material implementation or integration choices.
- `ask / full_control` asks about small execution choices too.

No mode overrides human-only blockers, destructive or out-of-scope actions, or cross-harness takeover consent.

## Durable board

| Path | Purpose |
|---|---|
| `.agent-board/environment/` | Verified harness facts and confirmed model policy. |
| `.agent-board/tasks/*.json` | Frozen portable task contracts. |
| `.agent-board/claims/` | Worker leases. |
| `.agent-board/runs/` | Append-only execution evidence, including actual runtime/model. |
| `.agent-board/reviews/` | Append-only review findings. |
| `.agent-board/decisions/` | Planning, approval, and reconciliation decisions. |
| `.agent-board/dashboard/` | Disposable HTML/JS dashboard assets. |

Task contracts freeze after plan approval. Runtime facts belong in state, claims, runs, and reviews. Claims are leases, not distributed locks. Git is for history and isolated worktrees, never locking.

## Quick start

Run these from the monorepo root:

```bash
# Initialize a board and record confirmed preflight facts.
python3 adaptive-orchestrator/scripts/init_board.py --name "Project" --goal "Goal" --autonomy autopilot
# Do not run the placeholder. Replace it with complete, user-confirmed research for this harness:
# nonempty models and allowed_models; profiles with roles, quality, cost, capabilities, family,
# and timestamped source links; every role default; autonomy; and multi_harness.
PREFLIGHT_JSON='<replace with complete user-confirmed research JSON>'
# Only run after replacing the placeholder with confirmed facts.
python3 adaptive-orchestrator/scripts/record_preflight.py --json "$PREFLIGHT_JSON"

# Freeze contracts and pass the model-aware plan gate before work.
python3 adaptive-orchestrator/scripts/plan_work.py --runtime <runtime>

# Only after a successful plan gate, select and claim work.
python3 adaptive-orchestrator/scripts/find_work.py --runtime <runtime>
python3 adaptive-orchestrator/scripts/claim_task.py TASK-0001 --runtime <runtime> --worker W

# Build and serve the read-only dashboard.
python3 adaptive-orchestrator/scripts/build_dashboard.py
python3 adaptive-orchestrator/scripts/serve_dashboard.py --board .agent-board
```

See [the skill manual](adaptive-orchestrator/SKILL.md) and its `references/` directory for the operating procedure and JSON contracts.

## Requirements

- Python 3.8+; standard library only.
- Git is recommended for isolated code-changing work.

## License

MIT — see [LICENSE](LICENSE).
