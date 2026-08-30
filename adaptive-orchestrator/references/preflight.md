# Preflight

For a new board, ask exactly `What are we building?` first. Then discover selectable models from the current harness context, its native list, or its API. Ask the user about models only if discovery is uncertain or unavailable.

Ask the user to choose `allowed_models`. Research every selected model in a separate pass before persisting policy. Start with official model cards and documentation. Use current benchmark evidence only as supplementary evidence. For every model, record source links, retrieval timestamps, confidence, known facts, unknown facts, roles, quality tier, and relative cost. Unknown facts stay `unknown`; do not fill them in by inference.

Present this assessment and get confirmation before writing `environment/<runtime-id>.json` with `record_preflight.py`. The stored policy includes `allowed_models`, profiles, and role defaults.

Also record only verified harness identity, tools, and capabilities. Persist `autonomy.mode` as `autopilot` or `ask`; an `ask` policy needs `autonomy.level` of `CEO`, `manager`, or `full_control`. Ask whether multi-harness is enabled; default to `false`.

On an existing board, refresh and confirm missing or stale model policy before a new claim. Do not ask for the goal again.
