import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from boardlib import read, requirement_match
from model_policy import route_task, validate_environment_policy


SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def safe_identifier(value):
    return isinstance(value, str) and bool(SAFE_IDENTIFIER.fullmatch(value))


def load_record(path, relative, diagnostics):
    try:
        record = read(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        diagnostics.append(f"{relative}: {error}")
        return None
    if not isinstance(record, dict):
        diagnostics.append(f"{relative}: expected object")
        return None
    return record


def claim_status(claim, task_id, now):
    required_strings = ("task", "claim_id", "runtime_id", "worker_id", "created_at", "heartbeat_at")
    for field in required_strings:
        if not isinstance(claim.get(field), str) or not claim[field]:
            return f"malformed claim: {field} is required"
    if claim["task"] != task_id:
        return "malformed claim: task does not match claim filename"
    attempt = claim.get("attempt")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        return "malformed claim: positive attempt is required"
    heartbeat = claim.get("heartbeat_at")
    lease = claim.get("lease_seconds")
    if not isinstance(lease, int) or isinstance(lease, bool) or lease < 30:
        return "malformed claim: lease_seconds must be at least 30"
    try:
        created_at = datetime.fromisoformat(claim["created_at"].replace("Z", "+00:00"))
        heartbeat_at = datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))
        if created_at.tzinfo is None or heartbeat_at.tzinfo is None:
            return "malformed claim: timestamps must include a timezone"
    except ValueError:
        return "malformed claim: invalid timestamp"
    if heartbeat_at + timedelta(seconds=lease) < now:
        return "expired claim requires reconciliation"
    return "active claim blocks task"


def valid_environment(environment):
    capabilities = environment.get("capabilities")
    if not isinstance(capabilities, dict):
        return False, "capabilities must be an object"
    if not all(value is True or value is False or value == "unknown" for value in capabilities.values()):
        return False, "invalid capability fact"
    tools = environment.get("tools")
    if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
        return False, "tools must be an array of strings"
    try:
        validate_environment_policy(environment)
    except ValueError as error:
        return False, "invalid model policy: " + str(error)
    return True, None


def dependencies_complete(board, task, diagnostics):
    dependencies = task.get("dependencies", [])
    if not isinstance(dependencies, list):
        return False, "dependencies must be an array"
    for dependency in dependencies:
        if not safe_identifier(dependency):
            return False, f"invalid dependency identifier: {dependency!r}"
        relative = f"state/{dependency}.json"
        state = load_record(board / "state" / f"{dependency}.json", relative, diagnostics)
        if state is None:
            return False, f"dependency state unavailable: {dependency}"
        if state.get("status") != "DONE":
            return False, f"dependency is not DONE: {dependency}"
    return True, None


def emit(report):
    print(json.dumps(report, indent=2))


parser = argparse.ArgumentParser()
parser.add_argument("--board", default=".agent-board")
parser.add_argument("--runtime", required=True)
args = parser.parse_args()
board = Path(args.board)
diagnostics, rejected, claim_issues = [], {}, []
if not safe_identifier(args.runtime):
    emit({
        "action": "no_eligible_work",
        "reason": "invalid runtime identifier",
        "rejected": rejected,
        "diagnostics": diagnostics,
        "claim_issues": claim_issues,
    })
    raise SystemExit

environment = load_record(
    board / "environment" / f"{args.runtime}.json",
    f"environment/{args.runtime}.json",
    diagnostics,
)
if environment is None:
    emit({
        "action": "no_eligible_work",
        "reason": "current environment is unavailable or invalid",
        "rejected": rejected,
        "diagnostics": diagnostics,
        "claim_issues": claim_issues,
    })
    raise SystemExit
environment_valid, environment_reason = valid_environment(environment)
if not environment_valid:
    diagnostics.append(f"environment/{args.runtime}.json: {environment_reason}")
    emit({
        "action": "no_eligible_work",
        "reason": "current environment is unavailable or invalid",
        "rejected": rejected,
        "diagnostics": diagnostics,
        "claim_issues": claim_issues,
    })
    raise SystemExit

preferred, transferable = [], []
try:
    task_paths = sorted((board / "tasks").glob("*.json"))
except OSError as error:
    diagnostics.append(f"tasks: {error}")
    task_paths = []

for path in task_paths:
    relative = f"tasks/{path.name}"
    task = load_record(path, relative, diagnostics)
    if task is None:
        continue
    task_id = task.get("id")
    if not safe_identifier(task_id):
        rejected[str(task_id)] = "invalid task identifier"
        continue
    state = load_record(board / "state" / f"{task_id}.json", f"state/{task_id}.json", diagnostics)
    if state is None:
        rejected[task_id] = "state unavailable or invalid"
        continue
    if state.get("status") != "READY":
        continue
    dependencies_ready, dependency_reason = dependencies_complete(board, task, diagnostics)
    if not dependencies_ready:
        rejected[task_id] = dependency_reason
        continue
    claim_path = board / "claims" / f"{task_id}.json"
    if claim_path.exists():
        claim = load_record(claim_path, f"claims/{task_id}.json", diagnostics)
        if claim is None:
            reason = "malformed claim requires reconciliation"
        else:
            reason = claim_status(claim, task_id, datetime.now(timezone.utc))
        rejected[task_id] = reason
        if reason != "active claim blocks task":
            claim_issues.append({"task": task_id, "action": "reconcile_claim", "reason": reason})
        continue
    try:
        matches, reason = requirement_match(task.get("requirements", {}), environment)
    except (AttributeError, TypeError, KeyError) as error:
        rejected[task_id] = f"invalid requirements: {error}"
        continue
    if not matches:
        rejected[task_id] = reason
        continue
    _, model_gap = route_task(task, environment["model_policy"])
    if model_gap is not None:
        rejected[task_id] = model_gap["reason"]
        continue
    execution = task.get("execution", {})
    if not isinstance(execution, dict):
        rejected[task_id] = "execution must be an object"
        continue
    if execution.get("preferred_runtime", args.runtime) == args.runtime:
        preferred.append(task)
    else:
        transferable.append(task)

if preferred:
    report = {"action": "ready_for_current_harness", "task": preferred[0]}
elif transferable:
    report = {
        "action": "ask_to_take_over",
        "task": transferable[0],
        "reason": "current harness satisfies hard requirements but is not the preferred runtime; explicit user approval is required",
    }
elif claim_issues:
    report = {
        "action": "reconcile_claim",
        "reason": claim_issues[0]["reason"],
    }
else:
    report = {
        "action": "no_eligible_work",
        "reason": "no READY dependency-complete unclaimed task satisfies this runtime",
    }
report.update({"rejected": rejected, "diagnostics": diagnostics, "claim_issues": claim_issues})
emit(report)
