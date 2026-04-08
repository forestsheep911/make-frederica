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
- Keep the rendered Notion page comfortably under the 100-block limit. Prefer merging related sentences into the same paragraph, and use in-block newlines instead of creating a new block for every short line.
- Treat blank lines as expensive because they often create extra blocks after Markdown-to-Notion conversion. Only split into a new block when the structure materially changes, such as a heading, a real list, a quote, or a code block.
- For important emphasis inside `body_markdown`, use inline formatting deliberately:
  - `**text**` for strong emphasis
  - `*text*` for lighter emphasis
  - `` `code` `` for inline commands, keys, and identifiers
  - `==text==` for Notion-style yellow highlight
  - `{{red|text}}`, `{{blue|text}}`, `{{green|text}}`, `{{yellow_background|text}}` for explicit Notion color annotations when color itself carries meaning
  - `[label](https://...)` for links
- When the content is operational or technical, include fenced code blocks with a language whenever code, config, commands, JSON, YAML, env vars, or diffs would make the note more reusable.
- When the conversation includes a concrete fix, command, config, query, payload, or implementation detail that matters later, preserve a representative snippet in `body_markdown` instead of paraphrasing everything away.
- Keep `summary` short for browsing. Put detailed code, config, and diagrams in `body_markdown`, not in `summary`.
- When structure, flow, or system shape matters, include a fenced `mermaid` block only if a small diagram will make the note easier to understand later.
- Prefer `mermaid` only for a few high-value cases:
  - architecture or component relationships
  - step flow or decision flow
  - state transitions or lifecycle progression
- Do not add a diagram just because the note is technical. Skip `mermaid` when a short paragraph, list, or table is clearer.
- Keep any `mermaid` block compact and readable. One small diagram is better than several decorative ones.
- Use richer Notion block shapes when they help:
  - `- [ ] task` or `- [x] task` for actionable checklists
  - `> [!NOTE] ...`, `> [!TIP] ...`, `> [!IMPORTANT] ...`, `> [!WARNING] ...`, or `> [!ERROR] ...` for callouts
  - `---` for a divider when the section boundary matters
  - `:::toggle Title` ... `:::` for foldable detail sections
  - Markdown tables for compact config, parameter, and comparison views when the rows are genuinely easier to scan as a table
- For visual rhythm, prefer one clean parent bullet with indented child bullets, notes, or code over a long flat list when the items clearly belong together.
- Notion does not support arbitrary font sizes through this pipeline. Use heading levels or callouts when visual hierarchy matters instead of inventing font-size syntax.

JSON schema:
{schema}

Low-block body example:
```markdown
# Overview

This session focused on tightening the Notion capture rules.
We moved the 100-block limit from a soft reminder into explicit validation.
We also clarified that related lines can stay in one paragraph block with internal newlines.

## Practical rule

Prefer one denser paragraph for one idea.
Only start a new block when the structure really changes.

## Rich formatting example

Use `==highlight==` for the one phrase that should pop.
Mark a real risk as {{red|high risk}} only when the color adds meaning.

> [!WARNING] Capture the exact config or command when future debugging depends on it.

```yaml
NOTION_TOKEN: ${{NOTION_TOKEN}}
NOTION_DATABASE_ID: abc123
```

:::toggle Verification details
| Check | Result |
| --- | --- |
| doctor | passed |
| capture | ready |
:::

```mermaid
flowchart TD
  A[Conversation] --> B[KnowledgeEntry JSON]
  B --> C[Notion blocks]
```
```
"""


def schema_snippet(source_tool: str) -> str:
    schema = {
        "schema_version": "knowledge-entry/v2",
        "entry_id": "ke-20260308-7f3a2c1d",
        "title": "Short page title",
        "entry_type": "decision",
        "source_tool": source_tool,
        "tool_version": "",
        "model": "",
        "thinking_mode": "high",
        "project": "make-frederica",
        "session_date": "2026-03-08T16:20:00+08:00",
        "session_id": "",
        "language": "en",
        "status": "active",
        "tags": ["notion", "workflow"],
        "topics": ["knowledge-capture", "schema-design"],
        "tech_stack": ["python", "notion-api"],
        "entities": ["KnowledgeEntry", "Notion", "entrykit"],
        "artifacts": ["repo:make-frederica", "cmd:entrykit capture"],
        "reusability_score": 80,
        "summary": "One short summary for database browsing.",
        "decisions": ["Keep a stable canonical note format and project it into backends."],
        "actions": [],
        "open_questions": [],
        "related_entries": [],
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
