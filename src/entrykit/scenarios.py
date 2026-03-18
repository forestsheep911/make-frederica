from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FakeBinary:
    name: str
    content: str


@dataclass(frozen=True)
class ScenarioExpectations:
    exit_code: int
    stdout_contains: list[str]
    stderr_contains: list[str]
    json_fields: dict[str, object]
    path_exists_from_json_field: str | None
    absent_paths: list[str]


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    argv: list[str]
    home_files: dict[str, str]
    env: dict[str, str]
    fake_bins: list[FakeBinary]
    path_mode: str
    input_json: dict[str, Any] | None
    input_text: str | None
    expectations: ScenarioExpectations


@dataclass(frozen=True)
class ScenarioSuite:
    suite_name: str
    scenarios: list[Scenario]


def load_scenario_suite(path: Path) -> ScenarioSuite:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid scenario JSON in `{path}`: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Scenario file `{path}` must contain a JSON object.")

    suite_name = str(payload.get("suite_name", "")).strip()
    if not suite_name:
        raise ValueError(f"Scenario file `{path}` is missing `suite_name`.")

    raw_scenarios = payload.get("scenarios")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise ValueError(f"Scenario file `{path}` must contain a non-empty `scenarios` array.")

    scenarios: list[Scenario] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_scenarios, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Scenario #{index} in `{path}` must be a JSON object.")
        scenario_id = str(item.get("id", "")).strip()
        if not scenario_id:
            raise ValueError(f"Scenario #{index} in `{path}` is missing `id`.")
        if scenario_id in seen_ids:
            raise ValueError(f"Scenario file `{path}` contains duplicate id `{scenario_id}`.")
        seen_ids.add(scenario_id)

        argv = item.get("argv")
        if not isinstance(argv, list) or any(not isinstance(arg, str) for arg in argv):
            raise ValueError(f"Scenario `{scenario_id}` in `{path}` must have `argv` as a list of strings.")

        home_files = item.get("home_files", {})
        if not isinstance(home_files, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in home_files.items()):
            raise ValueError(f"Scenario `{scenario_id}` in `{path}` must have `home_files` as a string map.")

        env = item.get("env", {})
        if not isinstance(env, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in env.items()):
            raise ValueError(f"Scenario `{scenario_id}` in `{path}` must have `env` as a string map.")

        path_mode = str(item.get("path_mode", "fake_only")).strip() or "fake_only"
        if path_mode not in {"fake_only", "inherit"}:
            raise ValueError(f"Scenario `{scenario_id}` in `{path}` has invalid path_mode `{path_mode}`.")

        raw_fake_bins = item.get("fake_bins", [])
        if not isinstance(raw_fake_bins, list):
            raise ValueError(f"Scenario `{scenario_id}` in `{path}` must have `fake_bins` as a list.")
        fake_bins: list[FakeBinary] = []
        for fake in raw_fake_bins:
            if not isinstance(fake, dict):
                raise ValueError(f"Scenario `{scenario_id}` in `{path}` has an invalid fake_bin entry.")
            name = str(fake.get("name", "")).strip()
            content = str(fake.get("content", ""))
            if not name:
                raise ValueError(f"Scenario `{scenario_id}` in `{path}` has a fake_bin without a name.")
            fake_bins.append(FakeBinary(name=name, content=content))

        input_json = item.get("input_json")
        if input_json is not None and not isinstance(input_json, dict):
            raise ValueError(f"Scenario `{scenario_id}` in `{path}` must have `input_json` as a JSON object.")
        input_text = item.get("input_text")
        if input_text is not None and not isinstance(input_text, str):
            raise ValueError(f"Scenario `{scenario_id}` in `{path}` must have `input_text` as a string.")

        expect = item.get("expect")
        if not isinstance(expect, dict):
            raise ValueError(f"Scenario `{scenario_id}` in `{path}` is missing `expect`.")

        expectations = ScenarioExpectations(
            exit_code=int(expect.get("exit_code", 0)),
            stdout_contains=_string_list(expect.get("stdout_contains", []), scenario_id, "stdout_contains"),
            stderr_contains=_string_list(expect.get("stderr_contains", []), scenario_id, "stderr_contains"),
            json_fields=_string_key_dict(expect.get("json_fields", {}), scenario_id, "json_fields"),
            path_exists_from_json_field=_optional_string(expect.get("path_exists_from_json_field"), scenario_id, "path_exists_from_json_field"),
            absent_paths=_string_list(expect.get("absent_paths", []), scenario_id, "absent_paths"),
        )

        scenarios.append(
            Scenario(
                scenario_id=scenario_id,
                argv=argv,
                home_files=home_files,
                env=env,
                fake_bins=fake_bins,
                path_mode=path_mode,
                input_json=input_json,
                input_text=input_text,
                expectations=expectations,
            )
        )

    return ScenarioSuite(suite_name=suite_name, scenarios=scenarios)


def _string_list(value: object, scenario_id: str, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"Scenario `{scenario_id}` must have `{field_name}` as a list of strings.")
    return list(value)


def _string_key_dict(value: object, scenario_id: str, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"Scenario `{scenario_id}` must have `{field_name}` as an object with string keys.")
    return dict(value)


def _optional_string(value: object, scenario_id: str, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Scenario `{scenario_id}` must have `{field_name}` as a string when present.")
    return value


def run_scenario_suite(suite: ScenarioSuite, *, repo_root: Path) -> dict[str, Any]:
    results = [run_scenario(scenario, repo_root=repo_root) for scenario in suite.scenarios]
    return {
        "ok": all(result["ok"] for result in results),
        "suite_name": suite.suite_name,
        "scenario_count": len(results),
        "results": results,
    }


def run_scenario(scenario: Scenario, *, repo_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        home = root / "home"
        home.mkdir(parents=True, exist_ok=True)
        bin_dir = root / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)

        input_path = None
        if scenario.input_json is not None:
            input_path = root / "input.json"
            input_path.write_text(json.dumps(scenario.input_json, ensure_ascii=False), encoding="utf-8")
        elif scenario.input_text is not None:
            input_path = root / "input.txt"
            input_path.write_text(scenario.input_text, encoding="utf-8")

        for relative_path, content in scenario.home_files.items():
            target = home / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(resolve_placeholder(content, home=home, input_path=input_path), encoding="utf-8")

        for fake in scenario.fake_bins:
            write_fake_binary(bin_dir, fake)

        argv = [resolve_placeholder(arg, home=home, input_path=input_path) for arg in scenario.argv]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo_root / "src")
        env["FREDERICA_HOME"] = str(home / ".frederica")
        env["PATH"] = str(bin_dir) if scenario.path_mode == "fake_only" else os.pathsep.join([str(bin_dir), env.get("PATH", "")])
        env.update({key: resolve_placeholder(value, home=home, input_path=input_path) for key, value in scenario.env.items()})

        process = subprocess.run(
            [sys.executable, "-m", "entrykit.cli", *argv],
            cwd=repo_root,
            text=True,
            capture_output=True,
            encoding="utf-8",
            env=env,
        )

        checks = evaluate_expectations(
            scenario,
            home=home,
            stdout=process.stdout,
            stderr=process.stderr,
            exit_code=process.returncode,
        )

        return {
            "id": scenario.scenario_id,
            "ok": all(check["ok"] for check in checks),
            "exit_code": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "checks": checks,
        }


def write_fake_binary(bin_dir: Path, fake: FakeBinary) -> None:
    if os.name == "nt":
        target = bin_dir / f"{fake.name}.cmd"
        target.write_text(fake.content or "@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    else:
        target = bin_dir / fake.name
        target.write_text(fake.content or "#!/bin/sh\nexit 0\n", encoding="utf-8")
        target.chmod(0o755)


def resolve_placeholder(value: str, *, home: Path, input_path: Path | None) -> str:
    result = value.replace("{home}", home.as_posix())
    if input_path is not None:
        result = result.replace("{input}", input_path.as_posix())
    return result


def evaluate_expectations(
    scenario: Scenario,
    *,
    home: Path,
    stdout: str,
    stderr: str,
    exit_code: int,
) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    expect = scenario.expectations

    checks.append(
        {
            "name": "exit_code",
            "ok": exit_code == expect.exit_code,
            "expected": expect.exit_code,
            "actual": exit_code,
        }
    )

    for text in expect.stdout_contains:
        checks.append({"name": f"stdout_contains:{text}", "ok": text in stdout})
    for text in expect.stderr_contains:
        checks.append({"name": f"stderr_contains:{text}", "ok": text in stderr})

    parsed_json: object | None = None
    if expect.json_fields or expect.path_exists_from_json_field:
        try:
            parsed_json = json.loads(stdout)
        except json.JSONDecodeError:
            checks.append(
                {
                    "name": "stdout_json_parse",
                    "ok": False,
                    "actual": stdout,
                }
            )
            return checks
        for dotted_key, expected_value in expect.json_fields.items():
            actual_value = get_json_field(parsed_json, dotted_key)
            checks.append(
                {
                    "name": f"json_field:{dotted_key}",
                    "ok": actual_value == expected_value,
                    "expected": expected_value,
                    "actual": actual_value,
                }
            )

    if expect.path_exists_from_json_field:
        assert parsed_json is not None
        path_value = get_json_field(parsed_json, expect.path_exists_from_json_field)
        checks.append(
            {
                "name": f"path_exists:{expect.path_exists_from_json_field}",
                "ok": isinstance(path_value, str) and Path(path_value).exists(),
                "actual": path_value,
            }
        )

    for relative_path in expect.absent_paths:
        checks.append(
            {
                "name": f"absent_path:{relative_path}",
                "ok": not (home / relative_path).exists(),
            }
        )

    return checks


def get_json_field(payload: object, dotted_key: str) -> object:
    current = payload
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def scenario_result_as_text(result: dict[str, Any]) -> str:
    lines = [
        f"Suite: {result['suite_name']}",
        f"Scenarios: {result['scenario_count']}",
    ]
    for scenario in result["results"]:
        status = "ok" if scenario["ok"] else "fail"
        lines.append(f"[{status}] {scenario['id']}")
        failed_checks = [check["name"] for check in scenario["checks"] if not check["ok"]]
        if failed_checks:
            lines.append("  failed: " + ", ".join(failed_checks))
    return "\n".join(lines)
