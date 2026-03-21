---
name: frederica
description: "[dev 2026-03-21.1] Summarize an AI chat session into a structured knowledge entry that can be written to a Notion knowledge base with `entrykit capture`. Use when a user wants to archive the key outcomes of a conversation, preserve reusable lessons, or turn a completed chat into a searchable note instead of a one-off summary."
---

# Frederica

## Overview

Turn a finished conversation into a reusable knowledge entry with a stable JSON schema and a flexible Markdown body. Use this skill when the conversation itself is the artifact you want to preserve.

If the user explicitly invokes `frederica`, treat that as a signal that they likely want a reusable capture workflow rather than an ordinary in-chat summary. Resolve the target backend from the user's explicit request first, then from the configured default output. Do not silently collapse back to a plain chat recap when a configured persistent target is available.

If the user explicitly asks to view or change frederica configuration, enter a configuration-management workflow instead of the capture workflow. Keep the boundary tight: only manage `~/.frederica/config/targets.json` and `~/.frederica/config/.env`.

## Compatibility

- Do not assume local `entrykit` access is available. Check for it before promising persistence.
- Treat backend writes as dependent on a successful local preflight, not just on the user's intent.
- Treat `~/.frederica/config/targets.json` as the control-plane config for `default_output` and backend-specific settings.
- Treat `screen`, `notion`, `obsidian`, and `local_markdown` as the known output target names in config.
- Treat only `screen`, `notion`, and `local_markdown` as currently executable capture targets.
- Treat `obsidian` as planned configuration state, not as a writable last-mile target yet.
- Treat a user's explicit backend request as higher priority than `default_output` for the current turn.
- Assume Notion writes require the environment expected by `entrykit`, including `NOTION_TOKEN` and `NOTION_DATABASE_ID`.
- Do not assume `entrykit doctor` and `entrykit capture` load environment variables identically. Treat `doctor` success as advisory until an actual write path has either succeeded or a same-process env load has been verified.
- On Windows terminals, prefer UTF-8 file-based handoff into `entrykit` instead of piping non-ASCII JSON through the shell.
- When working from the repository checkout instead of a global install, prefer `PYTHONPATH=src python3 -m entrykit.cli ...`.
- For intermediate files, prefer the OS temporary directory over creating `./tmp` inside the current repository. If a repo-local temp file is unavoidable, delete it before finishing.

## Preflight Order

Before any write attempt, use this order:

1. Check local execution capability first.
2. Use a fast-path tool check: see whether `entrykit` is actually runnable.
3. Only if that fast-path check fails, run fallback diagnosis in this order:
   - confirm global Python
   - confirm global `uv` when the environment policy expects it
   - then retry or reinterpret `entrykit` availability, including repo-checkout execution
4. Resolve the output target:
   - explicit user override for this turn
   - otherwise `default_output` from `~/.frederica/config/targets.json`
5. Run backend-specific checks only for the resolved target.
5. Only then decide whether to save immediately, ask a follow-up, or fall back to screen-only output.

Do not turn Python and `uv` checks into mandatory every-run gates when `entrykit` is already working.

If `entrykit doctor` is available, prefer it as the first fast-path preflight command because it can expose both runtime and backend-readiness status.

### What to check first

- Can the current assistant run local commands at all?
- Can `entrykit` run directly from the current environment?
- If `entrykit` runs, skip redundant Python and `uv` checks and continue to configuration.
- If `entrykit` does not run, diagnose the tool layer in this order:
  - Is Python available at the required version?
  - Is `uv` present when the local environment policy expects it?
  - If `entrykit` is not globally installed, can it still be run from the checked-out repo?
- What is the resolved output target for this turn?
- If the target is `screen`, do not block on persistence config.
- If the target is `notion`, check the configured env file.
- If the target is `obsidian`, check the configured vault path and target folder.
- If the target is `local_markdown`, check the configured output directory.

If the answer to the execution layer is no, stop promising persistence. In that case, produce a JSON or Markdown artifact and clearly say that the current agent can prepare the capture but cannot perform the local Notion write from this environment.

### Backend resolution after tool checks

If the tool layer is usable, resolve the output target in this order:

1. If the user explicitly names `screen`, `notion`, `obsidian`, or `local_markdown`, resolve that as the user's intended target for this turn.
2. Otherwise read `default_output` from `~/.frederica/config/targets.json`.
3. If `targets.json` does not exist, treat the default as `screen`.
4. If the resolved target is `screen` and the user did not express persistence intent, return the capture in chat.
5. If the resolved target is `screen` but the user explicitly asks to save, persist, archive, or store the note, do not silently fall back to screen output. Enter a short backend-setup or backend-selection follow-up instead.

Do not ask the user to choose a backend on every run when `default_output` already resolves the target.

### Backend-specific configuration checks

After resolving the target, check only the relevant backend configuration:

- `notion`
  - `~/.frederica/config/.env`
  - or an explicitly provided env file path
  - presence of `NOTION_TOKEN`
  - presence of `NOTION_DATABASE_ID`
- `local_markdown`
  - `~/.frederica/config/targets.json`
  - `backends.local_markdown.enabled`
  - `backends.local_markdown.output_dir`
- `obsidian`
  - `~/.frederica/config/targets.json`
  - `backends.obsidian.enabled`
  - `backends.obsidian.vault_path`
  - optional `backends.obsidian.folder`
  - but treat this as setup-only until the writer exists

If backend config is missing, say exactly what is missing before asking the user for anything else.

### How to interact when config is missing

When the resolved backend is persistent but config is missing:

1. State that local write capability exists, but the chosen backend config is incomplete.
2. Offer two explicit setup paths when the missing config is sensitive. Always present them as numbered options:
   - 1. Recommended: edit the local config file such as `~/.frederica/config/.env`
   - 2. Less safe: paste the values directly into chat for this setup step
3. Explicitly say that replying with just `1` or `2` is acceptable.
4. When offering direct paste for sensitive config, add a short warning that secrets pasted into chat are less safe than editing the local file directly.
5. If the user chooses the paste-in-chat path for sensitive values, ask for one field at a time rather than requesting all secrets in a single message.
6. For Notion, ask in this order when values are missing:
   - 1. `NOTION_TOKEN`
   - 2. `NOTION_DATABASE_ID`
7. After each pasted value, confirm which field was captured before asking for the next one.
8. If the user already has a config file or path elsewhere, ask for that path so it can be loaded explicitly.
9. For non-sensitive config such as vault paths or output directories, direct in-chat setup is acceptable.

When the user is choosing a backend for first-time setup:

1. Offer only currently writable persistent targets by default:
   - 1. `notion`
   - 2. `local_markdown`
2. Mention `screen` only as a non-persistent fallback, not as a save target.
3. Mention `obsidian` only if the user explicitly asks for it or already has it configured.
4. If `obsidian` comes up, say clearly that its config can be prepared now but `entrykit capture` cannot write to it yet.

Do not ask the user to paste secrets into chat by default when a local-file path would work. If direct paste is offered, label the local-file path as the recommended option and attach a warning to the paste-in-chat option.
If you present options, keep the numbering stable and accept a number-only reply.

## Config Workflow

Use this workflow when the user asks to view or change frederica configuration directly, for example:

- "用 frederica 改配置"
- "把默认输出改成 notion"
- "查看 frederica 当前配置"
- "更新 notion token"
- "修改 obsidian vault 路径"
- "修改本地 markdown 输出目录"

Treat these as configuration requests rather than summary or capture requests.

### Supported scope

- `~/.frederica/config/targets.json`
  - `default_output`
  - `backends.notion.enabled`
  - `backends.notion.env_file`
  - `backends.obsidian.enabled`
  - `backends.obsidian.vault_path`
  - `backends.obsidian.folder`
  - `backends.local_markdown.enabled`
  - `backends.local_markdown.output_dir`
- `~/.frederica/config/.env`
  - `NOTION_TOKEN`
  - `NOTION_DATABASE_ID`

Do not expand this skill into a general system-configuration assistant.

### Preferred command support

If local execution is available, prefer the supporting CLI for config work:

- `entrykit config show`
- `entrykit config set-default <screen|notion|obsidian|local_markdown>`
- `entrykit config set-notion ...`
- `entrykit config set-notion-secret ...`
- `entrykit config set-obsidian ...`
- `entrykit config set-local-markdown ...`

### Interaction rules

1. If the user asks to inspect config, show the current frederica config and backend status.
2. If the user asks to change non-sensitive config, such as `default_output` or local paths, update the config directly.
3. If the user asks to change sensitive config such as `NOTION_TOKEN`, offer two numbered setup paths:
   - 1. Recommended: edit the local env file directly
   - 2. Less safe: paste the secret into chat for this setup step
4. Explicitly say that replying with just `1` or `2` is acceptable.
5. If the user chooses direct paste for sensitive config, attach a short safety warning and then collect one field at a time instead of requesting all values together.
6. When values are captured in chat, confirm each field before asking for the next one.
7. If an obsolete legacy config such as `~/.config/entrykit/env.sh` still exists, say that frederica no longer uses it and offer to delete it.
8. After changing config, confirm what changed and, when useful, suggest `entrykit doctor`.

## Capture Workflow

1. Confirm the goal is to capture the conversation as a reusable note rather than answer a new question.
2. Resolve the output target before deciding the output shape:
   - explicit backend request for this turn
   - otherwise `default_output`
3. If the user says "总结" or asks for a recap without naming a backend, follow `default_output`.
4. If the user says "保存", "存下来", "归档", "记下来", or another clearly persistent intent, do the actual save when the resolved target is a configured writable backend. Do not stop at merely preparing JSON or Markdown for that backend.
5. If the user expresses clear persistence intent but resolution lands on `screen`, do not treat `screen` as the final target. Ask a short follow-up that moves toward a persistent backend or setup path.
6. Ask a follow-up only when the target is genuinely ambiguous, such as:
   - the user explicitly contrasts screen-only output with persistence
   - the user asks to save but the resolved target is `screen`
   - the user asks to save but both the explicit request and `default_output` are absent or invalid
7. If the follow-up is needed because persistence intent conflicts with `screen`, offer backend setup or backend choice instead of immediately producing a screen-only recap.
8. If the user names `notion`, use the full capture-and-write workflow.
9. If the user names `local_markdown`, use the full capture-and-write workflow.
10. If the user names `obsidian`, say clearly that the writer is not implemented yet. Offer either:
   - configure the obsidian path now for later
   - or save this turn to `local_markdown` or `notion`
11. If the current tool exposes runtime metadata through a command such as `/status`, inspect it before capturing and reuse any explicitly visible metadata such as model name, exact model identifier, or session id.
12. Default to the full current conversation as the capture scope. Narrow the scope only when the user explicitly asks to capture a subsection, a recent segment, or a single topic.
13. Extract the durable outcomes of the conversation:
   - What happened
   - What mattered
   - What is reusable later
14. Build a `KnowledgeEntry` JSON object that matches [`references/schema.md`](references/schema.md).
15. Keep the database-facing fields concise and searchable:
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
16. Write the long-form content into `body_markdown`. Adapt the structure to the material instead of forcing fixed headings.
17. Treat the Notion body as block-limited content rather than unlimited Markdown:
   - stay comfortably under 100 rendered Notion blocks
   - prefer in-block newlines over splitting every short sentence into a separate paragraph
   - use blank lines only when a real structural boundary is needed
18. If the draft appears likely to exceed the block budget, compress structure before saving:
   - merge adjacent paragraphs that belong to the same idea
   - avoid one-line paragraphs when they can be grouped
   - only keep list formatting when the list itself adds meaning
19. If capture quality matters, especially when another model produced the first draft, optionally run a second review pass with `entrykit review` so a separate LLM can check metadata guessing, language matching, scope coverage, detail level, and block-budget risk.
20. If the resolved target is `screen` and the user did not ask to persist, return the capture in chat and do not treat that as a failed save.
21. If the resolved target is a configured writable backend and local execution is available, execute the save instead of stopping at a prepared payload.
22. After the first successful save to a persistent backend, if `default_output` is still `screen`, ask a short follow-up about whether that backend should become the future default. Do not change `default_output` without the user's confirmation.
23. Before the first write attempt, run a fast-path local preflight such as `entrykit doctor` when available.
24. If that fast-path check fails, diagnose the local tool layer before giving up:
   - confirm command execution
   - confirm Python
   - confirm `uv` when expected
   - then retry `entrykit` via global install or repo-checkout execution
25. If the doctor or equivalent checks show that local execution is unavailable even after fallback diagnosis, do not claim the note was saved. Return a prepared artifact instead.
26. If the resolved target is `notion` and config is missing, explain the missing config and ask the user whether to:
   - 1. configure `~/.frederica/config/.env` as the recommended option
   - 2. provide a path to an existing env file
   - 3. paste the needed values directly, with a warning that this is less safe than editing the local file
27. Explicitly say that replying with just `1`, `2`, or `3` is acceptable.
28. If the user chooses direct paste, request the missing values one by one instead of all at once.
29. If the user wants the result saved and the resolved target is `notion` with a local `entrykit` command available, attempt `entrykit capture`.
30. If that capture attempt fails with missing environment variables such as `NOTION_TOKEN` or `NOTION_DATABASE_ID`, do not immediately treat the backend as unconfigured. First try a same-process env load from `~/.frederica/config/.env`, or from the resolved backend env file path if one is configured, and then retry `entrykit capture` once.
31. Only if the retry still reports missing variables should you treat Notion config as incomplete and enter the numbered setup flow.
32. If the user wants the result saved and the resolved target is `local_markdown` with a local `entrykit` command available, pass the JSON to `entrykit capture`.
33. On Windows, especially in PowerShell, do not default to piping non-ASCII JSON directly into `entrykit`. Prefer writing the JSON to a UTF-8 file first and then using `entrykit capture --input <path>`.
34. When a temporary JSON or transcript file is needed for `entrykit`, put it in the system temp directory rather than `./tmp` under the working repository unless the user explicitly asks otherwise.
35. If you had to create a repo-local temporary file or directory during capture, remove it before finishing so the worktree does not stay dirty.
36. If PowerShell piping is unavoidable, explicitly force UTF-8 before running `entrykit`, such as `[Console]::InputEncoding = [System.Text.Encoding]::UTF8`, `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`, `$env:PYTHONUTF8='1'`, and `$env:PYTHONIOENCODING='utf-8'`.
37. Treat mojibake such as `鎺掓煡浜` or `骞剁‘璁や簡` as an encoding failure rather than a content failure. If it appears, retry with a UTF-8 file-based flow instead of trusting the current terminal pipeline.
38. If local execution is needed from the repo checkout, prefer `PYTHONPATH=src python3 -m entrykit.cli ...`. If a reusable local install is needed, prefer a virtualenv rather than installing into a system-managed Python. Do not assume a bare `python` command exists, especially on macOS.

## Output Rules

- Return JSON only when the user asked for a structured capture payload.
- If the user invoked `frederica`, do not treat screen-only prose as the default when a configured writable backend is already available.
- If the user expressed clear persistence intent, do not let `screen` remain the final target unless the user explicitly accepts screen-only output after the follow-up.
- If the user expressed clear persistence intent and the target backend is unambiguous, perform the save instead of only preparing a capture payload.
- If a save just succeeded to a persistent backend and `default_output` is still `screen`, ask whether that backend should become the default for future plain “总结” requests. Do not switch it automatically.
- If the user is choosing a first persistent backend, prefer offering `notion` and `local_markdown` before mentioning `obsidian`.
- If the user explicitly asks for `obsidian`, be clear that config can be prepared now but direct capture writing is not implemented yet.
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
- If you offer setup options, number them and accept a number-only reply.
- If the user chooses to paste sensitive config, collect one field at a time.
- If the user asked to save but `default_output` is `screen`, do not quietly satisfy the request with a screen-only recap. Ask a short follow-up that moves toward a persistent backend or a setup step.
- If the user wants persistence but does not specify a destination, ask only when the target cannot be resolved from the configured backends.
- If the requested persistence backend is planned but not yet supported, say that clearly and provide the best intermediate artifact you can produce now.
- If obsolete legacy config files such as `~/.config/entrykit/env.sh` still exist, explain that frederica no longer uses them and offer to delete them.
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
