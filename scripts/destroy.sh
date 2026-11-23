#!/usr/bin/env bash
# Elimina todo lo que creó la PoC para no seguir pagando (la base de datos es lo más costoso).
# Uso:  ./scripts/destroy.sh TU_PROYECTO [dev|qa|prod]
set -euo pipefail

PROYECTO="${1:?Falta el ID del proyecto}"
AMBIENTE="${2:-dev}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"

gcloud config set project "${PROYECTO}" >/dev/null
cd "${RAIZ}/terraform"
terraform destroy -input=false -auto-approve \
  -var-file="envs/${AMBIENTE}.tfvars" \
  -var="project_id=${PROYECTO}" || {
  echo
  echo "El destroy falló. Lo más común es que la red no se pueda borrar porque Cloud SQL aún libera su conexión privada."
  echo "Espera 10 minutos y ejecuta este script de nuevo. Si usas un proyecto solo para el laboratorio,"
  echo "también puedes borrarlo completo:  gcloud projects delete ${PROYECTO}"
  exit 1
}
