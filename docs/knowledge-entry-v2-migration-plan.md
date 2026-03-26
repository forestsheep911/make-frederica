# KnowledgeEntry V2 Migration Plan

This document turns the `KnowledgeEntry v2` proposal into an implementation sequence for `make-frederica`.

The goal is to upgrade the canonical note structure without breaking existing v1 capture flows or silently losing data in writable backends.

## Scope

This plan covers:

- canonical model upgrade from v1 to a v2 superset
- v1 input compatibility
- local durable storage compatibility
- prompt and schema updates for new captures
- phased backend projection updates

This plan does not attempt to redesign Notion workflow status or complete all backend migrations in one step.

## Target V2 Fields

The current recommended v2 set is:

- `entry_id`
- `title`
- `entry_type`
- `source_tool`
- `tool_version`
- `model`
- `thinking_mode`
- `project`
- `session_date`
- `session_id`
- `language`
- `status`
- `tags`
- `topics`
- `tech_stack`
- `entities`
- `artifacts`
- `reusability_score`
- `summary`
- `decisions`
- `actions`
- `open_questions`
- `related_entries`
- `body_markdown`

## Migration Principles

1. Keep `KnowledgeEntry` as the canonical object name.
2. Make v2 a backward-compatible superset of v1.
3. Continue accepting v1 payloads as input.
4. Normalize all accepted payloads into an internal v2-shaped object.
5. Prefer safe defaults over guessed structured metadata.
6. Do not silently lose canonical v2 fields in writable backends.

## Normalization Rules

When reading a payload:

- preserve all existing v1 fields
- accept missing v2 fields
- generate `entry_id` when absent
- default list-like v2 fields to empty lists
- default optional scalar v2 fields to empty string or `None` equivalents
- do not infer `entry_type`, `status`, or `language` unless there is an explicit policy

Recommended defaults:

- `entry_type = ""`
- `language = ""`
- `status = ""`
- `topics = []`
- `tech_stack = []`
- `entities = []`
- `artifacts = []`
- `decisions = []`
- `actions = []`
- `open_questions = []`
- `related_entries = []`

## `entry_id` Strategy

`entry_id` should exist in the canonical object even when an incoming v1 payload lacks it.

Implementation rule:

- if `entry_id` is present, preserve it
- if it is absent, generate a deterministic fallback ID from stable content fields
- once persisted, the stored `entry_id` becomes the durable identifier

This keeps migration conservative while avoiding random ID churn for unchanged legacy payloads.

## Rollout Phases

### Phase 1: Canonical Model and Local Durability

Files:

- `src/entrykit/models.py`
- `src/entrykit/local_markdown.py`

Goals:

- expand `KnowledgeEntry` to the v2 superset
- keep `KnowledgeEntry.from_dict()` compatible with v1 input
- make `to_dict()` emit full v2
- make `local_markdown` preserve the full canonical object in frontmatter

Exit criteria:

- v1 JSON still parses
- v2 JSON parses
- local markdown output contains all canonical v2 fields

### Phase 2: Capture Prompt and Schema

Files:

- `src/entrykit/prompts.py`
- `skills/frederica/references/schema.md`
- `skills/frederica/examples/coding-session.json`
- `skills/frederica/SKILL.md`

Goals:

- teach capture flows to emit the v2 shape
- keep new fields optional and concise
- preserve current body-writing rules

Exit criteria:

- generated schema examples include the new fields
- skill guidance stays aligned with the canonical model

### Phase 3: Projection and Validation Follow-Up

Files:

- `src/entrykit/notion.py`
- `src/entrykit/linting.py`
- `src/entrykit/reviewing.py`

Goals:

- decide which v2 fields should become first-class Notion properties
- keep backend workflow status separate from canonical lifecycle status
- add lightweight validation around new fields where useful

Exit criteria:

- Notion projection is explicit about which fields it stores directly
- lint and review understand the v2 shape well enough to avoid drift

## Notion Guidance During Migration

The current Notion backend can remain partially projected during early rollout.

Recommended short-term rule:

- keep current Notion writes working
- do not block v2 rollout on a full Notion schema redesign
- only promote a small number of high-value v2 fields into properties first
- keep larger structured arrays in the body until a projection strategy is finalized

Candidate early Notion properties:

- `Entry Type`
- `Language`
- `Lifecycle Status`
- `Topics`
- `Tech Stack`

Candidate body sections:

- `Decisions`
- `Open Questions`
- `Artifacts`
- `Actions`

## Verification Checklist

Before calling the migration usable, verify:

- a v1 payload without `entry_id` is accepted and normalized
- a v2 payload round-trips through `to_dict()`
- `local_markdown` output preserves the new fields
- prompt/schema/example files match the canonical model
- existing Notion writes still function with the expanded model

## Recommended Immediate Next Step

Implement Phase 1 and Phase 2 first.

That gets the canonical shape upgraded and prevents local data loss. Notion projection can then be upgraded deliberately instead of being mixed into the same change set.
