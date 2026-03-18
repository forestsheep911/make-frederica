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


def render_markdown_entry(entry: KnowledgeEntry) -> str:
    lines = [
        "---",
        f"title: {_yaml_quote(entry.title)}",
        f"source_tool: {_yaml_quote(entry.source_tool)}",
        f"tool_version: {_yaml_quote(entry.tool_version or '')}",
        f"model: {_yaml_quote(entry.model or '')}",
        f"thinking_mode: {_yaml_quote(entry.thinking_mode)}",
        f"project: {_yaml_quote(entry.project or '')}",
        f"session_date: {_yaml_quote(entry.session_date)}",
        f"session_id: {_yaml_quote(entry.session_id or '')}",
        f"reusability_score: {entry.reusability_score}",
    ]
    if entry.tags:
        lines.append("tags:")
        lines.extend(f"  - {_yaml_quote(tag)}" for tag in entry.tags)
    else:
        lines.append("tags: []")
    lines.extend(
        [
            f"summary: {_yaml_quote(entry.summary)}",
            "---",
            "",
            entry.body_markdown,
            "",
        ]
    )
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
