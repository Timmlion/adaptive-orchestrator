# Agent Board Protocol v0.1
`.agent-board` is the shared durable source of truth. Layout: `protocol.json`, `project.json`, `environment/`, `organization/`, `tasks/`, `state/`, `claims/`, `runs/`, `reviews/`, `decisions/`, `change-requests/`, `events/`, `artifacts/`, `dashboard/`. Task definitions are frozen contracts after plan acceptance. Runs/reviews are append-only evidence. Dashboard is disposable.

States: `PLANNED READY CLAIMED IN_PROGRESS IN_REVIEW REVISION_REQUIRED BLOCKED WAITING_FOR_HUMAN WAITING_FOR_EXTERNAL DONE CANCELLED`. Normal flow: PLANNED→READY→CLAIMED→IN_PROGRESS→IN_REVIEW→DONE; rejection: IN_REVIEW→REVISION_REQUIRED→READY. Assume at-least-once execution.
