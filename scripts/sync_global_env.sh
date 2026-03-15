#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_SOURCE="${1:-${ROOT_DIR}/.env}"
FREDERICA_HOME="${FREDERICA_HOME:-${HOME}/.frederica}"
CONFIG_DIR="${FREDERICA_HOME}/config"
ENV_TARGET="${CONFIG_DIR}/env.sh"
DOTENV_TARGET="${CONFIG_DIR}/.env"
LAUNCHCTL_TARGET="${CONFIG_DIR}/load-launchctl-env.sh"

if [[ ! -f "${ENV_SOURCE}" ]]; then
  echo "Env file not found: ${ENV_SOURCE}" >&2
  exit 1
fi

NOTION_TOKEN="$(grep '^NOTION_TOKEN=' "${ENV_SOURCE}" | cut -d= -f2- || true)"
NOTION_DATABASE_ID="$(grep '^NOTION_DATABASE_ID=' "${ENV_SOURCE}" | cut -d= -f2- || true)"

if [[ -z "${NOTION_TOKEN}" || -z "${NOTION_DATABASE_ID}" ]]; then
  echo "Env file must contain NOTION_TOKEN and NOTION_DATABASE_ID" >&2
  exit 1
fi

mkdir -p "${CONFIG_DIR}"
umask 077

cat > "${ENV_TARGET}" <<EOF
export NOTION_TOKEN='${NOTION_TOKEN}'
export NOTION_DATABASE_ID='${NOTION_DATABASE_ID}'
EOF

cat > "${DOTENV_TARGET}" <<EOF
NOTION_TOKEN='${NOTION_TOKEN}'
NOTION_DATABASE_ID='${NOTION_DATABASE_ID}'
EOF

cat > "${LAUNCHCTL_TARGET}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

FREDERICA_HOME="${FREDERICA_HOME:-${HOME}/.frederica}"
ENV_FILE="${FREDERICA_HOME}/config/env.sh"
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"
launchctl setenv NOTION_TOKEN "${NOTION_TOKEN}"
launchctl setenv NOTION_DATABASE_ID "${NOTION_DATABASE_ID}"
EOF

chmod 600 "${ENV_TARGET}"
chmod 600 "${DOTENV_TARGET}"
chmod 700 "${LAUNCHCTL_TARGET}"
"${LAUNCHCTL_TARGET}"

echo "Wrote ${ENV_TARGET}"
echo "Wrote ${DOTENV_TARGET}"
echo "Applied NOTION_TOKEN and NOTION_DATABASE_ID to launchctl for the current login session"
