from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from entrykit.local_markdown import build_output_path, render_markdown_entry, write_markdown_entry
from entrykit.models import KnowledgeEntry


def _sample_entry() -> KnowledgeEntry:
    return KnowledgeEntry(
        title="Capture coding-session architecture decisions",
        source_tool="codex",
        tool_version="",
        model="",
        thinking_mode="unknown",
        project="entrykit",
        session_date="2026-03-08T16:20:00+08:00",
        session_id="",
        tags=["notion", "capture"],
        reusability_score=84,
        summary="Short summary",
        body_markdown="# Overview\n\nBody text.",
    )


class LocalMarkdownTests(unittest.TestCase):
    def test_render_markdown_entry_includes_front_matter_and_body(self) -> None:
        rendered = render_markdown_entry(_sample_entry())

        self.assertIn("---\n", rendered)
        self.assertIn('title: "Capture coding-session architecture decisions"', rendered)
        self.assertIn("tags:\n  - \"notion\"\n  - \"capture\"", rendered)
        self.assertTrue(rendered.endswith("# Overview\n\nBody text.\n"))

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
