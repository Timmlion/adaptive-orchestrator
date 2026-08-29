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


if __name__ == "__main__":
    unittest.main()
