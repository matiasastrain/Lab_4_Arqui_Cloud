#!/usr/bin/env bash
# Despliega la PoC completa con Terraform.
# Uso: ./scripts/deploy.sh PROYECTO [dev|qa|prod] [-var=...]
#   ej: ./scripts/deploy.sh pdi-cloud-515801 dev
#       ./scripts/deploy.sh pdi-cloud-515801 dev -var=acceso_publico=false
set -euo pipefail

PROYECTO="${1:?Uso: ./scripts/deploy.sh PROYECTO [dev|qa|prod] [-var=...]}"
AMBIENTE="${2:-dev}"
shift $(( $# >= 2 ? 2 : 1 ))
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
REGION_ESTADO="southamerica-west1"
BUCKET_ESTADO="${PROYECTO}-tfstate-pdi"

case "$AMBIENTE" in dev|qa|prod) ;; *) echo "Ambiente inválido: $AMBIENTE"; exit 1 ;; esac
for c in gcloud terraform python3; do
  command -v "$c" >/dev/null || { echo "Falta '$c'. Para Terraform en Cloud Shell, ver la sección 'Instalar Terraform' del README."; exit 1; }
done

echo "==> Proyecto: $PROYECTO | Ambiente: $AMBIENTE"
gcloud config set project "$PROYECTO" >/dev/null
gcloud services enable storage.googleapis.com serviceusage.googleapis.com cloudresourcemanager.googleapis.com --project "$PROYECTO"

# Estado remoto versionado, un prefijo por ambiente (dev/qa/prod no se pisan)
if ! gcloud storage buckets describe "gs://$BUCKET_ESTADO" >/dev/null 2>&1; then
  echo "==> Creando bucket de estado gs://$BUCKET_ESTADO"
  gcloud storage buckets create "gs://$BUCKET_ESTADO" --project "$PROYECTO" \
    --location "$REGION_ESTADO" --uniform-bucket-level-access --public-access-prevention
  gcloud storage buckets update "gs://$BUCKET_ESTADO" --versioning
fi

cd "$RAIZ/terraform"
terraform init -reconfigure -input=false \
  -backend-config="bucket=$BUCKET_ESTADO" \
  -backend-config="prefix=pdi/$AMBIENTE"

echo "==> terraform apply (12 a 20 minutos: Cloud SQL y Cloud Build son lo más lento)"
terraform apply -auto-approve -input=false \
  -var-file="envs/$AMBIENTE.tfvars" \
  -var="project_id=$PROYECTO" "$@"

echo
echo "==> Listo. Salidas:"
terraform output
echo
echo "Clave del funcionario:  cd terraform && terraform output -raw funcionario_api_key"
echo "Prueba de punta a punta: cd terraform && eval \"\$(terraform output -raw prueba_rapida)\""
