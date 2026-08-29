import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_board.py"


def validate(board):
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--board", str(board)],
        capture_output=True,
        text=True,
    )


class ValidateBoardTests(unittest.TestCase):
    def test_reports_malformed_protocol_json_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            (board / "protocol.json").write_text("{")
            (board / "project.json").write_text(json.dumps({}))

            result = validate(board)

        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR: protocol.json:", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_reports_malformed_project_json_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            (board / "protocol.json").write_text(json.dumps({}))
            (board / "project.json").write_text("{")

            result = validate(board)

        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR: project.json:", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_reports_unrelated_malformed_state_json_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            (board / "protocol.json").write_text(json.dumps({}))
            (board / "project.json").write_text(json.dumps({}))
            (board / "state").mkdir()
            (board / "state" / "unrelated.json").write_text("{")

            result = validate(board)

        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR: state/unrelated.json:", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_reports_malformed_nested_audit_records_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            (board / "protocol.json").write_text(json.dumps({}))
            (board / "project.json").write_text(json.dumps({}))
            records = {
                "claims/bad.json": "{",
                "runs/TASK-a/bad.json": "[]",
                "reviews/TASK-a/bad.json": "{",
                "decisions/nested/bad.json": "null",
            }
            for relative, contents in records.items():
                path = board / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents)

            result = validate(board)

        self.assertEqual(result.returncode, 1)
        for relative in records:
            self.assertIn(f"ERROR: {relative}:", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_accepts_clean_minimal_board(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            (board / "protocol.json").write_text(json.dumps({}))
            (board / "project.json").write_text(json.dumps({}))

            result = validate(board)

        self.assertEqual(result.returncode, 0)
        self.assertIn("OK: 0 tasks, DAG valid", result.stdout)


if __name__ == "__main__":
    unittest.main()
