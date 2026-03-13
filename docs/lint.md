# Lint

`entrykit lint` checks whether a captured `KnowledgeEntry` is merely valid JSON or also reasonably consistent with the source conversation.

## What it checks

- visible metadata mismatch
  - example: `/status` shows `gpt-5.4`, but `model` is `Gemini 2.5 Pro`
- missing visible metadata
  - example: `/status` shows a `Session:` value, but `session_id` is empty
- dominant-language mismatch
  - example: the conversation is mainly Chinese, but the summary/body is English
- detail mismatch
  - example: the user asked for `事无巨细`, but the body is still very short
- likely partial-session coverage
  - example: the source conversation is very long, but the body is short enough that it may only cover the last few turns
- Notion block-budget risk
  - example: the body already renders to 90+ blocks and is likely to become fragile
- Notion block-limit overflow
  - example: the body renders to more than 100 blocks and should be compressed before capture

## Usage

Lint a JSON capture only:

```bash
entrykit lint --input captured.json
```

Lint against the original conversation too:

```bash
entrykit lint --input captured.json --conversation conversation.txt
```

Return machine-readable output:

```bash
entrykit lint --input captured.json --conversation conversation.txt --json
```

Fail the command if any issue is found:

```bash
entrykit lint --input captured.json --conversation conversation.txt --strict
```

## Capture with lint gate

To refuse a Notion write when lint finds issues:

```bash
entrykit capture --input captured.json --conversation conversation.txt --strict-lint
```

## Current boundary

This is still a heuristic local checker. It does not fully understand semantics the way an LLM reviewer could, but it is good at catching the specific classes of mistakes we have already observed in practice.

If you want a second-pass semantic review, use [`entrykit review`](review.md) after lint.

## Notion block checks

`entrykit lint` now also estimates how many Notion blocks `body_markdown` will render into.

The formatted output now prints the current usage directly, for example `Notion block usage: 87/100.` The JSON form also includes `block_count` and `block_limit`.

- `notion-block-limit-near`
  - warning at 90 blocks or more
  - treat this as a cue to merge adjacent paragraphs and prefer in-block newlines
- `notion-block-limit-exceeded`
  - error above 100 blocks
  - `entrykit capture` will refuse to write until the body is compressed
