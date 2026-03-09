from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from entrykit.linting import LintResult, result_as_json
from entrykit.models import KnowledgeEntry

ALLOWED_REVIEW_RESULTS = {"pass", "uncertain", "major_issue"}
ALLOWED_REVIEW_SEVERITIES = {"warning", "error"}

REVIEW_PROMPT = """You are reviewing a proposed `KnowledgeEntry` before it is written to Notion.

This is a focused second-pass review, not a fresh summarization task.

Review only against these rules:
- Do not guess `tool_version`, `model`, or `session_id`. Only keep them when they are explicitly visible in the conversation.
- `title`, `summary`, and `body_markdown` must follow the dominant language of the conversation unless the user explicitly asked for another language.
- The capture should cover the whole current session unless the user explicitly narrowed the scope.
- The detail level should match the user's latest instruction. If the user asked for a detailed or exhaustive recap, the body should preserve the full sequence instead of compressing too much.
- Focus on the capture that is already written. Do not invent new facts that are not supported by the conversation.

Return JSON only. Do not wrap it in Markdown fences. Do not add explanation before or after the JSON.

Decision meanings:
- `pass`: acceptable as-is, maybe with minor polish only.
- `uncertain`: some issues or ambiguity exist, but a human could still choose to write this version.
- `major_issue`: important rule violations exist. In this case, include a fully revised `revised_entry`.

Response schema:
{response_schema}

Local heuristic lint findings to pay attention to:
{lint_result}

Proposed capture JSON:
<capture_json>
{entry_json}
</capture_json>

Source conversation:
<conversation>
{conversation}
</conversation>
"""


@dataclass(frozen=True)
class ReviewIssue:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class ReviewResult:
    result: str
    summary: str
    issues: list[ReviewIssue]
    suggested_changes: list[str]
    revised_entry: KnowledgeEntry | None

    @property
    def ok(self) -> bool:
        return self.result == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result,
            "summary": self.summary,
            "issues": [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
            "suggested_changes": self.suggested_changes,
            "revised_entry": None if self.revised_entry is None else self.revised_entry.to_dict(),
        }


def review_schema_snippet() -> str:
    schema = {
        "result": "uncertain",
        "summary": "The capture is mostly usable, but the model appears inferred and the language does not match the conversation.",
        "issues": [
            {
                "severity": "warning",
                "code": "model-may-be-inferred",
                "message": "The capture sets `model`, but the conversation does not show an explicit model string.",
            }
        ],
        "suggested_changes": [
            "Leave `model` empty because it was not explicitly visible.",
            "Rewrite `title`, `summary`, and `body_markdown` in Chinese.",
        ],
        "revised_entry": None,
    }
    return json.dumps(schema, ensure_ascii=False, indent=2)


def render_review_prompt(entry: KnowledgeEntry, conversation: str, lint_result: LintResult) -> str:
    entry_json = json.dumps(entry.to_dict(), indent=2, ensure_ascii=False)
    return REVIEW_PROMPT.format(
        response_schema=review_schema_snippet(),
        lint_result=result_as_json(lint_result),
        entry_json=entry_json,
        conversation=conversation.strip(),
    )


def parse_review_result(raw: str) -> ReviewResult:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid review JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Top-level review payload must be an object")

    result = str(payload.get("result", "")).strip()
    if result not in ALLOWED_REVIEW_RESULTS:
        allowed = ", ".join(sorted(ALLOWED_REVIEW_RESULTS))
        raise ValueError(f"review result must be one of: {allowed}")

    summary = str(payload.get("summary", "")).strip()
    if not summary:
        raise ValueError("review summary is required")

    raw_issues = payload.get("issues", [])
    if not isinstance(raw_issues, list):
        raise ValueError("review issues must be a list")

    issues: list[ReviewIssue] = []
    for item in raw_issues:
        if not isinstance(item, dict):
            raise ValueError("each review issue must be an object")
        severity = str(item.get("severity", "")).strip()
        if severity not in ALLOWED_REVIEW_SEVERITIES:
            allowed = ", ".join(sorted(ALLOWED_REVIEW_SEVERITIES))
            raise ValueError(f"review issue severity must be one of: {allowed}")
        code = str(item.get("code", "")).strip()
        message = str(item.get("message", "")).strip()
        if not code or not message:
            raise ValueError("each review issue must include non-empty code and message")
        issues.append(ReviewIssue(severity=severity, code=code, message=message))

    raw_changes = payload.get("suggested_changes", [])
    if not isinstance(raw_changes, list):
        raise ValueError("suggested_changes must be a list of strings")
    suggested_changes: list[str] = []
    for item in raw_changes:
        if not isinstance(item, str):
            raise ValueError("suggested_changes must be a list of strings")
        stripped = item.strip()
        if stripped:
            suggested_changes.append(stripped)

    revised_entry_payload = payload.get("revised_entry")
    revised_entry = None
    if revised_entry_payload is not None:
        if not isinstance(revised_entry_payload, dict):
            raise ValueError("revised_entry must be an object when present")
        revised_entry = KnowledgeEntry.from_dict(revised_entry_payload)

    if result == "major_issue" and revised_entry is None:
        raise ValueError("major_issue review results must include revised_entry")

    return ReviewResult(
        result=result,
        summary=summary,
        issues=issues,
        suggested_changes=suggested_changes,
        revised_entry=revised_entry,
    )


def format_review_result(result: ReviewResult) -> str:
    lines = [f"Review result: {result.result}", result.summary]
    if result.issues:
        lines.append("Issues:")
        for issue in result.issues:
            lines.append(f"- [{issue.severity}] {issue.code}: {issue.message}")
    if result.suggested_changes:
        lines.append("Suggested changes:")
        for change in result.suggested_changes:
            lines.append(f"- {change}")
    if result.revised_entry is not None:
        lines.append("A revised_entry is present in the review output.")
    return "\n".join(lines)


def review_result_as_json(result: ReviewResult) -> str:
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
