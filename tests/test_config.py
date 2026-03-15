from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from entrykit.config import Settings, TargetSettings, default_env_path, default_targets_path, frederica_home


class ConfigTests(unittest.TestCase):
    def test_frederica_home_defaults_under_user_home(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch("pathlib.Path.home", return_value=Path("/tmp/test-home")):
                self.assertEqual(frederica_home(), Path("/tmp/test-home/.frederica"))
                self.assertEqual(default_env_path(), Path("/tmp/test-home/.frederica/config/.env"))
                self.assertEqual(default_targets_path(), Path("/tmp/test-home/.frederica/config/targets.json"))

    def test_settings_load_uses_default_frederica_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            env_path = home / ".frederica" / "config" / ".env"
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(
                "NOTION_TOKEN=test-token\nNOTION_DATABASE_ID=test-db\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    settings = Settings.load()

            self.assertEqual(settings.notion_token, "test-token")
            self.assertEqual(settings.notion_database_id, "test-db")

    def test_settings_load_falls_back_to_legacy_env_when_default_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            legacy_path = home / ".config" / "entrykit" / "env.sh"
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_path.write_text(
                "export NOTION_TOKEN='legacy-token'\nexport NOTION_DATABASE_ID='legacy-db'\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    settings = Settings.load()

            self.assertEqual(settings.notion_token, "legacy-token")
            self.assertEqual(settings.notion_database_id, "legacy-db")

    def test_target_settings_defaults_to_screen(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            with patch.dict(os.environ, {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    settings = TargetSettings.load()

            self.assertEqual(settings.default_output, "screen")
            self.assertFalse(settings.notion.enabled)
            self.assertFalse(settings.obsidian.enabled)
            self.assertFalse(settings.local_markdown.enabled)
            self.assertEqual(settings.source_path, home / ".frederica" / "config" / "targets.json")

    def test_target_settings_loads_targets_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            targets_path = home / ".frederica" / "config" / "targets.json"
            targets_path.parent.mkdir(parents=True, exist_ok=True)
            targets_path.write_text(
                """
                {
                  "default_output": "obsidian",
                  "backends": {
                    "notion": {
                      "enabled": true,
                      "env_file": "~/custom.env"
                    },
                    "obsidian": {
                      "enabled": true,
                      "vault_path": "~/vault",
                      "folder": "Frederica"
                    },
                    "local_markdown": {
                      "enabled": true,
                      "output_dir": "~/notes"
                    }
                  }
                }
                """,
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with patch("pathlib.Path.home", return_value=home):
                    settings = TargetSettings.load()

            self.assertEqual(settings.default_output, "obsidian")
            self.assertTrue(settings.notion.enabled)
            self.assertEqual(settings.notion.env_file, home / "custom.env")
            self.assertTrue(settings.obsidian.enabled)
            self.assertEqual(settings.obsidian.vault_path, "~/vault")
            self.assertEqual(settings.obsidian.folder, "Frederica")
            self.assertTrue(settings.local_markdown.enabled)
            self.assertEqual(settings.local_markdown.output_dir, "~/notes")


if __name__ == "__main__":
    unittest.main()
