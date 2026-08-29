# Adaptive Orchestrator Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an adaptive new/resume workflow, persisted preflight and multi-harness work discovery, plus a read-only live JSON dashboard.

**Architecture:** `.agent-board` remains the sole persistent project state. New CLI helpers record verified runtime preflight and choose eligible READY work; any cross-harness task is only proposed, never claimed automatically. The dashboard consists of disposable `index.html` and `app.js`, served with a read-only Python API that reconstructs its response from board JSON files per request.

**Tech Stack:** Python 3 standard library (`argparse`, `http.server`, `json`, `unittest`), vanilla HTML/CSS/JavaScript.

---

## File structure

- Modify: `SKILL.md` — mandatory invocation flow, adaptive preflight, resume report and panel startup.
- Modify: `references/preflight.md` — persisted preflight contract and question sequence.
- Modify: `references/protocol.md` — panel API and dashboard non-authority rule.
- Modify: `references/schemas/task.schema.json` — optional harness preference under `execution`.
- Create: `references/schemas/environment.schema.json` — runtime/preflight JSON contract.
- Modify: `scripts/boardlib.py` — board reading, requirement matching and reusable board snapshot helpers.
- Modify: `scripts/init_board.py` — accept and persist the selected autonomy policy.
- Create: `scripts/record_preflight.py` — validate and atomically persist verified runtime facts.
- Create: `scripts/find_work.py` — report preferred READY work or a user-confirmed cross-harness proposal.
- Modify: `scripts/build_dashboard.py` — write only HTML and JS assets, never board data.
- Create: `scripts/serve_dashboard.py` — read-only HTTP API and static dashboard server.
- Modify: `agents/openai.yaml` — refresh the user-facing prompt to mention new/resume behavior.
- Create: `tests/test_orchestration.py` — unit and subprocess coverage of state, selection and preflight.
- Create: `tests/test_dashboard.py` — HTTP/API and generated dashboard coverage.

## Task 1: Add board primitives and their RED tests

**Files:**
- Create: `tests/test_orchestration.py`
- Modify: `scripts/boardlib.py`

- [ ] **Step 1: Write failing tests for task eligibility and board snapshots.**

```python
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from boardlib import board_snapshot, requirement_match

class BoardLibTests(unittest.TestCase):
    def test_requirement_match_rejects_unknown_hard_capability(self):
        ok, reasons = requirement_match(
            {"capabilities": {"vision": True}, "tools": ["shell"]},
            {"capabilities": {"vision": "unknown"}, "tools": ["shell"]},
        )
        self.assertFalse(ok)
        self.assertEqual(reasons, ["capability vision is unknown"])

    def test_requirement_match_accepts_verified_requirements(self):
        ok, reasons = requirement_match(
            {"capabilities": {"vision": True}, "tools": ["shell"]},
            {"capabilities": {"vision": True}, "tools": ["shell", "browser"]},
        )
        self.assertTrue(ok)
        self.assertEqual(reasons, [])

    def test_board_snapshot_returns_json_records_and_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = Path(tmp) / ".agent-board"
            (board / "tasks").mkdir(parents=True)
            (board / "state").mkdir()
            (board / "claims").mkdir()
            (board / "runs").mkdir()
            (board / "runs" / "TASK-a").mkdir()
            (board / "reviews").mkdir()
            (board / "project.json").write_text(json.dumps({"name": "Demo"}))
            (board / "tasks" / "TASK-a.json").write_text(json.dumps({"id": "TASK-a"}))
            (board / "state" / "TASK-a.json").write_text(json.dumps({"status": "READY"}))
            (board / "runs" / "TASK-a" / "RUN-a.json").write_text(json.dumps({"run_id": "RUN-a"}))
            snapshot = board_snapshot(board)
            self.assertEqual(snapshot["project"]["name"], "Demo")
            self.assertEqual(snapshot["tasks"][0]["id"], "TASK-a")
            self.assertEqual(snapshot["states"]["TASK-a"]["status"], "READY")
            self.assertEqual(snapshot["runs"][0]["run_id"], "RUN-a")
            self.assertEqual(snapshot["diagnostics"], [])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails.**

Run: `python -m unittest tests.test_orchestration -v`

Expected: import failure because `board_snapshot` and `requirement_match` do not yet exist.

- [ ] **Step 3: Implement the minimal reusable functions in `scripts/boardlib.py`.**

Append these functions after `set_state`:

```python
def _json_files(directory):
    directory = Path(directory)
    return sorted(directory.rglob("*.json")) if directory.exists() else []

def requirement_match(requirements, environment):
    reasons = []
    capabilities = environment.get("capabilities", {})
    for name, required in requirements.get("capabilities", {}).items():
        actual = capabilities.get(name, "unknown")
        if actual == "unknown":
            reasons.append(f"capability {name} is unknown")
        elif actual != required:
            reasons.append(f"capability {name}={actual!r} does not satisfy {required!r}")
    tools = set(environment.get("tools", []))
    for tool in requirements.get("tools", []):
        if tool not in tools:
            reasons.append(f"tool {tool} is unavailable")
    return not reasons, reasons

def board_snapshot(board):
    board = Path(board)
    snapshot = {"project": None, "tasks": [], "states": {}, "claims": [], "runs": [], "reviews": [], "diagnostics": []}
    project = board / "project.json"
    if project.exists():
        try: snapshot["project"] = read(project)
        except Exception as exc: snapshot["diagnostics"].append(f"project.json: {exc}")
    else:
        snapshot["diagnostics"].append("missing project.json")
    for key, directory in (("tasks", "tasks"), ("claims", "claims"), ("runs", "runs"), ("reviews", "reviews")):
        for path in _json_files(board / directory):
            try: snapshot[key].append(read(path))
            except Exception as exc: snapshot["diagnostics"].append(f"{directory}/{path.name}: {exc}")
    for path in _json_files(board / "state"):
        try: snapshot["states"][path.stem] = read(path)
        except Exception as exc: snapshot["diagnostics"].append(f"state/{path.name}: {exc}")
    return snapshot
```

- [ ] **Step 4: Run the focused test and then the complete test suite.**

Run: `python -m unittest tests.test_orchestration -v`

Expected: three passing tests.

Run: `python -m unittest discover -v`

Expected: all discovered tests pass.

- [ ] **Step 5: Commit if this directory has become a Git repository.**

Run: `git rev-parse --is-inside-work-tree`

Expected: `true`; only then run `git add scripts/boardlib.py tests/test_orchestration.py && git commit -m "feat: add board selection primitives"`. If it remains outside Git, do not create a commit and record that fact in the implementation handoff.

## Task 2: Persist preflight and select work without auto-claiming it

**Files:**
- Create: `references/schemas/environment.schema.json`
- Modify: `scripts/init_board.py`
- Create: `scripts/record_preflight.py`
- Create: `scripts/find_work.py`
- Modify: `tests/test_orchestration.py`

- [ ] **Step 1: Write failing subprocess tests for preflight and cross-harness proposals.**

Append this test class to `tests/test_orchestration.py`:

```python
import subprocess

ROOT = Path(__file__).parents[1]

class CommandTests(unittest.TestCase):
    def make_board(self, tmp):
        board = Path(tmp) / ".agent-board"
        for name in ("tasks", "state", "environment", "claims", "runs", "reviews"):
            (board / name).mkdir(parents=True, exist_ok=True)
        (board / "project.json").write_text(json.dumps({"name": "Demo", "goal": "Test", "mode": "autonomous", "phase": "execution"}))
        return board

    def test_record_preflight_persists_autonomy_and_multi_harness(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = self.make_board(tmp)
            payload = {"runtime_id": "codex", "harness": "Codex", "capabilities": {"vision": True}, "tools": ["shell"], "models": ["gpt"], "autonomy": {"mode": "ask", "level": "manager"}, "multi_harness": {"enabled": True, "harnesses": [{"runtime_id": "claude", "purpose": "planning"}]}}
            result = subprocess.run([sys.executable, "scripts/record_preflight.py", "--board", str(board), "--json", json.dumps(payload)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            saved = json.loads((board / "environment" / "codex.json").read_text())
            self.assertEqual(saved["autonomy"], {"mode": "ask", "level": "manager"})
            self.assertTrue(saved["multi_harness"]["enabled"])

    def test_find_work_proposes_other_harness_without_claiming(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = self.make_board(tmp)
            (board / "environment" / "codex.json").write_text(json.dumps({"runtime_id": "codex", "capabilities": {"coding": True}, "tools": ["shell"]}))
            task = {"id": "TASK-a", "title": "Code", "dependencies": [], "requirements": {"capabilities": {"coding": True}, "tools": ["shell"]}, "execution": {"preferred_runtime": "claude"}}
            (board / "tasks" / "TASK-a.json").write_text(json.dumps(task))
            (board / "state" / "TASK-a.json").write_text(json.dumps({"status": "READY"}))
            result = subprocess.run([sys.executable, "scripts/find_work.py", "--board", str(board), "--runtime", "codex"], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["action"], "ask_to_take_over")
            self.assertEqual(report["task"]["id"], "TASK-a")
            self.assertFalse((board / "claims" / "TASK-a.json").exists())
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `python -m unittest tests.test_orchestration.CommandTests -v`

Expected: failures because the two scripts do not exist.

- [ ] **Step 3: Create the environment schema.**

Create `references/schemas/environment.schema.json` with this complete schema:

```json
{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","required":["runtime_id","harness","capabilities","tools","models","autonomy","multi_harness"],"properties":{"runtime_id":{"type":"string"},"harness":{"type":"string"},"capabilities":{"type":"object","additionalProperties":{"anyOf":[{"type":"boolean"},{"const":"unknown"}]}},"tools":{"type":"array","items":{"type":"string"}},"models":{"type":"array","items":{"type":"string"}},"autonomy":{"type":"object","required":["mode"],"properties":{"mode":{"enum":["autopilot","ask"]},"level":{"enum":["CEO","manager","full_control"]}},"allOf":[{"if":{"properties":{"mode":{"const":"ask"}}},"then":{"required":["level"]}}]},"multi_harness":{"type":"object","required":["enabled","harnesses"],"properties":{"enabled":{"type":"boolean"},"harnesses":{"type":"array","items":{"type":"object","required":["runtime_id","purpose"],"properties":{"runtime_id":{"type":"string"},"purpose":{"type":"string"},"capabilities":{"type":"object"},"tools":{"type":"array","items":{"type":"string"}}}}}}}}}
```

- [ ] **Step 4: Create `record_preflight.py` with validation and atomic persistence.**

```python
import argparse, json
from pathlib import Path
from boardlib import write_atomic

parser = argparse.ArgumentParser()
parser.add_argument("--board", default=".agent-board")
parser.add_argument("--json", required=True)
args = parser.parse_args()
data = json.loads(args.json)
required = {"runtime_id", "harness", "capabilities", "tools", "models", "autonomy", "multi_harness"}
missing = sorted(required - data.keys())
if missing: raise SystemExit("missing preflight fields: " + ", ".join(missing))
if data["autonomy"].get("mode") not in {"autopilot", "ask"}: raise SystemExit("invalid autonomy mode")
if data["autonomy"]["mode"] == "ask" and data["autonomy"].get("level") not in {"CEO", "manager", "full_control"}: raise SystemExit("ask mode requires CEO, manager, or full_control")
if not isinstance(data["multi_harness"].get("enabled"), bool) or not isinstance(data["multi_harness"].get("harnesses"), list): raise SystemExit("invalid multi_harness")
path = Path(args.board) / "environment" / f'{data["runtime_id"]}.json'
write_atomic(path, data)
print(path.resolve())
```

- [ ] **Step 5: Create `find_work.py` with explicit proposal semantics.**

```python
import argparse, json
from pathlib import Path
from boardlib import read, requirement_match

parser = argparse.ArgumentParser()
parser.add_argument("--board", default=".agent-board")
parser.add_argument("--runtime", required=True)
args = parser.parse_args()
board = Path(args.board)
environment = read(board / "environment" / f"{args.runtime}.json")
eligible, preferred, transferable, rejected = [], [], [], []
for path in sorted((board / "tasks").glob("*.json")):
    task = read(path); task_id = task["id"]
    state = read(board / "state" / f"{task_id}.json")
    if state["status"] != "READY": continue
    if not all(read(board / "state" / f"{dep}.json")["status"] == "DONE" for dep in task.get("dependencies", [])): continue
    claim = board / "claims" / f"{task_id}.json"
    if claim.exists(): rejected.append({"id": task_id, "reason": "active claim exists"}); continue
    ok, reasons = requirement_match(task.get("requirements", {}), environment)
    if not ok: rejected.append({"id": task_id, "reason": "; ".join(reasons)}); continue
    eligible.append(task)
    if task.get("execution", {}).get("preferred_runtime", args.runtime) == args.runtime: preferred.append(task)
    else: transferable.append(task)
if preferred: report = {"action": "ready_for_current_harness", "task": preferred[0], "rejected": rejected}
elif transferable: report = {"action": "ask_to_take_over", "task": transferable[0], "reason": "current harness satisfies hard requirements but is not the preferred runtime; explicit user approval is required", "rejected": rejected}
else: report = {"action": "no_eligible_work", "reason": "no READY dependency-complete task satisfies this runtime", "rejected": rejected}
print(json.dumps(report, indent=2))
```

- [ ] **Step 6: Add `--autonomy` to `init_board.py`.**

Replace the parser and project write with:

```python
p=argparse.ArgumentParser();p.add_argument('--board',default='.agent-board');p.add_argument('--name',required=True);p.add_argument('--goal',required=True);p.add_argument('--mode',choices=['autonomous','supervised'],default='autonomous');p.add_argument('--autonomy',choices=['autopilot','ask'],default='autopilot');a=p.parse_args();b=Path(a.board)
for d in ['environment','organization/departments','tasks','state','claims','runs','reviews','decisions','change-requests','events','artifacts','dashboard']:(b/d).mkdir(parents=True,exist_ok=True)
write_atomic(b/'protocol.json',{'protocol':'agent-board','version':'0.1'});write_atomic(b/'project.json',{'schema_version':'0.1','name':a.name,'goal':a.goal,'mode':a.mode,'autonomy':a.autonomy,'phase':'planning','created_at':now()});print(b.resolve())
```

- [ ] **Step 7: Run tests and verify cross-harness work was not claimed.**

Run: `python -m unittest tests.test_orchestration -v`

Expected: all tests pass, including `ask_to_take_over` and the absent claim file assertion.

- [ ] **Step 8: Commit if Git is available.**

Run: `git rev-parse --is-inside-work-tree`; when `true`, run `git add references/schemas/environment.schema.json scripts/init_board.py scripts/record_preflight.py scripts/find_work.py tests/test_orchestration.py && git commit -m "feat: add persisted preflight and work proposals"`.

## Task 3: Replace the snapshot dashboard with a live read-only panel

**Files:**
- Create: `tests/test_dashboard.py`
- Modify: `scripts/build_dashboard.py`
- Create: `scripts/serve_dashboard.py`

- [ ] **Step 1: Write failing tests for generated assets and live JSON API.**

```python
import json, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).parents[1]

class DashboardTests(unittest.TestCase):
    def test_build_dashboard_writes_shell_and_fetching_javascript(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = Path(tmp) / ".agent-board"; board.mkdir()
            result = subprocess.run([sys.executable, "scripts/build_dashboard.py", "--board", str(board)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('app.js', (board / "dashboard" / "index.html").read_text())
            self.assertIn('/api/board', (board / "dashboard" / "app.js").read_text())

    def test_server_reflects_board_json_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = Path(tmp) / ".agent-board"; board.mkdir()
            (board / "project.json").write_text(json.dumps({"name": "First"}))
            process = subprocess.Popen([sys.executable, "scripts/serve_dashboard.py", "--board", str(board), "--port", "8765"], cwd=ROOT)
            try:
                time.sleep(0.2)
                self.assertEqual(json.load(urlopen("http://127.0.0.1:8765/api/board"))["project"]["name"], "First")
                (board / "project.json").write_text(json.dumps({"name": "Second"}))
                self.assertEqual(json.load(urlopen("http://127.0.0.1:8765/api/board"))["project"]["name"], "Second")
            finally:
                process.terminate(); process.wait()
```

- [ ] **Step 2: Run dashboard tests to verify they fail.**

Run: `python -m unittest tests.test_dashboard -v`

Expected: the asset assertion fails and `serve_dashboard.py` is missing.

- [ ] **Step 3: Replace `build_dashboard.py` with an asset-only generator.**

```python
import argparse
from pathlib import Path

parser = argparse.ArgumentParser(); parser.add_argument("--board", default=".agent-board"); args = parser.parse_args()
dashboard = Path(args.board) / "dashboard"; dashboard.mkdir(parents=True, exist_ok=True)
(dashboard / "index.html").write_text("""<!doctype html><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Agent Board</title><main><h1 id=\"name\">Agent Board</h1><p id=\"summary\"></p><p id=\"error\" role=\"alert\"></p><section id=\"tasks\"></section></main><script src=\"app.js\"></script>""")
(dashboard / "app.js").write_text("""const byId=id=>document.getElementById(id);\nasync function refresh(){try{const board=await fetch('/api/board',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()});const p=board.project||{};byId('name').textContent=p.name||'Agent Board';byId('summary').textContent=[p.goal,p.phase].filter(Boolean).join(' · ');byId('error').textContent=board.diagnostics.join(' | ');byId('tasks').innerHTML='<table><tr><th>Task</th><th>Title</th><th>Status</th><th>Claim</th></tr>'+board.tasks.map(t=>`<tr><td>${t.id}</td><td>${t.title||''}</td><td>${(board.states[t.id]||{}).status||'unknown'}</td><td>${(board.claims.find(c=>c.task===t.id)||{}).runtime_id||''}</td></tr>`).join('')+'</table>'}catch(e){byId('error').textContent='Unable to refresh board: '+e.message}}\nrefresh();setInterval(refresh,5000);""")
print((dashboard / "index.html").resolve())
```

- [ ] **Step 4: Create the read-only dashboard server.**

```python
import argparse, json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from boardlib import board_snapshot

parser = argparse.ArgumentParser(); parser.add_argument("--board", default=".agent-board"); parser.add_argument("--host", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8765); args = parser.parse_args()
board = Path(args.board).resolve(); dashboard = board / "dashboard"
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw): super().__init__(*a, directory=str(dashboard), **kw)
    def do_GET(self):
        if self.path == "/api/board":
            body = json.dumps(board_snapshot(board)).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        return super().do_GET()
ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
```

- [ ] **Step 5: Run dashboard tests and manually inspect the panel.**

Run: `python -m unittest tests.test_dashboard -v`

Expected: both tests pass.

Run: `python scripts/build_dashboard.py --board /tmp/demo/.agent-board && python scripts/serve_dashboard.py --board /tmp/demo/.agent-board --port 8765`

Expected: `http://127.0.0.1:8765/` loads a panel and data refreshes after JSON changes.

- [ ] **Step 6: Commit if Git is available.**

Run: `git rev-parse --is-inside-work-tree`; when `true`, run `git add scripts/build_dashboard.py scripts/serve_dashboard.py tests/test_dashboard.py && git commit -m "feat: add live read-only board dashboard"`.

## Task 4: Teach the skill the new interaction contract

**Files:**
- Modify: `SKILL.md`
- Modify: `references/preflight.md`
- Modify: `references/protocol.md`
- Modify: `references/schemas/task.schema.json`
- Modify: `agents/openai.yaml`

- [ ] **Step 1: Write a failing documentation-contract test.**

Add this test to `tests/test_orchestration.py`:

```python
    def test_skill_documents_new_resume_preflight_and_dashboard_contract(self):
        text = (ROOT / "SKILL.md").read_text()
        for phrase in ("What are we building?", "autopilot", "full_control", "ask_to_take_over", "serve_dashboard.py"):
            self.assertIn(phrase, text)
```

- [ ] **Step 2: Run it to verify it fails.**

Run: `python -m unittest tests.test_orchestration.CommandTests.test_skill_documents_new_resume_preflight_and_dashboard_contract -v`

Expected: failure because the current skill does not contain the required invocation contract.

- [ ] **Step 3: Rewrite the workflow parts of `SKILL.md`.**

Keep protocol invariants, then add a mandatory entry decision before modes: if `.agent-board/` is absent, ask exactly `What are we building?` and follow it with needed preflight questions; if it exists, validate it, summarize completed/blocked/READY work and run `find_work.py`. Document that `ask_to_take_over` requires explicit user approval before `claim_task.py`. Add the preflight choices `autopilot`, `CEO`, `manager`, and `full_control`. Replace dashboard generation text with `build_dashboard.py` plus `serve_dashboard.py`, explicitly stating that the panel is read-only and `/api/board` is reconstructed from JSON on every request.

- [ ] **Step 4: Update reference contracts and schema.**

In `references/preflight.md`, document goal-first questioning, verified/unknown values, autonomy selections and optional multi-harness inventory/purpose. In `references/protocol.md`, document the asset-only dashboard and read-only API. In `references/schemas/task.schema.json`, define `execution.properties.preferred_runtime` as a string and describe it as optional preference, not a hard requirement. Update `agents/openai.yaml` so `short_description` is `Goal-first project orchestration with adaptive preflight and a live JSON board` and add `default_prompt: "Start or resume an Agent Board project with adaptive preflight."`.

- [ ] **Step 5: Run documentation and full-suite verification.**

Run: `python -m unittest discover -v`

Expected: all tests pass.

Run: `python scripts/validate_board.py --help && python scripts/find_work.py --help && python scripts/serve_dashboard.py --help`

Expected: each command exits successfully and prints usage.

- [ ] **Step 6: Commit if Git is available.**

Run: `git rev-parse --is-inside-work-tree`; when `true`, run `git add SKILL.md references/preflight.md references/protocol.md references/schemas/task.schema.json agents/openai.yaml tests/test_orchestration.py && git commit -m "docs: define adaptive orchestration workflow"`.

## Final verification

- [ ] Run `python -m unittest discover -v`; expect all tests to pass.
- [ ] Create a temporary board with `init_board.py`, record a verified preflight, add one preferred and one other-runtime READY task, and confirm `find_work.py` chooses the preferred task first.
- [ ] Remove the preferred task, confirm `find_work.py` returns `ask_to_take_over`, and verify no claim file is created before the user gives approval.
- [ ] Run `build_dashboard.py` and `serve_dashboard.py`; modify `project.json`, refresh the browser, and confirm the title changes without regenerating HTML.
- [ ] Run `git status --short`; preserve unrelated changes. If this folder is still not a Git repository, state that commits were intentionally skipped.
