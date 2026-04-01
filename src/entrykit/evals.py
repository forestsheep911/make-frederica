from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_FREDERICA_COVERAGE = {
    "notion_capture",
    "language_and_metadata",
    "block_budget",
    "fast_path_preflight",
    "explicit_backend_override",
    "save_intent_with_screen_default",
    "post_save_default_followup",
    "config_local_markdown",
    "config_notion_secret",
    "first_time_backend_setup",
    "explicit_screen_override",
    "post_save_default_followup_local_markdown",
    "obsidian_planned_backend",
    "note_reading",
}


@dataclass(frozen=True)
class SkillEval:
    eval_id: int
    prompt: str
    expected_output: str
    files: list[str]
    covers: list[str]


@dataclass(frozen=True)
class EvalSuite:
    skill_name: str
    evals: list[SkillEval]


def load_eval_suite(path: Path) -> EvalSuite:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid eval JSON in `{path}`: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Eval file `{path}` must contain a JSON object.")

    skill_name = str(payload.get("skill_name", "")).strip()
    if not skill_name:
        raise ValueError(f"Eval file `{path}` is missing `skill_name`.")

    raw_evals = payload.get("evals")
    if not isinstance(raw_evals, list) or not raw_evals:
        raise ValueError(f"Eval file `{path}` must contain a non-empty `evals` array.")

    evals: list[SkillEval] = []
    seen_ids: set[int] = set()
    for index, raw_eval in enumerate(raw_evals, start=1):
        if not isinstance(raw_eval, dict):
            raise ValueError(f"Eval #{index} in `{path}` must be a JSON object.")
        eval_id = raw_eval.get("id")
        if not isinstance(eval_id, int):
            raise ValueError(f"Eval #{index} in `{path}` must have an integer `id`.")
        if eval_id in seen_ids:
            raise ValueError(f"Eval file `{path}` contains duplicate id `{eval_id}`.")
        seen_ids.add(eval_id)

        prompt = str(raw_eval.get("prompt", "")).strip()
        expected_output = str(raw_eval.get("expected_output", "")).strip()
        if not prompt:
            raise ValueError(f"Eval id `{eval_id}` in `{path}` is missing `prompt`.")
        if not expected_output:
            raise ValueError(f"Eval id `{eval_id}` in `{path}` is missing `expected_output`.")

        files = raw_eval.get("files", [])
        if not isinstance(files, list) or any(not isinstance(item, str) for item in files):
            raise ValueError(f"Eval id `{eval_id}` in `{path}` must have `files` as a list of strings.")

        covers = raw_eval.get("covers", [])
        if not isinstance(covers, list) or any(not isinstance(item, str) or not item.strip() for item in covers):
            raise ValueError(f"Eval id `{eval_id}` in `{path}` must have `covers` as a list of non-empty strings.")

        evals.append(
            SkillEval(
                eval_id=eval_id,
                prompt=prompt,
                expected_output=expected_output,
                files=files,
                covers=[item.strip() for item in covers],
            )
        )

    return EvalSuite(skill_name=skill_name, evals=evals)


def validate_eval_suite(suite: EvalSuite) -> dict[str, Any]:
    coverage = sorted({item for eval_item in suite.evals for item in eval_item.covers})
    missing_coverage: list[str] = []
    if suite.skill_name == "frederica":
        missing_coverage = sorted(REQUIRED_FREDERICA_COVERAGE - set(coverage))

    return {
        "ok": not missing_coverage,
        "skill_name": suite.skill_name,
        "eval_count": len(suite.evals),
        "coverage": coverage,
        "missing_coverage": missing_coverage,
    }


def result_as_text(result: dict[str, Any]) -> str:
    lines = [
        f"Skill: {result['skill_name']}",
        f"Evals: {result['eval_count']}",
        "Coverage: " + (", ".join(result["coverage"]) if result["coverage"] else "none"),
    ]
    if result["missing_coverage"]:
        lines.append("Missing coverage: " + ", ".join(result["missing_coverage"]))
    else:
        lines.append("Missing coverage: none")
    return "\n".join(lines)
