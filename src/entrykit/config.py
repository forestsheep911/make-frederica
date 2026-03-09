from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


@dataclass(frozen=True)
class Settings:
    notion_token: str
    notion_database_id: str

    @classmethod
    def load(cls, env_path: Path | None = None) -> "Settings":
        if env_path is None:
            env_path = Path.cwd() / ".env"
        load_dotenv(env_path)

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
