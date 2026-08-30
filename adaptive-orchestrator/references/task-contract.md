# Task Contract

Require ID, title, department, objective, dependencies, context references, role, complexity, capability and tool requirements, acceptance criteria, verification, and review policy. Each criterion has an ID, description, and method: `automated_test`, `inspection`, `artifact_check`, `integration_test`, or `human_acceptance`.

Contracts are portable. They may require a role, complexity, and verified capabilities, but never name a concrete model or worker. `plan_work.py` resolves each frozen contract through the confirmed model policy. A missing capability or invalid route blocks the plan; it is not a reason to weaken a contract.

After freeze, material changes require a change request and revision trail.
