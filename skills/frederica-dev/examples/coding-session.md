# Example Source Conversation

Use this example to understand what kind of chat should trigger the skill and what details should survive the summary.

## Context

The user is building a Notion-backed knowledge capture tool for AI chat sessions. They want a stable schema, a Notion database for searchable metadata, and flexible page bodies for long-form notes.

## Conversation Excerpt

User:
I use Claude Code, Cursor, Codex, and Gemini CLI. After a session, I want to summarize the main points and save them somewhere useful. I think Notion is the right destination. Can this become a skill later?

Assistant:
Yes. Start with a single database and a stable JSON schema. Keep the searchable metadata in database properties and write the long-form note into the page body. Do not overfit the schema to future skill updates.

User:
I do not want a fixed body template like Problem / Next Action. That does not fit every kind of content.

Assistant:
Then keep `body_markdown` flexible. Require only a short overview plus whatever headings the content actually needs.

User:
Add model name and thinking depth if available. Also add a score for how reusable the note is later.

Assistant:
Use `model` when explicitly known and preserve the visible model name exactly as shown by the tool. Use `thinking_mode` with `unknown`, `low`, `medium`, `high`, or `extra-high`. Add `reusability_score` as an integer from `0` to `100`.

## What To Preserve

- The decision to use a single Notion database
- The split between searchable properties and page body content
- The flexible body structure requirement
- The metadata fields that make future filtering possible
- The fact that unknown model metadata should stay unknown instead of guessed
