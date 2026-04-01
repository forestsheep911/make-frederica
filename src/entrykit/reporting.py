from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from urllib import error, request

from entrykit.config import frederica_home
from entrykit.notion import NotionClient, rich_text_plain_text


@dataclass(frozen=True)
class ReportNote:
    page_id: str
    title: str
    project: str
    session_date: str
    summary: str
    topics: list[str]
    language: str | None
    entry_type: str | None
    body_text: str
    url: str


@dataclass(frozen=True)
class ReportPlan:
    kind: str
    question: str
    source: str
    scope: str
    target: str | None
    start_date: str
    end_date: str
    relative_days: int | None
    group_by: str
    focus_terms: list[str]
    include_body: bool
    limit: int


@dataclass(frozen=True)
class ReportQuery:
    kind: str
    question: str
    source: str
    scope: str
    target: str | None
    start_date: str
    end_date: str
    group_by: str
    focus_terms: list[str]
    include_body: bool
    limit: int


STATUS_KEYWORDS = ("如何了", "怎么样了", "状态", "进展如何", "进行得如何", "最近如何", "status", "health")
RISK_KEYWORDS = ("风险", "问题", "未决", "open question", "risk", "issue")
NEXT_STEP_KEYWORDS = ("下一步", "后续", "待办", "行动", "next step", "next steps", "follow-up", "todo")
DECISION_KEYWORDS = ("决定", "决策", "结论", "判断", "decision", "decisions")
BLOCKER_KEYWORDS = ("阻塞", "卡住", "卡点", "拦住", "blocked", "blocker")
ACTION_KEYWORDS = ("行动", "动作", "待办", "后续", "下一步", "action", "actions", "todo")
PROJECT_LIST_KEYWORDS = ("项目", "projects", "project", "按项目", "什么项目", "哪些项目")
SCHEMA_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
PLANNER_FOCUS_ENUM = ["status", "progress", "risks", "blockers", "decisions", "actions", "next_steps", "projects"]
DEFAULT_LLM_PLANNER_MODEL = "gpt-4o-mini"


def resolve_report_range(
    *,
    start_date: str | None,
    end_date: str | None,
    relative_days: int | None = None,
    today: date | None = None,
) -> tuple[date, date]:
    if bool(start_date) != bool(end_date):
        raise ValueError("Use both --start-date and --end-date together.")

    if start_date and end_date:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    else:
        anchor = today or date.today()
        days = relative_days if relative_days is not None else 30
        if days <= 0:
            raise ValueError("relative_days must be greater than 0.")
        end = anchor
        start = anchor - timedelta(days=days - 1)

    if start > end:
        raise ValueError("--start-date must be on or before --end-date.")
    return start, end


def plan_report_query(
    query: str,
    *,
    today: date | None = None,
    default_limit: int = 50,
    schema_snapshot: dict[str, Any] | None = None,
) -> ReportPlan:
    raw = query.strip()
    if not raw:
        raise ValueError("Report query must not be empty.")

    anchor = today or date.today()
    project = _extract_project_filter(raw, schema_snapshot=schema_snapshot)
    scope = "project" if project else "all"
    group_by = "project" if _should_group_by_project(raw, project=project) else "none"
    focus_terms = _infer_focus_terms(raw)
    start, end, relative_days = _infer_date_window(raw, today=anchor, project=project)

    return ReportPlan(
        kind="note-answer",
        question=raw,
        source="notion",
        scope=scope,
        target=project,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        relative_days=relative_days,
        group_by=group_by,
        focus_terms=focus_terms,
        include_body=True,
        limit=default_limit,
    )


def llm_planner_available(*, api_key: str | None = None) -> bool:
    key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
    return bool(key)


def llm_planner_model() -> str:
    return os.getenv("ENTRYKIT_PLANNER_MODEL", "").strip() or DEFAULT_LLM_PLANNER_MODEL


def plan_report_query_with_llm(
    query: str,
    *,
    today: date | None = None,
    default_limit: int = 50,
    schema_snapshot: dict[str, Any] | None = None,
    planner_schema: dict[str, Any] | None = None,
    api_key: str | None = None,
    model: str | None = None,
    timeout_seconds: float = 20.0,
) -> ReportPlan:
    raw = query.strip()
    if not raw:
        raise ValueError("Report query must not be empty.")
    key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENAI_API_KEY is required for llm planner mode.")

    anchor = today or date.today()
    planner_view = planner_schema if planner_schema is not None else planner_schema_summary(schema_snapshot)
    response_payload = _openai_chat_completion(
        api_key=key,
        model=model or llm_planner_model(),
        question=raw,
        today=anchor,
        default_limit=default_limit,
        planner_schema=planner_view,
        timeout_seconds=timeout_seconds,
    )
    return _coerce_llm_plan(
        response_payload,
        question=raw,
        today=anchor,
        default_limit=default_limit,
    )


def _infer_date_window(query: str, *, today: date, project: str | None) -> tuple[date, date, int | None]:
    lowered = query.lower()
    if any(token in query for token in ("本周",)) or "this week" in lowered:
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end, None
    if any(token in query for token in ("最近7天", "最近 7 天", "过去7天", "过去 7 天")) or "last 7 days" in lowered:
        return resolve_report_range(start_date=None, end_date=None, relative_days=7, today=today) + (7,)
    if any(token in query for token in ("最近两周", "最近 2 周", "过去两周", "过去 2 周", "最近14天", "最近 14 天", "过去14天", "过去 14 天")) or "last 14 days" in lowered or "two weeks" in lowered:
        return resolve_report_range(start_date=None, end_date=None, relative_days=14, today=today) + (14,)
    if any(token in query for token in ("最近",)) or "recent" in lowered:
        return resolve_report_range(start_date=None, end_date=None, relative_days=30, today=today) + (30,)
    fallback_days = 30 if project else 14
    return resolve_report_range(start_date=None, end_date=None, relative_days=fallback_days, today=today) + (fallback_days,)


def _should_group_by_project(query: str, *, project: str | None) -> bool:
    if project:
        return False
    lowered = query.lower()
    return any(token in query for token in PROJECT_LIST_KEYWORDS) or any(token in lowered for token in PROJECT_LIST_KEYWORDS)


def _coerce_llm_plan(
    payload: dict[str, Any],
    *,
    question: str,
    today: date,
    default_limit: int,
) -> ReportPlan:
    scope = str(payload.get("scope", "all")).strip() or "all"
    if scope not in {"all", "project"}:
        scope = "project" if payload.get("target") else "all"
    target_raw = payload.get("target")
    target = str(target_raw).strip() if isinstance(target_raw, str) and str(target_raw).strip() else None
    if scope == "project" and not target:
        raise ValueError("LLM planner returned project scope without a target.")
    if scope == "all":
        target = None

    relative_days = payload.get("relative_days")
    relative_days_value = int(relative_days) if isinstance(relative_days, int) and relative_days > 0 else None
    start_raw = payload.get("start_date")
    end_raw = payload.get("end_date")
    start_date = str(start_raw).strip() if isinstance(start_raw, str) and str(start_raw).strip() else None
    end_date = str(end_raw).strip() if isinstance(end_raw, str) and str(end_raw).strip() else None
    start, end = resolve_report_range(
        start_date=start_date,
        end_date=end_date,
        relative_days=relative_days_value,
        today=today,
    )

    group_by = str(payload.get("group_by", "none")).strip() or "none"
    if group_by not in {"none", "project"}:
        group_by = "project" if scope == "all" and "projects" in payload.get("focus_terms", []) else "none"

    raw_focus_terms = payload.get("focus_terms", [])
    focus_terms: list[str] = []
    if isinstance(raw_focus_terms, list):
        for value in raw_focus_terms:
            token = str(value).strip()
            if token in PLANNER_FOCUS_ENUM and token not in focus_terms:
                focus_terms.append(token)
    if not focus_terms:
        focus_terms = ["progress"]

    include_body = bool(payload.get("include_body", True))
    limit_raw = payload.get("limit", default_limit)
    limit = int(limit_raw) if isinstance(limit_raw, int) and 1 <= limit_raw <= 100 else default_limit

    return ReportPlan(
        kind="note-answer",
        question=question,
        source="notion",
        scope=scope,
        target=target,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        relative_days=relative_days_value,
        group_by=group_by,
        focus_terms=focus_terms,
        include_body=include_body,
        limit=limit,
    )


def _openai_chat_completion(
    *,
    api_key: str,
    model: str,
    question: str,
    today: date,
    default_limit: int,
    planner_schema: dict[str, Any] | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    schema_text = json.dumps(planner_schema, ensure_ascii=False, indent=2) if planner_schema is not None else "null"
    system_prompt = (
        "You are a query planner for a Notion-backed note reader.\n"
        "Return JSON only.\n"
        "Map the user's question into a structured query plan.\n"
        f"Today is {today.isoformat()}.\n"
        f"Default limit is {default_limit}.\n"
        "Prefer preserving the user's time range and scope.\n"
        "Use scope=project only when the question clearly targets one project.\n"
        "Use group_by=project when the user asks what projects were worked on.\n"
        "Use relative_days for rolling windows when possible.\n"
        "Available focus terms: status, progress, risks, blockers, decisions, actions, next_steps, projects.\n"
        "Planner schema summary:\n"
        f"{schema_text}"
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "note_query_plan",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "scope": {"type": "string", "enum": ["all", "project"]},
                        "target": {"type": ["string", "null"]},
                        "start_date": {"type": ["string", "null"]},
                        "end_date": {"type": ["string", "null"]},
                        "relative_days": {"type": ["integer", "null"], "minimum": 1, "maximum": 365},
                        "group_by": {"type": "string", "enum": ["none", "project"]},
                        "focus_terms": {
                            "type": "array",
                            "items": {"type": "string", "enum": PLANNER_FOCUS_ENUM},
                            "minItems": 1,
                            "maxItems": 6,
                        },
                        "include_body": {"type": "boolean"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                    "required": [
                        "scope",
                        "target",
                        "start_date",
                        "end_date",
                        "relative_days",
                        "group_by",
                        "focus_terms",
                        "include_body",
                        "limit",
                    ],
                },
            },
        },
    }
    req = request.Request(
        url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    org = os.getenv("OPENAI_ORGANIZATION", "").strip()
    project = os.getenv("OPENAI_PROJECT", "").strip()
    if org:
        req.add_header("OpenAI-Organization", org)
    if project:
        req.add_header("OpenAI-Project", project)

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"LLM planner request failed: {detail or exc.reason}") from exc
    except error.URLError as exc:
        raise ValueError(f"LLM planner request failed: {exc.reason}") from exc

    try:
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("content is not a string")
        result = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("LLM planner returned an unexpected response shape.") from exc
    if not isinstance(result, dict):
        raise ValueError("LLM planner returned non-object JSON.")
    return result


def _extract_project_filter(query: str, *, schema_snapshot: dict[str, Any] | None = None) -> str | None:
    known_projects = _schema_candidates(schema_snapshot, "Project")
    for project in known_projects:
        if project and project.lower() in query.lower():
            return project
    patterns = [
        r"([A-Za-z0-9._-]+)\s*(?:项目)?(?:现在|最近)?(?:进行得如何了|进展如何了|进展如何|状态如何|怎么样了|如何了)",
        r"([A-Za-z0-9._-]+)\s*(?:项目)?(?:有)?(?:什么)?(?:阻塞|卡点|风险|问题|决策|决定|下一步|待办)",
        r"(?:总结|汇总|看下|看看|查看|说说|问下)?\s*([A-Za-z0-9._-]+)\s*(?:项目)?(?:本周|最近\s*7\s*天|最近7天|过去\s*7\s*天|过去7天|最近两周|过去两周|最近14天|过去14天)?(?:工作|进展|周报|总结|情况)",
        r"(?:项目|project)\s*[:：]?\s*([A-Za-z0-9._-]+)",
        r"([A-Za-z0-9._-]+)\s+(?:progress|status|blockers|risks)",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def notion_schema_cache_path() -> Path:
    return frederica_home() / "cache" / "notion-schema.json"


def legacy_schema_cache_path() -> Path:
    return frederica_home() / "cache" / "notion-report-schema.json"


def summarize_database_schema(database: dict[str, Any]) -> dict[str, Any]:
    properties = database.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}
    fields: dict[str, dict[str, Any]] = {}
    candidates: dict[str, list[str]] = {}
    for name, meta in properties.items():
        if not isinstance(meta, dict):
            continue
        field_type = str(meta.get("type", "")).strip()
        field_info: dict[str, Any] = {"type": field_type}
        if field_type == "select":
            options = meta.get("select", {}).get("options", [])
            values = [str(item.get("name", "")).strip() for item in options if str(item.get("name", "")).strip()]
            field_info["options"] = values
            candidates[name] = values
        elif field_type == "multi_select":
            options = meta.get("multi_select", {}).get("options", [])
            values = [str(item.get("name", "")).strip() for item in options if str(item.get("name", "")).strip()]
            field_info["options"] = values
            candidates[name] = values
        fields[str(name)] = field_info
    return {"fields": fields, "candidates": candidates}


def load_schema_snapshot(
    *,
    cache_path: Path | None = None,
    database_id: str,
    max_age_seconds: int = SCHEMA_CACHE_MAX_AGE_SECONDS,
    now: float | None = None,
) -> dict[str, Any] | None:
    primary_path = cache_path or notion_schema_cache_path()
    candidate_paths = [primary_path]
    legacy_path = legacy_schema_cache_path()
    if cache_path is None and legacy_path != primary_path:
        candidate_paths.append(legacy_path)

    payload = None
    path = None
    for candidate in candidate_paths:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        path = candidate
        break

    if payload is None or path is None:
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("database_id", "")).strip() != database_id:
        return None
    fetched_at = payload.get("fetched_at")
    if not isinstance(fetched_at, (int, float)):
        return None
    current_time = now if now is not None else time.time()
    if current_time - float(fetched_at) > max_age_seconds:
        return None
    snapshot = payload.get("snapshot")
    if path != primary_path and isinstance(snapshot, dict):
        save_schema_snapshot(cache_path=primary_path, database_id=database_id, snapshot=snapshot, now=fetched_at)
    return snapshot if isinstance(snapshot, dict) else None


def save_schema_snapshot(
    *,
    cache_path: Path | None,
    database_id: str,
    snapshot: dict[str, Any],
    now: float | None = None,
) -> Path:
    path = cache_path or notion_schema_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "database_id": database_id,
        "fetched_at": now if now is not None else time.time(),
        "snapshot": snapshot,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def resolve_schema_snapshot(
    client: NotionClient,
    database_id: str,
    *,
    cache_path: Path | None = None,
    max_age_seconds: int = SCHEMA_CACHE_MAX_AGE_SECONDS,
    force_refresh: bool = False,
) -> dict[str, Any]:
    if not force_refresh:
        cached = load_schema_snapshot(
            cache_path=cache_path,
            database_id=database_id,
            max_age_seconds=max_age_seconds,
        )
        if cached is not None:
            return cached
    database = client.retrieve_database(database_id)
    snapshot = summarize_database_schema(database)
    save_schema_snapshot(cache_path=cache_path, database_id=database_id, snapshot=snapshot)
    return snapshot


def planner_schema_summary(schema_snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(schema_snapshot, dict):
        return None
    fields = schema_snapshot.get("fields", {})
    if not isinstance(fields, dict):
        return None
    summary_fields: list[dict[str, Any]] = []
    for name in sorted(fields):
        meta = fields.get(name, {})
        if not isinstance(meta, dict):
            continue
        item: dict[str, Any] = {
            "name": name,
            "type": str(meta.get("type", "")).strip(),
        }
        options = meta.get("options", [])
        if isinstance(options, list) and options:
            item["sample_options"] = [str(value) for value in options[:12]]
            item["option_count"] = len(options)
        summary_fields.append(item)
    return {"fields": summary_fields}


def _schema_candidates(schema_snapshot: dict[str, Any] | None, field_name: str) -> list[str]:
    if not isinstance(schema_snapshot, dict):
        return []
    candidates = schema_snapshot.get("candidates", {})
    if not isinstance(candidates, dict):
        return []
    values = candidates.get(field_name, [])
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _infer_focus_terms(query: str) -> list[str]:
    lowered = query.lower()
    terms: list[str] = []

    def add(name: str) -> None:
        if name not in terms:
            terms.append(name)

    if any(token in query for token in STATUS_KEYWORDS) or any(token in lowered for token in STATUS_KEYWORDS):
        add("status")
    if "进展" in query or "progress" in lowered or "做了什么" in query:
        add("progress")
    if any(token in query for token in RISK_KEYWORDS) or any(token in lowered for token in RISK_KEYWORDS):
        add("risks")
    if any(token in query for token in BLOCKER_KEYWORDS) or any(token in lowered for token in BLOCKER_KEYWORDS):
        add("blockers")
    if any(token in query for token in DECISION_KEYWORDS) or any(token in lowered for token in DECISION_KEYWORDS):
        add("decisions")
    if any(token in query for token in ACTION_KEYWORDS) or any(token in lowered for token in ACTION_KEYWORDS):
        add("actions")
    if any(token in query for token in NEXT_STEP_KEYWORDS) or any(token in lowered for token in NEXT_STEP_KEYWORDS):
        add("next_steps")
    if any(token in query for token in PROJECT_LIST_KEYWORDS) or any(token in lowered for token in PROJECT_LIST_KEYWORDS):
        add("projects")
    if not terms:
        add("progress")
    return terms


def _date_in_range(raw_value: str, start: date, end: date) -> bool:
    if not raw_value:
        return False
    return start.isoformat() <= raw_value[:10] <= end.isoformat()


def _session_start(properties: dict[str, Any]) -> str:
    return (properties.get("Session Date", {}).get("date") or {}).get("start", "")


def _property_select_name(properties: dict[str, Any], name: str) -> str | None:
    selected = properties.get(name, {}).get("select") or {}
    value = str(selected.get("name", "")).strip()
    return value or None


def _property_multi_select_names(properties: dict[str, Any], name: str) -> list[str]:
    values = properties.get(name, {}).get("multi_select", [])
    return [str(item.get("name", "")).strip() for item in values if str(item.get("name", "")).strip()]


def _plain_text_from_block(block: dict[str, Any]) -> str:
    block_type = str(block.get("type", "")).strip()
    if not block_type:
        return ""
    payload = block.get(block_type, {})
    parts = payload.get("rich_text", [])
    if not isinstance(parts, list):
        return ""
    return "".join(str(part.get("plain_text", "")) for part in parts).strip()


def fetch_notion_report_notes(
    client: NotionClient,
    database_id: str,
    *,
    start: date,
    end: date,
    project: str | None = None,
    include_body: bool = True,
    limit: int = 50,
) -> list[ReportNote]:
    project_filter = project.strip().lower() if project else None
    notes: list[ReportNote] = []
    cursor: str | None = None

    while True:
        response = client.query_database(database_id, start_cursor=cursor)
        for page in response.get("results", []):
            properties = page.get("properties", {})
            session_date = _session_start(properties)
            if not _date_in_range(session_date, start, end):
                continue

            project_name = rich_text_plain_text(properties.get("Project", {}).get("rich_text", [])) or "(no project)"
            if project_filter and project_name.lower() != project_filter:
                continue

            body_text = ""
            if include_body:
                body_blocks = client.list_all_block_children(page["id"])
                lines = [_plain_text_from_block(block) for block in body_blocks]
                body_text = "\n".join(line for line in lines if line).strip()

            notes.append(
                ReportNote(
                    page_id=str(page.get("id", "")),
                    title=rich_text_plain_text(properties.get("Name", {}).get("title", [])),
                    project=project_name,
                    session_date=session_date,
                    summary=rich_text_plain_text(properties.get("Summary", {}).get("rich_text", [])),
                    topics=_property_multi_select_names(properties, "Topics"),
                    language=_property_select_name(properties, "Language"),
                    entry_type=_property_select_name(properties, "Entry Type"),
                    body_text=body_text,
                    url=str(page.get("url", "")),
                )
            )
            if len(notes) >= limit:
                break

        if len(notes) >= limit or not response.get("has_more"):
            break
        cursor = response.get("next_cursor")

    notes.sort(key=lambda note: (note.session_date, note.project.lower(), note.title.lower()), reverse=True)
    return notes


def build_report_from_plan(
    plan: ReportPlan,
    notes: list[ReportNote],
    *,
    start: date,
    end: date,
) -> dict[str, Any]:
    return build_report_from_query(
        query=plan_to_query(plan),
        notes=notes,
        start=start,
        end=end,
    )


def build_report_from_query(
    query: ReportQuery,
    notes: list[ReportNote],
    *,
    start: date,
    end: date,
) -> dict[str, Any]:
    ranked_notes = _rank_notes(notes, query.focus_terms, query.question)
    if query.group_by == "project":
        return _build_grouped_project_answer(query, ranked_notes, start=start, end=end)
    return _build_focused_answer(query, ranked_notes, start=start, end=end)


def _build_grouped_project_answer(query: ReportQuery, notes: list[ReportNote], *, start: date, end: date) -> dict[str, Any]:
    grouped: dict[str, list[ReportNote]] = {}
    for note in notes:
        grouped.setdefault(note.project, []).append(note)

    groups = []
    for project_name, project_notes in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0].lower())):
        dates = sorted({note.session_date[:10] for note in project_notes if note.session_date})
        groups.append(
            {
                "project": project_name,
                "entry_count": len(project_notes),
                "dates": dates,
                "entries": [
                    {
                        "title": note.title,
                        "session_date": note.session_date,
                        "summary": note.summary,
                        "url": note.url,
                    }
                    for note in project_notes[:5]
                ],
            }
        )

    return {
        "kind": "note-answer",
        "question": query.question,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "entry_count": len(notes),
        "project_count": len(groups),
        "group_by": query.group_by,
        "focus_terms": query.focus_terms,
        "groups": groups,
        "sources": _collect_sources(notes),
    }


def _build_focused_answer(query: ReportQuery, notes: list[ReportNote], *, start: date, end: date) -> dict[str, Any]:
    latest = notes[0] if notes else None
    sections = [
        {
            "heading": "Recent Notes",
            "items": [
                {
                    "title": note.title,
                    "session_date": note.session_date,
                    "summary": note.summary,
                    "url": note.url,
                }
                for note in notes[:5]
            ],
        }
    ]

    signal_map = [
        ("risks", "Risks", RISK_KEYWORDS),
        ("blockers", "Blockers", BLOCKER_KEYWORDS),
        ("decisions", "Decisions", DECISION_KEYWORDS),
        ("actions", "Actions", ACTION_KEYWORDS),
        ("next_steps", "Next Steps", NEXT_STEP_KEYWORDS),
    ]
    for key, heading, keywords in signal_map:
        if key in query.focus_terms:
            sections.append({"heading": heading, "items": _extract_signal_lines(notes, keywords, limit=5)})

    return {
        "kind": "note-answer",
        "question": query.question,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "entry_count": len(notes),
        "project_count": len({note.project for note in notes}),
        "group_by": query.group_by,
        "focus_terms": query.focus_terms,
        "target": query.target,
        "summary": (latest.summary or latest.title) if latest else "No matching notes found.",
        "sections": sections,
        "sources": _collect_sources(notes[:8]),
    }


def render_report(report: dict[str, Any]) -> str:
    lines = [
        f"Note Answer ({report['date_range']['start']} to {report['date_range']['end']})",
        f"Question: {report['question']}",
        f"Entries: {report['entry_count']}",
    ]
    if report.get("group_by") == "project":
        lines.append(f"Projects: {report['project_count']}")
        groups = report.get("groups", [])
        assert isinstance(groups, list)
        if not groups:
            lines.append("")
            lines.append("No matching notes found.")
        for group in groups:
            assert isinstance(group, dict)
            lines.append("")
            lines.append(f"[{group['project']}] {group['entry_count']} entr{'y' if group['entry_count'] == 1 else 'ies'}")
            dates = group.get("dates", [])
            if dates:
                lines.append("Dates: " + ", ".join(str(item) for item in dates))
            entries = group.get("entries", [])
            assert isinstance(entries, list)
            for entry in entries:
                assert isinstance(entry, dict)
                line = f"- {str(entry.get('session_date', ''))[:10]} {entry.get('title', '')}"
                summary = str(entry.get("summary", "")).strip()
                if summary:
                    line += f": {summary}"
                lines.append(line)
    else:
        target = str(report.get("target", "")).strip()
        if target:
            lines.append(f"Target: {target}")
        lines.append("")
        lines.append("Summary:")
        lines.append(str(report.get("summary", "No matching notes found.")))
        sections = report.get("sections", [])
        assert isinstance(sections, list)
        for section in sections:
            assert isinstance(section, dict)
            lines.append("")
            lines.append(f"{section['heading']}:")
            items = section.get("items", [])
            assert isinstance(items, list)
            if not items:
                lines.append("- None identified from retrieved notes.")
                continue
            for item in items:
                if isinstance(item, dict):
                    line = f"- {str(item.get('session_date', ''))[:10]} {item.get('title', '')}"
                    summary = str(item.get("summary", "")).strip()
                    if summary:
                        line += f": {summary}"
                    lines.append(line)
                else:
                    lines.append(f"- {item}")

    _append_sources_section(lines, report.get("sources", []))
    return "\n".join(lines)


def _rank_notes(notes: list[ReportNote], focus_terms: list[str], question: str) -> list[ReportNote]:
    keywords = [token.lower() for token in focus_terms]
    if question:
        keywords.extend(token.lower() for token in re.findall(r"[A-Za-z0-9._-]+|[\u4e00-\u9fff]{2,}", question))
    deduped_keywords = [token for token in dict.fromkeys(keywords) if token]

    def score(note: ReportNote) -> tuple[int, str]:
        haystack = " ".join([note.title, note.summary, note.body_text, note.project, " ".join(note.topics)]).lower()
        hits = sum(1 for token in deduped_keywords if token in haystack)
        return (hits, note.session_date)

    return sorted(notes, key=score, reverse=True)


def _extract_signal_lines(notes: list[ReportNote], keywords: tuple[str, ...], *, limit: int) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    lowered_keywords = tuple(keyword.lower() for keyword in keywords)

    for note in notes:
        for source_line in note.body_text.splitlines():
            line = source_line.strip(" -\t")
            if not line:
                continue
            lowered = line.lower()
            if any(keyword in lowered for keyword in lowered_keywords):
                if line not in seen:
                    results.append(line)
                    seen.add(line)
                    if len(results) >= limit:
                        return results
    return results


def _collect_sources(notes: list[ReportNote]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for note in notes:
        key = note.page_id or note.url or f"{note.session_date}|{note.title}"
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "title": note.title or "(untitled)",
                "project": note.project,
                "session_date": note.session_date[:10],
                "url": note.url,
            }
        )
    return sources


def _append_sources_section(lines: list[str], sources: object) -> None:
    values = sources if isinstance(sources, list) else []
    lines.append("")
    lines.append("Sources:")
    if not values:
        lines.append("- None")
        return
    for item in values:
        if not isinstance(item, dict):
            continue
        date_text = str(item.get("session_date", "")).strip()
        project = str(item.get("project", "")).strip()
        title = str(item.get("title", "")).strip() or "(untitled)"
        url = str(item.get("url", "")).strip()
        line = f"- {date_text} [{project}] {title}" if project else f"- {date_text} {title}"
        if url:
            line += f" ({url})"
        lines.append(line)


def plan_to_dict(plan: ReportPlan) -> dict[str, Any]:
    return {
        "kind": plan.kind,
        "question": plan.question,
        "source": plan.source,
        "scope": plan.scope,
        "target": plan.target,
        "start_date": plan.start_date,
        "end_date": plan.end_date,
        "relative_days": plan.relative_days,
        "group_by": plan.group_by,
        "focus_terms": plan.focus_terms,
        "include_body": plan.include_body,
        "limit": plan.limit,
    }


def plan_to_query(plan: ReportPlan) -> ReportQuery:
    return ReportQuery(
        kind=plan.kind,
        question=plan.question,
        source=plan.source,
        scope=plan.scope,
        target=plan.target,
        start_date=plan.start_date,
        end_date=plan.end_date,
        group_by=plan.group_by,
        focus_terms=list(plan.focus_terms),
        include_body=plan.include_body,
        limit=plan.limit,
    )


def query_to_dict(query: ReportQuery) -> dict[str, Any]:
    return {
        "kind": query.kind,
        "question": query.question,
        "source": query.source,
        "scope": query.scope,
        "target": query.target,
        "start_date": query.start_date,
        "end_date": query.end_date,
        "group_by": query.group_by,
        "focus_terms": query.focus_terms,
        "include_body": query.include_body,
        "limit": query.limit,
    }
