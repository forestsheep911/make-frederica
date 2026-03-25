from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from entrykit.cli import (
    build_parser,
    cmd_bootstrap_notion,
    cmd_capture,
    cmd_config,
    cmd_doctor,
    cmd_inspect_notion,
    config_view,
    decode_utf8,
    doctor_result,
    format_doctor_result,
    read_input,
    read_text_file,
)


class CliEncodingTests(unittest.TestCase):
    def test_bootstrap_notion_parser_uses_optional_env_file(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["bootstrap-notion"])
        self.assertIsNone(args.env_file)

    def test_inspect_notion_parser_uses_optional_env_file(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["inspect-notion"])
        self.assertIsNone(args.env_file)

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
                    "output": None,
                    "status": "Captured",
                    "env_file": None,
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

            self.assertTrue(result["ok"])
            checks = result["checks"]
            self.assertFalse(checks["uv"]["ok"])
            self.assertEqual(result["default_output"], "screen")
            self.assertFalse(checks["targets"]["exists"])
            backends = checks["backends"]
            self.assertFalse(backends["notion"]["ok"])
            self.assertIn("NOTION_TOKEN", backends["notion"]["missing"])
            text = format_doctor_result(result)
            self.assertIn("Default output: screen", text)

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

    def test_cmd_bootstrap_notion_uses_default_frederica_env(self) -> None:
        args = type("Args", (), {"env_file": None, "dry_run": True})()
        with patch("entrykit.cli.Settings.load") as load_settings:
            with patch("entrykit.cli.NotionClient") as notion_client:
                notion_client.return_value.retrieve_database.return_value = {"properties": {}}
                code = cmd_bootstrap_notion(args)

        self.assertEqual(code, 0)
        load_settings.assert_called_once_with(Path.home() / ".frederica" / "config" / ".env")

    def test_cmd_inspect_notion_uses_default_frederica_env(self) -> None:
        args = type("Args", (), {"env_file": None})()
        fake_settings = type("Settings", (), {"notion_token": "token", "notion_database_id": "db"})()
        with patch("entrykit.cli.Settings.load", return_value=fake_settings) as load_settings:
            with patch("entrykit.cli.NotionClient") as notion_client:
                notion_client.return_value.retrieve_database.return_value = {"properties": {}}
                with patch("sys.stdout", new=io.StringIO()):
                    code = cmd_inspect_notion(args)

        self.assertEqual(code, 0)
        load_settings.assert_called_once_with(Path.home() / ".frederica" / "config" / ".env")

    def test_doctor_requires_ready_default_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            targets_path = home / ".frederica" / "config" / "targets.json"
            targets_path.parent.mkdir(parents=True, exist_ok=True)
            targets_path.write_text(
                """
                {
                  "default_output": "local_markdown",
                  "backends": {
                    "local_markdown": {
                      "enabled": true,
                      "output_dir": "missing/notes"
                    }
                  }
                }
                """,
                encoding="utf-8",
            )
            args = type("Args", (), {"env_file": None, "json": False})()

            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    with patch("shutil.which", return_value="/usr/bin/uv"):
                        result = doctor_result(args)

            self.assertFalse(result["ok"])
            backends = result["checks"]["backends"]
            self.assertFalse(backends["local_markdown"]["ok"])

    def test_doctor_accepts_ready_local_markdown_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            output_dir = home / "notes"
            output_dir.mkdir(parents=True, exist_ok=True)
            targets_path = home / ".frederica" / "config" / "targets.json"
            targets_path.parent.mkdir(parents=True, exist_ok=True)
            targets_path.write_text(
                json.dumps(
                    {
                        "default_output": "local_markdown",
                        "backends": {
                            "local_markdown": {
                                "enabled": True,
                                "output_dir": str(output_dir),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            args = type("Args", (), {"env_file": None, "json": False})()

            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    with patch("shutil.which", return_value="/usr/bin/uv"):
                        result = doctor_result(args)

            self.assertTrue(result["ok"])
            self.assertEqual(result["default_output"], "local_markdown")
            backends = result["checks"]["backends"]
            self.assertTrue(backends["local_markdown"]["ok"])

    def test_config_show_returns_targets_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            args = type("Args", (), {"config_command": "show", "json": True})()
            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    with patch("shutil.which", return_value="/usr/bin/uv"):
                        with patch("sys.stdout", new=io.StringIO()) as stdout:
                            code = cmd_config(args)

            self.assertEqual(code, 0)
            self.assertIn('"default_output": "screen"', stdout.getvalue())

    def test_config_set_default_writes_targets_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            args = type("Args", (), {"config_command": "set-default", "output": "notion"})()
            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    code = cmd_config(args)

            self.assertEqual(code, 0)
            payload = json.loads((home / ".frederica" / "config" / "targets.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["default_output"], "notion")

    def test_config_set_obsidian_updates_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            args = type(
                "Args",
                (),
                {
                    "config_command": "set-obsidian",
                    "vault_path": str(home / "vault"),
                    "folder": "Frederica",
                    "enable": True,
                    "disable": False,
                },
            )()
            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    code = cmd_config(args)

            self.assertEqual(code, 0)
            payload = json.loads((home / ".frederica" / "config" / "targets.json").read_text(encoding="utf-8"))
            self.assertTrue(payload["backends"]["obsidian"]["enabled"])
            self.assertEqual(payload["backends"]["obsidian"]["folder"], "Frederica")

    def test_config_set_notion_secret_writes_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            args = type(
                "Args",
                (),
                {
                    "config_command": "set-notion-secret",
                    "token": "secret-token",
                    "database_id": "db-123",
                    "env_file": None,
                },
            )()
            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    code = cmd_config(args)

            self.assertEqual(code, 0)
            env_text = (home / ".frederica" / "config" / ".env").read_text(encoding="utf-8")
            self.assertIn("NOTION_TOKEN='secret-token'", env_text)
            self.assertIn("NOTION_DATABASE_ID='db-123'", env_text)

    def test_cmd_capture_writes_local_markdown_from_default_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            output_dir = home / "notes"
            targets_path = home / ".frederica" / "config" / "targets.json"
            targets_path.parent.mkdir(parents=True, exist_ok=True)
            targets_path.write_text(
                json.dumps(
                    {
                        "default_output": "local_markdown",
                        "backends": {
                            "local_markdown": {
                                "enabled": True,
                                "output_dir": str(output_dir),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            input_path = home / "captured.json"
            input_path.write_text(
                json.dumps(
                    {
                        "title": "Capture coding-session architecture decisions",
                        "source_tool": "codex",
                        "tool_version": "",
                        "model": "",
                        "thinking_mode": "unknown",
                        "project": "entrykit",
                        "session_date": "2026-03-08T16:20:00+08:00",
                        "session_id": "",
                        "tags": ["notion", "capture"],
                        "reusability_score": 84,
                        "summary": "Short summary",
                        "body_markdown": "# Overview\n\nBody text.",
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
                    "output": None,
                    "status": "Captured",
                    "env_file": None,
                },
            )()

            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        code = cmd_capture(args)

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["target"], "local_markdown")
            written = Path(payload["path"])
            self.assertTrue(written.exists())
            text = written.read_text(encoding="utf-8")
            self.assertIn('title: "Capture coding-session architecture decisions"', text)
            self.assertIn("# Overview\n\nBody text.", text)

    def test_cmd_capture_local_markdown_dry_run_prints_rendered_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            output_dir = home / "notes"
            targets_path = home / ".frederica" / "config" / "targets.json"
            targets_path.parent.mkdir(parents=True, exist_ok=True)
            targets_path.write_text(
                json.dumps(
                    {
                        "default_output": "screen",
                        "backends": {
                            "local_markdown": {
                                "enabled": True,
                                "output_dir": str(output_dir),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            input_path = home / "captured.json"
            input_path.write_text(
                json.dumps(
                    {
                        "title": "Dry Run Note",
                        "source_tool": "codex",
                        "tool_version": "",
                        "model": "",
                        "thinking_mode": "unknown",
                        "project": "",
                        "session_date": "2026-03-08",
                        "session_id": "",
                        "tags": [],
                        "reusability_score": 50,
                        "summary": "Short summary",
                        "body_markdown": "Body text.",
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
                    "dry_run": True,
                    "output": "local_markdown",
                    "status": "Captured",
                    "env_file": None,
                },
            )()

            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        code = cmd_capture(args)

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["target"], "local_markdown")
            self.assertIn("---", payload["content"])
            self.assertIn("Body text.", payload["content"])
            self.assertFalse(output_dir.exists())

    def test_cmd_capture_local_markdown_requires_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            targets_path = home / ".frederica" / "config" / "targets.json"
            targets_path.parent.mkdir(parents=True, exist_ok=True)
            targets_path.write_text(
                json.dumps(
                    {
                        "default_output": "local_markdown",
                        "backends": {
                            "local_markdown": {
                                "enabled": True,
                                "output_dir": "",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            input_path = home / "captured.json"
            input_path.write_text(
                json.dumps(
                    {
                        "title": "Missing Output Dir",
                        "source_tool": "codex",
                        "tool_version": "",
                        "model": "",
                        "thinking_mode": "unknown",
                        "project": "",
                        "session_date": "2026-03-08",
                        "session_id": "",
                        "tags": [],
                        "reusability_score": 50,
                        "summary": "Short summary",
                        "body_markdown": "Body text.",
                    }
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
                    "output": None,
                    "status": "Captured",
                    "env_file": None,
                },
            )()

            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    with self.assertRaisesRegex(ValueError, "requires a configured output_dir"):
                        cmd_capture(args)

    def test_cmd_capture_explicit_notion_overrides_default_local_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            output_dir = home / "notes"
            targets_path = home / ".frederica" / "config" / "targets.json"
            env_path = home / ".frederica" / "config" / ".env"
            targets_path.parent.mkdir(parents=True, exist_ok=True)
            targets_path.write_text(
                json.dumps(
                    {
                        "default_output": "local_markdown",
                        "backends": {
                            "notion": {"enabled": True, "env_file": str(env_path)},
                            "local_markdown": {
                                "enabled": True,
                                "output_dir": str(output_dir),
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            env_path.write_text(
                "NOTION_TOKEN=test-token\nNOTION_DATABASE_ID=test-db\n",
                encoding="utf-8",
            )
            input_path = home / "captured.json"
            input_path.write_text(
                json.dumps(
                    {
                        "title": "Override To Notion",
                        "source_tool": "codex",
                        "tool_version": "",
                        "model": "",
                        "thinking_mode": "unknown",
                        "project": "",
                        "session_date": "2026-03-08",
                        "session_id": "",
                        "tags": [],
                        "reusability_score": 50,
                        "summary": "Short summary",
                        "body_markdown": "Body text.",
                    }
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
                    "dry_run": True,
                    "output": "notion",
                    "status": "Captured",
                    "env_file": None,
                },
            )()

            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        code = cmd_capture(args)

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["target"], "notion")
            self.assertIn("properties", payload)
            self.assertFalse(output_dir.exists())

    def test_cmd_capture_explicit_screen_overrides_default_local_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            output_dir = home / "notes"
            targets_path = home / ".frederica" / "config" / "targets.json"
            targets_path.parent.mkdir(parents=True, exist_ok=True)
            targets_path.write_text(
                json.dumps(
                    {
                        "default_output": "local_markdown",
                        "backends": {
                            "local_markdown": {
                                "enabled": True,
                                "output_dir": str(output_dir),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            input_path = home / "captured.json"
            input_path.write_text(
                json.dumps(
                    {
                        "title": "Override To Screen",
                        "source_tool": "codex",
                        "tool_version": "",
                        "model": "",
                        "thinking_mode": "unknown",
                        "project": "",
                        "session_date": "2026-03-08",
                        "session_id": "",
                        "tags": [],
                        "reusability_score": 50,
                        "summary": "Short summary",
                        "body_markdown": "Body text.",
                    }
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
                    "output": "screen",
                    "status": "Captured",
                    "env_file": None,
                },
            )()

            with patch.dict("os.environ", {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        code = cmd_capture(args)

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["target"], "screen")
            self.assertEqual(payload["entry"]["title"], "Override To Screen")
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
