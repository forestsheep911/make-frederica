from __future__ import annotations

import hashlib
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


def _clean_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def _default_entry_id(payload: dict[str, Any], session_date: str) -> str:
    date_prefix = session_date[:10].replace("-", "") if len(session_date) >= 10 else "unknown"
    fingerprint_payload = {
        "title": str(payload.get("title", "")).strip(),
        "source_tool": str(payload.get("source_tool", "")).strip(),
        "session_date": session_date,
        "session_id": str(payload.get("session_id", "")).strip(),
        "summary": str(payload.get("summary", "")).strip(),
        "body_markdown": str(payload.get("body_markdown", "")).strip(),
    }
    raw = json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"ke-{date_prefix}-{digest}"


@dataclass(frozen=True)
class KnowledgeEntry:
    entry_id: str
    title: str
    entry_type: str | None
    source_tool: str
    tool_version: str | None
    model: str | None
    thinking_mode: str
    project: str | None
    session_date: str
    session_id: str | None
    language: str | None
    status: str | None
    tags: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    reusability_score: int = 0
    summary: str = ""
    decisions: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    related_entries: list[str] = field(default_factory=list)
    body_markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "title": self.title,
            "entry_type": self.entry_type or "",
            "source_tool": self.source_tool,
            "tool_version": self.tool_version or "",
            "model": self.model or "",
            "thinking_mode": self.thinking_mode,
            "project": self.project or "",
            "session_date": self.session_date,
            "session_id": self.session_id or "",
            "language": self.language or "",
            "status": self.status or "",
            "tags": self.tags,
            "topics": self.topics,
            "tech_stack": self.tech_stack,
            "entities": self.entities,
            "artifacts": self.artifacts,
            "reusability_score": self.reusability_score,
            "summary": self.summary,
            "decisions": self.decisions,
            "actions": self.actions,
            "open_questions": self.open_questions,
            "related_entries": self.related_entries,
            "body_markdown": self.body_markdown,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KnowledgeEntry":
        title = str(payload.get("title", "")).strip()
        source_tool = str(payload.get("source_tool", "")).strip()
        tool_version = _clean_optional_string(payload.get("tool_version"))
        model = _clean_optional_string(payload.get("model"))
        project = _clean_optional_string(payload.get("project"))
        thinking_mode = str(payload.get("thinking_mode", "unknown")).strip().lower()
        session_date = str(payload.get("session_date", "")).strip()
        session_id = _clean_optional_string(payload.get("session_id"))
        summary = str(payload.get("summary", "")).strip()
        body_markdown = str(payload.get("body_markdown", "")).strip()
        entry_type = _clean_optional_string(payload.get("entry_type"))
        language = _clean_optional_string(payload.get("language"))
        status = _clean_optional_string(payload.get("status"))

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

        entry_id = _clean_optional_string(payload.get("entry_id")) or _default_entry_id(payload, session_date)
        tags = _as_string_list(payload.get("tags"), "tags")
        topics = _as_string_list(payload.get("topics"), "topics")
        tech_stack = _as_string_list(payload.get("tech_stack"), "tech_stack")
        entities = _as_string_list(payload.get("entities"), "entities")
        artifacts = _as_string_list(payload.get("artifacts"), "artifacts")
        decisions = _as_string_list(payload.get("decisions"), "decisions")
        actions = _as_string_list(payload.get("actions"), "actions")
        open_questions = _as_string_list(payload.get("open_questions"), "open_questions")
        related_entries = _as_string_list(payload.get("related_entries"), "related_entries")
        score = payload.get("reusability_score", 0)
        if not isinstance(score, int):
            raise ValueError("reusability_score must be an integer")
        if score < 0 or score > 100:
            raise ValueError("reusability_score must be between 0 and 100")

        return cls(
            entry_id=entry_id,
            title=title,
            entry_type=entry_type,
            source_tool=source_tool,
            tool_version=tool_version,
            model=model,
            thinking_mode=thinking_mode,
            project=project,
            session_date=session_date,
            session_id=session_id,
            language=language,
            status=status,
            tags=tags,
            topics=topics,
            tech_stack=tech_stack,
            entities=entities,
            artifacts=artifacts,
            reusability_score=score,
            summary=summary,
            decisions=decisions,
            actions=actions,
            open_questions=open_questions,
            related_entries=related_entries,
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
