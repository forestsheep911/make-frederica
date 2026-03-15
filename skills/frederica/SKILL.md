---
name: frederica
description: "[dev 2026-03-15.2] Summarize an AI chat session into a structured knowledge entry that can be written to a Notion knowledge base with `entrykit capture`. Use when a user wants to archive the key outcomes of a conversation, preserve reusable lessons, or turn a completed chat into a searchable note instead of a one-off summary."
---

# Frederica

## Overview

Turn a finished conversation into a reusable knowledge entry with a stable JSON schema and a flexible Markdown body. Use this skill when the conversation itself is the artifact you want to preserve.

If the user explicitly invokes `frederica`, treat that as a signal that they likely want a reusable capture workflow rather than an ordinary in-chat summary. When a writable cloud backend is already configured and there is no ambiguity about the target, prefer actual persistence over a screen-only recap. Do not silently collapse back to a plain chat recap unless the user makes that preference clear.

## Compatibility

- Assume the primary writable backend is Notion unless the user explicitly asks for another destination.
- Do not assume local `entrykit` access is available. Check for it before promising persistence.
- Treat Notion writes as dependent on a successful local preflight, not just on the user's intent.
- Assume Notion writes require the environment expected by `entrykit`, including `NOTION_TOKEN` and `NOTION_DATABASE_ID`.
- On Windows terminals, prefer UTF-8 file-based handoff into `entrykit` instead of piping non-ASCII JSON through the shell.
- When working from the repository checkout instead of a global install, prefer `PYTHONPATH=src python3 -m entrykit.cli ...`.
- For intermediate files, prefer the OS temporary directory over creating `./tmp` inside the current repository. If a repo-local temp file is unavoidable, delete it before finishing.

## Preflight Order

Before any Notion write attempt, use this order:

1. Check local execution capability first.
2. Use a fast-path tool check: see whether `entrykit` is actually runnable.
3. Only if that fast-path check fails, run fallback diagnosis in this order:
   - confirm global Python
   - confirm global `uv` when the environment policy expects it
   - then retry or reinterpret `entrykit` availability, including repo-checkout execution
4. Check whether the configured `frederica` runtime has the required Notion settings.
5. Only then decide whether to save immediately, ask a follow-up, or fall back to screen-only output.

Do not turn Python and `uv` checks into mandatory every-run gates when `entrykit` is already working.

If `entrykit doctor` is available, prefer it as the first fast-path preflight command.

### What to check first

- Can the current assistant run local commands at all?
- Can `entrykit` run directly from the current environment?
- If `entrykit` runs, skip redundant Python and `uv` checks and continue to configuration.
- If `entrykit` does not run, diagnose the tool layer in this order:
  - Is Python available at the required version?
  - Is `uv` present when the local environment policy expects it?
  - If `entrykit` is not globally installed, can it still be run from the checked-out repo?

If the answer to the execution layer is no, stop promising persistence. In that case, produce a JSON or Markdown artifact and clearly say that the current agent can prepare the capture but cannot perform the local Notion write from this environment.

### Configuration checks after tool checks

If the tool layer is usable, then check configuration:

- `~/.frederica/config/.env`
- or an explicitly provided env file path
- presence of `NOTION_TOKEN`
- presence of `NOTION_DATABASE_ID`

If config is missing, say exactly what is missing before asking the user for anything else.

### How to interact when config is missing

When the user wants persistence but Notion config is missing:

1. State that local write capability exists, but Notion config is incomplete.
2. Prefer telling the user where to place the config locally, such as `~/.frederica/config/.env`.
3. If the user already has a config file elsewhere, ask for its path so it can be loaded explicitly.
4. Only if the user wants to provide the values directly in chat, accept pasted `NOTION_TOKEN` and `NOTION_DATABASE_ID`.

Do not ask the user to paste secrets into chat by default when a local-file path would work.

## Capture Workflow

1. Confirm the goal is to capture the conversation as a reusable note rather than answer a new question.
2. Determine the persistence target before deciding the output shape.
3. If exactly one writable backend is already configured and the user invokes `frederica`, treat persistence to that backend as the default path unless the user explicitly asks for screen-only output.
4. If the user says "保存", "存下来", "归档", "记下来", or another clearly persistent intent, do the actual save when a single configured backend is available. Do not stop at merely preparing JSON or Markdown for that backend.
5. Ask a follow-up only when the target is genuinely ambiguous, such as:
   - multiple writable backends are configured
   - no writable backend is configured
   - the user explicitly contrasts screen-only output with persistence
6. If the user names Notion, use the full capture-and-write workflow.
7. If the user wants persistence to a backend that is not currently wired up, still prepare the `KnowledgeEntry` JSON or Markdown output and state that the last-mile write is not yet implemented for that backend.
8. If the current tool exposes runtime metadata through a command such as `/status`, inspect it before capturing and reuse any explicitly visible metadata such as model name, exact model identifier, or session id.
9. Default to the full current conversation as the capture scope. Narrow the scope only when the user explicitly asks to capture a subsection, a recent segment, or a single topic.
10. Extract the durable outcomes of the conversation:
   - What happened
   - What mattered
   - What is reusable later
11. Build a `KnowledgeEntry` JSON object that matches [`references/schema.md`](references/schema.md).
12. Keep the database-facing fields concise and searchable:
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
13. Write the long-form content into `body_markdown`. Adapt the structure to the material instead of forcing fixed headings.
14. Treat the Notion body as block-limited content rather than unlimited Markdown:
   - stay comfortably under 100 rendered Notion blocks
   - prefer in-block newlines over splitting every short sentence into a separate paragraph
   - use blank lines only when a real structural boundary is needed
15. If the draft appears likely to exceed the block budget, compress structure before saving:
   - merge adjacent paragraphs that belong to the same idea
   - avoid one-line paragraphs when they can be grouped
   - only keep list formatting when the list itself adds meaning
16. If capture quality matters, especially when another model produced the first draft, optionally run a second review pass with `entrykit review` so a separate LLM can check metadata guessing, language matching, scope coverage, detail level, and block-budget risk.
17. If the resolved target is a configured writable backend and local execution is available, execute the save instead of stopping at a prepared payload.
18. Before the first write attempt, run a fast-path local preflight such as `entrykit doctor` when available.
19. If that fast-path check fails, diagnose the local tool layer before giving up:
   - confirm command execution
   - confirm Python
   - confirm `uv` when expected
   - then retry `entrykit` via global install or repo-checkout execution
20. If the doctor or equivalent checks show that local execution is unavailable even after fallback diagnosis, do not claim the note was saved. Return a prepared artifact instead.
21. If the doctor or equivalent checks show that Notion config is missing, explain the missing config and ask the user whether to:
   - configure `~/.frederica/config/.env`
   - provide a path to an existing env file
   - paste the needed values directly
22. If the user wants the result saved and a local `entrykit` command is available, pass the JSON to `entrykit capture`.
23. On Windows, especially in PowerShell, do not default to piping non-ASCII JSON directly into `entrykit`. Prefer writing the JSON to a UTF-8 file first and then using `entrykit capture --input <path>`.
24. When a temporary JSON or transcript file is needed for `entrykit`, put it in the system temp directory rather than `./tmp` under the working repository unless the user explicitly asks otherwise.
25. If you had to create a repo-local temporary file or directory during capture, remove it before finishing so the worktree does not stay dirty.
26. If PowerShell piping is unavoidable, explicitly force UTF-8 before running `entrykit`, such as `[Console]::InputEncoding = [System.Text.Encoding]::UTF8`, `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`, `$env:PYTHONUTF8='1'`, and `$env:PYTHONIOENCODING='utf-8'`.
27. Treat mojibake such as `鎺掓煡浜` or `骞剁‘璁や簡` as an encoding failure rather than a content failure. If it appears, retry with a UTF-8 file-based flow instead of trusting the current terminal pipeline.
28. If local execution is needed from the repo checkout, prefer `PYTHONPATH=src python3 -m entrykit.cli ...`. If a reusable local install is needed, prefer a virtualenv rather than installing into a system-managed Python. Do not assume a bare `python` command exists, especially on macOS.

## Output Rules

- Return JSON only when the user asked for a structured capture payload.
- If the user invoked `frederica`, do not treat screen-only prose as the default when a configured writable backend is already available.
- If the user expressed clear persistence intent and the target backend is unambiguous, perform the save instead of only preparing a capture payload.
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
- Keep the rendered Notion body under 100 blocks. Do not spend blocks on cosmetic spacing.
- Prefer in-block newlines inside a paragraph when content belongs together.
- Treat every blank-line paragraph split as a cost against the Notion block budget.
- Keep enough context in `body_markdown` that the entry still makes sense weeks later.
- Default to concise-but-complete coverage. If the user explicitly asks for a detailed, exhaustive, or step-by-step recap, preserve the full sequence instead of compressing aggressively.
- When running `entrykit` from Windows terminals, preserve UTF-8 end to end for any non-ASCII content. Prefer UTF-8 files over shell pipes for Chinese or other non-ASCII text.

## Body Guidance

- Start with a short overview.
- Choose headings that fit the material. A coding fix, a travel note, and a research summary should not use the same template.
- Prefer fewer, denser paragraphs over many one-line paragraphs.
- Use lists only when sequence or grouping matters. If not, fold the content back into normal paragraphs.
- When several short observations belong to one theme, keep them inside one paragraph block with line breaks instead of spending one block per line.
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
- If local execution is unavailable, do not shift the blame to missing Notion credentials before you have established that the local tool layer is runnable.
- If local execution is available but Notion config is missing, ask for the local config path first. Only ask the user to paste secrets directly when they explicitly choose that route.
- If the user wants persistence but does not specify a destination, ask only when the target cannot be resolved from the configured backends.
- If the requested persistence backend is planned but not yet supported, say that clearly and provide the best intermediate artifact you can produce now.
- If Windows terminal output shows mojibake, do not keep going with the same command shape. Switch to a UTF-8 file plus `--input`, or explicitly set PowerShell and Python UTF-8 settings before retrying.
- If any repo-local `tmp/` or other temporary capture directory was created during the workflow, remove it before finishing unless the user explicitly asked to keep it.
- If a second review pass is available, treat it as advisory quality control rather than a hard blocker. The user may still choose to save the note.

## Final Self-Check

Before returning the final JSON, check these points:

- Did `model` come from an explicitly visible string? If not, set it to an empty string.
- Did `tool_version` come from an explicitly visible string? If not, set it to an empty string.
- Did `session_id` come from an explicitly visible string? If not, set it to an empty string.
- Are `title`, `summary`, and `body_markdown` written in the dominant language of the conversation?
- Did the summary scope cover the whole current session unless the user explicitly narrowed it?
- Did the detail level match the user's latest instruction?
- If a writable backend was configured and unambiguous, did you default to actual persistence rather than a screen-only recap?
- If you asked a follow-up about the destination, was that because the target was genuinely ambiguous rather than just because saving was possible?
- If the workflow includes `entrykit` on Windows, did you avoid non-UTF-8 pipes or explicitly force UTF-8 before capture?
- Will `body_markdown` likely stay under 100 rendered Notion blocks after Markdown conversion?
- Did you use in-block newlines and paragraph merging where they reduce block count without harming readability?

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
- Read [`evals/evals.json`](evals/evals.json) for a starter evaluation set covering save intent, language matching, and block-budget discipline.
