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
    normalize_code_language,
    render_notion_markdown,
    rich_text,
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
        self.assertEqual(
            properties["Schema Version"]["rich_text"][0]["text"]["content"], "knowledge-entry/v2"
        )
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

    def test_render_notion_markdown_skips_sections_already_present_in_body(self) -> None:
        entry = KnowledgeEntry.from_dict(
            {
                "title": "Body already structured",
                "source_tool": "codex",
                "tool_version": "",
                "model": "",
                "thinking_mode": "unknown",
                "project": "entrykit",
                "session_date": "2026-03-08T16:20:00+08:00",
                "session_id": "",
                "reusability_score": 60,
                "summary": "Summary.",
                "decisions": ["Keep the body flexible."],
                "actions": ["Update the projection."],
                "open_questions": ["Should all arrays become properties?"],
                "artifacts": ["repo:make-frederica"],
                "body_markdown": (
                    "# Overview\n\n"
                    "Paragraph text.\n\n"
                    "## Key Decisions\n\n"
                    "- Keep the body flexible.\n\n"
                    "## Next Steps\n\n"
                    "- Update the projection.\n\n"
                    "## Open Questions\n\n"
                    "- Should all arrays become properties?\n\n"
                    "## Artifacts\n\n"
                    "- repo:make-frederica"
                ),
            }
        )
        rendered = render_notion_markdown(entry)
        self.assertEqual(rendered.count("## Decisions"), 0)
        self.assertEqual(rendered.count("## Actions"), 0)
        self.assertEqual(rendered.count("## Open Questions"), 1)
        self.assertEqual(rendered.count("## Artifacts"), 1)
        self.assertEqual(rendered.count("## Key Decisions"), 1)
        self.assertEqual(rendered.count("## Next Steps"), 1)

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

    def test_rich_text_supports_inline_annotations(self) -> None:
        parts = rich_text(
            "Use **bold**, *italic*, `code`, ~~old~~, ==focus==, {red|risk}, and [docs](https://example.com)."
        )
        plain = "".join(part["text"]["content"] for part in parts)
        self.assertIn("Use ", plain)
        self.assertTrue(any(part["annotations"]["bold"] for part in parts))
        self.assertTrue(any(part["annotations"]["italic"] for part in parts))
        self.assertTrue(any(part["annotations"]["code"] for part in parts))
        self.assertTrue(any(part["annotations"]["strikethrough"] for part in parts))
        self.assertTrue(any(part["annotations"]["color"] == "yellow_background" for part in parts))
        self.assertTrue(any(part["annotations"]["color"] == "red" for part in parts))
        self.assertTrue(any(part["text"].get("link", {}).get("url") == "https://example.com" for part in parts))

    def test_markdown_to_blocks_supports_callout_todo_and_divider(self) -> None:
        blocks = markdown_to_blocks(
            "> [!WARNING] Keep the exact env values\n\n- [ ] write docs\n- [x] verify capture\n\n---"
        )
        self.assertEqual(blocks[0]["type"], "callout")
        self.assertEqual(blocks[0]["callout"]["color"], "orange_background")
        self.assertEqual(blocks[1]["type"], "to_do")
        self.assertFalse(blocks[1]["to_do"]["checked"])
        self.assertEqual(blocks[2]["type"], "to_do")
        self.assertTrue(blocks[2]["to_do"]["checked"])
        self.assertEqual(blocks[3]["type"], "divider")

    def test_code_block_normalizes_common_language_aliases(self) -> None:
        blocks = markdown_to_blocks("```yml\nkey: value\n```")
        self.assertEqual(blocks[0]["type"], "code")
        self.assertEqual(blocks[0]["code"]["language"], "yaml")
        self.assertEqual(normalize_code_language("toml"), "plain text")
        mermaid_blocks = markdown_to_blocks("```mermaid\nflowchart TD\nA-->B\n```")
        self.assertEqual(mermaid_blocks[0]["code"]["language"], "mermaid")

    def test_markdown_to_blocks_supports_toggle_blocks(self) -> None:
        blocks = markdown_to_blocks(
            ":::toggle Debug details\n"
            "Keep the short summary above.\n\n"
            "```bash\n"
            "entrykit doctor\n"
            "```\n"
            ":::"
        )
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["type"], "toggle")
        self.assertEqual(blocks[0]["toggle"]["rich_text"][0]["text"]["content"], "Debug details")
        self.assertEqual(blocks[0]["toggle"]["children"][0]["type"], "paragraph")
        self.assertEqual(blocks[0]["toggle"]["children"][1]["type"], "code")

    def test_markdown_to_blocks_supports_markdown_tables(self) -> None:
        blocks = markdown_to_blocks(
            "| Key | Value |\n"
            "| --- | --- |\n"
            "| Model | gpt-5.4 |\n"
            "| Env | production |"
        )
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["type"], "table")
        self.assertTrue(blocks[0]["table"]["has_column_header"])
        self.assertEqual(blocks[0]["table"]["table_width"], 2)
        self.assertEqual(len(blocks[0]["table"]["children"]), 3)
        self.assertEqual(
            blocks[0]["table"]["children"][1]["table_row"]["cells"][0][0]["text"]["content"],
            "Model",
        )

    def test_markdown_to_blocks_supports_nested_list_children(self) -> None:
        blocks = markdown_to_blocks(
            "- Summary\n"
            "  - Detail A\n"
            "  - Detail B\n"
            "    - Deep detail\n"
            "- Next item"
        )
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["type"], "bulleted_list_item")
        first_children = blocks[0]["bulleted_list_item"]["children"]
        self.assertEqual(len(first_children), 2)
        self.assertEqual(first_children[0]["type"], "bulleted_list_item")
        self.assertEqual(first_children[1]["type"], "bulleted_list_item")
        deep_children = first_children[1]["bulleted_list_item"]["children"]
        self.assertEqual(deep_children[0]["type"], "bulleted_list_item")
        self.assertEqual(
            deep_children[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"],
            "Deep detail",
        )

    def test_markdown_to_blocks_supports_list_item_mixed_children(self) -> None:
        blocks = markdown_to_blocks(
            "- Deployment checklist\n"
            "  Keep the command below for the real run.\n\n"
            "  ```bash\n"
            "  entrykit capture --input captured.json\n"
            "  ```\n"
            "  - [x] Verified env"
        )
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["type"], "bulleted_list_item")
        children = blocks[0]["bulleted_list_item"]["children"]
        self.assertEqual(children[0]["type"], "paragraph")
        self.assertEqual(children[1]["type"], "code")
        self.assertEqual(children[2]["type"], "to_do")
        self.assertTrue(children[2]["to_do"]["checked"])

    def test_desired_database_properties(self) -> None:
        properties = desired_database_properties()
        self.assertEqual(properties["Source Tool"]["select"], {})
        self.assertEqual(properties["Tool Version"]["rich_text"], {})
        self.assertEqual(
            properties["Thinking Mode"]["select"]["options"][-1]["name"], "extra-high"
        )
        self.assertEqual(properties["Reusability Score"]["number"]["format"], "number")
        self.assertEqual(properties["Model"]["rich_text"], {})
        self.assertEqual(properties["Schema Version"]["rich_text"], {})
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
