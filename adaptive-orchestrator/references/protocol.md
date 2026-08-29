# Agent Board Protocol v0.1
`.agent-board` is the shared durable source of truth. Layout: `protocol.json`, `project.json`, `environment/`, `organization/`, `tasks/`, `state/`, `claims/`, `runs/`, `reviews/`, `decisions/`, `change-requests/`, `events/`, `artifacts/`, `dashboard/`. Task definitions are frozen contracts after plan acceptance. Runs/reviews are append-only evidence. Dashboard is disposable.

`dashboard/index.html` and `dashboard/app.js` are presentation assets only. `serve_dashboard.py` supplies a loopback, read-only `/api/board` response reconstructed from JSON files per request; no dashboard route mutates the board. Missing or malformed records become diagnostics in that projection.

States: `PLANNED READY CLAIMED IN_PROGRESS IN_REVIEW REVISION_REQUIRED BLOCKED WAITING_FOR_HUMAN WAITING_FOR_EXTERNAL DONE CANCELLED`. Normal flow: PLANNED→READY→CLAIMED→IN_PROGRESS→IN_REVIEW→DONE; rejection: IN_REVIEW→REVISION_REQUIRED→READY. Assume at-least-once execution.
