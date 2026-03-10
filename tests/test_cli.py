from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from entrykit.cli import decode_utf8, read_input, read_text_file


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


if __name__ == "__main__":
    unittest.main()
