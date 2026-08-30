# Model Selection

Select only from `allowed_models`. Route in this exact order:

1. `allowed_models` allowlist;
2. verified model capabilities;
3. requested role;
4. sufficient quality tier;
5. cheapest relative cost among the remaining candidates.

Unknown is not verified and never satisfies a hard requirement. Do not infer capabilities, quality, cost, or roles from a model name or an unrelated source.

The plan assigns a model from policy, but the actual model belongs only in append-only run evidence. Give critics fresh context. Run deterministic tests before a critic. For high-risk work, prefer a stronger model or a diverse model family when the policy allows it.
