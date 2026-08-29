"""Validation helpers for persisted environment model policies."""

from datetime import datetime
from urllib.parse import urlparse


ROLES = {"fast_worker", "coder", "reasoner", "critic", "escalation"}
ROLE = ROLES
QUALITY_TIERS = {"basic", "standard", "advanced"}
RELATIVE_COSTS = {"low", "medium", "high", "unknown"}
RESEARCH_STATUSES = {"verified", "unknown"}
CONFIDENCES = {"low", "medium", "high"}
QUALITY_MINIMUM = {"low": "basic", "medium": "standard", "high": "advanced"}
QUALITY_RANK = {"basic": 0, "standard": 1, "advanced": 2}
COST_RANK = {"low": 0, "medium": 1, "high": 2, "unknown": 3}


def is_fact(value):
    return type(value) is bool or value == "unknown"


def _nonempty_string(value):
    return isinstance(value, str) and bool(value)


def _exact_keys(value, expected, field):
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(field)


def _string_list(value, field):
    if not isinstance(value, list) or not all(_nonempty_string(item) for item in value):
        raise ValueError(field)
    if len(set(value)) != len(value):
        raise ValueError(field)


def _enum(value, allowed, field):
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(field)


def _validate_research(research):
    _exact_keys(research, {"status", "confidence", "sources"}, "research")
    _enum(research["status"], RESEARCH_STATUSES, "research.status")
    _enum(research["confidence"], CONFIDENCES, "research.confidence")
    sources = research["sources"]
    if not isinstance(sources, list):
        raise ValueError("research.sources")
    if research["status"] == "verified" and not sources:
        raise ValueError("research.sources")
    for source in sources:
        _exact_keys(source, {"url", "retrieved_at", "summary"}, "research.sources")
        if not _nonempty_string(source["url"]):
            raise ValueError("research.sources.url")
        try:
            parsed_url = urlparse(source["url"])
        except ValueError:
            raise ValueError("research.sources.url")
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("research.sources.url")
        if not _nonempty_string(source["summary"]):
            raise ValueError("research.sources.summary")
        timestamp = source["retrieved_at"]
        if not _nonempty_string(timestamp):
            raise ValueError("research.sources.retrieved_at")
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("research.sources.retrieved_at")
        if parsed.tzinfo is None:
            raise ValueError("research.sources.retrieved_at")


def validate_model_policy(models, policy):
    """Raise ValueError naming an invalid field, or return None when valid."""
    _string_list(models, "models")
    _exact_keys(policy, {"allowed_models", "profiles", "role_defaults"}, "model_policy")
    allowed_models = policy["allowed_models"]
    _string_list(allowed_models, "allowed_models")
    if not allowed_models:
        raise ValueError("allowed_models")
    if not set(allowed_models).issubset(set(models)):
        raise ValueError("allowed_models")

    profiles = policy["profiles"]
    if not isinstance(profiles, list):
        raise ValueError("profiles")
    profile_ids = []
    for profile in profiles:
        _exact_keys(
            profile,
            {"id", "roles", "quality_tier", "relative_cost", "capabilities", "family", "research"},
            "profiles",
        )
        model_id = profile["id"]
        if not _nonempty_string(model_id) or model_id not in allowed_models:
            raise ValueError("profiles.id")
        profile_ids.append(model_id)
        roles = profile["roles"]
        _string_list(roles, "profiles.roles")
        if not roles or not set(roles).issubset(ROLES):
            raise ValueError("profiles.roles")
        _enum(profile["quality_tier"], QUALITY_TIERS, "profiles.quality_tier")
        _enum(profile["relative_cost"], RELATIVE_COSTS, "profiles.relative_cost")
        capabilities = profile["capabilities"]
        if not isinstance(capabilities, dict) or not all(is_fact(value) for value in capabilities.values()):
            raise ValueError("profiles.capabilities")
        if not _nonempty_string(profile["family"]):
            raise ValueError("profiles.family")
        _validate_research(profile["research"])
    if len(profile_ids) != len(set(profile_ids)) or set(profile_ids) != set(allowed_models):
        raise ValueError("profiles")

    role_defaults = policy["role_defaults"]
    _exact_keys(role_defaults, ROLES, "role_defaults")
    profiles_by_id = {profile["id"]: profile for profile in profiles}
    for role, model_id in role_defaults.items():
        if not _nonempty_string(model_id) or model_id not in allowed_models:
            raise ValueError("role_defaults." + role)
        if role not in profiles_by_id[model_id]["roles"]:
            raise ValueError("role_defaults." + role)


def validate_environment_policy(environment):
    if not isinstance(environment, dict):
        raise ValueError("environment")
    if "models" not in environment:
        raise ValueError("models")
    if "model_policy" not in environment:
        raise ValueError("model_policy")
    validate_model_policy(environment["models"], environment["model_policy"])


def _gap(task, role, reason, capability=None, candidates_checked=None):
    return {
        "task": task.get("id") if isinstance(task, dict) else None,
        "role": role,
        "capability": capability,
        "reason": reason,
        "candidates_checked": candidates_checked or [],
    }


def _task_route_requirements(task):
    if not isinstance(task, dict):
        return None, _gap(task, None, "task must be an object")
    if not _nonempty_string(task.get("id")):
        return None, _gap(task, None, "task.id must be a non-empty string")
    execution = task.get("execution", {})
    if not isinstance(execution, dict):
        return None, _gap(task, None, "execution must be an object")
    review_policy = task.get("review_policy", {})
    if not isinstance(review_policy, dict):
        return None, _gap(task, None, "review_policy must be an object")
    role = execution.get("model_role", "coder")
    complexity = execution.get("model_complexity", "medium")
    required_capabilities = execution.get("required_model_capabilities", {})
    if not isinstance(role, str) or role not in ROLES:
        return None, _gap(task, None, "execution.model_role is invalid")
    if not isinstance(complexity, str) or complexity not in QUALITY_MINIMUM:
        return None, _gap(task, role, "execution.model_complexity is invalid")
    if not isinstance(required_capabilities, dict):
        return None, _gap(task, role, "execution.required_model_capabilities must be an object")
    if not all(_nonempty_string(name) for name in required_capabilities):
        return None, _gap(task, role, "execution.required_model_capabilities keys must be non-empty strings")
    if not all(value is True for value in required_capabilities.values()):
        return None, _gap(task, role, "execution.required_model_capabilities values must be true")
    independent_context = review_policy.get("independent_context", False)
    if not isinstance(independent_context, bool):
        return None, _gap(task, role, "review_policy.independent_context must be boolean")
    review_role = review_policy.get("model_role")
    if review_role is not None and (not isinstance(review_role, str) or review_role not in ROLES):
        return None, _gap(task, role, "review_policy.model_role is invalid")
    if independent_context:
        role = review_role or "critic"
    return (role, complexity, {name for name, value in required_capabilities.items() if value is True}, independent_context), None


def route_task(task, policy):
    """Return a deterministic route and optional capability/policy gap for one task."""
    requirements, gap = _task_route_requirements(task)
    if gap is not None:
        return None, gap
    role, complexity, required_capabilities, independent_context = requirements
    try:
        validate_model_policy(policy.get("allowed_models"), policy)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return None, _gap(task, role, "invalid model policy: " + str(error))
    candidates = []
    checked = []
    for profile in policy["profiles"]:
        profile_id = profile["id"]
        checked.append(profile_id)
        if role not in profile["roles"]:
            continue
        if QUALITY_RANK[profile["quality_tier"]] < QUALITY_RANK[QUALITY_MINIMUM[complexity]]:
            continue
        missing = next((name for name in sorted(required_capabilities) if profile["capabilities"].get(name) is not True), None)
        if missing is not None:
            continue
        candidates.append(profile)
    if not candidates:
        missing_capability = next(iter(sorted(required_capabilities)), None)
        reason = "no eligible model for role " + role
        if missing_capability is not None:
            reason += " with required capability " + missing_capability
        return None, _gap(task, role, reason, missing_capability, checked)
    selected = min(candidates, key=lambda profile: (COST_RANK[profile["relative_cost"]], profile["id"]))
    return {
        "task": task.get("id"),
        "model": selected["id"],
        "role": role,
        "model_complexity": complexity,
        "independent_context": independent_context,
        "research_status": selected["research"]["status"],
    }, None


def plan_projection(environment, tasks, states, runtime):
    """Produce a JSON-safe, read-only routing projection for planned work."""
    report = {
        "status": "ready",
        "runtime": runtime,
        "routes": [],
        "capability_gaps": [],
        "blocked_tasks": [],
        "research_warnings": [],
        "summary": {},
    }
    try:
        validate_environment_policy(environment)
    except (KeyError, TypeError, ValueError) as error:
        report["status"] = "blocked"
        report["blocked_tasks"].append({"task": None, "reason": "invalid environment policy: " + str(error)})
        report["summary"] = {"routed": 0, "gaps": 0, "blocked": 1, "research_warnings": 0}
        return report
    if not isinstance(tasks, list):
        tasks = []
    if not isinstance(states, dict):
        states = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not _nonempty_string(task_id):
            _, gap = route_task(task, environment["model_policy"])
            report["capability_gaps"].append(gap)
            report["status"] = "blocked"
            report["blocked_tasks"].append({"task": None, "reason": gap["reason"]})
            continue
        state = states.get(task_id, {})
        status = state.get("status") if isinstance(state, dict) else None
        if status not in {"PLANNED", "READY"}:
            continue
        route, gap = route_task(task, environment["model_policy"])
        if gap is not None:
            report["capability_gaps"].append(gap)
            report["status"] = "blocked"
            report["blocked_tasks"].append({"task": task_id, "reason": gap["reason"]})
            continue
        report["routes"].append(route)
        if route["research_status"] == "unknown":
            report["research_warnings"].append({"task": task_id, "model": route["model"], "reason": "model research is unknown"})
    report["summary"] = {
        "routed": len(report["routes"]),
        "gaps": len(report["capability_gaps"]),
        "blocked": len(report["blocked_tasks"]),
        "research_warnings": len(report["research_warnings"]),
    }
    return report
