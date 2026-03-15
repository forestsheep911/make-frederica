#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_SOURCE="${ROOT_DIR}/dist/entrykit"
FREDERICA_HOME="${FREDERICA_HOME:-${HOME}/.frederica}"
BIN_DIR="${FREDERICA_HOME}/bin"
BIN_TARGET="${BIN_DIR}/entrykit"
SKILL_SOURCE="${ROOT_DIR}/skills/frederica"
CODEX_SKILL_TARGET="${HOME}/.codex/skills/frederica"
AGENTS_SKILL_TARGET="${HOME}/.agents/skills/frederica"
LEGACY_CODEX_SKILL_TARGET="${HOME}/.codex/skills/chat-knowledge-capture"
LEGACY_AGENTS_SKILL_TARGET="${HOME}/.agents/skills/chat-knowledge-capture"
ZSHRC="${HOME}/.zshrc"
ENV_HOOK_LINE='if [ -f "${FREDERICA_HOME:-$HOME/.frederica}/config/env.sh" ]; then . "${FREDERICA_HOME:-$HOME/.frederica}/config/env.sh"; fi'
PATH_HOOK_LINE='export PATH="${FREDERICA_HOME:-$HOME/.frederica}/bin:$PATH"'

if [[ ! -x "${BIN_SOURCE}" ]]; then
  echo "Binary not found or not executable: ${BIN_SOURCE}" >&2
  echo "Build it first with ./scripts/build_binary.sh" >&2
  exit 1
fi

mkdir -p "${BIN_DIR}" "${HOME}/.codex/skills" "${HOME}/.agents/skills"
install -m 755 "${BIN_SOURCE}" "${BIN_TARGET}"
rm -rf \
  "${CODEX_SKILL_TARGET}" \
  "${AGENTS_SKILL_TARGET}" \
  "${LEGACY_CODEX_SKILL_TARGET}" \
  "${LEGACY_AGENTS_SKILL_TARGET}"
cp -R "${SKILL_SOURCE}" "${CODEX_SKILL_TARGET}"
cp -R "${SKILL_SOURCE}" "${AGENTS_SKILL_TARGET}"

"${ROOT_DIR}/scripts/sync_global_env.sh" "${ROOT_DIR}/.env"

touch "${ZSHRC}"
if ! grep -Fq "${PATH_HOOK_LINE}" "${ZSHRC}"; then
  printf '\n# frederica bin\n%s\n' "${PATH_HOOK_LINE}" >> "${ZSHRC}"
fi
if ! grep -Fq "${ENV_HOOK_LINE}" "${ZSHRC}"; then
  printf '\n# frederica env\n%s\n' "${ENV_HOOK_LINE}" >> "${ZSHRC}"
fi

echo "Installed binary to ${BIN_TARGET}"
echo "Installed skill to ${CODEX_SKILL_TARGET}"
echo "Installed skill to ${AGENTS_SKILL_TARGET}"
echo "Updated ${ZSHRC} to include ${BIN_DIR} on PATH"
echo "Updated ${ZSHRC} to source ${FREDERICA_HOME}/config/env.sh"
echo "Restart Codex or Gemini CLI to refresh the installed skills list"
