import http.client
import json
import select
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


@contextmanager
def running_server(board):
    server = subprocess.Popen(
        [sys.executable, str(SCRIPTS / "serve_dashboard.py"), "--board", str(board), "--port", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        ready, _, _ = select.select([server.stdout], [], [], 5)
        if not ready:
            raise AssertionError("dashboard server did not report readiness")
        line = server.stdout.readline().strip()
        if not line.startswith("READY "):
            raise AssertionError(f"unexpected dashboard server readiness: {line!r}")
        yield server, int(line.removeprefix("READY "))
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
            raise AssertionError("dashboard server did not terminate")
        finally:
            server.stdout.close()
            server.stderr.close()
        if server.returncode != 0:
            raise AssertionError(f"dashboard server exited with {server.returncode}")


def get(port, path):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


class DashboardTests(unittest.TestCase):
    def routing_environment(self):
        return {
            "models": ["fast", "deep"],
            "model_policy": {
                "allowed_models": ["fast", "deep"],
                "profiles": [
                    {"id": "fast", "roles": ["fast_worker", "coder", "escalation"], "quality_tier": "standard", "relative_cost": "low", "capabilities": {"coding": True}, "family": "test", "research": {"status": "verified", "confidence": "high", "sources": [{"url": "https://example.com/fast", "retrieved_at": "2026-08-29T12:00:00Z", "summary": "Verified."}]}},
                    {"id": "deep", "roles": ["reasoner", "critic"], "quality_tier": "advanced", "relative_cost": "high", "capabilities": {"coding": True}, "family": "test", "research": {"status": "unknown", "confidence": "medium", "sources": []}},
                ],
                "role_defaults": {"fast_worker": "fast", "coder": "fast", "reasoner": "deep", "critic": "deep", "escalation": "fast"},
            },
        }

    def test_generator_writes_shell_that_loads_live_api_client(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / ".agent-board"
            subprocess.run(
                [sys.executable, str(SCRIPTS / "build_dashboard.py"), "--board", str(board)],
                check=True,
                capture_output=True,
                text=True,
            )

            index = (board / "dashboard" / "index.html").read_text()
            app = (board / "dashboard" / "app.js").read_text()

        self.assertIn('src="app.js"', index)
        self.assertIn("/api/board", app)
        self.assertIn("claim.worker_id", app)
        self.assertIn('id="runs"', index)
        self.assertIn('id="reviews"', index)
        self.assertIn("snapshot.runs", app)
        self.assertIn("snapshot.reviews", app)
        for element_id in ("plan-summary", "model-policy", "model-routes", "capability-gaps"):
            self.assertIn(f'id="{element_id}"', index)
        for reference in ("snapshot.environments", "snapshot.plan", "plan.summary", "research_warnings", "capability_gaps"):
            self.assertIn(reference, app)
        for summary_field in ("routed", "gaps", "blocked", "research_warnings"):
            self.assertIn(summary_field, app)
        self.assertIn("No confirmed model policy yet", app)
        self.assertIn("No capability gaps", app)
        self.assertNotIn("innerHTML", app)
        self.assertNotIn("project.json", index + app)

    def test_api_reads_project_changes_without_dashboard_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / ".agent-board"
            board.mkdir()
            project = board / "project.json"
            project.write_text(json.dumps({"name": "First", "goal": "Goal", "phase": "planning"}))
            with running_server(board) as (_, port):
                status, headers, body = get(port, "/api/board")
                self.assertEqual(status, 200)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertEqual(json.loads(body)["project"]["name"], "First")

                project.write_text(json.dumps({"name": "Second", "goal": "Goal", "phase": "delivery"}))
                status, _, body = get(port, "/api/board")
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["project"]["name"], "Second")

    def test_api_returns_diagnostics_for_missing_and_malformed_records(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / ".agent-board"
            (board / "tasks").mkdir(parents=True)
            (board / "tasks" / "broken.json").write_text("{")
            with running_server(board) as (_, port):
                _, _, body = get(port, "/api/board")
                diagnostics = json.loads(body)["diagnostics"]
                self.assertIn("project.json: missing", diagnostics)
                self.assertTrue(any(item.startswith("tasks/broken.json:") for item in diagnostics))

    def test_api_returns_valid_json_for_malformed_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / ".agent-board"
            environment = board / "environment" / "codex.json"
            environment.parent.mkdir(parents=True)
            environment.write_text("{")
            with running_server(board) as (_, port):
                status, _, body = get(port, "/api/board")

        snapshot = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(snapshot["environments"], {})
        self.assertTrue(any(item.startswith("environment/codex.json:") for item in snapshot["diagnostics"]))

    def test_api_returns_valid_json_when_snapshot_has_non_finite_values(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / ".agent-board"
            board.mkdir()
            (board / "project.json").write_text('{"name": NaN}')

            with running_server(board) as (_, port):
                status, headers, body = get(port, "/api/board")

        self.assertEqual(status, 500)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("error", json.loads(body))

    def test_api_refreshes_model_routes_after_task_complexity_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / ".agent-board"
            board.mkdir()
            environment = board / "environment" / "codex.json"
            environment.parent.mkdir()
            environment.write_text(json.dumps(self.routing_environment()))
            task = board / "tasks" / "TASK-a.json"
            task.parent.mkdir()
            task.write_text(json.dumps({"id": "TASK-a", "execution": {"model_role": "coder", "model_complexity": "medium"}}))
            state = board / "state" / "TASK-a.json"
            state.parent.mkdir()
            state.write_text(json.dumps({"status": "READY"}))

            with running_server(board) as (_, port):
                _, _, body = get(port, "/api/board")
                self.assertEqual(json.loads(body)["plan"]["codex"]["routes"][0]["model"], "fast")

                task.write_text(json.dumps({"id": "TASK-a", "execution": {"model_role": "reasoner", "model_complexity": "high"}}))
                _, _, body = get(port, "/api/board")
                self.assertEqual(json.loads(body)["plan"]["codex"]["routes"][0]["model"], "deep")


if __name__ == "__main__":
    unittest.main()
