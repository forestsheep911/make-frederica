from __future__ import annotations

import unittest

from entrykit.models import KnowledgeEntry
from entrykit.notion import (
    BLOCK_WARNING_THRESHOLD,
    MAX_NOTION_BLOCKS,
    MODEL_ALIASES,
    build_properties,
    build_schema_patch,
    count_markdown_blocks,
    cleanup_legacy_model_properties,
    desired_database_properties,
    markdown_to_blocks,
    render_notion_markdown,
    validate_block_limit,
)


class NotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entry = KnowledgeEntry.from_dict(
            {
                "entry_id": "ke-20260308-12345678",
                "title": "Adaptive body structures",
                "entry_type": "decision",
                "source_tool": "claude-code",
                "tool_version": "1.2.3",
                "model": "Claude Sonnet 4",
                "thinking_mode": "extra-high",
                "project": "entrykit",
                "session_date": "2026-03-08T16:20:00+08:00",
                "session_id": "session-123",
                "language": "en",
                "status": "active",
                "tags": ["notes"],
                "topics": ["schema-design"],
                "tech_stack": ["python"],
                "entities": ["KnowledgeEntry"],
                "artifacts": ["repo:make-frederica"],
                "reusability_score": 67,
                "summary": "Let the AI pick the body structure.",
                "decisions": ["Keep the body flexible."],
                "actions": ["Update the projection."],
                "open_questions": ["Should all arrays become properties?"],
                "related_entries": ["ke-20260307-deadbeef"],
                "body_markdown": (
                    "# Overview\n\n"
                    "Paragraph text.\n\n"
                    "- bullet one\n"
                    "1. ordered item\n\n"
                    "```json\n{}\n```"
                ),
            }
        )

    def test_build_properties(self) -> None:
        properties = build_properties(self.entry, "Captured")
        self.assertEqual(properties["Thinking Mode"]["select"]["name"], "extra-high")
        self.assertEqual(properties["Reusability Score"]["number"], 67)
        self.assertEqual(
            properties["Tool Version"]["rich_text"][0]["text"]["content"], "1.2.3"
        )
        self.assertEqual(
            properties["Session Date"]["date"]["start"], "2026-03-08T16:20:00+08:00"
        )
        self.assertEqual(
            properties["Model"]["rich_text"][0]["text"]["content"],
            "Claude Sonnet 4",
        )
        self.assertEqual(properties["Session ID"]["rich_text"][0]["text"]["content"], "session-123")
        self.assertEqual(properties["Entry Type"]["select"]["name"], "decision")
        self.assertEqual(properties["Language"]["select"]["name"], "en")
        self.assertEqual(properties["Lifecycle Status"]["select"]["name"], "active")
        self.assertEqual(properties["Topics"]["multi_select"][0]["name"], "schema-design")
        self.assertEqual(properties["Tech Stack"]["multi_select"][0]["name"], "python")

    def test_render_notion_markdown_appends_structured_sections(self) -> None:
        rendered = render_notion_markdown(self.entry)
        self.assertIn("## Decisions", rendered)
        self.assertIn("- Keep the body flexible.", rendered)
        self.assertIn("## Actions", rendered)
        self.assertIn("## Open Questions", rendered)
        self.assertIn("## Artifacts", rendered)

    def test_markdown_to_blocks(self) -> None:
        blocks = markdown_to_blocks(self.entry.body_markdown)
        self.assertEqual(blocks[0]["type"], "heading_1")
        self.assertEqual(blocks[1]["type"], "paragraph")
        self.assertEqual(blocks[2]["type"], "bulleted_list_item")
        self.assertEqual(blocks[3]["type"], "numbered_list_item")
        self.assertEqual(blocks[4]["type"], "code")

    def test_paragraph_keeps_in_block_newlines(self) -> None:
        blocks = markdown_to_blocks("第一行\n第二行\n第三行")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["type"], "paragraph")
        self.assertEqual(
            blocks[0]["paragraph"]["rich_text"][0]["text"]["content"],
            "第一行\n第二行\n第三行",
        )

    def test_validate_block_limit_rejects_large_body(self) -> None:
        markdown = "\n\n".join(f"第 {index} 段" for index in range(MAX_NOTION_BLOCKS + 1))
        with self.assertRaisesRegex(ValueError, "exceeds the limit"):
            validate_block_limit(markdown)

    def test_count_markdown_blocks_matches_warning_threshold_shape(self) -> None:
        markdown = "\n\n".join(f"段落 {index}" for index in range(BLOCK_WARNING_THRESHOLD))
        self.assertEqual(count_markdown_blocks(markdown), BLOCK_WARNING_THRESHOLD)

    def test_desired_database_properties(self) -> None:
        properties = desired_database_properties()
        self.assertEqual(properties["Source Tool"]["select"], {})
        self.assertEqual(properties["Tool Version"]["rich_text"], {})
        self.assertEqual(
            properties["Thinking Mode"]["select"]["options"][-1]["name"], "extra-high"
        )
        self.assertEqual(properties["Reusability Score"]["number"]["format"], "number")
        self.assertEqual(properties["Model"]["rich_text"], {})
        self.assertEqual(properties["Session ID"]["rich_text"], {})
        self.assertIn("Entry Type", properties)
        self.assertIn("Language", properties)
        self.assertIn("Lifecycle Status", properties)
        self.assertIn("Topics", properties)
        self.assertIn("Tech Stack", properties)
        patch = build_schema_patch({"Name": {"type": "title"}, "Model Version": {"type": "rich_text"}})
        self.assertEqual(patch["Model Version"]["name"], "Model")
        cleanup = cleanup_legacy_model_properties(
            {"Name": {"type": "title"}, "Model": {"type": "rich_text"}, "Model 1": {"type": "rich_text"}}
        )
        self.assertEqual(cleanup["Model 1"], None)
        self.assertIn("Model 1", MODEL_ALIASES)


if __name__ == "__main__":
    unittest.main()
