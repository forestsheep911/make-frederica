# Cross-Tool Workflow

Inside `make-frederica`, there are two working layers:

- `skills/frederica/`
  - The skill logic and examples
- `entrykit`
  - The supporting local CLI that validates JSON and writes to Notion

## Recommended local workflow

### 1. Native workflow in Codex

Use the local skill to shape the summary, then write the result to Notion:

```bash
entrykit capture --input examples/coding-session.json
```

### 2. Use the same skill in other assistants

If another assistant can consume the same skill files, use `frederica` directly there as well. The durable contract is still the same `KnowledgeEntry` JSON.

When the user explicitly invokes `frederica`, the assistant should treat persistence as the default path if exactly one writable backend is already configured.

Ask a follow-up only when the target is genuinely ambiguous, for example:

- screen-only summary in the current chat
- write the result to Notion
- prepare a local artifact for another backend such as Markdown or a future Obsidian flow

If the user says "save", "archive", or another clearly persistent intent and Notion is the only configured writable backend, the assistant should perform the actual write instead of stopping at a prepared payload.

This keeps `frederica` distinct from ordinary summarization while still making cloud persistence the default behavior when the environment is already configured.

### 3. Fallback workflow for tools that only accept prompts

Generate a reusable prompt:

```bash
entrykit render-prompt --source-tool cursor
```

or:

```bash
entrykit render-prompt --source-tool gemini-cli --include-example
```

Paste that prompt into the target tool together with the conversation content. Ask it to return JSON only. Save the JSON to a file, then import it locally:

```bash
entrykit capture --input captured.json
```

On Windows, especially in PowerShell, prefer the file-based flow above over piping JSON directly into `entrykit`. This avoids mojibake when the shell or Python process does not stay on UTF-8 for non-ASCII text such as Chinese.

If piping is unavoidable, force UTF-8 first:

```powershell
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
```

If you see garbled text such as `鎺掓煡浜` or `骞剁‘璁や簡`, treat it as an encoding failure and retry with `--input` from a UTF-8 file instead of continuing with the same pipe-based command.

If the tool exposes runtime metadata through a command like `/status`, run that first and include the visible output in the captured context so fields such as `model_id` or `session_id` can be filled without guessing.

## Why this works

- The summary logic stays stable across tools because the JSON contract is fixed.
- The last-mile Notion write stays local, so secrets do not need to be pasted into other tools.
- You can improve the skill and the supporting CLI independently while keeping the same `KnowledgeEntry` schema.

## Current boundary

This workflow does not yet auto-read Cursor or Gemini CLI conversation history. It assumes you manually paste the conversation or the generated JSON.
