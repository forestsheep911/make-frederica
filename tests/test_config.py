from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from entrykit.config import Settings, default_env_path, frederica_home


class ConfigTests(unittest.TestCase):
    def test_frederica_home_defaults_under_user_home(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch("pathlib.Path.home", return_value=Path("/tmp/test-home")):
                self.assertEqual(frederica_home(), Path("/tmp/test-home/.frederica"))
                self.assertEqual(default_env_path(), Path("/tmp/test-home/.frederica/config/.env"))

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


if __name__ == "__main__":
    unittest.main()
