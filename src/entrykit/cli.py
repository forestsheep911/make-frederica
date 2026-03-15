from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from entrykit.config import Settings, default_env_path, frederica_home
from entrykit.linting import format_lint_result, lint_entry, result_as_json
from entrykit.models import KnowledgeEntry
from entrykit.notion import (
    NotionClient,
    backfill_model_property,
    NotionError,
    BLOCK_WARNING_THRESHOLD,
    build_schema_patch,
    build_properties,
    cleanup_legacy_model_properties,
    markdown_to_blocks,
    validate_block_limit,
)
from entrykit.prompts import render_capture_prompt
from entrykit.reviewing import (
    format_review_result,
    parse_review_result,
    render_review_prompt,
    review_result_as_json,
)


MIN_PYTHON = (3, 10)


def configure_stdio() -> None:
    if os.name != "nt":
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def decode_utf8(raw: bytes, source: str) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"{source} must be UTF-8 encoded. On Windows PowerShell, prefer a UTF-8 file plus "
            f"`--input`, or set `[Console]::InputEncoding` / `[Console]::OutputEncoding` to UTF-8 "
            f"together with `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` before retrying."
        ) from exc


def read_text_file(path: Path) -> str:
    return decode_utf8(path.read_bytes(), f"Input file `{path}`")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="entrykit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser(
        "capture",
        help="Create a Notion knowledge entry from structured JSON.",
    )
    capture.add_argument(
        "--input",
        type=Path,
        help="Path to a JSON file. If omitted, read JSON from stdin.",
    )
    capture.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to a .env file. Defaults to ./.env.",
    )
    capture.add_argument(
        "--status",
        default="Captured",
        help="Value written to the Notion Status select property.",
    )
    capture.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate input and print the derived Notion payload without writing.",
    )
    capture.add_argument(
        "--conversation",
        type=Path,
        help="Optional path to the source conversation transcript for lint checks.",
    )
    capture.add_argument(
        "--strict-lint",
        action="store_true",
        help="Run lint before writing and fail if lint reports any issue.",
    )

    bootstrap = subparsers.add_parser(
        "bootstrap-notion",
        help="Create or align the Notion database schema expected by entrykit.",
    )
    bootstrap.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to a .env file. Defaults to ./.env.",
    )
    bootstrap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the desired schema patch without sending it to Notion.",
    )

    inspect = subparsers.add_parser(
        "inspect-notion",
        help="Print the current Notion database properties.",
    )
    inspect.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to a .env file. Defaults to ./.env.",
    )

    doctor = subparsers.add_parser(
        "doctor",
        help="Check local runtime prerequisites and Notion configuration.",
    )
    doctor.add_argument(
        "--env-file",
        type=Path,
        help="Optional explicit .env path. Defaults to ~/.frederica/config/.env.",
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        help="Print the doctor result as JSON.",
    )

    render_prompt = subparsers.add_parser(
        "render-prompt",
        help="Render a reusable capture prompt for tools without native skill integration.",
    )
    render_prompt.add_argument(
        "--source-tool",
        default="generic",
        help="Value to prefill for the source_tool field, such as codex, cursor, or gemini-cli.",
    )
    render_prompt.add_argument(
        "--include-example",
        action="store_true",
        help="Append a complete JSON example after the schema.",
    )

    lint = subparsers.add_parser(
        "lint",
        help="Check a capture JSON payload for schema and rule-consistency issues.",
    )
    lint.add_argument(
        "--input",
        type=Path,
        help="Path to a JSON file. If omitted, read JSON from stdin.",
    )
    lint.add_argument(
        "--conversation",
        type=Path,
        help="Optional path to the source conversation transcript for heuristic checks.",
    )
    lint.add_argument(
        "--json",
        action="store_true",
        help="Print the lint result as JSON.",
    )
    lint.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 1 when lint reports any issue.",
    )

    review = subparsers.add_parser(
        "review",
        help="Prepare or validate a second-pass LLM review for a capture.",
    )
    review.add_argument(
        "--input",
        type=Path,
        help="Path to the capture JSON. If omitted, read the capture JSON from stdin.",
    )
    review.add_argument(
        "--conversation",
        type=Path,
        help="Path to the source conversation transcript. Required when rendering a review prompt.",
    )
    review.add_argument(
        "--response",
        type=Path,
        help="Path to an LLM review JSON response. If omitted, print a review prompt instead.",
    )
    review.add_argument(
        "--json",
        action="store_true",
        help="Print validated review output as normalized JSON.",
    )
    return parser


def read_input(input_path: Path | None) -> str:
    if input_path is None:
        return decode_utf8(sys.stdin.buffer.read(), "stdin")
    return read_text_file(input_path)


def cmd_capture(args: argparse.Namespace) -> int:
    raw = read_input(args.input)
    entry = KnowledgeEntry.from_json(raw)
    block_count = validate_block_limit(entry.body_markdown)
    if args.strict_lint:
        conversation = None
        if args.conversation:
            conversation = read_text_file(args.conversation)
        result = lint_entry(entry, conversation=conversation)
        if not result.ok:
            print(format_lint_result(result), file=sys.stderr)
            return 1
    if args.dry_run:
        payload = {
            "properties": build_properties(entry, args.status),
            "children": markdown_to_blocks(entry.body_markdown),
            "block_count": block_count,
            "block_limit_warning": block_count >= BLOCK_WARNING_THRESHOLD,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    settings = Settings.load(args.env_file)
    client = NotionClient(settings.notion_token)
    response = client.create_page(settings.notion_database_id, entry, args.status)
    print(
        json.dumps(
            {
                "id": response.get("id"),
                "url": response.get("url"),
                "title": entry.title,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def cmd_bootstrap_notion(args: argparse.Namespace) -> int:
    settings = Settings.load(args.env_file)
    client = NotionClient(settings.notion_token)
    current = client.retrieve_database(settings.notion_database_id)
    patch = build_schema_patch(current.get("properties", {}))
    schema = {"properties": patch}
    if args.dry_run:
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        return 0
    if not patch:
        response = current
        changed = False
    else:
        response = client.update_database_schema(settings.notion_database_id, patch)
        changed = True

    refreshed = client.retrieve_database(settings.notion_database_id)
    migrated_pages = backfill_model_property(client, settings.notion_database_id)
    cleanup_patch = cleanup_legacy_model_properties(refreshed.get("properties", {}))
    if cleanup_patch:
        refreshed = client.update_database_schema(settings.notion_database_id, cleanup_patch)
        changed = True

    print(
        json.dumps(
            {
                "id": refreshed.get("id"),
                "title": refreshed.get("title"),
                "properties": sorted(refreshed.get("properties", {}).keys()),
                "changed": changed,
                "migrated_pages": migrated_pages,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def cmd_inspect_notion(args: argparse.Namespace) -> int:
    settings = Settings.load(args.env_file)
    client = NotionClient(settings.notion_token)
    response = client.retrieve_database(settings.notion_database_id)
    properties = {
        name: meta.get("type") for name, meta in response.get("properties", {}).items()
    }
    print(json.dumps(properties, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def doctor_result(args: argparse.Namespace) -> dict[str, object]:
    env_path = args.env_file or default_env_path()
    python_version = ".".join(str(part) for part in sys.version_info[:3])
    python_ok = sys.version_info >= MIN_PYTHON
    uv_path = shutil.which("uv")
    env_exists = env_path.exists()

    missing_env: list[str] = []
    settings_ok = True
    try:
        Settings.load(args.env_file)
    except ValueError as exc:
        settings_ok = False
        text = str(exc)
        marker = "Missing required environment variables:"
        if marker in text:
            missing = text.split(marker, 1)[1].strip()
            missing_env = [item.strip() for item in missing.split(",") if item.strip()]

    return {
        "ok": python_ok and settings_ok,
        "frederica_home": str(frederica_home()),
        "env_file": str(env_path),
        "checks": {
            "python": {
                "ok": python_ok,
                "version": python_version,
                "required": ">=" + ".".join(str(part) for part in MIN_PYTHON),
            },
            "uv": {
                "ok": uv_path is not None,
                "path": uv_path or "",
            },
            "env_file": {
                "ok": env_exists,
                "path": str(env_path),
            },
            "notion_config": {
                "ok": settings_ok,
                "missing": missing_env,
            },
        },
    }


def format_doctor_result(result: dict[str, object]) -> str:
    checks = result["checks"]
    assert isinstance(checks, dict)
    python_check = checks["python"]
    uv_check = checks["uv"]
    env_check = checks["env_file"]
    notion_check = checks["notion_config"]
    assert isinstance(python_check, dict)
    assert isinstance(uv_check, dict)
    assert isinstance(env_check, dict)
    assert isinstance(notion_check, dict)

    lines = [
        f"Frederica home: {result['frederica_home']}",
        f"Config file: {result['env_file']}",
        f"[{'ok' if python_check['ok'] else 'missing'}] Python {python_check['version']} (required {python_check['required']})",
        f"[{'ok' if uv_check['ok'] else 'missing'}] uv {uv_check['path'] or 'not found'}",
        f"[{'ok' if env_check['ok'] else 'missing'}] env file {env_check['path']}",
    ]
    missing = notion_check.get("missing", [])
    if notion_check["ok"]:
        lines.append("[ok] Notion config is complete")
    else:
        lines.append(
            "[missing] Notion config missing: " + ", ".join(missing) if missing else "[missing] Notion config is incomplete"
        )
        lines.append(
            "Next step: create or update ~/.frederica/config/.env, or provide an explicit --env-file path before capture."
        )
    return "\n".join(lines)


def cmd_doctor(args: argparse.Namespace) -> int:
    result = doctor_result(args)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_doctor_result(result))
    return 0 if result["ok"] else 1


def cmd_render_prompt(args: argparse.Namespace) -> int:
    print(
        render_capture_prompt(
            source_tool=args.source_tool,
            include_example=args.include_example,
        )
    )
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    raw = read_input(args.input)
    entry = KnowledgeEntry.from_json(raw)
    conversation = None
    if args.conversation:
        conversation = read_text_file(args.conversation)
    result = lint_entry(entry, conversation=conversation)
    if args.json:
        print(result_as_json(result))
    else:
        print(format_lint_result(result))
    if args.strict and not result.ok:
        return 1
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    raw = read_input(args.input)
    entry = KnowledgeEntry.from_json(raw)

    if args.response:
        review_raw = read_text_file(args.response)
        result = parse_review_result(review_raw)
        if args.json:
            print(review_result_as_json(result))
        else:
            print(format_review_result(result))
        return 0

    if not args.conversation:
        raise ValueError("--conversation is required when rendering a review prompt")

    conversation = read_text_file(args.conversation)
    lint_result = lint_entry(entry, conversation=conversation)
    print(render_review_prompt(entry, conversation=conversation, lint_result=lint_result))
    return 0


def main() -> None:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "capture":
            raise SystemExit(cmd_capture(args))
        if args.command == "bootstrap-notion":
            raise SystemExit(cmd_bootstrap_notion(args))
        if args.command == "inspect-notion":
            raise SystemExit(cmd_inspect_notion(args))
        if args.command == "doctor":
            raise SystemExit(cmd_doctor(args))
        if args.command == "render-prompt":
            raise SystemExit(cmd_render_prompt(args))
        if args.command == "lint":
            raise SystemExit(cmd_lint(args))
        if args.command == "review":
            raise SystemExit(cmd_review(args))
        raise SystemExit(f"Unknown command: {args.command}")
    except (ValueError, FileNotFoundError, NotionError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
