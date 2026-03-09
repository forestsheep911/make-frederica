# make-frederica

`make-frederica` is the development and packaging repo for the `frederica` skill.

This repo is not the final end-user skill distribution repo. Its job is to help you design, test, package, and validate the skill and the supporting tooling around it.

Today that support layer is mainly `entrykit`, a small CLI for turning AI chat summaries into structured Notion knowledge entries.

This repo focuses on three things:

- developing the `frederica` skill in a local, testable form
- maintaining `entrykit` as a supporting CLI for capture, lint, review, and Notion writes
- validating the contracts that will later be exported into a user-facing skills repository

## What it does

Main parts of the repo:

- `skills/frederica-dev/`: development version of the skill
- `src/entrykit/`: supporting CLI and capture logic
- `tests/`: unit tests for the supporting tooling
- `scripts/`: build and install helpers for local development

The `entrykit` CLI currently provides these commands:

- `entrykit capture`: validate a capture payload and write it to Notion
- `entrykit bootstrap-notion`: align a Notion database schema with the fields `entrykit` expects
- `entrykit inspect-notion`: print the current Notion database properties
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

See [docs/install-and-build.md](/Users/bxu/dev/rdpj/frederica/docs/install-and-build.md) for local build details and [docs/global-install.md](/Users/bxu/dev/rdpj/frederica/docs/global-install.md) for machine-level installation during development.

## Configuration

Create a local `.env` file from the example:

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

- [skills/frederica-dev](/Users/bxu/dev/rdpj/frederica/skills/frederica-dev): development skill files and examples
- [src/entrykit](/Users/bxu/dev/rdpj/frederica/src/entrykit): supporting CLI, models, linting, Notion integration, review helpers
- [tests](/Users/bxu/dev/rdpj/frederica/tests): unit tests
- [docs](/Users/bxu/dev/rdpj/frederica/docs): workflow and install notes
- [examples](/Users/bxu/dev/rdpj/frederica/examples): sample capture payloads
- [scripts](/Users/bxu/dev/rdpj/frederica/scripts): build and install helpers

## Repository role

Use this repo to make and verify the skill.

- Keep end-user distribution concerns separate from development concerns.
- Treat `entrykit` as supporting tooling, not as the entire product identity.
- Export polished skill contents later into a dedicated skills repo such as `my-skills`.

## Documentation

- [docs/install-and-build.md](/Users/bxu/dev/rdpj/frederica/docs/install-and-build.md)
- [docs/global-install.md](/Users/bxu/dev/rdpj/frederica/docs/global-install.md)
- [docs/lint.md](/Users/bxu/dev/rdpj/frederica/docs/lint.md)
- [docs/review.md](/Users/bxu/dev/rdpj/frederica/docs/review.md)
- [docs/cross-tool-workflow.md](/Users/bxu/dev/rdpj/frederica/docs/cross-tool-workflow.md)

## License

MIT. See [LICENSE](/Users/bxu/dev/rdpj/frederica/LICENSE).
