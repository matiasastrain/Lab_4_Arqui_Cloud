#!/usr/bin/env bash
# Despliega la PoC completa en GCP. Pensado para Cloud Shell (ya trae gcloud, terraform y credenciales).
# Uso:  ./scripts/deploy.sh TU_PROYECTO [dev|qa|prod]
set -euo pipefail

PROYECTO="${1:?Falta el ID del proyecto. Uso: ./scripts/deploy.sh TU_PROYECTO [dev|qa|prod]}"
AMBIENTE="${2:-dev}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Proyecto: ${PROYECTO}  |  Ambiente: ${AMBIENTE}"
gcloud config set project "${PROYECTO}" >/dev/null

echo "==> Habilitando las APIs mínimas para que Terraform pueda empezar"
gcloud services enable cloudresourcemanager.googleapis.com serviceusage.googleapis.com iam.googleapis.com

cd "${RAIZ}/terraform"
terraform init -input=false
terraform apply -input=false -auto-approve \
  -var-file="envs/${AMBIENTE}.tfvars" \
  -var="project_id=${PROYECTO}"

echo
echo "==> Listo. URLs:"
terraform output url_portal
terraform output url_api
echo
echo "Clave del funcionario:  terraform output -raw funcionario_api_key"
echo "Prueba de punta a punta:"
terraform output -raw prueba_rapida
echo
