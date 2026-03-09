from __future__ import annotations

import json
from pathlib import Path


BASE_PROMPT = """Summarize this conversation into a single `KnowledgeEntry` JSON object for later import into Notion.

Return JSON only. Do not wrap it in Markdown fences. Do not add explanation before or after the JSON.

Requirements:
- `source_tool` must be `{source_tool}`.
- `tool_version` should store the tool or client version only when it is explicitly visible, such as `v0.111.0`. Otherwise use an empty string.
- `model` should store the visible model name exactly as shown by the tool, such as `gpt-5.4` or `Claude Sonnet 4.5`. Otherwise use an empty string.
- Never infer `model` from subscription tier, product family, or background knowledge about the provider. If it was not explicitly visible, leave it empty.
- `thinking_mode` must be one of `unknown`, `low`, `medium`, `high`, `extra-high`.
- `session_id` should store the tool's conversation or session identifier only when it is explicitly available. Otherwise use an empty string.
- `session_date` should prefer full ISO 8601 date-time when available, such as `2026-03-08T16:20:00+08:00`.
- `reusability_score` must be an integer from `0` to `100`.
- `tags` should be inferred from the conversation. Prefer 3 to 8 concise tags. Reuse common tags when they fit, such as `debugging`, `workflow`, `notion`, `prompting`, `python`, `cursor`, `codex`, `claude-code`, `gemini-cli`, `design`, `travel`, `research`, `architecture`, or `testing`.
- `title`, `summary`, and `body_markdown` should follow the dominant language of the conversation unless the user explicitly asks for another language.
- Do not switch to English for technical content unless the user explicitly asks for English.
- `summary` must stay concise enough for a database list view.
- `body_markdown` must preserve the useful substance of the conversation, but the heading structure should adapt to the content instead of forcing a fixed template.
- Keep enough concrete context that the note is still useful later.
- Default to concise-but-complete coverage. If the user explicitly asks for a detailed or exhaustive recap, increase detail instead of compressing aggressively.

JSON schema:
{schema}
"""


def schema_snippet(source_tool: str) -> str:
    schema = {
        "title": "Short page title",
        "source_tool": source_tool,
        "tool_version": "",
        "model": "",
        "thinking_mode": "high",
        "project": "make-frederica",
        "session_date": "2026-03-08T16:20:00+08:00",
        "session_id": "",
        "tags": ["notion", "workflow"],
        "reusability_score": 80,
        "summary": "One short summary for database browsing.",
        "body_markdown": "# Overview\n\nMain notes go here.",
    }
    return json.dumps(schema, ensure_ascii=False, indent=2)


def render_capture_prompt(source_tool: str, include_example: bool = False) -> str:
    prompt = BASE_PROMPT.format(
        source_tool=source_tool,
        schema=schema_snippet(source_tool),
    )
    if not include_example:
        return prompt

    example_path = Path(__file__).resolve().parents[2] / "examples" / "coding-session.json"
    example = example_path.read_text(encoding="utf-8").strip()
    return f"{prompt}\nExample JSON:\n{example}\n"
