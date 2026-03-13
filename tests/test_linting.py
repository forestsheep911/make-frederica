from __future__ import annotations

import unittest

from entrykit.linting import format_lint_result, lint_entry, result_as_json
from entrykit.models import KnowledgeEntry


class LintingTests(unittest.TestCase):
    def test_detects_visible_metadata_mismatch(self) -> None:
        entry = KnowledgeEntry.from_dict(
            {
                "title": "记录状态信息",
                "source_tool": "codex",
                "tool_version": "v0.111.0",
                "model": "Gemini 2.5 Pro",
                "thinking_mode": "high",
                "project": "entrykit",
                "session_date": "2026-03-08T16:20:00+08:00",
                "session_id": "wrong-session",
                "tags": ["metadata"],
                "reusability_score": 70,
                "summary": "中文摘要。",
                "body_markdown": "# 概览\n\n中文正文。",
            }
        )
        conversation = """
/status

OpenAI Codex (v0.111.0)
Model:                gpt-5.4 (reasoning high, summaries auto)
Session:              019cc940-7028-7d23-8424-514cfb703030
"""
        result = lint_entry(entry, conversation=conversation)
        codes = {issue.code for issue in result.issues}
        self.assertIn("model-mismatch", codes)
        self.assertIn("session-id-mismatch", codes)

    def test_detects_language_mismatch(self) -> None:
        entry = KnowledgeEntry.from_dict(
            {
                "title": "English title",
                "source_tool": "gemini-cli",
                "tool_version": "",
                "model": "",
                "thinking_mode": "unknown",
                "project": "entrykit",
                "session_date": "2026-03-08T16:20:00+08:00",
                "session_id": "",
                "tags": ["workflow"],
                "reusability_score": 60,
                "summary": "English summary.",
                "body_markdown": "# Overview\n\nEnglish technical content only.",
            }
        )
        conversation = "这次主要用中文讨论 skill 设计、Notion 落库方式，以及后续怎么做全局安装。"
        result = lint_entry(entry, conversation=conversation)
        codes = {issue.code for issue in result.issues}
        self.assertIn("language-mismatch", codes)
        self.assertIn("body-language-mismatch", codes)

    def test_detects_detail_mismatch(self) -> None:
        entry = KnowledgeEntry.from_dict(
            {
                "title": "详细复盘",
                "source_tool": "gemini-cli",
                "tool_version": "",
                "model": "",
                "thinking_mode": "unknown",
                "project": "entrykit",
                "session_date": "2026-03-08T16:20:00+08:00",
                "session_id": "",
                "tags": ["debugging"],
                "reusability_score": 75,
                "summary": "简要摘要。",
                "body_markdown": "# 概览\n\n很短。",
            }
        )
        conversation = "请你事无巨细地详细归纳出全过程，包含所有失败尝试和排查逻辑。"
        result = lint_entry(entry, conversation=conversation)
        codes = {issue.code for issue in result.issues}
        self.assertIn("detail-mismatch", codes)

    def test_detects_notion_block_limit_exceeded(self) -> None:
        entry = KnowledgeEntry.from_dict(
            {
                "title": "block 超限",
                "source_tool": "codex",
                "tool_version": "",
                "model": "",
                "thinking_mode": "unknown",
                "project": "entrykit",
                "session_date": "2026-03-08T16:20:00+08:00",
                "session_id": "",
                "tags": ["notion"],
                "reusability_score": 50,
                "summary": "测试 block 约束。",
                "body_markdown": "\n\n".join(f"第 {index} 段" for index in range(101)),
            }
        )
        result = lint_entry(entry)
        codes = {issue.code for issue in result.issues}
        self.assertIn("notion-block-limit-exceeded", codes)
        self.assertEqual(result.block_count, 101)

    def test_warns_when_notion_block_limit_is_near(self) -> None:
        entry = KnowledgeEntry.from_dict(
            {
                "title": "block 接近上限",
                "source_tool": "codex",
                "tool_version": "",
                "model": "",
                "thinking_mode": "unknown",
                "project": "entrykit",
                "session_date": "2026-03-08T16:20:00+08:00",
                "session_id": "",
                "tags": ["notion"],
                "reusability_score": 50,
                "summary": "测试 block 预警。",
                "body_markdown": "\n\n".join(f"第 {index} 段" for index in range(90)),
            }
        )
        result = lint_entry(entry)
        codes = {issue.code for issue in result.issues}
        self.assertIn("notion-block-limit-near", codes)
        self.assertIn("Notion block usage: 90/100.", format_lint_result(result))

    def test_lint_json_includes_block_usage(self) -> None:
        entry = KnowledgeEntry.from_dict(
            {
                "title": "block 计数",
                "source_tool": "codex",
                "tool_version": "",
                "model": "",
                "thinking_mode": "unknown",
                "project": "entrykit",
                "session_date": "2026-03-08T16:20:00+08:00",
                "session_id": "",
                "tags": ["notion"],
                "reusability_score": 50,
                "summary": "测试 lint json。",
                "body_markdown": "第一行\n第二行",
            }
        )
        result = lint_entry(entry)
        payload = result_as_json(result)
        self.assertIn('"block_count": 1', payload)
        self.assertIn('"block_limit": 100', payload)

    def test_clean_case_passes(self) -> None:
        entry = KnowledgeEntry.from_dict(
            {
                "title": "统一模型字段",
                "source_tool": "codex",
                "tool_version": "v0.111.0",
                "model": "gpt-5.4",
                "thinking_mode": "high",
                "project": "entrykit",
                "session_date": "2026-03-08T16:20:00+08:00",
                "session_id": "019cc940-7028-7d23-8424-514cfb703030",
                "tags": ["schema", "workflow"],
                "reusability_score": 88,
                "summary": "这次对话完成了 schema 收敛。",
                "body_markdown": "# 概览\n\n这次对话主要是中文，并且正文也保持中文。",
            }
        )
        conversation = """
/status
OpenAI Codex (v0.111.0)
Model:                gpt-5.4 (reasoning high, summaries auto)
Session:              019cc940-7028-7d23-8424-514cfb703030

这次我们主要用中文讨论 schema 的简化和 skill 的约束。
"""
        result = lint_entry(entry, conversation=conversation)
        self.assertTrue(result.ok)
        self.assertEqual(
            format_lint_result(result),
            "Lint passed with no issues.\nNotion block usage: 2/100.",
        )


if __name__ == "__main__":
    unittest.main()
