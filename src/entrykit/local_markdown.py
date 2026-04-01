from __future__ import annotations

import re
from pathlib import Path

from entrykit.models import KnowledgeEntry


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "note"


def _yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _append_yaml_string(lines: list[str], name: str, value: str | None, *, required: bool = False) -> None:
    cleaned = (value or "").strip()
    if cleaned or required:
        lines.append(f"{name}: {_yaml_quote(cleaned)}")


def _append_yaml_string_list(lines: list[str], name: str, values: list[str]) -> None:
    if not values:
        return
    lines.append(f"{name}:")
    lines.extend(f"  - {_yaml_quote(value)}" for value in values)


def render_markdown_entry(entry: KnowledgeEntry) -> str:
    lines = ["---"]
    _append_yaml_string(lines, "schema_version", entry.schema_version, required=True)
    _append_yaml_string(lines, "entry_id", entry.entry_id, required=True)
    _append_yaml_string(lines, "title", entry.title, required=True)
    lines.append("")

    _append_yaml_string(lines, "entry_type", entry.entry_type)
    _append_yaml_string(lines, "source_tool", entry.source_tool, required=True)
    _append_yaml_string(lines, "tool_version", entry.tool_version)
    _append_yaml_string(lines, "model", entry.model)
    _append_yaml_string(lines, "thinking_mode", entry.thinking_mode, required=True)
    lines.append("")

    _append_yaml_string(lines, "project", entry.project)
    _append_yaml_string(lines, "session_date", entry.session_date, required=True)
    _append_yaml_string(lines, "session_id", entry.session_id)
    _append_yaml_string(lines, "language", entry.language)
    _append_yaml_string(lines, "status", entry.status)
    lines.append("")

    lines.append(f"reusability_score: {entry.reusability_score}")
    _append_yaml_string_list(lines, "tags", entry.tags)
    _append_yaml_string_list(lines, "topics", entry.topics)
    _append_yaml_string_list(lines, "tech_stack", entry.tech_stack)
    _append_yaml_string_list(lines, "entities", entry.entities)
    _append_yaml_string_list(lines, "artifacts", entry.artifacts)
    _append_yaml_string(lines, "summary", entry.summary, required=True)
    _append_yaml_string_list(lines, "decisions", entry.decisions)
    _append_yaml_string_list(lines, "actions", entry.actions)
    _append_yaml_string_list(lines, "open_questions", entry.open_questions)
    _append_yaml_string_list(lines, "related_entries", entry.related_entries)
    while lines and lines[-1] == "":
        lines.pop()
    body = entry.body_markdown.strip()
    body_lines = ["> " + entry.summary]
    if body:
        body_lines.extend(["", body])
    lines.extend(["---", "", "\n".join(body_lines), ""])
    return "\n".join(lines)


def build_output_path(entry: KnowledgeEntry, output_dir: Path) -> Path:
    date_prefix = entry.session_date[:10]
    base_name = f"{date_prefix}-{_slugify(entry.title)}"
    candidate = output_dir / f"{base_name}.md"
    suffix = 2
    while candidate.exists():
        candidate = output_dir / f"{base_name}-{suffix}.md"
        suffix += 1
    return candidate


def write_markdown_entry(entry: KnowledgeEntry, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = build_output_path(entry, output_dir)
    path.write_text(render_markdown_entry(entry), encoding="utf-8")
    return path
