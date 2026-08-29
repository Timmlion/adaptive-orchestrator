import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PreflightAndWorkTests(unittest.TestCase):
    def run_script(self, script, *args):
        return subprocess.run(
            [sys.executable, f"scripts/{script}", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def write_environment(self, board, runtime="codex"):
        environment = {
            "runtime_id": runtime,
            "harness": "Codex",
            "capabilities": {"coding": True},
            "tools": ["shell"],
            "models": ["gpt"],
            "model_policy": self.valid_model_policy(),
            "autonomy": {"mode": "autopilot"},
            "multi_harness": {"enabled": False, "harnesses": []},
        }
        path = board / "environment" / f"{runtime}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(environment))

    def valid_model_policy(self):
        return {
            "allowed_models": ["gpt"],
            "profiles": [
                {
                    "id": "gpt",
                    "roles": ["fast_worker", "coder", "reasoner", "critic", "escalation"],
                    "quality_tier": "advanced",
                    "relative_cost": "high",
                    "capabilities": {"coding": True, "vision": "unknown"},
                    "family": "GPT",
                    "research": {
                        "status": "verified",
                        "confidence": "high",
                        "sources": [
                            {
                                "url": "https://example.com/models/gpt",
                                "retrieved_at": "2026-08-29T12:00:00Z",
                                "summary": "Verified model profile.",
                            }
                        ],
                    },
                }
            ],
            "role_defaults": {
                "fast_worker": "gpt",
                "coder": "gpt",
                "reasoner": "gpt",
                "critic": "gpt",
                "escalation": "gpt",
            },
        }

    def valid_preflight_payload(self):
        return {
            "runtime_id": "codex",
            "harness": "Codex",
            "capabilities": {"vision": True, "browser": "unknown"},
            "tools": ["shell"],
            "models": ["gpt"],
            "model_policy": self.valid_model_policy(),
            "autonomy": {"mode": "ask", "level": "manager"},
            "multi_harness": {
                "enabled": True,
                "harnesses": [{"runtime_id": "claude", "purpose": "planning"}],
            },
        }

    def write_task(self, board, task, status="READY"):
        (board / "tasks").mkdir(parents=True, exist_ok=True)
        (board / "state").mkdir(parents=True, exist_ok=True)
        (board / "tasks" / f"{task['id']}.json").write_text(json.dumps(task))
        (board / "state" / f"{task['id']}.json").write_text(
            json.dumps({"task": task["id"], "status": status})
        )

    def test_record_preflight_persists_ask_manager_and_multi_harness(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            payload = self.valid_preflight_payload()
            result = self.run_script(
                "record_preflight.py", "--board", str(board), "--json", json.dumps(payload)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            saved = json.loads((board / "environment" / "codex.json").read_text())

        self.assertEqual(saved["autonomy"], {"mode": "ask", "level": "manager"})
        self.assertTrue(saved["multi_harness"]["enabled"])
        self.assertEqual(saved["multi_harness"]["harnesses"][0]["runtime_id"], "claude")

    def test_record_preflight_persists_valid_model_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            payload = self.valid_preflight_payload()
            result = self.run_script(
                "record_preflight.py", "--board", str(board), "--json", json.dumps(payload)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            saved = json.loads((board / "environment" / "codex.json").read_text())

        self.assertEqual(saved["model_policy"], payload["model_policy"])

    def test_record_preflight_rejects_invalid_model_policies(self):
        cases = (
            ("allowed_missing_raw", lambda policy: policy.update({"allowed_models": ["other"]}), "allowed_models"),
            ("duplicate_allowed", lambda policy: policy.update({"allowed_models": ["gpt", "gpt"]}), "allowed_models"),
            ("profile_outside_allowlist", lambda policy: policy["profiles"][0].update({"id": "other"}), "profiles"),
            ("invalid_capability_fact", lambda policy: policy["profiles"][0]["capabilities"].update({"coding": "probably"}), "capabilities"),
            ("verified_without_sources", lambda policy: policy["profiles"][0]["research"].update({"sources": []}), "research"),
            ("role_default_without_role", lambda policy: policy["profiles"][0]["roles"].remove("coder"), "role_defaults"),
        )
        for name, mutate, expected_error in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                payload = self.valid_preflight_payload()
                mutate(payload["model_policy"])
                result = self.run_script(
                    "record_preflight.py", "--board", directory, "--json", json.dumps(payload)
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("model_policy", result.stderr)
                self.assertIn(expected_error, result.stderr)

    def test_find_work_returns_preferred_eligible_task(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            self.write_environment(board)
            task = {
                "id": "TASK-current",
                "title": "Current runtime task",
                "dependencies": [],
                "requirements": {"capabilities": {"coding": True}, "tools": ["shell"]},
                "execution": {"preferred_runtime": "codex"},
            }
            self.write_task(board, task)

            result = self.run_script("find_work.py", "--board", str(board), "--runtime", "codex")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)

        self.assertEqual(report["action"], "ready_for_current_harness")
        self.assertEqual(report["task"]["id"], "TASK-current")

    def test_find_work_proposes_other_runtime_without_claiming(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            self.write_environment(board)
            task = {
                "id": "TASK-other",
                "title": "Other runtime task",
                "dependencies": [],
                "requirements": {"capabilities": {"coding": True}, "tools": ["shell"]},
                "execution": {"preferred_runtime": "claude"},
            }
            self.write_task(board, task)

            result = self.run_script("find_work.py", "--board", str(board), "--runtime", "codex")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertFalse((board / "claims" / "TASK-other.json").exists())

        self.assertEqual(report["action"], "ask_to_take_over")
        self.assertIn("explicit user approval", report["reason"])

    def test_find_work_excludes_unknown_or_false_required_capabilities(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            self.write_environment(board)
            environment_path = board / "environment" / "codex.json"
            environment = json.loads(environment_path.read_text())
            environment["capabilities"].update({"vision": "unknown", "browser": False})
            environment_path.write_text(json.dumps(environment))
            for task_id, capability in (("TASK-unknown", "vision"), ("TASK-false", "browser")):
                self.write_task(
                    board,
                    {
                        "id": task_id,
                        "title": task_id,
                        "dependencies": [],
                        "requirements": {"capabilities": {capability: True}},
                        "execution": {"preferred_runtime": "codex"},
                    },
                )

            result = self.run_script("find_work.py", "--board", str(board), "--runtime", "codex")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)

        self.assertEqual(report["action"], "no_eligible_work")
        self.assertIn("TASK-unknown", report["rejected"])
        self.assertIn("TASK-false", report["rejected"])

    def test_init_board_persists_autonomy(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / "board"
            result = self.run_script(
                "init_board.py",
                "--board",
                str(board),
                "--name",
                "Demo",
                "--goal",
                "Test",
                "--autonomy",
                "ask",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            project = json.loads((board / "project.json").read_text())

        self.assertEqual(project["autonomy"], "ask")

    def test_record_preflight_rejects_invalid_nested_harness_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = {
                "runtime_id": "codex",
                "harness": "Codex",
                "capabilities": {},
                "tools": [],
                "models": ["gpt"],
                "model_policy": self.valid_model_policy(),
                "autonomy": {"mode": "autopilot"},
                "multi_harness": {
                    "enabled": True,
                    "harnesses": [{"runtime_id": "claude", "purpose": "review", "tools": [False]}],
                },
            }
            result = self.run_script(
                "record_preflight.py", "--board", directory, "--json", json.dumps(payload)
            )
            payload["multi_harness"]["harnesses"][0]["tools"] = ["shell"]
            payload["multi_harness"]["harnesses"][0]["capabilities"] = {"vision": "maybe"}
            capability_result = self.run_script(
                "record_preflight.py", "--board", directory, "--json", json.dumps(payload)
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tools", result.stderr)
        self.assertNotEqual(capability_result.returncode, 0)
        self.assertIn("capabilities", capability_result.stderr)

    def test_find_work_reports_expired_claim_for_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            self.write_environment(board)
            task = {
                "id": "TASK-expired",
                "title": "Expired claim",
                "dependencies": [],
                "requirements": {"capabilities": {"coding": True}},
                "execution": {"preferred_runtime": "codex"},
            }
            self.write_task(board, task)
            claims = board / "claims"
            claims.mkdir()
            claims.joinpath("TASK-expired.json").write_text(
                json.dumps({
                    "task": "TASK-expired",
                    "claim_id": "CLM-expired",
                    "runtime_id": "codex",
                    "worker_id": "worker",
                    "created_at": (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat(),
                    "heartbeat_at": (datetime.now(timezone.utc) - timedelta(seconds=61)).isoformat(),
                    "lease_seconds": 30,
                    "attempt": 1,
                })
            )

            result = self.run_script("find_work.py", "--board", str(board), "--runtime", "codex")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)

        self.assertEqual(report["action"], "reconcile_claim")
        self.assertIn("expired", report["reason"])
        self.assertEqual(report["claim_issues"][0]["action"], "reconcile_claim")

    def test_find_work_skips_bad_records_and_selects_unaffected_work(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            self.write_environment(board)
            self.write_task(
                board,
                {
                    "id": "TASK-good",
                    "title": "Good",
                    "dependencies": [],
                    "requirements": {"capabilities": {"coding": True}},
                    "execution": {"preferred_runtime": "codex"},
                },
            )
            (board / "tasks" / "bad.json").write_text("{")
            (board / "tasks" / "bad-id.json").write_text(
                json.dumps({"id": "../../escape", "title": "Bad", "dependencies": [], "requirements": {}})
            )

            result = self.run_script("find_work.py", "--board", str(board), "--runtime", "codex")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)

        self.assertEqual(report["action"], "ready_for_current_harness")
        self.assertEqual(report["task"]["id"], "TASK-good")
        self.assertTrue(any("tasks/bad.json" in item for item in report["diagnostics"]))
        self.assertIn("../../escape", report["rejected"])

    def test_find_work_returns_report_for_invalid_runtime_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_script("find_work.py", "--board", directory, "--runtime", "../escape")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["action"], "no_eligible_work")
        self.assertIn("invalid runtime", report["reason"])

    def test_find_work_rejects_malformed_environment_facts_for_legacy_requirements(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            self.write_environment(board)
            environment_path = board / "environment" / "codex.json"
            environment = json.loads(environment_path.read_text())
            environment["capabilities"]["coding"] = "unverified"
            environment["tools"] = ["shell", False]
            environment_path.write_text(json.dumps(environment))
            self.write_task(
                board,
                {
                    "id": "TASK-legacy",
                    "title": "Legacy requirements",
                    "dependencies": [],
                    "requirements": {"required_capabilities": ["coding"]},
                    "execution": {"preferred_runtime": "codex"},
                },
            )

            result = self.run_script("find_work.py", "--board", str(board), "--runtime", "codex")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)

        self.assertEqual(report["action"], "no_eligible_work")
        self.assertIn("invalid", report["reason"])
        self.assertTrue(any("invalid capability" in item for item in report["diagnostics"]))

    def test_find_work_requires_full_claim_contract_before_active_block(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            self.write_environment(board)
            task = {
                "id": "TASK-incomplete-claim",
                "title": "Incomplete claim",
                "dependencies": [],
                "requirements": {"capabilities": {"coding": True}},
                "execution": {"preferred_runtime": "codex"},
            }
            self.write_task(board, task)
            claims = board / "claims"
            claims.mkdir()
            claims.joinpath("TASK-incomplete-claim.json").write_text(
                json.dumps({
                    "task": "TASK-incomplete-claim",
                    "heartbeat_at": datetime.now(timezone.utc).isoformat(),
                    "lease_seconds": 900,
                })
            )

            result = self.run_script("find_work.py", "--board", str(board), "--runtime", "codex")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)

        self.assertEqual(report["action"], "reconcile_claim")
        self.assertIn("malformed", report["reason"])
        self.assertNotEqual(report["rejected"]["TASK-incomplete-claim"], "active claim blocks task")


if __name__ == "__main__":
    unittest.main()
