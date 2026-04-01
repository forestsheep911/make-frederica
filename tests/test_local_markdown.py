from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from entrykit.local_markdown import build_output_path, render_markdown_entry, write_markdown_entry
from entrykit.models import KnowledgeEntry


def _sample_entry() -> KnowledgeEntry:
    return KnowledgeEntry(
        schema_version="knowledge-entry/v2",
        entry_id="ke-20260308-12345678",
        title="Capture coding-session architecture decisions",
        entry_type="decision",
        source_tool="codex",
        tool_version="",
        model="",
        thinking_mode="unknown",
        project="entrykit",
        session_date="2026-03-08T16:20:00+08:00",
        session_id="",
        language="en",
        status="active",
        tags=["notion", "capture"],
        topics=["schema-design"],
        tech_stack=["python"],
        entities=["KnowledgeEntry"],
        artifacts=["repo:make-frederica"],
        reusability_score=84,
        summary="Short summary",
        decisions=["Keep a canonical v2 shape."],
        actions=["Add regression tests."],
        open_questions=[],
        related_entries=["ke-20260307-deadbeef"],
        body_markdown="# Overview\n\nBody text.",
    )


class LocalMarkdownTests(unittest.TestCase):
    def test_render_markdown_entry_includes_front_matter_and_body(self) -> None:
        rendered = render_markdown_entry(_sample_entry())

        self.assertIn("---\n", rendered)
        self.assertIn('schema_version: "knowledge-entry/v2"', rendered)
        self.assertIn('entry_id: "ke-20260308-12345678"', rendered)
        self.assertIn('title: "Capture coding-session architecture decisions"', rendered)
        self.assertIn("tags:\n  - \"notion\"\n  - \"capture\"", rendered)
        self.assertIn("topics:\n  - \"schema-design\"", rendered)
        self.assertIn("tech_stack:\n  - \"python\"", rendered)
        self.assertIn("decisions:\n  - \"Keep a canonical v2 shape.\"", rendered)
        self.assertIn("> Short summary\n\n# Overview\n\nBody text.", rendered)
        self.assertNotIn("open_questions: []", rendered)

    def test_render_markdown_entry_omits_empty_optional_fields(self) -> None:
        entry = KnowledgeEntry(
            schema_version="knowledge-entry/v2",
            entry_id="ke-20260308-00000000",
            title="Minimal note",
            entry_type=None,
            source_tool="codex",
            tool_version=None,
            model=None,
            thinking_mode="unknown",
            project=None,
            session_date="2026-03-08",
            session_id=None,
            language=None,
            status=None,
            tags=[],
            topics=[],
            tech_stack=[],
            entities=[],
            artifacts=[],
            reusability_score=50,
            summary="Short summary",
            decisions=[],
            actions=[],
            open_questions=[],
            related_entries=[],
            body_markdown="Body text.",
        )

        rendered = render_markdown_entry(entry)

        self.assertIn('schema_version: "knowledge-entry/v2"', rendered)
        self.assertIn('source_tool: "codex"', rendered)
        self.assertIn('session_date: "2026-03-08"', rendered)
        self.assertIn('summary: "Short summary"', rendered)
        self.assertNotIn('entry_type: ""', rendered)
        self.assertNotIn('tool_version: ""', rendered)
        self.assertNotIn("tags: []", rendered)
        self.assertNotIn("decisions: []", rendered)
        self.assertIn("> Short summary\n\nBody text.", rendered)

    def test_build_output_path_appends_numeric_suffix_for_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "2026-03-08-capture-coding-session-architecture-decisions.md").write_text(
                "existing",
                encoding="utf-8",
            )

            path = build_output_path(_sample_entry(), output_dir)

        self.assertEqual(path.name, "2026-03-08-capture-coding-session-architecture-decisions-2.md")

    def test_write_markdown_entry_creates_utf8_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_markdown_entry(_sample_entry(), Path(tmpdir))

            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8").splitlines()[0], "---")


if __name__ == "__main__":
    unittest.main()
