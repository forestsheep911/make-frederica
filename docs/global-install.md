# Global Install

Use the compiled binary and local skill as machine-level development tools on this Mac.

The dedicated runtime home is `~/.frederica`. Keep the toolchain there instead of inside the current working repository, because `frederica` is a note-capture helper and should not dirty arbitrary git projects with its own environment files.

This document describes the current macOS flow.
On Windows, the practical development-time global install may instead be a wrapper script that points at the repo checkout plus a Python 3.10+ interpreter. In that case, prefer a direct `python` executable over `py` when choosing the interpreter, because GUI or sandboxed environments may expose `python` while `py` cannot discover any installed runtimes.

## One-command install

Build first if needed:

```bash
./scripts/build_binary.sh
```

Then install globally:

```bash
./scripts/install_global.sh
```

This does four things:

- installs `dist/entrykit` to `~/.frederica/bin/entrykit`
- installs the stable skill to `~/.codex/skills/frederica`
- writes `~/.frederica/config/env.sh` and `~/.frederica/config/.env`
- applies `NOTION_TOKEN` and `NOTION_DATABASE_ID` to `launchctl` for the current login session

## Local dev vs global stable

Inside this repo, the skill uses the same stable name `frederica` as the installed global copy.

`./scripts/install_global.sh` copies the skill as-is to the global skill directories.

## Shell visibility

The installer also adds a small hook to `~/.zshrc` so new terminal sessions load:

- `~/.frederica/bin` onto `PATH`
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`

## GUI app note

The installer runs `launchctl setenv` so apps launched within the current macOS login session can inherit the variables. If a GUI app still does not see them, restart that app or log out and back in.

## Updating after changes

Re-run:

```bash
./scripts/install_global.sh
```

after rebuilding the binary or changing the skill contents.
The installer also removes the legacy global skill name `chat-knowledge-capture` during migration to `frederica`.
