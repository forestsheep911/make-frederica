# KnowledgeEntry V2 Proposal

This document proposes a `KnowledgeEntry v2` shape for `make-frederica`.

The goal is not to finalize the schema immediately. The goal is to create a discussion draft that is good enough to evaluate against three product directions:

- storing captured entries in Notion today
- supporting additional storage backends later
- improving future retrieval, intelligent reading, and question answering

## Status

Draft for discussion.

Not yet approved for implementation.

## Context

The current durable contract in this repository is the `KnowledgeEntry` JSON object. Notion is an important backend, but it should be treated as a projection target rather than the primary data model.

The current v1 shape is intentionally small:

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
- `body_markdown`

This works for basic capture and browsing. It is less complete for higher-quality retrieval and QA, especially when we want to answer questions such as:

- What decision did we make on this topic?
- What was still unresolved?
- Which entries are still current versus superseded?
- Which files, repos, tools, or systems were involved?
- Which entries are likely relevant before vector search even starts?

## Problem Statement

If future retrieval depends too heavily on free-text embeddings alone, several problems are likely:

- low precision for exact entities such as file paths, commands, model names, versions, or IDs
- weak filtering for date, status, project, or note type
- poor handling of stale versus current knowledge
- difficulty extracting the final answer from a note that mixes background, options, and decisions in prose

Pure vector retrieval is not enough. Pure structured storage is also not enough. The likely long-term direction is a hybrid system:

- structured metadata for filtering and ranking
- full text for exact lexical matching
- embeddings for semantic recall
- reranking for final candidate quality

That means the schema should preserve both:

- flexible narrative context
- a small set of high-value structured facts

## Design Goals

The v2 proposal should optimize for these goals:

1. Keep a stable canonical format that is not tied to Notion.
2. Preserve backward compatibility with current v1 captures where practical.
3. Add only fields with clear retrieval or QA value.
4. Separate storage concerns from indexing concerns.
5. Keep authoring burden reasonable so the schema remains usable in normal chat capture flows.
6. Make the migration path explicit enough that implementation can proceed without hidden schema decisions.

## Non-Goals

This proposal does not attempt to:

- define a full knowledge graph model
- define chunk-level indexing format in detail
- require every backend to expose every field as native properties
- force all useful information into rigid fields

## Proposed Direction

Treat `KnowledgeEntry` as the canonical persisted note object.

Then derive two additional views from it:

1. Backend projection
   A storage-specific shape such as Notion properties plus page body.

2. Retrieval projection
   An index-oriented representation for full-text search, semantic chunking, and reranking.

This keeps the core note format stable while allowing different downstream systems to evolve independently.

## Implementation Constraints

The current repository does not start from a blank slate. A workable v2 proposal needs to fit these constraints:

- the current runtime model only accepts the v1 fields
- the current `local_markdown` backend serializes only the v1 frontmatter fields
- the current Notion `Status` property is an operational page status, not a canonical lifecycle field
- the current model has no stable entry identifier beyond optional `session_id`

That means the v2 discussion cannot stop at field desirability. It also needs to define:

- how v1 payloads are normalized
- how v2-only fields survive backends that cannot project them natively yet
- how canonical lifecycle state differs from backend workflow state
- how entries are identified across updates, supersession, and retrieval indexes

## Proposed V2 Shape

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
  "session_id": "session-123",
  "language": "zh-CN",
  "status": "active",
  "tags": ["notion", "rag", "architecture"],
  "topics": ["knowledge-capture", "retrieval", "schema-design"],
  "tech_stack": ["python", "notion-api"],
  "entities": ["Notion", "KnowledgeEntry", "RAG", "entrykit"],
  "artifacts": [
    "repo:make-frederica",
    "file:src/entrykit/models.py",
    "file:src/entrykit/notion.py"
  ],
  "reusability_score": 85,
  "summary": "Discussion about whether the current structured fields are sufficient for future retrieval and QA.",
  "decisions": [
    "Treat KnowledgeEntry as the canonical schema instead of using the Notion database shape as the primary model."
  ],
  "actions": [
    "Draft a v2 schema proposal.",
    "Define a Notion projection and a retrieval projection."
  ],
  "open_questions": [
    "Which fields should be mandatory versus optional?",
    "Should chunk-level metadata be derived from the note body or authored explicitly?"
  ],
  "related_entries": [],
  "body_markdown": "# Overview\n\nMain notes go here."
}
```

## Field Groups

The proposed fields fall into four groups.

### 1. Core identity and provenance

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

These fields answer basic questions such as:

- what this note is
- where it came from
- when it happened
- whether it is still current

### 2. Retrieval-oriented metadata

- `tags`
- `topics`
- `tech_stack`
- `entities`
- `artifacts`
- `reusability_score`

These fields help narrow search space before semantic retrieval and help ranking afterward.

### 3. QA-critical structured facts

- `summary`
- `decisions`
- `actions`
- `open_questions`
- `related_entries`

These fields are meant to capture the parts that users most often want an answer system to quote or synthesize.

### 4. Full narrative context

- `body_markdown`

This remains the main free-text body and should continue to preserve context, nuance, examples, and detailed explanation.

## Proposed Field Definitions

### Existing fields retained from v1

- `entry_id`
  Stable canonical identifier for the note.

  Why it matters:
  Without a stable ID, `related_entries`, supersession, chunk inheritance, deduplication, and update-in-place semantics all remain ambiguous.

- `title`
  Short human-readable note title.

- `source_tool`
  Human-readable capture source such as `codex`, `cursor`, or `claude-code`.

- `tool_version`
  Visible tool version only when explicitly exposed.

- `model`
  Visible model name only when explicitly exposed.

- `thinking_mode`
  Existing semantic label such as `unknown`, `low`, `medium`, `high`, or `extra-high`.

- `project`
  Repository, initiative, or workstream name when relevant.

- `session_date`
  ISO 8601 date or datetime.

- `session_id`
  Visible runtime session identifier when explicitly available.

- `tags`
  Free-form short labels. Keep them, but treat them as weak structure rather than the primary taxonomy.

- `reusability_score`
  Operator-facing signal for how reusable the note is likely to be.

- `summary`
  One or two sentences suitable for list browsing and coarse retrieval.

- `body_markdown`
  Main content body.

### New proposed fields

- `entry_type`
  A normalized note category.

  Candidate values:
  - `decision`
  - `discussion`
  - `howto`
  - `debugging`
  - `meeting`
  - `proposal`
  - `reference`
  - `status_update`

  Why it matters:
  Retrieval quality usually improves when we can distinguish a final decision from a brainstorm or an implementation log.

- `language`
  Dominant language of the note, such as `zh-CN` or `en`.

  Why it matters:
  Useful for multilingual retrieval, ranking, translation policies, and index segmentation.

- `status`
  Lifecycle status of the note.

  Candidate values:
  - `active`
  - `draft`
  - `superseded`
  - `archived`

  Why it matters:
  This is an important guardrail against stale retrieval.

  Important distinction:
  This field should describe the knowledge lifecycle of the note itself. It should not automatically reuse an existing backend workflow field with different semantics.

- `topics`
  A small list of normalized topical labels.

  Why it matters:
  More stable and intentional than free-form tags. Useful for search filters and taxonomy pages.

- `tech_stack`
  A small list of primary technologies, frameworks, or platforms involved in the note.

  Candidate examples:
  - `python`
  - `typescript`
  - `react`
  - `fastapi`
  - `notion-api`
  - `postgres`

  Why it matters:
  Many notes in this repository are software-development notes. A dedicated technology field makes it easier to retrieve notes by stack without overloading `tags`, `topics`, or `entities`.

- `entities`
  A list of explicit named entities involved in the note, such as products, systems, services, APIs, classes, or major concepts.

  Why it matters:
  Improves exact match and targeted retrieval without requiring heavy entity extraction at query time.

- `artifacts`
  References to concrete artifacts mentioned in the note.

  Candidate examples:
  - `repo:make-frederica`
  - `file:src/entrykit/models.py`
  - `cmd:entrykit capture`
  - `url:https://...`
  - `issue:123`

  Why it matters:
  This is one of the most valuable additions for engineering and workflow knowledge.

- `decisions`
  A list of explicit decisions or conclusions reached in the session.

  Why it matters:
  QA systems are often asked for the conclusion, not the full transcript.

- `actions`
  A list of next steps, follow-ups, or implementation actions.

  Why it matters:
  Useful for operational tracking and query patterns such as "what did we say we would do next?"

- `open_questions`
  A list of unresolved issues.

  Why it matters:
  Lets the knowledge base answer "what is still undecided?" rather than pretending every note contains a conclusion.

- `related_entries`
  References to other note IDs or stable keys.

  Why it matters:
  Provides a lightweight bridge toward knowledge graph behavior without requiring full graph modeling now.

## Why These Fields

This proposal intentionally focuses on fields with high expected value for future retrieval and QA.

It does not yet add more granular fields such as:

- `assumptions`
- `constraints`
- `tradeoffs`
- `alternatives_considered`
- `risks`

Those may be valuable later, but they add schema weight quickly. The proposed approach is to keep those in `body_markdown` for now and revisit them only if they repeatedly prove necessary.

This is also why `last_verified_at` is not part of the current recommended v2 set. It may become useful later, but it assumes an ongoing verification workflow. For this project's current note-taking pattern, that would likely add more maintenance burden than retrieval value.

## Versioning and Upgrade Strategy

The main open implementation question is not just "which fields belong in v2". It is also "how does the system upgrade from v1 to v2 without breaking captures or losing data".

Recommended approach:

1. Keep `KnowledgeEntry` as the canonical object name.
2. Introduce v2 as a backward-compatible superset of v1 rather than a separate top-level type name.
3. Normalize all accepted v1 payloads into an internal v2-shaped object before backend projection.
4. Treat missing v2 fields as absent or defaulted, not as validation failures, during the migration window.

This implies an explicit read/write contract:

- v1 input remains accepted
- internal processing moves toward a normalized v2 shape
- backends may project only a subset of fields
- canonical storage must still preserve the full v2 object when available

### Why add `entry_id`

`entry_id` is the one addition that should be treated as foundational rather than optional nice-to-have metadata.

Without it, the system cannot define these behaviors cleanly:

- `related_entries` pointing to another note
- `status = superseded` pointing to the replacement note
- chunk-level inheritance from a stable parent note
- deduplicating repeated captures of the same material
- updating an existing durable note instead of always creating a new one

Suggested shape:

- string
- opaque but stable
- generated by the application when absent
- not derived from user-editable title text alone

The exact format is less important than the guarantee that the ID is stable once assigned.

### v1 to v2 normalization

When a v1 payload is read:

- preserve all existing v1 fields unchanged
- generate `entry_id` if it is missing
- leave all new v2 fields absent unless they can be derived safely
- do not guess `entry_type`, `status`, or `last_verified_at` unless there is an explicit policy for doing so

This keeps the migration conservative and avoids silently inventing structure that looks authoritative later.

## Indexing Implications

The schema should support a retrieval pipeline that combines multiple signals rather than relying on one method.

Recommended retrieval layers:

1. Structured filtering
   Use fields such as `project`, `entry_type`, `status`, `session_date`, `topics`, `tech_stack`, and `language`.

2. Full-text retrieval
   Use `title`, `summary`, `decisions`, `open_questions`, `artifacts`, and `body_markdown`.

3. Semantic retrieval
   Embed note chunks, not only full notes.

4. Reranking
   Reorder candidates using both query relevance and metadata relevance.

### Note-level versus chunk-level indexing

The canonical schema should remain note-oriented.

Chunking should be treated as an index-layer concern, not a primary persistence concern. A future retrieval index may derive chunk-level records with inherited metadata such as:

- parent entry ID
- `project`
- `entry_type`
- `status`
- `session_date`
- `topics`
- `tech_stack`
- `entities`

This avoids polluting the canonical note format with indexing-specific implementation details.

The chunk layer should inherit `entry_id` as the stable parent reference. A retrieval design that mentions parent-child note relationships without a canonical note ID is underspecified.

## Notion Projection Guidance

Notion should not be expected to mirror the canonical schema exactly.

An important implementation detail is that the current Notion database already uses a `Status` property for operational workflow state. That existing property should not be silently redefined as the canonical lifecycle field unless the migration plan explicitly says so.

Recommended Notion properties for filtering and list views:

- `Name`
- `Entry Type`
- `Source Tool`
- `Thinking Mode`
- `Project`
- `Session Date`
- `Language`
- `Lifecycle Status`
- `Tags`
- `Topics`
- `Tech Stack`
- `Entities`
- `Reusability Score`
- `Summary`

Recommended body sections in the Notion page content:

- `Decisions`
- `Actions`
- `Open Questions`
- `Artifacts`
- main narrative body

This keeps Notion useful for browsing without overloading database properties with long or awkward arrays.

### Canonical lifecycle vs backend workflow state

The proposal should distinguish these two concepts explicitly:

- canonical lifecycle status
  Example values: `active`, `draft`, `superseded`, `archived`

- backend workflow status
  Example values in Notion today: `Captured`

Recommended rule:

- `status` in `KnowledgeEntry v2` means canonical lifecycle state
- existing backend workflow properties may continue to exist separately during migration
- if Notion eventually exposes the canonical lifecycle state directly, that should happen through an explicit schema migration rather than by overloading the old field name implicitly

### Field boundary guidance

To keep the schema usable, the retrieval-oriented fields should have distinct roles:

- `topics`
  What the note is about conceptually.
  Examples: `schema-design`, `retrieval`, `debugging-workflow`

- `tech_stack`
  Which technologies or platforms the note primarily involves.
  Examples: `python`, `react`, `notion-api`

- `entities`
  Which specific named systems, products, classes, services, or concepts appear in the note.
  Examples: `KnowledgeEntry`, `Notion`, `entrykit`, `FastAPI`

- `artifacts`
  Which concrete files, commands, URLs, repos, issues, or other durable references are involved.
  Examples: `file:src/entrykit/models.py`, `cmd:entrykit capture`

## Compatibility Strategy

Implementation should remain backward compatible with current v1 inputs as much as possible.

Suggested compatibility rules:

- existing v1 payloads remain valid
- new v2 fields start as optional
- Notion writes may ignore fields that are not yet projected into properties
- local JSON should preserve the full canonical object even when a backend only stores part of it natively
- any backend that cannot project a v2 field natively must either preserve it through a lossless canonical representation or declare the field unsupported for durable storage

This implies three storage truths:

1. Canonical JSON should be the richest representation.
2. Backend projection may be partial.
3. Retrieval indexes may add derived structure not present in the original note.

### Backend compatibility requirement

The migration is not safe if a backend silently drops newly added canonical fields.

In practice this means:

- Notion may project only a subset of v2 fields into database properties if the remainder are preserved in page content or another durable representation
- `local_markdown` should not remain a v1-only serializer if it is expected to serve as durable local storage
- during rollout, every writable backend should be classified as one of:
  - lossless for v2
  - partial but acceptable with documented degradation
  - not yet compatible with v2 canonical storage

## Suggested Rollout

### Phase 1

Add a minimal high-value set of new fields and migration plumbing:

- `entry_id`
- `entry_type`
- `language`
- `status`
- `topics`
- `tech_stack`
- `entities`
- `decisions`
- `open_questions`
- `artifacts`

Required implementation outcomes for Phase 1:

- v1 input still parses
- internal normalization can represent v2
- no writable backend silently loses canonical v2 fields
- `status` semantics are separated from existing backend workflow status

This should already improve retrieval quality materially while keeping authoring overhead manageable.

### Phase 2

Add:

- `actions`
- `related_entries`

These improve workflow continuity.

### Phase 3

Evaluate whether repeated usage justifies more granular structure such as:

- `assumptions`
- `constraints`
- `tradeoffs`
- `alternatives_considered`
- `risks`

## Open Questions

Questions still worth discussing before implementation:

- Which fields should be mandatory, if any, beyond the current v1 required set?
- Should `entry_id` always be generated on write, or only once a note becomes durable?
- Should `entry_type` and `status` be strict enums or soft strings with recommended values?
- Should `topics` be centrally curated or allowed to drift organically at first?
- Should `tech_stack` use a centrally curated vocabulary or a recommended-but-open list?
- Should `entities` be manually authored, LLM-extracted, or both?
- Should `artifacts` use a typed string convention or a structured object format?
- How much of the new schema should be visible as first-class Notion properties?
- When should a note be marked `superseded`, and should that also require a replacement `entry_id` link?
- Should `local_markdown` become a lossless canonical backup format, or remain an intentionally partial projection?

## Recommendation

Adopt the general direction of `KnowledgeEntry v2`, but keep the first implementation deliberately small.

The most important decision is not the exact spelling of every field. The most important decision is to separate:

- the canonical note schema
- backend-specific projections
- retrieval-oriented derived indexes

If that separation holds, the system can support Notion now and evolve toward higher-quality retrieval later without forcing another full schema reset.

Before implementation starts, the proposal should be treated as incomplete unless it answers four migration-critical questions explicitly:

- how `entry_id` is assigned
- how v1 payloads normalize into v2
- how canonical `status` differs from backend workflow status
- how each writable backend avoids silent loss of v2 fields
