from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

ALLOWED_THINKING_MODES = {
    "unknown",
    "low",
    "medium",
    "high",
    "extra-high",
}


def _as_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    result = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must be a list of strings")
        stripped = item.strip()
        if stripped:
            result.append(stripped)
    return result


@dataclass(frozen=True)
class KnowledgeEntry:
    title: str
    source_tool: str
    tool_version: str | None
    model: str | None
    thinking_mode: str
    project: str | None
    session_date: str
    session_id: str | None
    tags: list[str] = field(default_factory=list)
    reusability_score: int = 0
    summary: str = ""
    body_markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "source_tool": self.source_tool,
            "tool_version": self.tool_version or "",
            "model": self.model or "",
            "thinking_mode": self.thinking_mode,
            "project": self.project or "",
            "session_date": self.session_date,
            "session_id": self.session_id or "",
            "tags": self.tags,
            "reusability_score": self.reusability_score,
            "summary": self.summary,
            "body_markdown": self.body_markdown,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KnowledgeEntry":
        title = str(payload.get("title", "")).strip()
        source_tool = str(payload.get("source_tool", "")).strip()
        tool_version = payload.get("tool_version")
        model = payload.get("model")
        project = payload.get("project")
        thinking_mode = str(payload.get("thinking_mode", "unknown")).strip().lower()
        session_date = str(payload.get("session_date", "")).strip()
        session_id = payload.get("session_id")
        summary = str(payload.get("summary", "")).strip()
        body_markdown = str(payload.get("body_markdown", "")).strip()

        if not title:
            raise ValueError("title is required")
        if not source_tool:
            raise ValueError("source_tool is required")
        if thinking_mode not in ALLOWED_THINKING_MODES:
            allowed = ", ".join(sorted(ALLOWED_THINKING_MODES))
            raise ValueError(f"thinking_mode must be one of: {allowed}")
        if not session_date:
            raise ValueError("session_date is required")
        validate_session_date(session_date)
        if not summary:
            raise ValueError("summary is required")
        if not body_markdown:
            raise ValueError("body_markdown is required")

        tags = _as_string_list(payload.get("tags"), "tags")
        score = payload.get("reusability_score", 0)
        if not isinstance(score, int):
            raise ValueError("reusability_score must be an integer")
        if score < 0 or score > 100:
            raise ValueError("reusability_score must be between 0 and 100")

        if tool_version is not None:
            tool_version = str(tool_version).strip() or None
        if model is not None:
            model = str(model).strip() or None
        if project is not None:
            project = str(project).strip() or None
        if session_id is not None:
            session_id = str(session_id).strip() or None

        return cls(
            title=title,
            source_tool=source_tool,
            tool_version=tool_version,
            model=model,
            thinking_mode=thinking_mode,
            project=project,
            session_date=session_date,
            session_id=session_id,
            tags=tags,
            reusability_score=score,
            summary=summary,
            body_markdown=body_markdown,
        )

    @classmethod
    def from_json(cls, raw: str) -> "KnowledgeEntry":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON input: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Top-level JSON payload must be an object")
        return cls.from_dict(payload)


def validate_session_date(value: str) -> None:
    try:
        date.fromisoformat(value)
        return
    except ValueError:
        pass

    try:
        datetime.fromisoformat(value)
        return
    except ValueError as exc:
        raise ValueError(
            "session_date must be ISO 8601 date or datetime, such as 2026-03-08 or 2026-03-08T16:20:00+08:00"
        ) from exc
