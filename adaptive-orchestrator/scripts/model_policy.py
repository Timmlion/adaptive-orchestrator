"""Validation helpers for persisted environment model policies."""

from datetime import datetime
from urllib.parse import urlparse


ROLES = {"fast_worker", "coder", "reasoner", "critic", "escalation"}
QUALITY_TIERS = {"basic", "standard", "advanced"}
RELATIVE_COSTS = {"low", "medium", "high", "unknown"}
RESEARCH_STATUSES = {"verified", "unknown"}
CONFIDENCES = {"low", "medium", "high"}


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
