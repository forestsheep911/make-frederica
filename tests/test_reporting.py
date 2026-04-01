from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from entrykit.reporting import (
    ReportNote,
    build_report_from_plan,
    build_report_from_query,
    _coerce_llm_plan,
    legacy_schema_cache_path,
    load_schema_snapshot,
    notion_schema_cache_path,
    plan_report_query,
    planner_schema_summary,
    plan_to_dict,
    plan_to_query,
    query_to_dict,
    render_report,
    resolve_report_range,
    resolve_schema_snapshot,
    save_schema_snapshot,
    summarize_database_schema,
)


class ReportingTests(unittest.TestCase):
    def test_resolve_report_range_defaults_to_relative_window(self) -> None:
        start, end = resolve_report_range(
            start_date=None,
            end_date=None,
            relative_days=14,
            today=date(2026, 3, 27),
        )
        self.assertEqual(start.isoformat(), "2026-03-14")
        self.assertEqual(end.isoformat(), "2026-03-27")

    def test_resolve_report_range_accepts_explicit_dates(self) -> None:
        start, end = resolve_report_range(
            start_date="2026-03-20",
            end_date="2026-03-27",
        )
        self.assertEqual(start.isoformat(), "2026-03-20")
        self.assertEqual(end.isoformat(), "2026-03-27")

    def test_resolve_report_range_requires_both_explicit_dates(self) -> None:
        with self.assertRaisesRegex(ValueError, "Use both --start-date and --end-date together"):
            resolve_report_range(start_date="2026-03-20", end_date=None)

    def test_plan_report_query_for_recent_projects_question(self) -> None:
        plan = plan_report_query("最近两周都做了些什么项目？", today=date(2026, 3, 27))
        self.assertEqual(plan.kind, "note-answer")
        self.assertEqual(plan.scope, "all")
        self.assertEqual(plan.target, None)
        self.assertEqual(plan.start_date, "2026-03-14")
        self.assertEqual(plan.end_date, "2026-03-27")
        self.assertEqual(plan.group_by, "project")
        self.assertIn("projects", plan.focus_terms)

    def test_plan_report_query_for_project_question(self) -> None:
        plan = plan_report_query("make-frederica 有什么阻塞和下一步", today=date(2026, 3, 27))
        self.assertEqual(plan.kind, "note-answer")
        self.assertEqual(plan.scope, "project")
        self.assertEqual(plan.target, "make-frederica")
        self.assertEqual(plan.group_by, "none")
        self.assertIn("blockers", plan.focus_terms)
        self.assertIn("actions", plan.focus_terms)
        self.assertIn("next_steps", plan.focus_terms)

        payload = plan_to_dict(plan)
        self.assertEqual(payload["target"], "make-frederica")
        self.assertEqual(payload["kind"], "note-answer")

    def test_plan_to_query_schema(self) -> None:
        plan = plan_report_query("make-frederica 现在进行得如何了", today=date(2026, 3, 27))
        query = plan_to_query(plan)
        self.assertEqual(query.kind, "note-answer")
        self.assertEqual(query.target, "make-frederica")
        self.assertEqual(query.group_by, "none")

        payload = query_to_dict(query)
        self.assertEqual(payload["kind"], "note-answer")
        self.assertEqual(payload["target"], "make-frederica")

    def test_coerce_llm_plan_prefers_relative_window_and_focus_terms(self) -> None:
        plan = _coerce_llm_plan(
            {
                "scope": "project",
                "target": "make-frederica",
                "start_date": None,
                "end_date": None,
                "relative_days": 14,
                "group_by": "none",
                "focus_terms": ["blockers", "next_steps", "projects", "blockers"],
                "include_body": True,
                "limit": 12,
            },
            question="make-frederica 最近两周有什么阻塞和下一步",
            today=date(2026, 3, 27),
            default_limit=50,
        )
        self.assertEqual(plan.target, "make-frederica")
        self.assertEqual(plan.start_date, "2026-03-14")
        self.assertEqual(plan.end_date, "2026-03-27")
        self.assertEqual(plan.focus_terms, ["blockers", "next_steps", "projects"])
        self.assertEqual(plan.limit, 12)

    def test_coerce_llm_plan_requires_project_target(self) -> None:
        with self.assertRaisesRegex(ValueError, "project scope without a target"):
            _coerce_llm_plan(
                {
                    "scope": "project",
                    "target": None,
                    "start_date": None,
                    "end_date": None,
                    "relative_days": 14,
                    "group_by": "none",
                    "focus_terms": ["progress"],
                    "include_body": True,
                    "limit": 20,
                },
                question="某项目最近进展如何",
                today=date(2026, 3, 27),
                default_limit=50,
            )

    def test_build_report_from_plan_groups_projects(self) -> None:
        notes = [
            ReportNote(
                page_id="page-1",
                title="Frederica 升级到 v2 结构并完成本机全局安装",
                project="make-frederica",
                session_date="2026-03-26T09:00:00+08:00",
                summary="完成了 v2 升级、自动 bootstrap 和安装验证。",
                topics=["knowledge-entry-v2"],
                language="zh-CN",
                entry_type="decision",
                body_text="detail",
                url="https://example.com/page-1",
            ),
            ReportNote(
                page_id="page-2",
                title="Kinmail 重生线首轮落地：部署、插件工作流与安全收口",
                project="kinmail",
                session_date="2026-03-24T16:16:00+08:00",
                summary="完成首轮底座搭建。",
                topics=[],
                language="zh-CN",
                entry_type="decision",
                body_text="detail",
                url="https://example.com/page-2",
            ),
        ]
        plan = plan_report_query("最近两周都做了些什么项目？", today=date(2026, 3, 27))
        report = build_report_from_plan(
            plan,
            notes,
            start=date(2026, 3, 14),
            end=date(2026, 3, 27),
        )
        self.assertEqual(report["kind"], "note-answer")
        self.assertEqual(report["group_by"], "project")
        self.assertEqual(report["project_count"], 2)

        rendered = render_report(report)
        self.assertIn("Question: 最近两周都做了些什么项目？", rendered)
        self.assertIn("[make-frederica] 1 entry", rendered)
        self.assertIn("Sources:", rendered)

    def test_build_report_from_query_for_focused_project_question(self) -> None:
        notes = [
            ReportNote(
                page_id="page-1",
                title="收紧 frederica 的本地 Markdown 工作流与交付规则",
                project="make-frederica",
                session_date="2026-03-27T10:00:00+08:00",
                summary="本地持久化优先走 local_markdown，交付规则更明确。",
                topics=["local-markdown"],
                language="zh-CN",
                entry_type="decision",
                body_text="后续计划：继续收紧交付规则。\n阻塞：还没有真正的 LLM 查询层。",
                url="https://example.com/page-1",
            ),
            ReportNote(
                page_id="page-2",
                title="Frederica 升级到 v2 结构并完成本机全局安装",
                project="make-frederica",
                session_date="2026-03-26T09:00:00+08:00",
                summary="完成了 v2 升级、自动 bootstrap 和安装验证。",
                topics=["knowledge-entry-v2"],
                language="zh-CN",
                entry_type="decision",
                body_text="下一步：补 LLM planner。",
                url="https://example.com/page-2",
            ),
        ]
        plan = plan_report_query("make-frederica 有什么阻塞和下一步", today=date(2026, 3, 27))
        query = plan_to_query(plan)
        report = build_report_from_query(
            query,
            notes,
            start=date(2026, 2, 26),
            end=date(2026, 3, 27),
        )
        self.assertEqual(report["kind"], "note-answer")
        self.assertEqual(report["target"], "make-frederica")
        rendered = render_report(report)
        self.assertIn("Target: make-frederica", rendered)
        self.assertIn("Blockers:", rendered)
        self.assertIn("Next Steps:", rendered)
        self.assertIn("Sources:", rendered)

    def test_plan_report_query_rejects_empty_query(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            plan_report_query("")

    def test_summarize_database_schema_extracts_options(self) -> None:
        snapshot = summarize_database_schema(
            {
                "properties": {
                    "Tags": {
                        "type": "multi_select",
                        "multi_select": {"options": [{"name": "workflow"}, {"name": "notion"}]},
                    },
                    "Entry Type": {
                        "type": "select",
                        "select": {"options": [{"name": "decision"}, {"name": "reference"}]},
                    },
                    "Project": {
                        "type": "rich_text",
                        "rich_text": {},
                    },
                }
            }
        )
        self.assertEqual(snapshot["fields"]["Tags"]["type"], "multi_select")
        self.assertEqual(snapshot["fields"]["Entry Type"]["options"], ["decision", "reference"])
        self.assertEqual(snapshot["candidates"]["Tags"], ["workflow", "notion"])

    def test_load_and_save_schema_snapshot_uses_age_and_database_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schema.json"
            save_schema_snapshot(
                cache_path=path,
                database_id="db-1",
                snapshot={"fields": {"Tags": {"type": "multi_select"}}},
                now=100.0,
            )
            loaded = load_schema_snapshot(cache_path=path, database_id="db-1", max_age_seconds=60, now=120.0)
            self.assertEqual(loaded, {"fields": {"Tags": {"type": "multi_select"}}})
            self.assertIsNone(load_schema_snapshot(cache_path=path, database_id="db-2", max_age_seconds=60, now=120.0))
            self.assertIsNone(load_schema_snapshot(cache_path=path, database_id="db-1", max_age_seconds=10, now=120.0))

    def test_resolve_schema_snapshot_prefers_cache_then_refreshes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schema.json"
            cached_snapshot = {"fields": {"Tags": {"type": "multi_select"}}, "candidates": {"Tags": ["workflow"]}}
            save_schema_snapshot(cache_path=path, database_id="db-1", snapshot=cached_snapshot)
            client = Mock()
            loaded = resolve_schema_snapshot(client, "db-1", cache_path=path)
            self.assertEqual(loaded, cached_snapshot)
            client.retrieve_database.assert_not_called()

            client.retrieve_database.return_value = {
                "properties": {
                    "Topics": {
                        "type": "multi_select",
                        "multi_select": {"options": [{"name": "retrieval"}]},
                    }
                }
            }
            refreshed = resolve_schema_snapshot(client, "db-1", cache_path=path, force_refresh=True)
            self.assertEqual(refreshed["candidates"]["Topics"], ["retrieval"])
            client.retrieve_database.assert_called_once_with("db-1")

    def test_notion_schema_cache_path_uses_new_name(self) -> None:
        self.assertEqual(notion_schema_cache_path().name, "notion-schema.json")
        self.assertEqual(legacy_schema_cache_path().name, "notion-report-schema.json")

    def test_planner_schema_summary_is_compact(self) -> None:
        summary = planner_schema_summary(
            {
                "fields": {
                    "Tags": {
                        "type": "multi_select",
                        "options": ["workflow", "notion", "python"],
                    },
                    "Project": {
                        "type": "rich_text",
                    },
                }
            }
        )
        assert summary is not None
        self.assertEqual(
            summary,
            {
                "fields": [
                    {"name": "Project", "type": "rich_text"},
                    {
                        "name": "Tags",
                        "type": "multi_select",
                        "sample_options": ["workflow", "notion", "python"],
                        "option_count": 3,
                    },
                ]
            },
        )


if __name__ == "__main__":
    unittest.main()
