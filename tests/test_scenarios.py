from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from entrykit.cli import cmd_check_scenarios
from entrykit.scenarios import load_scenario_suite, run_scenario_suite


class ScenarioTests(unittest.TestCase):
    def test_run_frederica_scenario_suite_reports_ok(self) -> None:
        suite = load_scenario_suite(Path("skills/frederica/evals/scenarios.json"))

        result = run_scenario_suite(suite, repo_root=Path.cwd())

        self.assertTrue(result["ok"])
        self.assertEqual(result["suite_name"], "frederica-environment")

    def test_cmd_check_scenarios_prints_json(self) -> None:
        args = type(
            "Args",
            (),
            {
                "input": Path("skills/frederica/evals/scenarios.json"),
                "json": True,
            },
        )()

        with patch("sys.stdout", new=io.StringIO()) as stdout:
            code = cmd_check_scenarios(args)

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["scenario_count"], 6)

    def test_scenario_suite_reports_failure_for_wrong_expectation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "scenarios.json"
            path.write_text(
                json.dumps(
                    {
                        "suite_name": "bad-suite",
                        "scenarios": [
                            {
                                "id": "bad-doctor",
                                "argv": ["doctor", "--json"],
                                "home_files": {},
                                "env": {},
                                "fake_bins": [],
                                "path_mode": "fake_only",
                                "expect": {
                                    "exit_code": 1,
                                    "json_fields": {
                                        "ok": True
                                    }
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            suite = load_scenario_suite(path)
            result = run_scenario_suite(suite, repo_root=Path.cwd())

        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
