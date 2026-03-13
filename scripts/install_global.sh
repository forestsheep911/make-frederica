#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_SOURCE="${ROOT_DIR}/dist/entrykit"
BIN_TARGET="${HOME}/.local/bin/entrykit"
SKILL_SOURCE="${ROOT_DIR}/skills/frederica"
CODEX_SKILL_TARGET="${HOME}/.codex/skills/frederica"
AGENTS_SKILL_TARGET="${HOME}/.agents/skills/frederica"
LEGACY_CODEX_SKILL_TARGET="${HOME}/.codex/skills/chat-knowledge-capture"
LEGACY_AGENTS_SKILL_TARGET="${HOME}/.agents/skills/chat-knowledge-capture"
ZSHRC="${HOME}/.zshrc"
HOOK_LINE='if [ -f "$HOME/.config/entrykit/env.sh" ]; then . "$HOME/.config/entrykit/env.sh"; fi'

if [[ ! -x "${BIN_SOURCE}" ]]; then
  echo "Binary not found or not executable: ${BIN_SOURCE}" >&2
  echo "Build it first with ./scripts/build_binary.sh" >&2
  exit 1
fi

mkdir -p "${HOME}/.local/bin" "${HOME}/.codex/skills" "${HOME}/.agents/skills"
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
if ! grep -Fq "${HOOK_LINE}" "${ZSHRC}"; then
  printf '\n# entrykit global env\n%s\n' "${HOOK_LINE}" >> "${ZSHRC}"
fi

echo "Installed binary to ${BIN_TARGET}"
echo "Installed skill to ${CODEX_SKILL_TARGET}"
echo "Installed skill to ${AGENTS_SKILL_TARGET}"
echo "Updated ${ZSHRC} to source ~/.config/entrykit/env.sh"
echo "Restart Codex or Gemini CLI to refresh the installed skills list"
