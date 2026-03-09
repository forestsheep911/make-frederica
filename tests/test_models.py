from __future__ import annotations

import unittest

from entrykit.models import KnowledgeEntry


class KnowledgeEntryTests(unittest.TestCase):
    def test_valid_payload(self) -> None:
        entry = KnowledgeEntry.from_dict(
            {
                "title": "Codex summary workflow",
                "source_tool": "codex",
                "tool_version": "v0.111.0",
                "model": "gpt-5.4",
                "thinking_mode": "high",
                "project": "entrykit",
                "session_date": "2026-03-08T16:20:00+08:00",
                "session_id": "chatcmpl-demo",
                "tags": ["workflow", "capture"],
                "reusability_score": 82,
                "summary": "Use a stable JSON schema before writing to Notion.",
                "body_markdown": "# Overview\n\nThis worked well.",
            }
        )
        self.assertEqual(entry.reusability_score, 82)
        self.assertEqual(entry.thinking_mode, "high")
        self.assertEqual(entry.tool_version, "v0.111.0")
        self.assertEqual(entry.model, "gpt-5.4")
        self.assertEqual(entry.session_id, "chatcmpl-demo")

    def test_invalid_score_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 0 and 100"):
            KnowledgeEntry.from_dict(
                {
                    "title": "Bad score",
                    "source_tool": "codex",
                    "thinking_mode": "unknown",
                    "session_date": "2026-03-08T16:20:00+08:00",
                    "reusability_score": 101,
                    "summary": "bad",
                    "body_markdown": "body",
                }
            )

    def test_invalid_thinking_mode_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "thinking_mode must be one of"):
            KnowledgeEntry.from_dict(
                {
                    "title": "Bad mode",
                    "source_tool": "codex",
                    "thinking_mode": "ultra",
                    "session_date": "2026-03-08T16:20:00+08:00",
                    "reusability_score": 10,
                    "summary": "bad",
                    "body_markdown": "body",
                }
            )

    def test_invalid_session_date_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "ISO 8601"):
            KnowledgeEntry.from_dict(
                {
                    "title": "Bad date",
                    "source_tool": "codex",
                    "thinking_mode": "unknown",
                    "session_date": "03/08/2026 16:20",
                    "reusability_score": 10,
                    "summary": "bad",
                    "body_markdown": "body",
                }
            )


if __name__ == "__main__":
    unittest.main()
