from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def frederica_home() -> Path:
    override = os.getenv("FREDERICA_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".frederica"


def default_env_path() -> Path:
    return frederica_home() / "config" / ".env"


def legacy_env_path() -> Path:
    return Path.home() / ".config" / "entrykit" / "env.sh"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


@dataclass(frozen=True)
class Settings:
    notion_token: str
    notion_database_id: str

    @classmethod
    def load(cls, env_path: Path | None = None) -> "Settings":
        if env_path is None:
            env_path = default_env_path()
        load_dotenv(env_path)
        if env_path == default_env_path():
            load_dotenv(legacy_env_path())

        token = os.getenv("NOTION_TOKEN", "").strip()
        database_id = os.getenv("NOTION_DATABASE_ID", "").strip()
        missing = []
        if not token:
            missing.append("NOTION_TOKEN")
        if not database_id:
            missing.append("NOTION_DATABASE_ID")
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"Missing required environment variables: {names}")

        return cls(notion_token=token, notion_database_id=database_id)
