# Preflight

For a new board, ask the goal before preflight. Then write `environment/<runtime-id>.json` with only verified harness identity, models, tools and capabilities; use `unknown` when unverifiable. Distinguish available models from models selectable per worker.

Persist `autonomy.mode` as `autopilot` or `ask`. An `ask` policy requires `autonomy.level`: `CEO`, `manager` or `full_control`.

Ask whether multi-harness is enabled. The default is `false`. When enabled, record known harness runtime IDs, intended purposes and only their verified facts. Harness roles are scheduling preferences; current verified requirements determine eligibility.
