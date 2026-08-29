import argparse
import json
import re
from pathlib import Path

from boardlib import write_atomic


REQUIRED = {"runtime_id", "harness", "capabilities", "tools", "models", "autonomy", "multi_harness"}
RUNTIME_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def fail(message):
    raise SystemExit(message)


def strings(value, name):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        fail(f"{name} must be an array of strings")


def validate(data):
    if not isinstance(data, dict):
        fail("preflight must be a JSON object")
    missing = REQUIRED - data.keys()
    if missing:
        fail("missing required fields: " + ", ".join(sorted(missing)))
    if not isinstance(data["runtime_id"], str) or not RUNTIME_ID.fullmatch(data["runtime_id"]):
        fail("runtime_id must contain only letters, numbers, underscores, or hyphens")
    if not isinstance(data["harness"], str) or not data["harness"]:
        fail("harness must be a non-empty string")
    capabilities = data["capabilities"]
    if not isinstance(capabilities, dict) or not all(value is True or value is False or value == "unknown" for value in capabilities.values()):
        fail("capabilities must map names to true, false, or unknown")
    strings(data["tools"], "tools")
    strings(data["models"], "models")
    autonomy = data["autonomy"]
    if not isinstance(autonomy, dict) or autonomy.get("mode") not in {"autopilot", "ask"}:
        fail("autonomy mode must be autopilot or ask")
    if autonomy["mode"] == "ask" and autonomy.get("level") not in {"CEO", "manager", "full_control"}:
        fail("ask mode requires CEO, manager, or full_control")
    if "level" in autonomy and autonomy["level"] not in {"CEO", "manager", "full_control"}:
        fail("invalid autonomy level")
    multi_harness = data["multi_harness"]
    if not isinstance(multi_harness, dict) or not isinstance(multi_harness.get("enabled"), bool):
        fail("multi_harness enabled must be boolean")
    harnesses = multi_harness.get("harnesses")
    if not isinstance(harnesses, list):
        fail("multi_harness harnesses must be an array")
    for harness in harnesses:
        if not isinstance(harness, dict) or not all(isinstance(harness.get(name), str) and harness[name] for name in ("runtime_id", "purpose")):
            fail("each multi_harness inventory entry requires runtime_id and purpose")
        if "tools" in harness:
            strings(harness["tools"], "multi_harness tools")
        if "capabilities" in harness:
            facts = harness["capabilities"]
            if not isinstance(facts, dict) or not all(value is True or value is False or value == "unknown" for value in facts.values()):
                fail("multi_harness capabilities must map names to true, false, or unknown")


parser = argparse.ArgumentParser()
parser.add_argument("--board", default=".agent-board")
parser.add_argument("--json", required=True, dest="payload")
args = parser.parse_args()
try:
    data = json.loads(args.payload)
except json.JSONDecodeError as error:
    fail(f"invalid JSON: {error.msg}")
validate(data)
path = Path(args.board) / "environment" / f"{data['runtime_id']}.json"
write_atomic(path, data)
print(path.resolve())
