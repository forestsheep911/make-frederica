# Cross-Tool Workflow

Inside `make-frederica`, there are two working layers:

- `skills/frederica-dev/`
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

If the tool exposes runtime metadata through a command like `/status`, run that first and include the visible output in the captured context so fields such as `model_id` or `session_id` can be filled without guessing.

## Why this works

- The summary logic stays stable across tools because the JSON contract is fixed.
- The last-mile Notion write stays local, so secrets do not need to be pasted into other tools.
- You can improve the skill and the supporting CLI independently while keeping the same `KnowledgeEntry` schema.

## Current boundary

This workflow does not yet auto-read Cursor or Gemini CLI conversation history. It assumes you manually paste the conversation or the generated JSON.
