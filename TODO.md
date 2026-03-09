# TODO

Open questions and future design work for `make-frederica`.

This file is for unresolved product and workflow questions. It is not a commitment to current behavior.

## Storage backends

- Support outputs beyond Notion.
  - Candidate targets:
    - local folder output
    - Obsidian vault output
    - other note systems
- Decide what the durable intermediate contract should be.
  - Keep `KnowledgeEntry` as the internal canonical format.
  - Add backend adapters for:
    - Notion page write
    - markdown file export
    - Obsidian-compatible file export
- Decide which backend is the default.
  - Current default is effectively Notion because `entrykit` is Notion-oriented.
  - Future versions may need backend selection at runtime.
- Decide whether skill behavior should mention backend choices directly or defer that to the supporting tool.

## Environment and setup

- Decide how first-time users provide credentials or configuration.
  - Options to evaluate:
    - guide the user to edit a local `.env` file
    - guide the user to run an installer that writes a config file
    - guide the user to set shell environment variables
    - avoid API-backed storage by default and use local-file output first
- Avoid asking users to paste API keys into chat unless there is no better path.
  - Prefer local file edits, terminal commands, or installer-driven setup.
- Decide which layer owns setup guidance.
  - The skill itself
  - the supporting CLI
  - external install docs
- Document the minimum viable setup path for:
  - local dev
  - end users
  - users who do not want any external API dependency

## Interaction model

- Decide what should happen when a user says: `Use frederica to summarize this conversation.`
- Clarify which values should be inferred, defaulted, or explicitly confirmed.
  - Candidate parameters:
    - detail level
    - output destination
    - output format
    - whether to save automatically or just draft in chat
    - whether to run review/lint before saving
- Decide the default interaction policy.
  - Option A: ask the user every time
  - Option B: use defaults unless the user specifies otherwise
  - Option C: infer from tone/context when safe, ask only when ambiguity affects output
- Likely direction:
  - use strong defaults
  - ask only for decisions that materially affect destination or fidelity
- Define which cases require confirmation.
  - Writing to an external system
  - choosing a storage backend
  - switching language
  - changing scope from whole session to partial session
  - using unusually high detail

## Output modes

- Define the supported output modes clearly.
  - chat-only draft
  - structured JSON only
  - local file output
  - Notion write
  - future Obsidian export
- Decide how users select an output mode.
  - explicit prompt instruction
  - remembered preference
  - tool configuration
  - interactive follow-up question
- Decide whether there should be one universal default mode.

## Future conversation design work

- Map all places where user interaction may be needed.
  - first-time setup
  - backend selection
  - save confirmation
  - overwrite behavior
  - scope narrowing
  - detail-level override
  - language override
  - review pass approval
- Separate:
  - questions that block execution
  - questions that can be handled with defaults
  - questions that should only appear in advanced flows
- Design a lightweight preference model so frequent users are not asked the same questions repeatedly.
