# Global Install

Use the compiled binary and local skill as machine-level development tools on this Mac.

The dedicated runtime home is `~/.frederica`. Keep the toolchain there instead of inside the current working repository, because `frederica` is a note-capture helper and should not dirty arbitrary git projects with its own environment files.

This document describes the current macOS flow.
On Windows, use the PowerShell installer `scripts/install_global_windows.ps1`. It installs wrapper scripts that point at the repo checkout plus a Python 3.10+ interpreter, preferring a direct `python` executable over `py`.

## One-command install

On macOS or Linux:

Build first if needed:

```bash
./scripts/build_binary.sh
```

On Windows, build the executable with:

```powershell
.\scripts\build_binary_windows.ps1
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

## Windows development-time install

On Windows, do not use `install_global.sh`. Use the PowerShell installer instead:

From PowerShell:

```powershell
.\scripts\install_global_windows.ps1 -SyncEnv -AddToUserPath
```

That script:

- creates `~/.frederica/bin/entrykit.cmd`
- creates `~/.frederica/bin/entrykit.ps1`
- installs the stable skill to `~/.codex/skills/frederica` and `~/.agents/skills/frederica`
- optionally copies the repo `.env` into `~/.frederica/config/.env`
- optionally prepends `~/.frederica/bin` to the user `PATH`

The generated wrappers resolve Python in this order:

- `ENTRYKIT_PYTHON_BIN`
- `python`
- `py -3`

## Local Markdown backend after install

After installation, the current recommended local persistent backend is `local_markdown`.

Example setup:

```bash
entrykit config set-default local_markdown
entrykit config set-local-markdown --enable --output-dir ~/notes/frederica
```

If you use Obsidian without Obsidian Sync or a dedicated backend, point `output_dir` to a folder inside your local vault instead of a generic notes directory.

Example:

```bash
entrykit config set-local-markdown --enable --output-dir ~/Documents/MyVault/Frederica
```

That gives Obsidian users a working local flow today while `obsidian` remains a future backend enhancement.
