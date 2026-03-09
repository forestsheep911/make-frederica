# Knowledge Entry Schema

Use this schema when summarizing a chat session for `entrykit capture`.

Default to the full current conversation unless the user explicitly asks to capture only a subsection or a narrower topic.

## Required JSON shape

```json
{
  "title": "Short page title",
  "source_tool": "codex",
  "tool_version": "v0.111.0",
  "model": "gpt-5.4",
  "thinking_mode": "high",
  "project": "make-frederica",
  "session_date": "2026-03-08T16:20:00+08:00",
  "session_id": "",
  "tags": ["notion", "workflow"],
  "reusability_score": 80,
  "summary": "One short summary for database browsing.",
  "body_markdown": "# Overview\n\nMain notes go here."
}
```

## Field rules

- `title`: Required. Short and specific.
- `source_tool`: Required. Human-readable tool label such as `codex`, `claude-code`, `cursor`, or `gemini-cli`.
- `tool_version`: Optional. Store the visible tool or client version when it is explicitly exposed, such as `v0.111.0`. Leave empty rather than guessing.
- `model`: Optional. Store the visible model name exactly as the tool shows it, such as `gpt-5.4`, `Claude Sonnet 4.5`, or `Gemini 2.5 Pro`. Leave empty rather than guessing.
  Never infer it from plan name, product tier, provider defaults, or general background knowledge.
- `thinking_mode`: Optional semantic label, but the JSON field is required. Use one of `unknown`, `low`, `medium`, `high`, `extra-high`.
- `project`: Optional repository or initiative name.
- `session_date`: Required. Prefer full ISO 8601 date-time, such as `2026-03-08T16:20:00+08:00`. A plain date is still accepted.
- `session_id`: Optional. Store the conversation or session identifier only when the tool explicitly exposes it, for example through `/status` or an equivalent runtime metadata command.
- `tags`: Optional list of short tags. Infer them from the conversation. Prefer 3 to 8 tags. Reuse common tags when they fit, such as `debugging`, `workflow`, `notion`, `prompting`, `python`, `cursor`, `codex`, `claude-code`, `gemini-cli`, `design`, `travel`, `research`, `architecture`, or `testing`.
- `reusability_score`: Required integer from `0` to `100`.
- `summary`: Required. One or two sentences suitable for Notion list views. Follow the dominant language of the conversation unless the user explicitly asks for another language.
- `body_markdown`: Required. Markdown body written for the Notion page content. Follow the dominant language of the conversation unless the user explicitly asks for another language.

## Body guidelines

- Adapt the structure to the content instead of forcing fixed sections.
- Start with a short overview.
- Keep the note in the dominant language of the source conversation unless the user explicitly asks for translation.
- Do not switch to English for technical content unless the user explicitly asks for English.
- Default to concise-but-complete coverage. If the user explicitly requests a detailed or exhaustive recap, preserve the full sequence instead of compressing it heavily.
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
