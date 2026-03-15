# make-frederica

`make-frederica` is the development and packaging repo for the `frederica` skill.

This repo is not the final end-user skill distribution repo. Its job is to help you design, test, package, and validate the skill and the supporting tooling around it.

Today that support layer is mainly `entrykit`, a small CLI for turning AI chat summaries into structured Notion knowledge entries.

For machine-level use, `frederica` and `entrykit` should live under a dedicated user directory such as `~/.frederica` rather than inside whatever project directory happens to be open. This avoids dirtying unrelated git worktrees for a note-capture tool.

This repo focuses on three things:

- developing the `frederica` skill in a local, testable form
- maintaining `entrykit` as a supporting CLI for capture, lint, review, and Notion writes
- validating the contracts that will later be exported into a user-facing skills repository

## What it does

Main parts of the repo:

- `skills/frederica/`: development version of the skill
- `src/entrykit/`: supporting CLI and capture logic
- `tests/`: unit tests for the supporting tooling
- `scripts/`: build and install helpers for local development

The `entrykit` CLI currently provides these commands:

- `entrykit capture`: validate a capture payload and write it to Notion
- `entrykit bootstrap-notion`: align a Notion database schema with the fields `entrykit` expects
- `entrykit inspect-notion`: print the current Notion database properties
- `entrykit doctor`: check local runtime prerequisites and Notion configuration
- `entrykit render-prompt`: print a reusable capture prompt for tools without native integration
- `entrykit lint`: run schema and heuristic checks on a capture payload
- `entrykit review`: prepare or validate a second-pass review response for a capture

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

See [docs/install-and-build.md](docs/install-and-build.md) for local build details and [docs/global-install.md](docs/global-install.md) for machine-level installation during development.

## Configuration

For machine-level use, the default config location is `~/.frederica/config/.env`.

For local repo development, you can still point commands at a repo-local file with `--env-file .env`.

Create a local `.env` file from the example if you are developing inside this repository:

```bash
cp .env.example .env
```

Required variables:

- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`

Do not commit `.env`. Only `.env.example` belongs in the repository.

## Quick start

Inspect the configured Notion database with the supporting CLI:

```bash
entrykit doctor
```

Then inspect the configured Notion database:

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

Run lint checks:

```bash
entrykit lint --input examples/coding-session.json --strict
```

Prepare a review prompt:

```bash
entrykit review --input examples/coding-session.json --conversation conversation.txt
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
