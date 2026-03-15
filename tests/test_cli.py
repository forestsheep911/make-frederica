from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from entrykit.cli import (
    cmd_capture,
    cmd_doctor,
    decode_utf8,
    doctor_result,
    format_doctor_result,
    read_input,
    read_text_file,
)


class CliEncodingTests(unittest.TestCase):
    def test_read_text_file_accepts_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "captured.json"
            path.write_bytes("\ufeff中文内容".encode("utf-8"))

            self.assertEqual(read_text_file(path), "中文内容")

    def test_read_input_reads_stdin_as_utf8_bytes(self) -> None:
        stdin = io.TextIOWrapper(io.BytesIO("中文输入".encode("utf-8")), encoding="cp936")

        with patch("sys.stdin", stdin):
            self.assertEqual(read_input(None), "中文输入")

    def test_decode_utf8_reports_actionable_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "UTF-8 encoded"):
            decode_utf8(b"\xff\xfe\xfd", "stdin")

    def test_cmd_capture_rejects_body_over_block_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "captured.json"
            input_path.write_text(
                json.dumps(
                    {
                        "title": "too many blocks",
                        "source_tool": "codex",
                        "tool_version": "",
                        "model": "",
                        "thinking_mode": "unknown",
                        "project": "entrykit",
                        "session_date": "2026-03-08T16:20:00+08:00",
                        "session_id": "",
                        "tags": ["notion"],
                        "reusability_score": 50,
                        "summary": "summary",
                        "body_markdown": "\n\n".join(
                            f"paragraph {index}" for index in range(101)
                        ),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            args = type(
                "Args",
                (),
                {
                    "input": input_path,
                    "strict_lint": False,
                    "conversation": None,
                    "dry_run": False,
                    "status": "Captured",
                    "env_file": Path(".env"),
                },
            )()

            with self.assertRaisesRegex(ValueError, "exceeds the limit"):
                cmd_capture(args)

    def test_doctor_reports_missing_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            args = type("Args", (), {"env_file": None, "json": False})()
            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    with patch("shutil.which", return_value=None):
                        result = doctor_result(args)

            self.assertFalse(result["ok"])
            checks = result["checks"]
            self.assertFalse(checks["uv"]["ok"])
            self.assertFalse(checks["env_file"]["ok"])
            self.assertIn("NOTION_TOKEN", checks["notion_config"]["missing"])
            text = format_doctor_result(result)
            self.assertIn("Next step:", text)

    def test_cmd_doctor_returns_zero_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            env_path = home / ".frederica" / "config" / ".env"
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(
                "NOTION_TOKEN=test-token\nNOTION_DATABASE_ID=test-db\n",
                encoding="utf-8",
            )
            args = type("Args", (), {"env_file": None, "json": True})()

            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    with patch("shutil.which", return_value="/usr/bin/uv"):
                        with patch("sys.stdout", new=io.StringIO()) as stdout:
                            code = cmd_doctor(args)

            self.assertEqual(code, 0)
            self.assertIn('"ok": true', stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
