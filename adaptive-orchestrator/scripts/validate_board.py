import argparse
import sys
from pathlib import Path

from boardlib import STATUSES, read


parser = argparse.ArgumentParser()
parser.add_argument("--board", default=".agent-board")
args = parser.parse_args()
board = Path(args.board)
errors = []
tasks = {}
states = {}


def report(relative, message):
    errors.append(f"{relative}: {message}")


def read_object(path, relative):
    if not path.exists():
        report(relative, "missing")
        return None
    try:
        value = read(path)
    except Exception as error:
        report(relative, str(error))
        return None
    if not isinstance(value, dict):
        report(relative, "expected object")
        return None
    return value


for filename in ("protocol.json", "project.json"):
    read_object(board / filename, filename)

tasks_directory = board / "tasks"
for path in sorted(tasks_directory.glob("*.json")) if tasks_directory.exists() else []:
    relative = path.relative_to(board).as_posix()
    task = read_object(path, relative)
    if task is None:
        continue
    task_id = task.get("id")
    if not task_id:
        report(relative, "missing id")
        continue
    if task_id in tasks:
        errors.append(f"duplicate {task_id}")
    tasks[task_id] = task

state_directory = board / "state"
for path in sorted(state_directory.glob("*.json")) if state_directory.exists() else []:
    relative = path.relative_to(board).as_posix()
    state = read_object(path, relative)
    if state is None:
        continue
    states[path.stem] = state
    if state.get("status") not in STATUSES:
        report(relative, "illegal status")

for directory in ("claims", "runs", "reviews", "decisions"):
    root = board / directory
    for path in sorted(root.rglob("*.json")) if root.exists() else []:
        read_object(path, path.relative_to(board).as_posix())

for task_id, task in tasks.items():
    dependencies = task.get("dependencies", [])
    if not isinstance(dependencies, list):
        errors.append(f"{task_id}: dependencies must be a list")
        dependencies = []
    for dependency in dependencies:
        if dependency not in tasks:
            errors.append(f"{task_id}: missing dependency {dependency}")
    if task_id not in states:
        errors.append(f"{task_id}: missing state")

visiting = set()
done = set()


def visit(task_id):
    if task_id in visiting:
        errors.append(f"dependency cycle at {task_id}")
        return
    if task_id in done:
        return
    visiting.add(task_id)
    dependencies = tasks[task_id].get("dependencies", [])
    if isinstance(dependencies, list):
        for dependency in dependencies:
            if dependency in tasks:
                visit(dependency)
    visiting.remove(task_id)
    done.add(task_id)


for task_id in tasks:
    visit(task_id)

if errors:
    print("\n".join(f"ERROR: {error}" for error in errors))
    sys.exit(1)
print(f"OK: {len(tasks)} tasks, DAG valid")
