from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from entrykit.cli import cmd_check_evals
from entrykit.evals import load_eval_suite, validate_eval_suite


class EvalTests(unittest.TestCase):
    def test_validate_frederica_eval_suite_reports_ok(self) -> None:
        path = Path("skills/frederica/evals/evals.json")

        suite = load_eval_suite(path)
        result = validate_eval_suite(suite)

        self.assertTrue(result["ok"])
        self.assertEqual(result["skill_name"], "frederica")
        self.assertFalse(result["missing_coverage"])

    def test_validate_eval_suite_detects_missing_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "evals.json"
            path.write_text(
                json.dumps(
                    {
                        "skill_name": "frederica",
                        "evals": [
                            {
                                "id": 1,
                                "prompt": "Prompt",
                                "expected_output": "Expected",
                                "files": [],
                                "covers": ["notion_capture"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            suite = load_eval_suite(path)
            result = validate_eval_suite(suite)

        self.assertFalse(result["ok"])
        self.assertIn("first_time_backend_setup", result["missing_coverage"])

    def test_cmd_check_evals_prints_json(self) -> None:
        args = type(
            "Args",
            (),
            {
                "input": Path("skills/frederica/evals/evals.json"),
                "json": True,
            },
        )()

        with patch("sys.stdout", new=io.StringIO()) as stdout:
            code = cmd_check_evals(args)

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
