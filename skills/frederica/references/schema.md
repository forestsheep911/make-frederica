# Knowledge Entry Schema

Use this schema when summarizing a chat session for `entrykit capture`.

Default to the full current conversation unless the user explicitly asks to capture only a subsection or a narrower topic.

## Required JSON shape

```json
{
  "entry_id": "ke-20260308-7f3a2c1d",
  "title": "Short page title",
  "entry_type": "decision",
  "source_tool": "codex",
  "tool_version": "v0.111.0",
  "model": "gpt-5.4",
  "thinking_mode": "high",
  "project": "make-frederica",
  "session_date": "2026-03-08T16:20:00+08:00",
  "session_id": "",
  "language": "zh-CN",
  "status": "active",
  "tags": ["notion", "workflow"],
  "topics": ["knowledge-capture", "schema-design"],
  "tech_stack": ["python", "notion-api"],
  "entities": ["KnowledgeEntry", "Notion", "entrykit"],
  "artifacts": ["repo:make-frederica", "cmd:entrykit capture"],
  "reusability_score": 80,
  "summary": "One short summary for database browsing.",
  "decisions": ["Keep the canonical note format stable and let backends project from it."],
  "actions": [],
  "open_questions": [],
  "related_entries": [],
  "body_markdown": "# Overview\n\nMain notes go here."
}
```

## Field rules

- `title`: Required. Short and specific.
- `entry_id`: Required in the canonical model. Preserve it when present. If the input is legacy v1 and the field is missing, the application may generate it during normalization.
- `entry_type`: Optional normalized note type such as `decision`, `discussion`, `howto`, `debugging`, `proposal`, or `reference`.
- `source_tool`: Required. Human-readable tool label such as `codex`, `claude-code`, `cursor`, or `gemini-cli`.
- `tool_version`: Optional. Store the visible tool or client version when it is explicitly exposed, such as `v0.111.0`. Leave empty rather than guessing.
- `model`: Optional. Store the visible model name exactly as the tool shows it, such as `gpt-5.4`, `Claude Sonnet 4.5`, or `Gemini 2.5 Pro`. Leave empty rather than guessing.
  Never infer it from plan name, product tier, provider defaults, or general background knowledge.
- `thinking_mode`: Optional semantic label, but the JSON field is required. Use one of `unknown`, `low`, `medium`, `high`, `extra-high`.
- `project`: Optional repository or initiative name.
- `session_date`: Required. Prefer full ISO 8601 date-time, such as `2026-03-08T16:20:00+08:00`. A plain date is still accepted.
- `session_id`: Optional. Store the conversation or session identifier only when the tool explicitly exposes it, for example through `/status` or an equivalent runtime metadata command.
- `language`: Optional dominant note language such as `zh-CN` or `en`.
- `status`: Optional canonical lifecycle state such as `active`, `draft`, `superseded`, or `archived`.
- `tags`: Optional list of short tags. Infer them from the conversation. Prefer 3 to 8 tags. Reuse common tags when they fit, such as `debugging`, `workflow`, `notion`, `prompting`, `python`, `cursor`, `codex`, `claude-code`, `gemini-cli`, `design`, `travel`, `research`, `architecture`, or `testing`.
- `topics`: Optional normalized topical labels for what the note is about.
- `tech_stack`: Optional list of primary technologies or platforms such as `python`, `react`, or `notion-api`.
- `entities`: Optional list of explicit named systems, products, APIs, classes, or concepts mentioned in the note.
- `artifacts`: Optional list of concrete references such as `file:...`, `repo:...`, `cmd:...`, `url:...`, or `issue:...`.
- `reusability_score`: Required integer from `0` to `100`.
- `summary`: Required. One or two sentences suitable for Notion list views. Follow the dominant language of the conversation unless the user explicitly asks for another language.
- `decisions`: Optional list of explicit conclusions reached in the session.
- `actions`: Optional list of follow-up steps or next actions.
- `open_questions`: Optional list of unresolved issues.
- `related_entries`: Optional list of related `entry_id` values or stable note keys.
- `body_markdown`: Required. Markdown body written for the Notion page content. Follow the dominant language of the conversation unless the user explicitly asks for another language.
  Keep the rendered result under 100 Notion blocks. Prefer in-block newlines and merged paragraphs over one-line-per-block formatting.

## Body guidelines

- Adapt the structure to the content instead of forcing fixed sections.
- Start with a short overview.
- Keep the note in the dominant language of the source conversation unless the user explicitly asks for translation.
- Do not switch to English for technical content unless the user explicitly asks for English.
- Default to concise-but-complete coverage. If the user explicitly requests a detailed or exhaustive recap, preserve the full sequence instead of compressing it heavily.
- Treat blank lines as costly because they often create extra Notion blocks.
- Prefer a paragraph with internal line breaks when several short statements belong to the same idea.
- Use lists only when the list shape adds meaning, not just to create visual separation.
- Preserve the context needed to make the notes useful later.
- Capture reusable lessons when they exist.
- Add steps, risks, conclusions, or actions only when they are relevant.

## Optional second review

When quality matters or another model produced the first draft, a second-pass review can check the same capture against the original conversation.

- Focus the review on a short list of high-risk failures:
  - guessed `model`, `tool_version`, or `session_id`
  - wrong dominant language
  - partial-session coverage
  - detail level that does not match the user's request
- Treat this review as advisory rather than a hard gate.
- A useful review outcome has three states:
  - `pass`
  - `uncertain`
  - `major_issue`
