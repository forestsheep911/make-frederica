from __future__ import annotations

import unittest

from entrykit.prompts import render_capture_prompt


class PromptTests(unittest.TestCase):
    def test_render_prompt_includes_source_tool(self) -> None:
        prompt = render_capture_prompt("cursor")
        self.assertIn("`source_tool` must be `cursor`.", prompt)
        self.assertIn('"source_tool": "cursor"', prompt)
        self.assertIn('"tool_version": ""', prompt)
        self.assertIn('"model": ""', prompt)
        self.assertIn('"session_id": ""', prompt)
        self.assertIn("2026-03-08T16:20:00+08:00", prompt)

    def test_render_prompt_with_example(self) -> None:
        prompt = render_capture_prompt("gemini-cli", include_example=True)
        self.assertIn("Example JSON:", prompt)
        self.assertIn('"title": "Capture coding-session architecture decisions"', prompt)


if __name__ == "__main__":
    unittest.main()
