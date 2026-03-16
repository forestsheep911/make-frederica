from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_OUTPUTS = {"screen", "notion", "obsidian", "local_markdown"}


def frederica_home() -> Path:
    override = os.getenv("FREDERICA_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".frederica"


def default_env_path() -> Path:
    return frederica_home() / "config" / ".env"


def default_targets_path() -> Path:
    return frederica_home() / "config" / "targets.json"


def legacy_env_path() -> Path:
    return Path.home() / ".config" / "entrykit" / "env.sh"


def expand_config_path(value: str) -> Path:
    if value.startswith("~"):
        return frederica_home().parent / value[2:] if value.startswith("~/") else Path.home() / value[1:]
    return Path(value)


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
class NotionTarget:
    enabled: bool
    env_file: Path


@dataclass(frozen=True)
class ObsidianTarget:
    enabled: bool
    vault_path: str
    folder: str


@dataclass(frozen=True)
class LocalMarkdownTarget:
    enabled: bool
    output_dir: str


@dataclass(frozen=True)
class TargetSettings:
    default_output: str
    notion: NotionTarget
    obsidian: ObsidianTarget
    local_markdown: LocalMarkdownTarget
    source_path: Path

    @classmethod
    def defaults(cls, path: Path | None = None) -> "TargetSettings":
        source_path = path or default_targets_path()
        return cls(
            default_output="screen",
            notion=NotionTarget(enabled=False, env_file=default_env_path()),
            obsidian=ObsidianTarget(enabled=False, vault_path="", folder=""),
            local_markdown=LocalMarkdownTarget(enabled=False, output_dir=""),
            source_path=source_path,
        )

    @classmethod
    def load(cls, path: Path | None = None) -> "TargetSettings":
        source_path = path or default_targets_path()
        settings = cls.defaults(source_path)
        if not source_path.exists():
            return settings

        payload = json.loads(source_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Target config `{source_path}` must be a JSON object.")

        default_output = str(payload.get("default_output", settings.default_output)).strip() or "screen"
        if default_output not in DEFAULT_OUTPUTS:
            allowed = ", ".join(sorted(DEFAULT_OUTPUTS))
            raise ValueError(
                f"Target config `{source_path}` has invalid `default_output` `{default_output}`. "
                f"Expected one of: {allowed}."
            )

        backends = payload.get("backends", {})
        if backends is None:
            backends = {}
        if not isinstance(backends, dict):
            raise ValueError(f"Target config `{source_path}` field `backends` must be a JSON object.")

        notion_payload = backends.get("notion", {})
        if notion_payload is None:
            notion_payload = {}
        if not isinstance(notion_payload, dict):
            raise ValueError(f"Target config `{source_path}` field `backends.notion` must be a JSON object.")

        obsidian_payload = backends.get("obsidian", {})
        if obsidian_payload is None:
            obsidian_payload = {}
        if not isinstance(obsidian_payload, dict):
            raise ValueError(f"Target config `{source_path}` field `backends.obsidian` must be a JSON object.")

        markdown_payload = backends.get("local_markdown", {})
        if markdown_payload is None:
            markdown_payload = {}
        if not isinstance(markdown_payload, dict):
            raise ValueError(
                f"Target config `{source_path}` field `backends.local_markdown` must be a JSON object."
            )

        notion_env = notion_payload.get("env_file")
        env_file = (
            expand_config_path(str(notion_env))
            if notion_env is not None and str(notion_env).strip()
            else settings.notion.env_file
        )

        return cls(
            default_output=default_output,
            notion=NotionTarget(
                enabled=bool(notion_payload.get("enabled", settings.notion.enabled)),
                env_file=env_file,
            ),
            obsidian=ObsidianTarget(
                enabled=bool(obsidian_payload.get("enabled", settings.obsidian.enabled)),
                vault_path=str(obsidian_payload.get("vault_path", settings.obsidian.vault_path)).strip(),
                folder=str(obsidian_payload.get("folder", settings.obsidian.folder)).strip(),
            ),
            local_markdown=LocalMarkdownTarget(
                enabled=bool(markdown_payload.get("enabled", settings.local_markdown.enabled)),
                output_dir=str(markdown_payload.get("output_dir", settings.local_markdown.output_dir)).strip(),
            ),
            source_path=source_path,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "default_output": self.default_output,
            "backends": {
                "notion": {
                    "enabled": self.notion.enabled,
                    "env_file": str(self.notion.env_file),
                },
                "obsidian": {
                    "enabled": self.obsidian.enabled,
                    "vault_path": self.obsidian.vault_path,
                    "folder": self.obsidian.folder,
                },
                "local_markdown": {
                    "enabled": self.local_markdown.enabled,
                    "output_dir": self.local_markdown.output_dir,
                },
            },
        }

    def save(self) -> None:
        self.source_path.parent.mkdir(parents=True, exist_ok=True)
        self.source_path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def with_default_output(self, default_output: str) -> "TargetSettings":
        if default_output not in DEFAULT_OUTPUTS:
            allowed = ", ".join(sorted(DEFAULT_OUTPUTS))
            raise ValueError(f"Invalid default_output `{default_output}`. Expected one of: {allowed}.")
        return TargetSettings(
            default_output=default_output,
            notion=self.notion,
            obsidian=self.obsidian,
            local_markdown=self.local_markdown,
            source_path=self.source_path,
        )

    def with_notion(self, *, enabled: bool | None = None, env_file: Path | None = None) -> "TargetSettings":
        return TargetSettings(
            default_output=self.default_output,
            notion=NotionTarget(
                enabled=self.notion.enabled if enabled is None else enabled,
                env_file=self.notion.env_file if env_file is None else env_file,
            ),
            obsidian=self.obsidian,
            local_markdown=self.local_markdown,
            source_path=self.source_path,
        )

    def with_obsidian(
        self,
        *,
        enabled: bool | None = None,
        vault_path: str | None = None,
        folder: str | None = None,
    ) -> "TargetSettings":
        return TargetSettings(
            default_output=self.default_output,
            notion=self.notion,
            obsidian=ObsidianTarget(
                enabled=self.obsidian.enabled if enabled is None else enabled,
                vault_path=self.obsidian.vault_path if vault_path is None else vault_path,
                folder=self.obsidian.folder if folder is None else folder,
            ),
            local_markdown=self.local_markdown,
            source_path=self.source_path,
        )

    def with_local_markdown(
        self,
        *,
        enabled: bool | None = None,
        output_dir: str | None = None,
    ) -> "TargetSettings":
        return TargetSettings(
            default_output=self.default_output,
            notion=self.notion,
            obsidian=self.obsidian,
            local_markdown=LocalMarkdownTarget(
                enabled=self.local_markdown.enabled if enabled is None else enabled,
                output_dir=self.local_markdown.output_dir if output_dir is None else output_dir,
            ),
            source_path=self.source_path,
        )


@dataclass(frozen=True)
class Settings:
    notion_token: str
    notion_database_id: str

    @classmethod
    def load(cls, env_path: Path | None = None) -> "Settings":
        if env_path is None:
            env_path = default_env_path()
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


def write_notion_env(env_path: Path, *, token: str | None = None, database_id: str | None = None) -> None:
    existing: dict[str, str] = {}
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            key, value = line.split("=", 1)
            existing[key.strip()] = value.strip().strip("'").strip('"')

    if token is not None:
        existing["NOTION_TOKEN"] = token
    if database_id is not None:
        existing["NOTION_DATABASE_ID"] = database_id

    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key in ("NOTION_TOKEN", "NOTION_DATABASE_ID"):
        value = existing.get(key, "")
        lines.append(f"{key}='{value}'")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
