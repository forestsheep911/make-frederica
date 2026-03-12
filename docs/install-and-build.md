# Install And Build

These notes are for local development inside `make-frederica`.

## Local Python install

For local development, either run the module directly:

```bash
PYTHONPATH=src python3 -m entrykit.cli inspect-notion
```

or install the package in a virtualenv and use the console script:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
entrykit inspect-notion
```

This is enough for your own machine if Python 3 is already available.
On macOS, prefer `python3`; do not assume `python` exists.

On Windows, `entrykit` only requires Python `>=3.10`. It does not require Python 3.13 specifically.
Prefer a directly runnable interpreter such as `python` or an explicit interpreter path over the Windows `py` launcher when you are working inside agent-controlled or GUI app environments, because `python` and `py` do not always discover interpreters the same way.

Examples:

```powershell
python -m entrykit.cli --help
```

or:

```powershell
C:\path\to\python.exe -m entrykit.cli --help
```

If you expose a global wrapper on Windows, make it prefer a direct Python executable first and only fall back to `py -3` when needed. If interpreter discovery is still unstable, allow an override such as `ENTRYKIT_PYTHON_BIN` pointing at a Python 3.10+ executable.

## Standalone binary build

To build a single-file executable for the current machine:

```bash
./scripts/build_binary.sh
```

That script:

- creates `.venv-build/`
- uses the virtualenv's interpreter directly instead of relying on a global `python` alias
- installs the `entrykit` CLI plus the build dependency `pyinstaller`
- produces `dist/entrykit`

## Global use on the same machine

After building, place the binary somewhere on your `PATH`, for example:

```bash
cp dist/entrykit ~/.local/bin/entrykit
```

or:

```bash
cp dist/entrykit /usr/local/bin/entrykit
```

Then other local tools can call `entrykit` directly without caring about `PYTHONPATH` or the project checkout layout.

## Guidance for agent-driven usage

When another assistant needs to run this repo locally, prefer these command forms:

```bash
entrykit capture --input captured.json
```

If the binary is not installed but the repo checkout is available:

```bash
PYTHONPATH=src python3 -m entrykit.cli capture --input captured.json
```

Avoid telling the agent to run a bare `python` command unless you have already verified that it exists on that machine.
On Windows, avoid assuming `py` works just because `python` works. They use different discovery logic and can diverge inside desktop-app sandboxes or other controlled execution environments.

## Current boundary

The built binary is machine-specific. If you want to share it with someone else, build it on the target platform or distribute the Python package instead.
