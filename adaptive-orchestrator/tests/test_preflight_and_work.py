import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model_policy import route_task


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

    def routing_environment(self):
        profiles = [
            ("fast", ["fast_worker", "coder", "escalation"], "standard", "low", {"coding": True, "vision": False}, "verified"),
            ("deep", ["reasoner"], "advanced", "high", {"coding": True, "vision": True}, "unknown"),
            ("critic", ["critic"], "standard", "medium", {"coding": True}, "verified"),
        ]
        return {
            "runtime_id": "codex", "harness": "Codex", "capabilities": {"coding": True},
            "tools": ["shell"], "models": [item[0] for item in profiles],
            "autonomy": {"mode": "autopilot"}, "multi_harness": {"enabled": False, "harnesses": []},
            "model_policy": {
                "allowed_models": [item[0] for item in profiles],
                "profiles": [
                    {
                        "id": model_id, "roles": roles, "quality_tier": quality,
                        "relative_cost": cost, "capabilities": capabilities, "family": "test",
                        "research": {
                            "status": research, "confidence": "high",
                            "sources": [] if research == "unknown" else [{
                                "url": "https://example.com/" + model_id,
                                "retrieved_at": "2026-08-29T12:00:00Z", "summary": "Verified.",
                            }],
                        },
                    }
                    for model_id, roles, quality, cost, capabilities, research in profiles
                ],
                "role_defaults": {"fast_worker": "fast", "coder": "fast", "reasoner": "deep", "critic": "critic", "escalation": "fast"},
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
            ("non_string_quality_tier", lambda policy: policy["profiles"][0].update({"quality_tier": []}), "quality_tier"),
            ("non_string_research_status", lambda policy: policy["profiles"][0]["research"].update({"status": []}), "research.status"),
            ("verified_without_sources", lambda policy: policy["profiles"][0]["research"].update({"sources": []}), "research"),
            ("role_default_without_role", lambda policy: policy["profiles"][0]["roles"].remove("coder"), "role_defaults"),
            ("malformed_bracketed_url", lambda policy: policy["profiles"][0]["research"]["sources"][0].update({"url": "https://[bad"}), "research.sources.url"),
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
                self.assertNotIn("Traceback", result.stderr)

    def test_record_preflight_rejects_malformed_verified_research_url(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = self.valid_preflight_payload()
            payload["model_policy"]["profiles"][0]["research"]["sources"][0]["url"] = "not-a-url"
            result = self.run_script(
                "record_preflight.py", "--board", directory, "--json", json.dumps(payload)
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("model_policy", result.stderr)
        self.assertIn("research.sources.url", result.stderr)

    def test_record_preflight_rejects_verified_research_url_with_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = self.valid_preflight_payload()
            payload["model_policy"]["profiles"][0]["research"]["sources"][0]["url"] = "https://example.com/not a valid URI"
            result = self.run_script(
                "record_preflight.py", "--board", directory, "--json", json.dumps(payload)
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("model_policy: research.sources.url", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_record_preflight_rejects_verified_research_url_with_c1_control(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = self.valid_preflight_payload()
            payload["model_policy"]["profiles"][0]["research"]["sources"][0]["url"] = "https://example.com/a\u0080b"
            result = self.run_script(
                "record_preflight.py", "--board", directory, "--json", json.dumps(payload)
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("model_policy: research.sources.url", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_plan_work_routes_models_and_reports_gaps_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            environment = self.routing_environment()
            environment_path = board / "environment" / "codex.json"
            environment_path.parent.mkdir(parents=True)
            environment_path.write_text(json.dumps(environment))
            tasks = (
                ("TASK-low", {"model_role": "coder", "model_complexity": "low"}),
                ("TASK-deep", {"model_role": "reasoner", "model_complexity": "high"}),
                ("TASK-vision", {"model_role": "coder", "required_model_capabilities": {"vision": True}}),
                ("TASK-critic", {"model_role": "coder"}),
            )
            for task_id, execution in tasks:
                task = {"id": task_id, "title": task_id, "dependencies": [], "requirements": {}, "execution": execution}
                if task_id == "TASK-critic":
                    task["review_policy"] = {"model_role": "critic", "independent_context": True}
                self.write_task(board, task, status="PLANNED")

            result = self.run_script("plan_work.py", "--board", str(board), "--runtime", "codex")

            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(result.stdout)
            self.assertFalse((board / "claims").exists())

        routes = {route["task"]: route for route in report["routes"]}
        self.assertEqual(routes["TASK-low"]["model"], "fast")
        self.assertEqual(routes["TASK-deep"]["model"], "deep")
        self.assertEqual(routes["TASK-critic"]["model"], "critic")
        self.assertEqual(routes["TASK-critic"]["role"], "critic")
        self.assertEqual(report["capability_gaps"][0]["task"], "TASK-vision")
        self.assertEqual(report["research_warnings"][0]["task"], "TASK-deep")

    def test_plan_work_and_find_work_reject_invalid_routing_data_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            environment = self.routing_environment()
            environment["model_policy"]["profiles"][0]["quality_tier"] = []
            environment_path = board / "environment" / "codex.json"
            environment_path.parent.mkdir(parents=True)
            environment_path.write_text(json.dumps(environment))
            task = {"id": "TASK-bad", "title": "Bad", "dependencies": [], "requirements": {}, "execution": []}
            self.write_task(board, task, status="READY")

            plan_result = self.run_script("plan_work.py", "--board", str(board), "--runtime", "codex")
            find_result = self.run_script("find_work.py", "--board", str(board), "--runtime", "codex")

        self.assertEqual(plan_result.returncode, 1, plan_result.stderr)
        self.assertNotIn("Traceback", plan_result.stderr)
        self.assertEqual(json.loads(plan_result.stdout)["status"], "blocked")
        self.assertEqual(find_result.returncode, 0, find_result.stderr)
        self.assertEqual(json.loads(find_result.stdout)["action"], "no_eligible_work")

    def test_plan_work_blocks_malformed_execution_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            environment = self.routing_environment()
            environment_path = board / "environment" / "codex.json"
            environment_path.parent.mkdir(parents=True)
            environment_path.write_text(json.dumps(environment))
            self.write_task(board, {
                "id": "TASK-bad-execution", "title": "Bad execution", "dependencies": [],
                "requirements": {}, "execution": [],
            }, status="PLANNED")

            result = self.run_script("plan_work.py", "--board", str(board), "--runtime", "codex")

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("execution must be an object", report["blocked_tasks"][0]["reason"])

    def test_plan_work_blocks_ready_capability_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            environment_path = board / "environment" / "codex.json"
            environment_path.parent.mkdir(parents=True)
            environment_path.write_text(json.dumps(self.routing_environment()))
            self.write_task(board, {
                "id": "TASK-ready-vision", "title": "Vision", "dependencies": [], "requirements": {},
                "execution": {"model_role": "coder", "required_model_capabilities": {"vision": True}},
            }, status="READY")

            result = self.run_script("plan_work.py", "--board", str(board), "--runtime", "codex")

        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["blocked_tasks"][0]["task"], "TASK-ready-vision")

    def test_plan_work_blocks_list_task_id_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            environment_path = board / "environment" / "codex.json"
            environment_path.parent.mkdir(parents=True)
            environment_path.write_text(json.dumps(self.routing_environment()))
            self.write_task(board, {
                "id": ["bad"], "title": "Bad id", "dependencies": [], "requirements": {}, "execution": {},
            }, status="READY")

            result = self.run_script("plan_work.py", "--board", str(board), "--runtime", "codex")

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(report["diagnostics"])

    def test_route_task_rejects_non_string_capability_keys(self):
        route, gap = route_task({
            "id": "TASK-bad-capability", "execution": {"required_model_capabilities": {1: True}},
        }, self.routing_environment()["model_policy"])

        self.assertIsNone(route)
        self.assertIn("required_model_capabilities", gap["reason"])

    def test_route_task_reports_the_first_missing_capability_before_role_or_tier(self):
        policy = self.routing_environment()["model_policy"]
        for profile in policy["profiles"]:
            profile["capabilities"] = {"browser": True, "vision": False}

        route, gap = route_task({
            "id": "TASK-capability-order",
            "execution": {
                "model_role": "critic",
                "model_complexity": "high",
                "required_model_capabilities": {"browser": True, "vision": True},
            },
        }, policy)

        self.assertIsNone(route)
        self.assertEqual(gap["capability"], "vision")
        self.assertIn("required capability vision", gap["reason"])

    def test_task_schema_and_plan_work_use_routing_complexity_vocabulary(self):
        schema = json.loads((ROOT / "references" / "schemas" / "task.schema.json").read_text())
        self.assertEqual(schema["properties"]["execution"]["properties"]["model_complexity"]["enum"], ["low", "medium", "high"])
        self.assertNotIn("advanced", schema["properties"]["execution"]["properties"]["model_complexity"]["enum"])
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            environment_path = board / "environment" / "codex.json"
            environment_path.parent.mkdir(parents=True)
            environment_path.write_text(json.dumps(self.routing_environment()))
            for task_id, execution in (
                ("TASK-low-complexity", {"model_role": "coder", "model_complexity": "low"}),
                ("TASK-medium-complexity", {"model_role": "coder", "model_complexity": "medium"}),
                ("TASK-high-complexity", {"model_role": "reasoner", "model_complexity": "high"}),
                ("TASK-advanced-complexity", {"model_role": "coder", "model_complexity": "advanced"}),
            ):
                self.write_task(board, {"id": task_id, "title": task_id, "dependencies": [], "requirements": {}, "execution": execution}, status="READY")

            result = self.run_script("plan_work.py", "--board", str(board), "--runtime", "codex")

        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual({item["task"] for item in report["routes"]}, {"TASK-low-complexity", "TASK-medium-complexity", "TASK-high-complexity"})
        self.assertIn("model_complexity is invalid", report["capability_gaps"][0]["reason"])

    def test_malformed_required_model_capabilities_block_planning_and_find_work(self):
        for value in (False, "not-true", "unknown"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                board = Path(directory)
                environment_path = board / "environment" / "codex.json"
                environment_path.parent.mkdir(parents=True)
                environment_path.write_text(json.dumps(self.routing_environment()))
                self.write_task(board, {
                    "id": "TASK-invalid-capability", "title": "Invalid capability", "dependencies": [], "requirements": {},
                    "execution": {"required_model_capabilities": {"vision": value}},
                }, status="READY")

                plan_result = self.run_script("plan_work.py", "--board", str(board), "--runtime", "codex")
                find_result = self.run_script("find_work.py", "--board", str(board), "--runtime", "codex")

                self.assertEqual(plan_result.returncode, 1, plan_result.stderr)
                report = json.loads(plan_result.stdout)
                self.assertEqual(report["status"], "blocked")
                self.assertIn("required_model_capabilities values must be true", report["capability_gaps"][0]["reason"])
                self.assertEqual(find_result.returncode, 0, find_result.stderr)
                self.assertIn("required_model_capabilities values must be true", json.loads(find_result.stdout)["rejected"]["TASK-invalid-capability"])

    def test_plan_work_rejects_absolute_runtime_without_reading_outside_board(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory) / "board"
            outside_environment = Path(directory) / "outside.json"
            outside_environment.write_text(json.dumps(self.routing_environment()))

            result = self.run_script("plan_work.py", "--board", str(board), "--runtime", str(outside_environment.with_suffix("")))

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("invalid runtime", report["blocked_tasks"][0]["reason"])

    def test_find_work_rejects_missing_persisted_model_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            environment = self.routing_environment()
            del environment["model_policy"]
            environment_path = board / "environment" / "codex.json"
            environment_path.parent.mkdir(parents=True)
            environment_path.write_text(json.dumps(environment))
            self.write_task(board, {
                "id": "TASK-coding", "title": "Coding", "dependencies": [], "requirements": {},
            })

            result = self.run_script("find_work.py", "--board", str(board), "--runtime", "codex")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["action"], "no_eligible_work")
        self.assertIn("model policy", report["diagnostics"][0])

    def test_find_work_rejects_task_without_model_capability_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            environment = self.routing_environment()
            environment_path = board / "environment" / "codex.json"
            environment_path.parent.mkdir(parents=True)
            environment_path.write_text(json.dumps(environment))
            self.write_task(board, {
                "id": "TASK-vision", "title": "Vision", "dependencies": [], "requirements": {},
                "execution": {"model_role": "coder", "required_model_capabilities": {"vision": True}},
            })

            result = self.run_script("find_work.py", "--board", str(board), "--runtime", "codex")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn("TASK-vision", report["rejected"])
        self.assertIn("capability", report["rejected"]["TASK-vision"])

    def test_find_work_refuses_all_claims_when_ready_plan_has_routing_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            board = Path(directory)
            environment_path = board / "environment" / "codex.json"
            environment_path.parent.mkdir(parents=True)
            environment_path.write_text(json.dumps(self.routing_environment()))
            self.write_task(board, {
                "id": "TASK-routable", "title": "Routable", "dependencies": [], "requirements": {},
                "execution": {"model_role": "coder"},
            })
            self.write_task(board, {
                "id": "TASK-vision-gap", "title": "Vision gap", "dependencies": [], "requirements": {},
                "execution": {"model_role": "coder", "required_model_capabilities": {"vision": True}},
            })

            plan_result = self.run_script("plan_work.py", "--board", str(board), "--runtime", "codex")
            find_result = self.run_script("find_work.py", "--board", str(board), "--runtime", "codex")

        self.assertEqual(plan_result.returncode, 1, plan_result.stderr)
        self.assertEqual(json.loads(plan_result.stdout)["status"], "blocked")
        self.assertEqual(find_result.returncode, 0, find_result.stderr)
        report = json.loads(find_result.stdout)
        self.assertEqual(report["action"], "no_eligible_work")
        self.assertIn("blocked", report["reason"])
        self.assertEqual(report["capability_gaps"][0]["task"], "TASK-vision-gap")
        self.assertFalse((board / "claims").exists())

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
