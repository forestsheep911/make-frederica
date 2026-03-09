#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_VENV="${ROOT_DIR}/.venv-build"
VENV_PYTHON="${BUILD_VENV}/bin/python"

python3 -m venv "${BUILD_VENV}"
"${VENV_PYTHON}" -m pip install --upgrade pip
"${VENV_PYTHON}" -m pip install -e "${ROOT_DIR}[build]"

"${BUILD_VENV}/bin/pyinstaller" \
  --noconfirm \
  --clean \
  --onefile \
  --name entrykit \
  --distpath "${ROOT_DIR}/dist" \
  --workpath "${ROOT_DIR}/build/pyinstaller" \
  --specpath "${ROOT_DIR}/build" \
  --paths "${ROOT_DIR}/src" \
  "${ROOT_DIR}/src/entrykit/cli.py"

printf '\nBuilt binary: %s\n' "${ROOT_DIR}/dist/entrykit"
