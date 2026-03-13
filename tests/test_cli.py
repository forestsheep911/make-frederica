from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from entrykit.cli import cmd_capture, decode_utf8, read_input, read_text_file


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


if __name__ == "__main__":
    unittest.main()
