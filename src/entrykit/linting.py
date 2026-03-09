from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from entrykit.models import KnowledgeEntry


@dataclass(frozen=True)
class LintIssue:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class LintResult:
    issues: list[LintIssue]

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def ok(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "issues": [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _dominant_language(text: str) -> str:
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_words = len(re.findall(r"[A-Za-z]{2,}", text))
    if cjk_chars >= max(20, latin_words):
        return "zh"
    if latin_words >= max(20, cjk_chars * 2):
        return "en"
    return "mixed"


def _visible_metadata(conversation: str) -> dict[str, str]:
    metadata: dict[str, str] = {}

    tool_match = re.search(r"OpenAI Codex\s+\((v[^)]+)\)", conversation)
    if tool_match:
        metadata["tool_version"] = tool_match.group(1).strip()

    model_match = re.search(r"Model:\s*([^\n]+)", conversation)
    if model_match:
        model_text = model_match.group(1).strip()
        label_match = re.match(r"([A-Za-z0-9_.\- ]+?)(?:\s*\(|$)", model_text)
        if label_match:
            metadata["model"] = label_match.group(1).strip()
        reasoning_match = re.search(r"reasoning\s+([a-z-]+)", model_text, re.IGNORECASE)
        if reasoning_match:
            metadata["thinking_mode"] = reasoning_match.group(1).lower()

    session_match = re.search(r"Session:\s*([A-Za-z0-9-]+)", conversation)
    if session_match:
        metadata["session_id"] = session_match.group(1).strip()

    return metadata


def _looks_like_provider_inference(conversation: str, model: str | None) -> bool:
    if not model:
        return False
    lower = conversation.lower()
    has_tier = "tier:" in lower or "plan" in lower or "google one ai pro" in lower
    has_explicit_model = bool(re.search(r"^\s*Model:\s*", conversation, re.MULTILINE))
    return has_tier and not has_explicit_model


def _asks_for_detailed_capture(conversation: str) -> bool:
    markers = [
        "事无巨细",
        "详细",
        "全过程",
        "完整踩坑",
        "exhaustive",
        "step-by-step",
        "detailed",
        "full sequence",
    ]
    lower = conversation.lower()
    return any(marker in conversation or marker in lower for marker in markers)


def _is_too_short_for_detailed_request(entry: KnowledgeEntry) -> bool:
    return len(entry.body_markdown) < 800


def _likely_under_covers_session(entry: KnowledgeEntry, conversation: str) -> bool:
    return len(conversation) > 6000 and len(entry.body_markdown) < 1500


def lint_entry(entry: KnowledgeEntry, conversation: str | None = None) -> LintResult:
    issues: list[LintIssue] = []

    if conversation:
        metadata = _visible_metadata(conversation)
        dominant_language = _dominant_language(conversation)
        combined_written = "\n".join([entry.title, entry.summary, entry.body_markdown])
        written_language = _dominant_language(combined_written)

        if dominant_language == "zh" and not _contains_cjk(combined_written):
            issues.append(
                LintIssue(
                    severity="error",
                    code="language-mismatch",
                    message=(
                        "Conversation appears Chinese-dominant, but title/summary/body do not "
                        "contain Chinese text."
                    ),
                )
            )
        elif dominant_language == "en" and not re.search(r"[A-Za-z]{2,}", combined_written):
            issues.append(
                LintIssue(
                    severity="error",
                    code="language-mismatch",
                    message=(
                        "Conversation appears English-dominant, but title/summary/body do not "
                        "contain enough English text."
                    ),
                )
            )

        if dominant_language in {"zh", "en"} and written_language not in {
            dominant_language,
            "mixed",
        }:
            issues.append(
                LintIssue(
                    severity="error",
                    code="language-mismatch",
                    message=(
                        f"Conversation appears to be {dominant_language}, but title/summary/body "
                        f"look {written_language}."
                    ),
                )
            )

        visible_model = metadata.get("model")
        if visible_model:
            if not entry.model:
                issues.append(
                    LintIssue(
                        severity="warning",
                        code="missing-visible-model",
                        message=f"Visible model `{visible_model}` was not copied into `model`.",
                    )
                )
            elif entry.model.strip() != visible_model:
                issues.append(
                    LintIssue(
                        severity="error",
                        code="model-mismatch",
                        message=(
                            f"`model` is `{entry.model}` but visible metadata shows `{visible_model}`."
                        ),
                    )
                )
        elif _looks_like_provider_inference(conversation, entry.model):
            issues.append(
                LintIssue(
                    severity="warning",
                    code="model-may-be-inferred",
                    message=(
                        "`model` is set even though the conversation shows provider/tier metadata "
                        "without an explicit model string."
                    ),
                )
            )

        visible_tool_version = metadata.get("tool_version")
        if visible_tool_version:
            if not entry.tool_version:
                issues.append(
                    LintIssue(
                        severity="warning",
                        code="missing-visible-tool-version",
                        message=(
                            f"Visible tool version `{visible_tool_version}` was not copied into `tool_version`."
                        ),
                    )
                )
            elif entry.tool_version.strip() != visible_tool_version:
                issues.append(
                    LintIssue(
                        severity="error",
                        code="tool-version-mismatch",
                        message=(
                            f"`tool_version` is `{entry.tool_version}` but visible metadata shows "
                            f"`{visible_tool_version}`."
                        ),
                    )
                )

        visible_session_id = metadata.get("session_id")
        if visible_session_id:
            if not entry.session_id:
                issues.append(
                    LintIssue(
                        severity="warning",
                        code="missing-visible-session-id",
                        message=(
                            f"Visible session id `{visible_session_id}` was not copied into `session_id`."
                        ),
                    )
                )
            elif entry.session_id.strip() != visible_session_id:
                issues.append(
                    LintIssue(
                        severity="error",
                        code="session-id-mismatch",
                        message=(
                            f"`session_id` is `{entry.session_id}` but visible metadata shows "
                            f"`{visible_session_id}`."
                        ),
                    )
                )

        visible_thinking = metadata.get("thinking_mode")
        if visible_thinking and entry.thinking_mode != visible_thinking:
            issues.append(
                LintIssue(
                    severity="error",
                    code="thinking-mode-mismatch",
                    message=(
                        f"`thinking_mode` is `{entry.thinking_mode}` but visible metadata shows "
                        f"`{visible_thinking}`."
                    ),
                )
            )

        if _asks_for_detailed_capture(conversation) and _is_too_short_for_detailed_request(entry):
            issues.append(
                LintIssue(
                    severity="warning",
                    code="detail-mismatch",
                    message=(
                        "The conversation appears to ask for a detailed or exhaustive capture, "
                        "but `body_markdown` is still relatively short."
                    ),
                )
            )

        if _likely_under_covers_session(entry, conversation):
            issues.append(
                LintIssue(
                    severity="warning",
                    code="possible-partial-session-summary",
                    message=(
                        "The source conversation is long, but the capture body is short enough "
                        "that it may only cover a recent slice instead of the full session."
                    ),
                )
            )

        if dominant_language == "zh" and not _contains_cjk(entry.body_markdown):
            issues.append(
                LintIssue(
                    severity="error",
                    code="body-language-mismatch",
                    message="The conversation looks Chinese-dominant, but `body_markdown` contains no Chinese text.",
                )
            )

    return LintResult(issues=issues)


def format_lint_result(result: LintResult) -> str:
    if result.ok:
        return "Lint passed with no issues."

    lines = [
        f"Lint found {result.error_count} error(s) and {result.warning_count} warning(s)."
    ]
    for issue in result.issues:
        lines.append(f"[{issue.severity}] {issue.code}: {issue.message}")
    return "\n".join(lines)


def result_as_json(result: LintResult) -> str:
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
