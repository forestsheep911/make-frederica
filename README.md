# make-frederica

`make-frederica` is the development and packaging repo for the `frederica` skill.

This repo is not the final end-user skill distribution repo. Its job is to help you design, test, package, and validate the skill and the supporting tooling around it.

Today that support layer is mainly `entrykit`, a small CLI for turning AI chat summaries into reusable notes and routing them toward the configured output target.

For machine-level use, `frederica` and `entrykit` should live under a dedicated user directory such as `~/.frederica` rather than inside whatever project directory happens to be open. This avoids dirtying unrelated git worktrees for a note-capture tool.

This repo focuses on three things:

- developing the `frederica` skill in a local, testable form
- maintaining `entrykit` as a supporting CLI for capture, lint, review, and backend-aware writes
- validating the contracts that will later be exported into a user-facing skills repository

## What it does

Main parts of the repo:

- `skills/frederica/`: development version of the skill
- `src/entrykit/`: supporting CLI and capture logic
- `tests/`: unit tests for the supporting tooling
- `scripts/`: build and install helpers for local development

The `entrykit` CLI currently provides these commands:

- `entrykit capture`: validate a capture payload and route it to the resolved output target
- `entrykit bootstrap-notion`: align a Notion database schema with the fields `entrykit` expects
- `entrykit inspect-notion`: print the current Notion database properties
- `entrykit doctor`: check local runtime prerequisites and Notion configuration
- `entrykit config ...`: show or update frederica config under `~/.frederica/config`
- `entrykit render-prompt`: print a reusable capture prompt for tools without native integration
- `entrykit report`: read notes from Notion and answer natural-language questions against saved notes
- `entrykit lint`: run schema and heuristic checks on a capture payload
- `entrykit review`: prepare or validate a second-pass review response for a capture
- `entrykit check-evals`: validate a skill eval file and report missing scenario coverage
- `entrykit check-scenarios`: run simulated local-environment scenarios against entrykit

## Install

### Local development use

```bash
PYTHONPATH=src python3 -m entrykit.cli --help
```

If you want the `entrykit` command on your machine for repeated local work, install it inside a virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
entrykit --help
```

### Standalone binary

```bash
./scripts/build_binary.sh
./dist/entrykit --help
```

On Windows, build the executable with PowerShell:

```powershell
.\scripts\build_binary_windows.ps1
.\dist\entrykit.exe --help
```

See [docs/install-and-build.md](docs/install-and-build.md) for local build details and [docs/global-install.md](docs/global-install.md) for machine-level installation during development.

## Configuration

For machine-level use, the default control-plane config lives under `~/.frederica/config/`.

- `targets.json`: default output target and backend-specific paths
- `.env`: Notion credentials when the selected backend is `notion`

For local repo development, you can still point commands at a repo-local file with `--env-file .env`.

For sensitive configuration such as `NOTION_TOKEN`, prefer editing the local config file directly. If a setup flow ever offers direct paste into chat, that should be treated as a less safe fallback rather than the recommended path.

The current output targets are:

- `screen`
- `notion`
- `local_markdown`

Planned future backend enhancements:

- `obsidian`

Minimal `targets.json` example:

```json
{
  "default_output": "screen",
  "backends": {
    "notion": {
      "enabled": false,
      "env_file": "~/.frederica/config/.env"
    },
    "obsidian": {
      "enabled": false,
      "vault_path": "",
      "folder": ""
    },
    "local_markdown": {
      "enabled": false,
      "output_dir": ""
    }
  }
}
```

Create a local `.env` file from the example if you are developing inside this repository:

```bash
cp .env.example .env
```

Required variables:

- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`

Do not commit `.env`. Only `.env.example` belongs in the repository.

## Quick start

Inspect the configured runtime and backend state with the supporting CLI:

```bash
entrykit doctor
```

`doctor` succeeds when Python is usable and the resolved `default_output` backend is ready. Missing `uv` is still reported, but only as an advisory signal.

Show the current frederica config:

```bash
entrykit config show
```

Update the default output:

```bash
entrykit config set-default notion
```

For first-time setup, the currently writable persistent targets are `notion` and `local_markdown`.

`obsidian` remains a planned future backend and is not part of the current released write targets.

If you use Obsidian today, configure `local_markdown.output_dir` to a folder inside your Obsidian vault. `entrykit` will write normal Markdown notes there, which Obsidian can use directly.

Enable local markdown output:

```bash
entrykit config set-local-markdown --enable --output-dir ~/notes/frederica
```

Then inspect the configured Notion database when `notion` is the resolved backend:

```bash
entrykit inspect-notion
```

Render a capture prompt:

```bash
entrykit render-prompt --source-tool codex --include-example
```

Validate a capture file without writing:

```bash
entrykit capture --input examples/coding-session.json --dry-run
```

Write a capture file to local markdown explicitly:

```bash
entrykit capture --input examples/coding-session.json --output local_markdown
```

Run lint checks:

```bash
entrykit lint --input examples/coding-session.json --strict
```

Prepare a review prompt:

```bash
entrykit review --input examples/coding-session.json --conversation conversation.txt
```

Ask a question directly against your Notion notes:

```bash
entrykit report --query "总结本周工作"
entrykit report --query "最近两周都做了些什么项目？"
entrykit report --query "make-frederica 现在进行得如何了"
entrykit report --query "make-frederica 有什么阻塞和下一步"
entrykit report --query "make-frederica 现在进行得如何了" --plan-only
entrykit report --query "最近两周都做了些什么项目？" --planner llm --plan-only
```

Planner modes:

- `--planner auto`: if `OPENAI_API_KEY` is configured, prefer the LLM planner and fall back to heuristics on planner failure
- `--planner heuristic`: skip the LLM planner and use local heuristics only
- `--planner llm`: require the OpenAI planner and fail if it is unavailable

Relevant environment variables for the LLM planner:

- `OPENAI_API_KEY`
- `ENTRYKIT_PLANNER_MODEL` (optional, defaults to `gpt-4o-mini`)
- `OPENAI_BASE_URL` (optional)
- `OPENAI_ORGANIZATION` (optional)
- `OPENAI_PROJECT` (optional)

The current read path is question-driven rather than report-template-driven: natural-language question -> normalized query schema -> live Notion retrieval -> rendered answer with source traces.

Validate the frederica eval suite:

```bash
entrykit check-evals --input skills/frederica/evals/evals.json
```

Run the frederica environment scenario suite:

```bash
entrykit check-scenarios --input skills/frederica/evals/scenarios.json
```

## Development

Run the test suite:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Project layout:

- [skills/frederica](skills/frederica): development skill files and examples
- [src/entrykit](src/entrykit): supporting CLI, models, linting, Notion integration, review helpers
- [tests](tests): unit tests
- [docs](docs): workflow and install notes
- [examples](examples): sample capture payloads
- [scripts](scripts): build and install helpers

## Repository role

Use this repo to make and verify the skill.

- Keep end-user distribution concerns separate from development concerns.
- Treat `entrykit` as supporting tooling, not as the entire product identity.
- Export polished skill contents later into a dedicated skills repo such as `my-skills`.

## Documentation

- [docs/install-and-build.md](docs/install-and-build.md)
- [docs/global-install.md](docs/global-install.md)
- [docs/lint.md](docs/lint.md)
- [docs/review.md](docs/review.md)
- [docs/cross-tool-workflow.md](docs/cross-tool-workflow.md)

## License

MIT. See [LICENSE](LICENSE).
