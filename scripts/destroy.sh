#!/usr/bin/env bash
# Elimina toda la infraestructura del ambiente.
# Uso: ./scripts/destroy.sh PROYECTO [dev|qa|prod]
set -euo pipefail

PROYECTO="${1:?Uso: ./scripts/destroy.sh PROYECTO [dev|qa|prod]}"
AMBIENTE="${2:-dev}"
shift $(( $# >= 2 ? 2 : 1 ))
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
BUCKET_ESTADO="${PROYECTO}-tfstate-pdi"

cd "$RAIZ/terraform"
terraform init -reconfigure -input=false \
  -backend-config="bucket=$BUCKET_ESTADO" \
  -backend-config="prefix=pdi/$AMBIENTE"

if [ "$AMBIENTE" = "prod" ]; then
  echo "PROD tiene proteger_datos = true. Para borrarlo, primero aplique con -var=proteger_datos=false."
fi

if ! terraform destroy -auto-approve -input=false -var-file="envs/$AMBIENTE.tfvars" -var="project_id=$PROYECTO" "$@"; then
  echo
  echo "La eliminación falló (normalmente la red, porque Cloud SQL libera el peering con demora)."
  echo "Espere unos 10 minutos y vuelva a ejecutar: ./scripts/destroy.sh $PROYECTO $AMBIENTE"
  exit 1
fi
echo "Infraestructura de $AMBIENTE eliminada. El bucket de estado gs://$BUCKET_ESTADO se conserva."
