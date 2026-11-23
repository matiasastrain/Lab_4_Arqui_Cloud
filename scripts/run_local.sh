#!/usr/bin/env bash
# Corre la PoC en tu computador SIN GCP (SQLite, disco local, avisos con plantilla). Sirve para demo y desarrollo.
# Uso:  ./scripts/run_local.sh    (API en :8080, portal en :8081)
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"

python3 -m pip install -q -r "${RAIZ}/app/requirements.txt"

mkdir -p "${TMP}/portal" && cp "${RAIZ}"/portal/{index.html,app.js,styles.css} "${TMP}/portal/"
echo 'window.PDI_CONFIG = { API_URL: "http://localhost:8080", ENV_NAME: "local" };' > "${TMP}/portal/config.js"
(cd "${TMP}/portal" && python3 -m http.server 8081 >/dev/null 2>&1) &
trap 'kill %1 2>/dev/null || true' EXIT

echo "Portal:  http://localhost:8081      API: http://localhost:8080/docs      Clave del funcionario: clave-local"
cd "${RAIZ}/app"
LOCAL_MODE=1 APP_MODE=gestor DATABASE_URL="sqlite:///${TMP}/local.db" LOCAL_STORAGE_DIR="${TMP}/storage" \
FUNCIONARIO_API_KEY=clave-local JWT_SECRET=desarrollo-local-solo-para-pruebas-32-bytes \
PORTAL_URL=http://localhost:8081 python3 -m uvicorn pdi.entry:app --port 8080
