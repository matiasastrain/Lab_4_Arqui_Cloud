#!/usr/bin/env bash
# Ejecuta la PoC sin Google Cloud: API con SQLite y disco (puerto 8000) y
# portal estático (puerto 8080). Sin Gemini: los avisos salen con plantilla.
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$RAIZ/.venv-local"

if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$RAIZ/app/requirements-dev.txt"
fi

export APP_MODE=gestor FUNCIONARIO_API_KEY="${FUNCIONARIO_API_KEY:-funcionario-local}" IA_HABILITADA=false
cd "$RAIZ/app"
"$VENV/bin/uvicorn" main:app --port 8000 &
API_PID=$!
cd "$RAIZ/portal"
python3 -m http.server 8080 --bind 127.0.0.1 >/dev/null 2>&1 &
PORTAL_PID=$!
trap 'kill $API_PID $PORTAL_PID 2>/dev/null' EXIT INT TERM

echo "Portal:  http://localhost:8080"
echo "API:     http://localhost:8000/docs"
echo "Clave del funcionario: $FUNCIONARIO_API_KEY"
echo "Prueba:  python3 scripts/e2e.py --api http://localhost:8000 --clave $FUNCIONARIO_API_KEY"
wait
