from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from entrykit.config import (
    Settings,
    TargetSettings,
    default_env_path,
    expand_config_path,
    frederica_home,
    legacy_env_path,
    write_notion_env,
)
from entrykit.evals import load_eval_suite, result_as_text, validate_eval_suite
from entrykit.linting import format_lint_result, lint_entry, result_as_json
from entrykit.local_markdown import build_output_path, render_markdown_entry, write_markdown_entry
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
from entrykit.scenarios import load_scenario_suite, run_scenario_suite, scenario_result_as_text


MIN_PYTHON = (3, 10)
UTF16_BOMS = (
    b"\xff\xfe",
    b"\xfe\xff",
    b"\xff\xfe\x00\x00",
    b"\x00\x00\xfe\xff",
)


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
        powershell_hint = (
            "On Windows PowerShell, prefer a UTF-8 file plus `--input`, and if you create the file "
            "in PowerShell use `Set-Content -Encoding utf8`. If piping is unavoidable, set "
            "`[Console]::InputEncoding` / `[Console]::OutputEncoding` to UTF-8 together with "
            "`PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` before retrying."
        )
        if raw.startswith(UTF16_BOMS) or b"\x00" in raw[:32]:
            raise ValueError(f"{source} appears to be UTF-16 or UTF-32 encoded. {powershell_hint}") from exc
        raise ValueError(
            f"{source} must be UTF-8 encoded. {powershell_hint}"
        ) from exc


def read_text_file(path: Path) -> str:
    return decode_utf8(path.read_bytes(), f"Input file `{path}`")


def obsidian_capture_error(targets: TargetSettings) -> ValueError:
    folder = targets.obsidian.folder or "(root)"
    if targets.obsidian.enabled:
        details = (
            f"Configured vault: {targets.obsidian.vault_path or 'not set'}; "
            f"folder: {folder}."
        )
    else:
        details = "The obsidian backend is not enabled in ~/.frederica/config/targets.json."
    return ValueError(
        "Output target `obsidian` is not implemented for capture yet. "
        f"{details} Configure the path now if you want, then use `notion` or `local_markdown` for this capture."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="entrykit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser(
        "capture",
        help="Validate a capture payload and route it to the resolved output target.",
    )
    capture.add_argument(
        "--input",
        type=Path,
        help="Path to a JSON file. If omitted, read JSON from stdin.",
    )
    capture.add_argument(
        "--env-file",
        type=Path,
        help="Path to a .env file when the resolved backend is notion.",
    )
    capture.add_argument(
        "--output",
        choices=["screen", "notion", "obsidian", "local_markdown"],
        help="Explicit output target for this run. Overrides default_output.",
    )
    capture.add_argument(
        "--status",
        default="Captured",
        help="Value written to the Notion Status select property.",
    )
    capture.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate input and print the derived output payload without writing.",
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
        help="Optional explicit .env path. Defaults to ~/.frederica/config/.env.",
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
        help="Optional explicit .env path. Defaults to ~/.frederica/config/.env.",
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

    config = subparsers.add_parser(
        "config",
        help="Show or modify frederica runtime configuration under ~/.frederica/config.",
    )
    config_subparsers = config.add_subparsers(dest="config_command", required=True)

    config_show = config_subparsers.add_parser(
        "show",
        help="Print the current frederica config and backend status.",
    )
    config_show.add_argument(
        "--json",
        action="store_true",
        help="Print the config view as JSON.",
    )

    config_set_default = config_subparsers.add_parser(
        "set-default",
        help="Set default_output in ~/.frederica/config/targets.json.",
    )
    config_set_default.add_argument(
        "output",
        choices=["screen", "notion", "obsidian", "local_markdown"],
        help="New default output target.",
    )

    config_set_notion = config_subparsers.add_parser(
        "set-notion",
        help="Update notion backend settings in targets.json.",
    )
    config_set_notion.add_argument("--env-file", type=str, help="Env file path for notion credentials.")
    config_set_notion.add_argument("--enable", action="store_true", help="Enable notion as a configured backend.")
    config_set_notion.add_argument("--disable", action="store_true", help="Disable notion as a configured backend.")

    config_set_notion_secret = config_subparsers.add_parser(
        "set-notion-secret",
        help="Write notion secrets into the selected env file.",
    )
    config_set_notion_secret.add_argument("--token", help="NOTION_TOKEN value.")
    config_set_notion_secret.add_argument("--database-id", help="NOTION_DATABASE_ID value.")
    config_set_notion_secret.add_argument("--env-file", type=str, help="Explicit env file path.")

    config_set_obsidian = config_subparsers.add_parser(
        "set-obsidian",
        help="Update obsidian backend settings in targets.json.",
    )
    config_set_obsidian.add_argument("--vault-path", help="Obsidian vault path.")
    config_set_obsidian.add_argument("--folder", help="Folder inside the vault.")
    config_set_obsidian.add_argument("--enable", action="store_true", help="Enable obsidian as a configured backend.")
    config_set_obsidian.add_argument("--disable", action="store_true", help="Disable obsidian as a configured backend.")

    config_set_markdown = config_subparsers.add_parser(
        "set-local-markdown",
        help="Update local_markdown backend settings in targets.json.",
    )
    config_set_markdown.add_argument("--output-dir", help="Filesystem output directory for markdown notes.")
    config_set_markdown.add_argument("--enable", action="store_true", help="Enable local_markdown as a configured backend.")
    config_set_markdown.add_argument("--disable", action="store_true", help="Disable local_markdown as a configured backend.")

    config_cleanup_legacy = config_subparsers.add_parser(
        "cleanup-legacy",
        help="Remove obsolete legacy entrykit config files that frederica no longer uses.",
    )
    config_cleanup_legacy.add_argument(
        "--dry-run",
        action="store_true",
        help="Print which obsolete files would be removed without deleting them.",
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

    check_evals = subparsers.add_parser(
        "check-evals",
        help="Validate a skill eval file and report coverage gaps.",
    )
    check_evals.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to an evals.json file.",
    )
    check_evals.add_argument(
        "--json",
        action="store_true",
        help="Print the eval validation result as JSON.",
    )

    check_scenarios = subparsers.add_parser(
        "check-scenarios",
        help="Run a suite of simulated local-environment scenarios against entrykit.",
    )
    check_scenarios.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to a scenarios.json file.",
    )
    check_scenarios.add_argument(
        "--json",
        action="store_true",
        help="Print the scenario results as JSON.",
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
    targets = TargetSettings.load()
    output = args.output or targets.default_output
    if args.strict_lint:
        conversation = None
        if args.conversation:
            conversation = read_text_file(args.conversation)
        result = lint_entry(entry, conversation=conversation)
        if not result.ok:
            print(format_lint_result(result), file=sys.stderr)
            return 1
    if output == "screen":
        payload = {
            "target": output,
            "entry": entry.to_dict(),
            "block_count": block_count,
            "block_limit_warning": block_count >= BLOCK_WARNING_THRESHOLD,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.dry_run:
        if output == "notion":
            payload = {
                "target": output,
                "properties": build_properties(entry, args.status),
                "children": markdown_to_blocks(entry.body_markdown),
                "block_count": block_count,
                "block_limit_warning": block_count >= BLOCK_WARNING_THRESHOLD,
            }
        elif output == "local_markdown":
            markdown_dir = Path(targets.local_markdown.output_dir).expanduser()
            payload = {
                "target": output,
                "output_path": str(build_output_path(entry, markdown_dir)),
                "content": render_markdown_entry(entry),
                "block_count": block_count,
                "block_limit_warning": block_count >= BLOCK_WARNING_THRESHOLD,
            }
        elif output == "obsidian":
            raise obsidian_capture_error(targets)
        else:
            raise ValueError(f"Output target `{output}` is not implemented for capture yet.")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if output == "notion":
        env_path = args.env_file or targets.notion.env_file or default_env_path()
        settings = Settings.load(env_path)
        client = NotionClient(settings.notion_token)
        response = client.create_page(settings.notion_database_id, entry, args.status)
        print(
            json.dumps(
                {
                    "target": output,
                    "id": response.get("id"),
                    "url": response.get("url"),
                    "title": entry.title,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if output == "local_markdown":
        output_dir = targets.local_markdown.output_dir
        if not targets.local_markdown.enabled:
            raise ValueError("Output target `local_markdown` is disabled in ~/.frederica/config/targets.json.")
        if not output_dir:
            raise ValueError("Output target `local_markdown` requires a configured output_dir.")
        path = write_markdown_entry(entry, Path(output_dir).expanduser())
        print(
            json.dumps(
                {
                    "target": output,
                    "path": str(path),
                    "title": entry.title,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if output == "obsidian":
        raise obsidian_capture_error(targets)

    raise ValueError(f"Output target `{output}` is not implemented for capture yet.")


def cmd_bootstrap_notion(args: argparse.Namespace) -> int:
    settings = Settings.load(args.env_file or default_env_path())
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
    settings = Settings.load(args.env_file or default_env_path())
    client = NotionClient(settings.notion_token)
    response = client.retrieve_database(settings.notion_database_id)
    properties = {
        name: meta.get("type") for name, meta in response.get("properties", {}).items()
    }
    print(json.dumps(properties, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def doctor_result(args: argparse.Namespace) -> dict[str, object]:
    python_version = ".".join(str(part) for part in sys.version_info[:3])
    python_ok = sys.version_info >= MIN_PYTHON
    uv_path = shutil.which("uv")
    targets = TargetSettings.load()

    notion_env_path = args.env_file or targets.notion.env_file or default_env_path()
    env_exists = notion_env_path.exists()
    legacy_path = legacy_env_path()
    legacy_exists = legacy_path.exists()

    missing_env: list[str] = []
    notion_ready = False
    try:
        Settings.load(notion_env_path)
        notion_ready = True
    except ValueError as exc:
        text = str(exc)
        marker = "Missing required environment variables:"
        if marker in text:
            missing = text.split(marker, 1)[1].strip()
            missing_env = [item.strip() for item in missing.split(",") if item.strip()]

    obsidian_vault = targets.obsidian.vault_path
    obsidian_vault_exists = Path(obsidian_vault).expanduser().is_dir() if obsidian_vault else False
    obsidian_ready = targets.obsidian.enabled and bool(obsidian_vault) and obsidian_vault_exists

    markdown_output_dir = targets.local_markdown.output_dir
    markdown_dir = Path(markdown_output_dir).expanduser() if markdown_output_dir else None
    markdown_parent_exists = False
    if markdown_dir is not None:
        markdown_parent_exists = markdown_dir.is_dir() or markdown_dir.parent.is_dir()
    markdown_ready = targets.local_markdown.enabled and bool(markdown_output_dir) and markdown_parent_exists

    default_output_ok = {
        "screen": True,
        "notion": targets.notion.enabled and notion_ready,
        "obsidian": obsidian_ready,
        "local_markdown": markdown_ready,
    }[targets.default_output]

    return {
        "ok": python_ok and default_output_ok,
        "runtime_ok": python_ok,
        "frederica_home": str(frederica_home()),
        "default_output": targets.default_output,
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
            "targets": {
                "ok": targets.default_output in {"screen", "notion", "obsidian", "local_markdown"},
                "path": str(targets.source_path),
                "exists": targets.source_path.exists(),
                "default_output": targets.default_output,
            },
            "legacy": {
                "path": str(legacy_path),
                "exists": legacy_exists,
                "obsolete": True,
            },
            "backends": {
                "screen": {
                    "ok": True,
                },
                "notion": {
                    "enabled": targets.notion.enabled,
                    "ok": targets.notion.enabled and notion_ready,
                    "env_file": str(notion_env_path),
                    "env_file_exists": env_exists,
                    "missing": missing_env,
                },
                "obsidian": {
                    "enabled": targets.obsidian.enabled,
                    "ok": obsidian_ready,
                    "vault_path": obsidian_vault,
                    "vault_exists": obsidian_vault_exists,
                    "folder": targets.obsidian.folder,
                },
                "local_markdown": {
                    "enabled": targets.local_markdown.enabled,
                    "ok": markdown_ready,
                    "output_dir": markdown_output_dir,
                    "path_ready": markdown_parent_exists,
                },
            },
        },
    }


def format_doctor_result(result: dict[str, object]) -> str:
    checks = result["checks"]
    assert isinstance(checks, dict)
    python_check = checks["python"]
    uv_check = checks["uv"]
    targets_check = checks["targets"]
    legacy_check = checks["legacy"]
    backends_check = checks["backends"]
    assert isinstance(python_check, dict)
    assert isinstance(uv_check, dict)
    assert isinstance(targets_check, dict)
    assert isinstance(legacy_check, dict)
    assert isinstance(backends_check, dict)
    notion_check = backends_check["notion"]
    obsidian_check = backends_check["obsidian"]
    markdown_check = backends_check["local_markdown"]
    assert isinstance(notion_check, dict)
    assert isinstance(obsidian_check, dict)
    assert isinstance(markdown_check, dict)

    lines = [
        f"Frederica home: {result['frederica_home']}",
        f"Default output: {result['default_output']}",
        f"[{'ok' if python_check['ok'] else 'missing'}] Python {python_check['version']} (required {python_check['required']})",
        f"[{'ok' if uv_check['ok'] else 'missing'}] uv {uv_check['path'] or 'not found'}",
        (
            f"[{'ok' if targets_check['exists'] else 'default'}] targets config {targets_check['path']}"
            f" (default_output={targets_check['default_output']})"
        ),
        (
            f"[{'obsolete' if legacy_check['exists'] else 'ok'}] legacy config "
            f"{legacy_check['path']}"
            + (" (unused by current frederica)" if legacy_check["exists"] else " not present")
        ),
        (
            f"[{'ok' if notion_check['ok'] else 'missing'}] notion"
            f" enabled={notion_check['enabled']} env={notion_check['env_file']}"
        ),
        (
            f"[{'ok' if obsidian_check['ok'] else 'missing'}] obsidian"
            f" enabled={obsidian_check['enabled']} vault={obsidian_check['vault_path'] or 'not set'}"
        ),
        (
            f"[{'ok' if markdown_check['ok'] else 'missing'}] local_markdown"
            f" enabled={markdown_check['enabled']} output={markdown_check['output_dir'] or 'not set'}"
        ),
    ]
    missing = notion_check.get("missing", [])
    if notion_check["enabled"] and not notion_check["ok"]:
        lines.append(
            "[missing] Notion config missing: " + ", ".join(missing) if missing else "[missing] Notion config is incomplete"
        )
        lines.append(
            "Next step: create or update ~/.frederica/config/.env, or provide an explicit --env-file path before capture."
        )
    if legacy_check["exists"]:
        lines.append(
            "Next step: remove the obsolete legacy config with `entrykit config cleanup-legacy` if you no longer need it."
        )
    if obsidian_check["enabled"] and not obsidian_check["ok"]:
        lines.append("Next step: set a valid Obsidian vault_path in ~/.frederica/config/targets.json.")
    if markdown_check["enabled"] and not markdown_check["ok"]:
        lines.append("Next step: set a writable local_markdown output_dir in ~/.frederica/config/targets.json.")
    return "\n".join(lines)


def cmd_doctor(args: argparse.Namespace) -> int:
    result = doctor_result(args)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_doctor_result(result))
    return 0 if result["ok"] else 1


def _config_enable_value(args: argparse.Namespace) -> bool | None:
    if getattr(args, "enable", False) and getattr(args, "disable", False):
        raise ValueError("Use only one of --enable or --disable.")
    if getattr(args, "enable", False):
        return True
    if getattr(args, "disable", False):
        return False
    return None


def config_view() -> dict[str, object]:
    targets = TargetSettings.load()
    doctor_args = type("Args", (), {"env_file": None, "json": True})()
    status = doctor_result(doctor_args)
    return {
        "frederica_home": str(frederica_home()),
        "targets": targets.to_dict(),
        "legacy": {
            "path": str(legacy_env_path()),
            "exists": legacy_env_path().exists(),
            "obsolete": True,
        },
        "status": status,
    }


def cleanup_legacy_paths(*, dry_run: bool) -> list[Path]:
    removed: list[Path] = []
    legacy_path = legacy_env_path()
    removed_names: set[str] = set()
    if legacy_path.exists():
        removed.append(legacy_path)
        removed_names.add(legacy_path.name)
        if not dry_run:
            legacy_path.unlink()

    legacy_dir = legacy_path.parent
    remaining_entries = []
    if legacy_dir.exists():
        remaining_entries = [entry for entry in legacy_dir.iterdir() if entry.name not in removed_names]
    if legacy_dir.exists() and not remaining_entries:
        removed.append(legacy_dir)
        if not dry_run:
            legacy_dir.rmdir()

    return removed


def format_config_view(view: dict[str, object]) -> str:
    targets = view["targets"]
    legacy = view["legacy"]
    status = view["status"]
    assert isinstance(targets, dict)
    assert isinstance(legacy, dict)
    assert isinstance(status, dict)
    backends = targets.get("backends", {})
    assert isinstance(backends, dict)
    notion = backends.get("notion", {})
    obsidian = backends.get("obsidian", {})
    local_markdown = backends.get("local_markdown", {})
    assert isinstance(notion, dict)
    assert isinstance(obsidian, dict)
    assert isinstance(local_markdown, dict)

    lines = [
        f"Frederica home: {view['frederica_home']}",
        f"Default output: {targets.get('default_output', 'screen')}",
        "Configured backends:",
        f"- notion: enabled={notion.get('enabled', False)} env={notion.get('env_file', 'not set')}",
        (
            f"- obsidian: enabled={obsidian.get('enabled', False)} "
            f"vault={obsidian.get('vault_path', '') or 'not set'} folder={obsidian.get('folder', '') or '(root)'}"
        ),
        (
            f"- local_markdown: enabled={local_markdown.get('enabled', False)} "
            f"output={local_markdown.get('output_dir', '') or 'not set'}"
        ),
        (
            f"Legacy config: {legacy.get('path')} "
            + ("present" if legacy.get("exists") else "not present")
        ),
        "",
        "Doctor status:",
        format_doctor_result(status),
    ]
    return "\n".join(lines)


def cmd_config(args: argparse.Namespace) -> int:
    if args.config_command == "show":
        payload = config_view()
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(format_config_view(payload))
        return 0

    targets = TargetSettings.load()

    if args.config_command == "set-default":
        targets = targets.with_default_output(args.output)
        targets.save()
        print(f"Updated default_output to {args.output} in {targets.source_path}")
        return 0

    if args.config_command == "set-notion":
        env_file = None
        if args.env_file:
            env_file = expand_config_path(args.env_file)
        enabled = _config_enable_value(args)
        targets = targets.with_notion(enabled=enabled, env_file=env_file)
        targets.save()
        print(f"Updated notion backend in {targets.source_path}")
        return 0

    if args.config_command == "set-notion-secret":
        env_file = expand_config_path(args.env_file) if args.env_file else targets.notion.env_file
        if args.token is None and args.database_id is None:
            raise ValueError("Provide at least one of --token or --database-id.")
        write_notion_env(env_file, token=args.token, database_id=args.database_id)
        print(f"Updated notion secrets in {env_file}")
        return 0

    if args.config_command == "set-obsidian":
        enabled = _config_enable_value(args)
        targets = targets.with_obsidian(
            enabled=enabled,
            vault_path=args.vault_path,
            folder=args.folder,
        )
        targets.save()
        print(f"Updated obsidian backend in {targets.source_path}")
        return 0

    if args.config_command == "set-local-markdown":
        enabled = _config_enable_value(args)
        targets = targets.with_local_markdown(
            enabled=enabled,
            output_dir=args.output_dir,
        )
        targets.save()
        print(f"Updated local_markdown backend in {targets.source_path}")
        return 0

    if args.config_command == "cleanup-legacy":
        legacy_path = legacy_env_path()
        removed = cleanup_legacy_paths(dry_run=args.dry_run)
        if not removed:
            print(f"No obsolete legacy config found at {legacy_path}")
            return 0
        if args.dry_run:
            for path in removed:
                print(f"Would remove obsolete legacy config: {path}")
            return 0
        for path in removed:
            print(f"Removed obsolete legacy config: {path}")
        return 0

    raise ValueError(f"Unknown config command: {args.config_command}")


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


def cmd_check_evals(args: argparse.Namespace) -> int:
    suite = load_eval_suite(args.input)
    result = validate_eval_suite(suite)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result_as_text(result))
    return 0 if result["ok"] else 1


def cmd_check_scenarios(args: argparse.Namespace) -> int:
    suite = load_scenario_suite(args.input)
    result = run_scenario_suite(suite, repo_root=Path.cwd())
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(scenario_result_as_text(result))
    return 0 if result["ok"] else 1


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
        if args.command == "config":
            raise SystemExit(cmd_config(args))
        if args.command == "render-prompt":
            raise SystemExit(cmd_render_prompt(args))
        if args.command == "lint":
            raise SystemExit(cmd_lint(args))
        if args.command == "review":
            raise SystemExit(cmd_review(args))
        if args.command == "check-evals":
            raise SystemExit(cmd_check_evals(args))
        if args.command == "check-scenarios":
            raise SystemExit(cmd_check_scenarios(args))
        raise SystemExit(f"Unknown command: {args.command}")
    except (ValueError, FileNotFoundError, NotionError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
