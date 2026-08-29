import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from boardlib import board_snapshot, requirement_match


class RequirementMatchTests(unittest.TestCase):
    def test_rejects_unknown_required_capability(self):
        matches, reason = requirement_match(
            {"capabilities": ["vision"]},
            {"capabilities": {"vision": "unknown"}},
        )

        self.assertFalse(matches)
        self.assertEqual(reason, "capability vision is unknown")

    def test_accepts_verified_capability_and_tools(self):
        matches, reason = requirement_match(
            {"capabilities": {"vision": True}, "tools": ["browser", "shell"]},
            {
                "capabilities": {"vision": True},
                "tools": ["browser", "shell"],
            },
        )

        self.assertTrue(matches)
        self.assertIsNone(reason)

    def test_rejects_false_capability_when_true_is_required(self):
        matches, _ = requirement_match(
            {"capabilities": {"vision": True}},
            {"capabilities": {"vision": False}},
        )

        self.assertFalse(matches)

    def test_rejects_missing_required_tool(self):
        matches, reason = requirement_match(
            {"tools": ["browser"]},
            {"tools": {}},
        )

        self.assertFalse(matches)
        self.assertEqual(reason, "tool browser is missing")

    def test_rejects_false_values_for_list_requirements(self):
        matches, _ = requirement_match(
            {"capabilities": ["vision"], "tools": ["browser"]},
            {"capabilities": {"vision": False}, "tools": {"browser": False}},
        )

        self.assertFalse(matches)


class BoardSnapshotTests(unittest.TestCase):
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

    def test_reads_board_records_and_nested_runs_without_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            records = {
                "project.json": {"name": "Demo"},
                "tasks/TASK-a.json": {"id": "TASK-a", "title": "Task A"},
                "state/TASK-a.json": {"status": "READY"},
                "claims/TASK-a.json": {"task": "TASK-a", "worker": "agent"},
                "runs/TASK-a/RUN-a.json": {"id": "RUN-a", "task": "TASK-a"},
                "reviews/TASK-a/REVIEW-a.json": {"id": "REVIEW-a", "task": "TASK-a"},
            }
            for relative_path, record in records.items():
                path = board / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(record))

            snapshot = board_snapshot(board)

        self.assertEqual(snapshot["project"], {"name": "Demo"})
        self.assertEqual(snapshot["tasks"], [{"id": "TASK-a", "title": "Task A"}])
        self.assertEqual(snapshot["states"]["TASK-a"]["status"], "READY")
        self.assertEqual(snapshot["claims"], [{"task": "TASK-a", "worker": "agent"}])
        self.assertEqual(snapshot["runs"], [{"id": "RUN-a", "task": "TASK-a"}])
        self.assertEqual(snapshot["reviews"], [{"id": "REVIEW-a", "task": "TASK-a"}])
        self.assertEqual(snapshot["diagnostics"], [])

    def test_omits_non_object_records_and_reports_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            (board / "project.json").write_text(json.dumps({"name": "Demo"}))
            for relative_path, record in {
                "tasks/TASK-a.json": [],
                "state/TASK-a.json": None,
            }.items():
                path = board / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(record))

            snapshot = board_snapshot(board)

        self.assertEqual(snapshot["tasks"], [])
        self.assertEqual(snapshot["states"], {})
        self.assertIn("tasks/TASK-a.json: expected object", snapshot["diagnostics"])
        self.assertIn("state/TASK-a.json: expected object", snapshot["diagnostics"])

    def test_includes_environments_and_model_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            environment = board / "environment" / "codex.json"
            environment.parent.mkdir()
            environment.write_text(json.dumps(self.routing_environment()))
            for relative_path, record in {
                "tasks/TASK-a.json": {"id": "TASK-a", "execution": {"model_role": "reasoner", "model_complexity": "high"}},
                "state/TASK-a.json": {"status": "READY"},
            }.items():
                path = board / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(record))

            snapshot = board_snapshot(board)

        self.assertEqual(snapshot["environments"]["codex"], self.routing_environment())
        self.assertEqual(snapshot["plan"]["codex"]["status"], "ready")
        self.assertEqual(snapshot["plan"]["codex"]["routes"][0]["model"], "deep")

    def test_invalid_environment_has_blocked_plan_and_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            environment = board / "environment" / "codex.json"
            environment.parent.mkdir()
            environment.write_text(json.dumps({"models": ["gpt"], "model_policy": {}}))

            snapshot = board_snapshot(board)

        self.assertEqual(snapshot["plan"]["codex"]["status"], "blocked")
        self.assertTrue(any(item.startswith("environment/codex.json: model_policy") for item in snapshot["diagnostics"]))


class SkillContractTests(unittest.TestCase):
    def test_skill_documents_adaptive_entry_and_live_dashboard(self):
        skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text()
        for phrase in (
            "What are we building?",
            "autopilot",
            "full_control",
            "ask_to_take_over",
            "serve_dashboard.py",
        ):
            self.assertIn(phrase, skill)


if __name__ == "__main__":
    unittest.main()
