# Review

`entrykit review` supports a second-pass LLM review for a capture JSON before writing it to Notion.

This is not a hard gate. The goal is to give a separate model a narrower job than the original summarization pass.

## What review focuses on

- guessed metadata
  - example: `model` says `Gemini 2.5 Pro`, but the conversation only shows a plan or tier
- dominant-language mismatch
  - example: the conversation is mainly Chinese, but the title, summary, and body are English
- partial-session coverage
  - example: the conversation spans many topics, but the body only describes the last few turns
- detail mismatch
  - example: the user asked for `事无巨细`, but the body still compresses heavily

## Output states

The review response should return one of three states:

- `pass`
  - acceptable as-is
- `uncertain`
  - some issues exist, but the user may still choose to write this version
- `major_issue`
  - important rule violations exist; include a full `revised_entry`

## Step 1: render a review prompt

```bash
entrykit review --input captured.json --conversation conversation.txt
```

This prints a prompt for a second LLM. The prompt includes:

- the proposed `KnowledgeEntry`
- the source conversation
- local heuristic lint findings to focus the review
- the required review JSON schema

## Step 2: validate the review response

Save the second LLM's JSON output to `review.json`, then run:

```bash
entrykit review --input captured.json --response review.json
```

Return normalized JSON instead:

```bash
entrykit review --input captured.json --response review.json --json
```

## Suggested human workflow

1. Generate the first `KnowledgeEntry`
2. Run `entrykit review` to prepare the second-pass review prompt
3. Ask another model to return the review JSON
4. If review says `pass`, write to Notion
5. If review says `uncertain`, either revise or write anyway
6. If review says `major_issue`, prefer the `revised_entry`, then review again if needed

## Current boundary

This command does not call an API by itself. It standardizes the review prompt and validates the review output so the same review contract can be reused across Codex, Gemini CLI, Cursor, or other tools.
