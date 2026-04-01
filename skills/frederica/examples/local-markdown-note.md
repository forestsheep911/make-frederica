---
schema_version: "knowledge-entry/v2"
entry_id: "ke-20260308-6ac2d8be"
title: "Stabilize AI chat capture schema for local notes"

entry_type: "decision"
source_tool: "codex"
model: "gpt-5.4"
thinking_mode: "high"

project: "make-frederica"
session_date: "2026-03-08T16:20:00+08:00"
language: "en"
status: "active"

reusability_score: 88
tags:
  - "knowledge-capture"
  - "local-markdown"
  - "schema"
topics:
  - "knowledge-capture"
  - "schema-design"
tech_stack:
  - "python"
entities:
  - "KnowledgeEntry"
  - "entrykit"
artifacts:
  - "repo:make-frederica"
  - "cmd:entrykit capture"
summary: "Store structured metadata in front matter and keep the readable note body in the same Markdown file."
decisions:
  - "Local Markdown notes should be delivered as a single file with metadata plus body."
  - "User-facing local note output should not default to a separate JSON payload."
---

> Store structured metadata in front matter and keep the readable note body in the same Markdown file.

# Overview

This session clarified what a local frederica note should look like when the user asks for a Markdown file rather than a backend-specific capture payload.

## Decisions

- Keep the final deliverable as one Markdown file.
- Use YAML front matter for the structured metadata.
- Keep the readable narrative note in the same file instead of splitting metadata into a separate JSON artifact.

## Why this works

The result is easier to read, archive, migrate, and reuse later. It also matches what users usually expect when they ask for a local Markdown note.

## Reusable lessons

- Capture payloads and user-facing note files are not the same thing.
- Local note output should optimize for a complete one-file artifact, not only for backend ingestion.
