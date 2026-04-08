from __future__ import annotations

import json
from dataclasses import dataclass
import re
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
NOTION_COLORS = {
    "default",
    "gray",
    "brown",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "pink",
    "red",
    "gray_background",
    "brown_background",
    "orange_background",
    "yellow_background",
    "green_background",
    "blue_background",
    "purple_background",
    "pink_background",
    "red_background",
}
INLINE_TOKEN_RE = re.compile(
    r"\[([^\]]+)\]\((https?://[^)\s]+)\)"
    r"|\*\*([^*\n][\s\S]*?)\*\*"
    r"|`([^`\n][\s\S]*?)`"
    r"|~~([^~\n][\s\S]*?)~~"
    r"|==([^=\n][\s\S]*?)=="
    r"|\{([a-z_]+)\|([^{}]+)\}"
    r"|\*([^*\n][^*\n]*?)\*"
)
TODO_RE = re.compile(r"^[-*]\s+\[( |x|X)\]\s+(.*)$")
NUMBERED_LIST_RE = re.compile(r"^\d+\.\s+(.*)$")
CALLOUT_RE = re.compile(r"^>\s*\[!([A-Za-z]+)\]\s*(.*)$")
DIVIDER_RE = re.compile(r"^([-*_])\1{2,}$")
TOGGLE_START_RE = re.compile(r"^:::(?:toggle|details)\s+(.*)$")
TOGGLE_END_RE = re.compile(r"^:::$")
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
COLOR_ALIASES = {
    "highlight": "yellow_background",
    "yellow_bg": "yellow_background",
    "red_bg": "red_background",
    "green_bg": "green_background",
    "blue_bg": "blue_background",
    "gray_bg": "gray_background",
}
CALLOUT_STYLES = {
    "NOTE": {"emoji": "📝", "color": "blue_background"},
    "TIP": {"emoji": "💡", "color": "green_background"},
    "IMPORTANT": {"emoji": "📌", "color": "yellow_background"},
    "WARNING": {"emoji": "⚠️", "color": "orange_background"},
    "ERROR": {"emoji": "🚨", "color": "red_background"},
}
NOTION_CODE_LANGUAGES = {
    "plain text",
    "abap",
    "arduino",
    "bash",
    "basic",
    "c",
    "clojure",
    "coffeescript",
    "c++",
    "c#",
    "css",
    "dart",
    "diff",
    "docker",
    "elixir",
    "elm",
    "erlang",
    "flow",
    "fortran",
    "f#",
    "gherkin",
    "glsl",
    "go",
    "graphql",
    "groovy",
    "haskell",
    "html",
    "java",
    "javascript",
    "json",
    "julia",
    "kotlin",
    "latex",
    "less",
    "lisp",
    "livescript",
    "lua",
    "makefile",
    "markdown",
    "markup",
    "matlab",
    "mermaid",
    "nix",
    "objective-c",
    "ocaml",
    "pascal",
    "perl",
    "php",
    "powershell",
    "prolog",
    "protobuf",
    "python",
    "r",
    "reason",
    "ruby",
    "rust",
    "sass",
    "scala",
    "scheme",
    "scss",
    "shell",
    "sql",
    "swift",
    "typescript",
    "vb.net",
    "verilog",
    "vhdl",
    "visual basic",
    "webassembly",
    "xml",
    "yaml",
    "java/c/c++/c#",
}
CODE_LANGUAGE_ALIASES = {
    "": "plain text",
    "text": "plain text",
    "txt": "plain text",
    "plaintext": "plain text",
    "plain": "plain text",
    "sh": "shell",
    "shellscript": "shell",
    "zsh": "shell",
    "console": "shell",
    "ps1": "powershell",
    "pwsh": "powershell",
    "yml": "yaml",
    "md": "markdown",
    "ts": "typescript",
    "tsx": "typescript",
    "js": "javascript",
    "jsx": "javascript",
    "py": "python",
    "rb": "ruby",
    "rs": "rust",
    "cs": "c#",
    "cpp": "c++",
    "cxx": "c++",
    "cc": "c++",
    "psql": "sql",
    "postgres": "sql",
    "toml": "plain text",
    "ini": "plain text",
    "env": "plain text",
    "conf": "plain text",
}


class NotionError(RuntimeError):
    """Raised when Notion API requests fail."""


def _normalize_heading(text: str) -> str:
    return " ".join(text.strip().lower().split())


SECTION_HEADING_ALIASES = {
    "Decisions": {_normalize_heading("Decisions"), _normalize_heading("Key Decisions")},
    "Actions": {_normalize_heading("Actions"), _normalize_heading("Next Actions"), _normalize_heading("Next Steps")},
    "Open Questions": {_normalize_heading("Open Questions"), _normalize_heading("Unresolved Questions")},
    "Artifacts": {_normalize_heading("Artifacts"), _normalize_heading("References")},
}


def _existing_headings(markdown: str) -> set[str]:
    headings: set[str] = set()
    for raw_line in markdown.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("#"):
            continue
        level = len(stripped) - len(stripped.lstrip("#"))
        heading_text = stripped[level:].strip()
        if heading_text:
            headings.add(_normalize_heading(heading_text))
    return headings


def _append_section(lines: list[str], heading: str, items: list[str]) -> None:
    if not items:
        return
    if lines and lines[-1] != "":
        lines.append("")
    lines.append(f"## {heading}")
    lines.append("")
    lines.extend(f"- {item}" for item in items)


def render_notion_markdown(entry: KnowledgeEntry) -> str:
    body = entry.body_markdown.strip()
    existing_headings = _existing_headings(body)
    lines = [body]
    if SECTION_HEADING_ALIASES["Decisions"].isdisjoint(existing_headings):
        _append_section(lines, "Decisions", entry.decisions)
    if SECTION_HEADING_ALIASES["Actions"].isdisjoint(existing_headings):
        _append_section(lines, "Actions", entry.actions)
    if SECTION_HEADING_ALIASES["Open Questions"].isdisjoint(existing_headings):
        _append_section(lines, "Open Questions", entry.open_questions)
    if SECTION_HEADING_ALIASES["Artifacts"].isdisjoint(existing_headings):
        _append_section(lines, "Artifacts", entry.artifacts)
    body = "\n".join(line for line in lines if line is not None).strip()
    return body + "\n"


def chunk_text(text: str, limit: int = MAX_RICH_TEXT) -> list[str]:
    if not text:
        return [""]
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + limit])
        start += limit
    return chunks


def _normalize_color(color: str | None) -> str:
    candidate = (color or "").strip().lower()
    if not candidate:
        return "default"
    candidate = COLOR_ALIASES.get(candidate, candidate)
    return candidate if candidate in NOTION_COLORS else "default"


def _make_text_part(
    content: str,
    *,
    bold: bool = False,
    italic: bool = False,
    strikethrough: bool = False,
    code: bool = False,
    color: str = "default",
    url: str | None = None,
) -> dict[str, Any]:
    part: dict[str, Any] = {
        "type": "text",
        "text": {
            "content": content,
        },
        "annotations": {
            "bold": bold,
            "italic": italic,
            "strikethrough": strikethrough,
            "underline": False,
            "code": code,
            "color": _normalize_color(color),
        },
    }
    if url:
        part["text"]["link"] = {"url": url}
    return part


def _chunk_part(part: dict[str, Any]) -> list[dict[str, Any]]:
    content = str(part.get("text", {}).get("content", ""))
    if not content:
        return []
    annotations = dict(part.get("annotations", {}))
    link = part.get("text", {}).get("link")
    chunks: list[dict[str, Any]] = []
    for piece in chunk_text(content):
        text_payload: dict[str, Any] = {"content": piece}
        if link:
            text_payload["link"] = dict(link)
        chunks.append(
            {
                "type": "text",
                "text": text_payload,
                "annotations": annotations,
            }
        )
    return chunks


def rich_text(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    parts: list[dict[str, Any]] = []
    cursor = 0
    for match in INLINE_TOKEN_RE.finditer(text):
        start, end = match.span()
        if start > cursor:
            parts.extend(_chunk_part(_make_text_part(text[cursor:start])))

        if match.group(1) is not None and match.group(2) is not None:
            parts.extend(_chunk_part(_make_text_part(match.group(1), url=match.group(2))))
        elif match.group(3) is not None:
            parts.extend(_chunk_part(_make_text_part(match.group(3), bold=True)))
        elif match.group(4) is not None:
            parts.extend(_chunk_part(_make_text_part(match.group(4), code=True)))
        elif match.group(5) is not None:
            parts.extend(_chunk_part(_make_text_part(match.group(5), strikethrough=True)))
        elif match.group(6) is not None:
            parts.extend(_chunk_part(_make_text_part(match.group(6), color="yellow_background")))
        elif match.group(7) is not None and match.group(8) is not None:
            parts.extend(_chunk_part(_make_text_part(match.group(8), color=match.group(7))))
        elif match.group(9) is not None:
            parts.extend(_chunk_part(_make_text_part(match.group(9), italic=True)))

        cursor = end

    if cursor < len(text):
        parts.extend(_chunk_part(_make_text_part(text[cursor:])))
    return parts


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


def list_block(kind: str, text: str, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rich_text": rich_text(text),
    }
    if children:
        payload["children"] = children
    return {
        "object": "block",
        "type": kind,
        kind: payload,
    }


def code_block(text: str, language: str = "plain text") -> dict[str, Any]:
    normalized_language = normalize_code_language(language)
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": [_make_text_part(chunk, code=True) for chunk in chunk_text(text)],
            "language": normalized_language,
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


def to_do_block(text: str, checked: bool, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rich_text": rich_text(text),
        "checked": checked,
    }
    if children:
        payload["children"] = children
    return {
        "object": "block",
        "type": "to_do",
        "to_do": payload,
    }


def divider_block() -> dict[str, Any]:
    return {
        "object": "block",
        "type": "divider",
        "divider": {},
    }


def callout_block(text: str, kind: str) -> dict[str, Any]:
    style = CALLOUT_STYLES.get(kind.upper(), CALLOUT_STYLES["NOTE"])
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": rich_text(text),
            "icon": {"type": "emoji", "emoji": style["emoji"]},
            "color": style["color"],
        },
    }


def toggle_block(text: str, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": rich_text(text),
            "children": children or [],
        },
    }


def table_row_block(cells: list[str]) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "table_row",
        "table_row": {
            "cells": [rich_text(cell) for cell in cells],
        },
    }


def table_block(rows: list[list[str]], has_column_header: bool) -> dict[str, Any]:
    width = max((len(row) for row in rows), default=0)
    normalized_rows = [row + [""] * (width - len(row)) for row in rows]
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": has_column_header,
            "has_row_header": False,
            "children": [table_row_block(row) for row in normalized_rows],
        },
    }


def normalize_code_language(language: str) -> str:
    normalized = (language or "").strip().lower()
    normalized = CODE_LANGUAGE_ALIASES.get(normalized, normalized)
    if normalized in NOTION_CODE_LANGUAGES:
        return normalized
    return "plain text"


def _line_indent(raw_line: str) -> int:
    indent = 0
    for char in raw_line:
        if char == " ":
            indent += 1
        elif char == "\t":
            indent += 4
        else:
            break
    return indent


def _strip_indent(raw_line: str, indent: int) -> str:
    remaining = indent
    index = 0
    while index < len(raw_line) and remaining > 0:
        if raw_line[index] == " ":
            remaining -= 1
        elif raw_line[index] == "\t":
            remaining -= min(4, remaining)
        else:
            break
        index += 1
    return raw_line[index:]


def _collect_indented_child_lines(lines: list[str], start: int, parent_indent: int) -> tuple[list[str], int]:
    child_lines: list[str] = []
    index = start
    child_indent: int | None = None
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if stripped and TOGGLE_END_RE.match(stripped):
            break
        if not stripped:
            child_lines.append("")
            index += 1
            continue
        indent = _line_indent(raw_line)
        if indent <= parent_indent:
            break
        if child_indent is None:
            child_indent = indent
        child_lines.append(_strip_indent(raw_line, child_indent))
        index += 1
    return child_lines, index


def _split_table_row(line: str) -> list[str]:
    trimmed = line.strip()
    if not trimmed.startswith("|") or "|" not in trimmed[1:]:
        return []
    raw = trimmed[1:-1] if trimmed.endswith("|") else trimmed[1:]
    return [cell.strip() for cell in raw.split("|")]


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(TABLE_SEPARATOR_CELL_RE.match(cell) for cell in cells)


def _parse_blocks(lines: list[str], start: int = 0, stop_on_toggle_end: bool = False) -> tuple[list[dict[str, Any]], int]:
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

    index = start
    while index < len(lines):
        raw_line = lines[index]
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
            index += 1
            continue

        if in_code:
            code_lines.append(raw_line)
            index += 1
            continue

        if stop_on_toggle_end and TOGGLE_END_RE.match(stripped):
            break

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        toggle_match = TOGGLE_START_RE.match(stripped)
        if toggle_match:
            flush_paragraph()
            child_blocks, consumed_index = _parse_blocks(lines, index + 1, stop_on_toggle_end=True)
            blocks.append(toggle_block(toggle_match.group(1).strip(), child_blocks))
            index = consumed_index + 1
            continue

        table_cells = _split_table_row(stripped)
        if table_cells:
            flush_paragraph()
            rows = [table_cells]
            has_column_header = False
            index += 1
            if index < len(lines) and _is_table_separator(lines[index].strip()):
                has_column_header = True
                index += 1
            while index < len(lines):
                next_cells = _split_table_row(lines[index].strip())
                if not next_cells:
                    break
                rows.append(next_cells)
                index += 1
            blocks.append(table_block(rows, has_column_header))
            continue

        if DIVIDER_RE.match(stripped):
            flush_paragraph()
            blocks.append(divider_block())
            index += 1
            continue

        if stripped.startswith("#"):
            flush_paragraph()
            level = min(len(stripped) - len(stripped.lstrip("#")), 3)
            heading_text = stripped[level:].strip()
            if heading_text:
                blocks.append(heading_block(level, heading_text))
            index += 1
            continue

        callout_match = CALLOUT_RE.match(stripped)
        if callout_match:
            flush_paragraph()
            callout_text = callout_match.group(2).strip()
            if callout_text:
                blocks.append(callout_block(callout_text, callout_match.group(1)))
            index += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            quote_text = stripped[1:].strip()
            if quote_text:
                blocks.append(quote_block(quote_text))
            index += 1
            continue

        todo_match = TODO_RE.match(stripped)
        if todo_match:
            flush_paragraph()
            child_lines, next_index = _collect_indented_child_lines(lines, index + 1, _line_indent(raw_line))
            child_blocks = markdown_to_blocks("\n".join(child_lines)) if child_lines else []
            blocks.append(
                to_do_block(
                    todo_match.group(2).strip(),
                    checked=todo_match.group(1).lower() == "x",
                    children=child_blocks,
                )
            )
            index = next_index
            continue

        if stripped[:2] in {"- ", "* "}:
            flush_paragraph()
            child_lines, next_index = _collect_indented_child_lines(lines, index + 1, _line_indent(raw_line))
            child_blocks = markdown_to_blocks("\n".join(child_lines)) if child_lines else []
            blocks.append(list_block("bulleted_list_item", stripped[2:].strip(), children=child_blocks))
            index = next_index
            continue

        numbered_match = NUMBERED_LIST_RE.match(stripped)
        if numbered_match:
            flush_paragraph()
            child_lines, next_index = _collect_indented_child_lines(lines, index + 1, _line_indent(raw_line))
            child_blocks = markdown_to_blocks("\n".join(child_lines)) if child_lines else []
            blocks.append(list_block("numbered_list_item", numbered_match.group(1).strip(), children=child_blocks))
            index = next_index
            continue

        paragraph_lines.append(raw_line)
        index += 1

    if in_code:
        flush_code()
    flush_paragraph()
    return blocks, index


def markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks, _ = _parse_blocks(markdown.splitlines())
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

    def list_block_children(self, block_id: str, start_cursor: str | None = None) -> dict[str, Any]:
        path = f"/blocks/{block_id}/children?page_size=100"
        if start_cursor:
            path += f"&start_cursor={start_cursor}"
        return self._request("GET", path)

    def list_all_block_children(self, block_id: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            response = self.list_block_children(block_id, start_cursor=cursor)
            blocks.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        return blocks

    def update_page_properties(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        payload = {"properties": properties}
        return self._request("PATCH", f"/pages/{page_id}", payload)

    def create_page(self, database_id: str, entry: KnowledgeEntry, status: str) -> dict[str, Any]:
        children = markdown_to_blocks(render_notion_markdown(entry))
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
        "Schema Version": {
            "rich_text": rich_text(entry.schema_version),
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

    if entry.entry_type:
        properties["Entry Type"] = {
            "select": {"name": entry.entry_type},
        }
    if entry.language:
        properties["Language"] = {
            "select": {"name": entry.language},
        }
    if entry.status:
        properties["Lifecycle Status"] = {
            "select": {"name": entry.status},
        }
    if entry.topics:
        properties["Topics"] = {
            "multi_select": [{"name": topic} for topic in entry.topics],
        }
    if entry.tech_stack:
        properties["Tech Stack"] = {
            "multi_select": [{"name": tech} for tech in entry.tech_stack],
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
        "Schema Version": {
            "rich_text": {},
        },
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
        "Entry Type": {
            "select": {},
        },
        "Language": {
            "select": {},
        },
        "Lifecycle Status": {
            "select": {
                "options": [
                    {"name": "active", "color": "green"},
                    {"name": "draft", "color": "gray"},
                    {"name": "superseded", "color": "yellow"},
                    {"name": "archived", "color": "brown"},
                ]
            },
        },
        "Topics": {
            "multi_select": {},
        },
        "Tech Stack": {
            "multi_select": {},
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
