---
name: frederica-dev
description: Summarize an AI chat session into a structured knowledge entry that can be written to a Notion knowledge base with `entrykit capture`. Use when a user wants to archive the key outcomes of a conversation, preserve reusable lessons, or turn a completed chat into a searchable note instead of a one-off summary.
---

# Frederica

## Overview

Turn a finished conversation into a reusable knowledge entry with a stable JSON schema and a flexible Markdown body. Use this skill when the conversation itself is the artifact you want to preserve.

## Capture Workflow

1. Confirm the goal is to capture the conversation as a reusable note rather than answer a new question.
2. If the current tool exposes runtime metadata through a command such as `/status`, inspect it before capturing and reuse any explicitly visible metadata such as model name, exact model identifier, or session id.
3. Default to the full current conversation as the capture scope. Narrow the scope only when the user explicitly asks to capture a subsection, a recent segment, or a single topic.
4. Extract the durable outcomes of the conversation:
   - What happened
   - What mattered
   - What is reusable later
5. Build a `KnowledgeEntry` JSON object that matches [`references/schema.md`](references/schema.md).
6. Keep the database-facing fields concise and searchable:
   - `title`
   - `source_tool`
   - `tool_version`
   - `model`
   - `thinking_mode`
   - `project`
   - `session_date`
   - `session_id`
   - `tags`
   - `reusability_score`
   - `summary`
7. Write the long-form content into `body_markdown`. Adapt the structure to the material instead of forcing fixed headings.
8. If capture quality matters, especially when another model produced the first draft, optionally run a second review pass with `entrykit review` so a separate LLM can check metadata guessing, language matching, scope coverage, and detail level.
9. If the user wants the result saved and a local `entrykit` command is available, pass the JSON to `entrykit capture`.
10. If local execution is needed from the repo checkout, prefer `PYTHONPATH=src python3 -m entrykit.cli ...`. If a reusable local install is needed, prefer a virtualenv rather than installing into a system-managed Python. Do not assume a bare `python` command exists, especially on macOS.

## Output Rules

- Return JSON only when the user asked for a structured capture payload.
- Prefer a short, concrete `title`.
- Use `tool_version` for the visible tool or client version when it is explicitly exposed, such as `v0.111.0`. Leave it empty instead of guessing.
- Use `model` for the visible model name exactly as the tool shows it, such as `gpt-5.4`, `Claude Sonnet 4.5`, or `Gemini 2.5 Pro`. Leave it empty instead of guessing.
- Never infer `model` from plan name, product tier, provider defaults, or general background knowledge. If the exact visible model string is missing, leave `model` empty.
- Unless the user explicitly narrows the scope, summarize the whole current session rather than only the most recent exchange.
- Set `thinking_mode` to one of `unknown`, `low`, `medium`, `high`, or `extra-high`.
- Use `session_id` only when the current tool explicitly exposes a conversation or session identifier, such as visible output from `/status` or an equivalent command.
- Infer `tags` from the conversation instead of using a fixed list. Prefer 3 to 8 concise tags. Reuse common tags when they fit, such as `debugging`, `workflow`, `notion`, `prompting`, `python`, `cursor`, `codex`, `claude-code`, `gemini-cli`, `design`, `travel`, `research`, `architecture`, and `testing`.
- Set `reusability_score` as an integer from `0` to `100`.
- Prefer full ISO 8601 date-time in `session_date` when available.
- Write `title`, `summary`, and `body_markdown` in the dominant language of the conversation unless the user explicitly asks for another language.
- Treat language matching as a hard constraint. Do not switch to English just because the topic is technical.
- Make `summary` short enough for Notion list views.
- Write `body_markdown` in Markdown that can be rendered as a Notion page body.
- Keep enough context in `body_markdown` that the entry still makes sense weeks later.
- Default to concise-but-complete coverage. If the user explicitly asks for a detailed, exhaustive, or step-by-step recap, preserve the full sequence instead of compressing aggressively.

## Body Guidance

- Start with a short overview.
- Choose headings that fit the material. A coding fix, a travel note, and a research summary should not use the same template.
- Preserve concrete details that make the note useful later.
- Capture reusable lessons when they exist.
- Add risks, actions, steps, alternatives, or conclusions only when they are actually present in the source conversation.

## Failure Handling

- If the source conversation is too thin to support a useful entry, say so and ask for the missing context instead of fabricating details.
- If `tool_version`, `model`, `session_id`, or `thinking_mode` is not explicit, prefer empty strings for the missing identifiers and `unknown` for `thinking_mode`.
- If the conversation covers multiple unrelated topics, either:
  - create one entry for the dominant topic, or
  - tell the user it should be split into multiple captures
- If local execution is unavailable, still produce the JSON so the user can save it and run `entrykit capture` later.
- If a second review pass is available, treat it as advisory quality control rather than a hard blocker. The user may still choose to save the note.

## Final Self-Check

Before returning the final JSON, check these points:

- Did `model` come from an explicitly visible string? If not, set it to an empty string.
- Did `tool_version` come from an explicitly visible string? If not, set it to an empty string.
- Did `session_id` come from an explicitly visible string? If not, set it to an empty string.
- Are `title`, `summary`, and `body_markdown` written in the dominant language of the conversation?
- Did the summary scope cover the whole current session unless the user explicitly narrowed it?
- Did the detail level match the user's latest instruction?

## Example Output

```json
{
  "title": "Stabilize chat-to-Notion capture schema",
  "source_tool": "codex",
  "tool_version": "v0.111.0",
  "model": "gpt-5.4",
  "thinking_mode": "high",
  "project": "make-frederica",
  "session_date": "2026-03-08T16:20:00+08:00",
  "session_id": "",
  "tags": ["notion", "knowledge-capture", "schema"],
  "reusability_score": 86,
  "summary": "Use a stable JSON schema for searchable metadata and keep long-form notes in the Notion page body.",
  "body_markdown": "# Overview\n\nWe settled on a single-database Notion design with flexible page content.\n\n## Why it works\n\n- Database properties stay searchable.\n- Long notes live in the page body.\n- Future note backends can map the same JSON differently."
}
```

## Examples

- Read [`examples/coding-session.md`](examples/coding-session.md) for a sample source conversation and the kind of material worth preserving.
- Read [`examples/coding-session.json`](examples/coding-session.json) for a complete `KnowledgeEntry` payload that can be sent to `entrykit capture`.
