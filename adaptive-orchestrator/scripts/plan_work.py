import argparse
import json
from pathlib import Path

from model_policy import plan_projection


def load_object(path, relative, diagnostics):
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        diagnostics.append(relative + ": " + str(error))
        return None
    if not isinstance(value, dict):
        diagnostics.append(relative + ": expected object")
        return None
    return value


def load_records(board, directory, diagnostics, keyed=False):
    records = {} if keyed else []
    try:
        paths = sorted((board / directory).glob("*.json"))
    except OSError as error:
        diagnostics.append(directory + ": " + str(error))
        return records
    for path in paths:
        value = load_object(path, directory + "/" + path.name, diagnostics)
        if value is None:
            continue
        if keyed:
            records[path.stem] = value
        else:
            records.append(value)
    return records


parser = argparse.ArgumentParser()
parser.add_argument("--board", default=".agent-board")
parser.add_argument("--runtime", required=True)
args = parser.parse_args()
board = Path(args.board)
diagnostics = []
environment = load_object(board / "environment" / (args.runtime + ".json"), "environment/" + args.runtime + ".json", diagnostics)
report = plan_projection(environment, load_records(board, "tasks", diagnostics), load_records(board, "state", diagnostics, True), args.runtime)
if diagnostics:
    report["diagnostics"] = diagnostics
print(json.dumps(report, indent=2, sort_keys=True))
if report["status"] == "blocked":
    raise SystemExit(1)
