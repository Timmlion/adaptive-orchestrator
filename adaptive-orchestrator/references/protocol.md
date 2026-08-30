# Agent Board Protocol v0.1

`.agent-board` is durable shared state. Its layout includes `protocol.json`, `project.json`, `environment/`, `organization/`, `tasks/`, `state/`, `claims/`, `runs/`, `reviews/`, `decisions/`, `change-requests/`, `events/`, `artifacts/`, and `dashboard/`. Frozen tasks are contracts; runs and reviews are append-only evidence. The dashboard is disposable.

For each runtime, `environment/<runtime>.json` keeps the confirmed `model_policy`, including `allowed_models` and researched profiles. Refresh and confirm a missing or stale policy before a new claim. The plan gate validates this policy and task routes before any claim.

Always build dashboard assets after plan freeze. `dashboard/index.html` and `dashboard/app.js` are presentation only. `serve_dashboard.py` gives a loopback, read-only `/api/board` projection rebuilt from JSON on each request. A verified browser preview may open the URL. If it cannot open, print the URL and give the same short briefing in chat; browser failure does not block text or execution.

States: `PLANNED READY CLAIMED IN_PROGRESS IN_REVIEW REVISION_REQUIRED BLOCKED WAITING_FOR_HUMAN WAITING_FOR_EXTERNAL DONE CANCELLED`. Normal flow is `PLANNED` → `READY` → `CLAIMED` → `IN_PROGRESS` → `IN_REVIEW` → `DONE`; rejection returns to `REVISION_REQUIRED` then `READY`. Execution is at-least-once.
