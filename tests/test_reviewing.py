from __future__ import annotations

import unittest

from entrykit.linting import lint_entry
from entrykit.models import KnowledgeEntry
from entrykit.reviewing import parse_review_result, render_review_prompt


class ReviewingTests(unittest.TestCase):
    def test_render_review_prompt_includes_capture_and_lint(self) -> None:
        entry = KnowledgeEntry.from_dict(
            {
                "title": "English title",
                "source_tool": "gemini-cli",
                "tool_version": "",
                "model": "Gemini 2.5 Pro",
                "thinking_mode": "unknown",
                "project": "entrykit",
                "session_date": "2026-03-08T16:20:00+08:00",
                "session_id": "",
                "tags": ["workflow"],
                "reusability_score": 60,
                "summary": "English summary.",
                "body_markdown": "# Overview\n\nEnglish content only.",
            }
        )
        conversation = "这次主要用中文讨论 skill 设计。Tier: Gemini Code Assist in Google One AI Pro。"
        lint_result = lint_entry(entry, conversation=conversation)
        prompt = render_review_prompt(entry, conversation=conversation, lint_result=lint_result)

        self.assertIn("Local heuristic lint findings", prompt)
        self.assertIn("model-may-be-inferred", prompt)
        self.assertIn("<capture_json>", prompt)
        self.assertIn('"result": "uncertain"', prompt)

    def test_parse_review_result_pass(self) -> None:
        raw = """
{
  "result": "pass",
  "summary": "The capture is acceptable as-is.",
  "issues": [],
  "suggested_changes": [],
  "revised_entry": null
}
"""
        result = parse_review_result(raw)
        self.assertEqual(result.result, "pass")
        self.assertTrue(result.ok)
        self.assertIsNone(result.revised_entry)

    def test_major_issue_requires_revised_entry(self) -> None:
        raw = """
{
  "result": "major_issue",
  "summary": "The capture guessed the model and used the wrong language.",
  "issues": [
    {
      "severity": "error",
      "code": "language-mismatch",
      "message": "The body should be Chinese."
    }
  ],
  "suggested_changes": [
    "Rewrite the note in Chinese."
  ],
  "revised_entry": null
}
"""
        with self.assertRaisesRegex(ValueError, "major_issue review results must include revised_entry"):
            parse_review_result(raw)

    def test_major_issue_accepts_revised_entry(self) -> None:
        raw = """
{
  "result": "major_issue",
  "summary": "The capture guessed the model and needs rewriting.",
  "issues": [
    {
      "severity": "error",
      "code": "model-mismatch",
      "message": "The model should be empty."
    }
  ],
  "suggested_changes": [
    "Clear the model field."
  ],
  "revised_entry": {
    "title": "中文标题",
    "source_tool": "gemini-cli",
    "tool_version": "",
    "model": "",
    "thinking_mode": "unknown",
    "project": "entrykit",
    "session_date": "2026-03-08T16:20:00+08:00",
    "session_id": "",
    "tags": ["workflow"],
    "reusability_score": 65,
    "summary": "中文摘要。",
    "body_markdown": "# 概览\\n\\n中文正文。"
  }
}
"""
        result = parse_review_result(raw)
        self.assertEqual(result.result, "major_issue")
        self.assertIsNotNone(result.revised_entry)
        self.assertEqual(result.revised_entry.model, None)


if __name__ == "__main__":
    unittest.main()
