from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from entrykit.models import KnowledgeEntry

NOTION_VERSION = "2022-06-28"
MAX_RICH_TEXT = 2000
MAX_NOTION_BLOCKS = 100
BLOCK_WARNING_THRESHOLD = 90
SCHEMA_RENAMES = {
    "Model ID": "Model",
    "Model Label": "Model",
    "Model Version": "Model",
}
MODEL_ALIASES = ["Model Version", "Model Label", "Model ID", "Model 1"]


class NotionError(RuntimeError):
    """Raised when Notion API requests fail."""


def chunk_text(text: str, limit: int = MAX_RICH_TEXT) -> list[str]:
    if not text:
        return [""]
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + limit])
        start += limit
    return chunks


def rich_text(text: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": {
                "content": chunk,
            },
        }
        for chunk in chunk_text(text)
    ]


def paragraph_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": rich_text(text),
        },
    }


def heading_block(level: int, text: str) -> dict[str, Any]:
    key = f"heading_{level}"
    return {
        "object": "block",
        "type": key,
        key: {
            "rich_text": rich_text(text),
        },
    }


def list_block(kind: str, text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": kind,
        kind: {
            "rich_text": rich_text(text),
        },
    }


def code_block(text: str, language: str = "plain text") -> dict[str, Any]:
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": rich_text(text),
            "language": language,
        },
    }


def quote_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "quote",
        "quote": {
            "rich_text": rich_text(text),
        },
    }


def markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    paragraph_lines: list[str] = []
    code_lines: list[str] = []
    in_code = False
    code_language = "plain text"

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        text = "\n".join(paragraph_lines).strip()
        if text:
            blocks.append(paragraph_block(text))
        paragraph_lines.clear()

    def flush_code() -> None:
        nonlocal code_language
        if not code_lines:
            return
        blocks.append(code_block("\n".join(code_lines), code_language))
        code_lines.clear()
        code_language = "plain text"

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            if in_code:
                flush_code()
                in_code = False
            else:
                in_code = True
                code_language = stripped[3:].strip() or "plain text"
            continue

        if in_code:
            code_lines.append(raw_line)
            continue

        if not stripped:
            flush_paragraph()
            continue

        if stripped.startswith("#"):
            flush_paragraph()
            level = min(len(stripped) - len(stripped.lstrip("#")), 3)
            heading_text = stripped[level:].strip()
            if heading_text:
                blocks.append(heading_block(level, heading_text))
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            quote_text = stripped[1:].strip()
            if quote_text:
                blocks.append(quote_block(quote_text))
            continue

        if stripped[:2] in {"- ", "* "}:
            flush_paragraph()
            blocks.append(list_block("bulleted_list_item", stripped[2:].strip()))
            continue

        parts = stripped.split(". ", 1)
        if len(parts) == 2 and parts[0].isdigit():
            flush_paragraph()
            blocks.append(list_block("numbered_list_item", parts[1].strip()))
            continue

        paragraph_lines.append(raw_line)

    if in_code:
        flush_code()
    flush_paragraph()
    return blocks


def count_markdown_blocks(markdown: str) -> int:
    return len(markdown_to_blocks(markdown))


def validate_block_limit(markdown: str, limit: int = MAX_NOTION_BLOCKS) -> int:
    block_count = count_markdown_blocks(markdown)
    if block_count > limit:
        raise ValueError(
            f"`body_markdown` renders to {block_count} Notion blocks, which exceeds the "
            f"limit of {limit}. Merge adjacent text into fewer blocks and prefer in-block "
            f"newlines before retrying."
        )
    return block_count


@dataclass
class NotionClient:
    token: str

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"https://api.notion.com/v1{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Notion-Version": NOTION_VERSION,
            },
        )
        try:
            with request.urlopen(req) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise NotionError(
                f"Notion API request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except error.URLError as exc:
            raise NotionError(f"Notion API request failed: {exc.reason}") from exc

        return json.loads(response_body)

    def retrieve_database(self, database_id: str) -> dict[str, Any]:
        return self._request("GET", f"/databases/{database_id}")

    def update_database_schema(
        self, database_id: str, properties: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {"properties": properties}
        return self._request("PATCH", f"/databases/{database_id}", payload)

    def query_database(
        self, database_id: str, start_cursor: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        return self._request("POST", f"/databases/{database_id}/query", payload)

    def update_page_properties(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        payload = {"properties": properties}
        return self._request("PATCH", f"/pages/{page_id}", payload)

    def create_page(self, database_id: str, entry: KnowledgeEntry, status: str) -> dict[str, Any]:
        children = markdown_to_blocks(entry.body_markdown)
        payload = {
            "parent": {"database_id": database_id},
            "properties": build_properties(entry, status),
            "children": children,
        }
        return self._request("POST", "/pages", payload)


def build_properties(entry: KnowledgeEntry, status: str) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "Name": {
            "title": rich_text(entry.title),
        },
        "Source Tool": {
            "select": {"name": entry.source_tool},
        },
        "Thinking Mode": {
            "select": {"name": entry.thinking_mode},
        },
        "Session Date": {
            "date": {"start": entry.session_date},
        },
        "Tags": {
            "multi_select": [{"name": tag} for tag in entry.tags],
        },
        "Reusability Score": {
            "number": entry.reusability_score,
        },
        "Summary": {
            "rich_text": rich_text(entry.summary),
        },
        "Status": {
            "select": {"name": status},
        },
    }

    if entry.tool_version:
        properties["Tool Version"] = {
            "rich_text": rich_text(entry.tool_version),
        }
    if entry.model:
        properties["Model"] = {
            "rich_text": rich_text(entry.model),
        }
    if entry.project:
        properties["Project"] = {
            "rich_text": rich_text(entry.project),
        }
    if entry.session_id:
        properties["Session ID"] = {
            "rich_text": rich_text(entry.session_id),
        }

    return properties


def desired_database_properties() -> dict[str, Any]:
    return {
        "Source Tool": {
            "select": {},
        },
        "Tool Version": {
            "rich_text": {},
        },
        "Model": {
            "rich_text": {},
        },
        "Thinking Mode": {
            "select": {
                "options": [
                    {"name": "unknown", "color": "default"},
                    {"name": "low", "color": "gray"},
                    {"name": "medium", "color": "blue"},
                    {"name": "high", "color": "orange"},
                    {"name": "extra-high", "color": "red"},
                ]
            },
        },
        "Project": {
            "rich_text": {},
        },
        "Session ID": {
            "rich_text": {},
        },
        "Session Date": {
            "date": {},
        },
        "Tags": {
            "multi_select": {},
        },
        "Reusability Score": {
            "number": {"format": "number"},
        },
        "Summary": {
            "rich_text": {},
        },
        "Status": {
            "select": {
                "options": [
                    {"name": "Captured", "color": "blue"},
                ]
            },
        },
    }


def build_schema_patch(existing_properties: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    effective_names = set(existing_properties.keys())

    if "Model" not in effective_names:
        for alias in MODEL_ALIASES:
            if alias in effective_names:
                patch[alias] = {"name": "Model"}
                effective_names.remove(alias)
                effective_names.add("Model")
                break

    for name, config in desired_database_properties().items():
        if name not in effective_names:
            patch[name] = config

    return patch


def rich_text_plain_text(parts: list[dict[str, Any]]) -> str:
    return "".join(part.get("plain_text", "") for part in parts).strip()


def backfill_model_property(client: NotionClient, database_id: str) -> int:
    updated = 0
    cursor: str | None = None

    while True:
        response = client.query_database(database_id, start_cursor=cursor)
        for page in response.get("results", []):
            properties = page.get("properties", {})
            model_rich = properties.get("Model", {}).get("rich_text", [])
            if rich_text_plain_text(model_rich):
                continue

            for alias in MODEL_ALIASES:
                alias_rich = properties.get(alias, {}).get("rich_text", [])
                if rich_text_plain_text(alias_rich):
                    client.update_page_properties(
                        page["id"],
                        {
                            "Model": {
                                "rich_text": alias_rich,
                            }
                        },
                    )
                    updated += 1
                    break

        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")

    return updated


def cleanup_legacy_model_properties(existing_properties: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "Model" not in existing_properties:
        return patch
    for alias in MODEL_ALIASES:
        if alias in existing_properties:
            patch[alias] = None
    return patch
