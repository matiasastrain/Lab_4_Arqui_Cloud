# PoC PDI Trámites Migratorios en Google Cloud (TICS400, Laboratorio 3)

Prueba de concepto + Infraestructura como código (Terraform) para el caso PDI Migraciones.
Todo corre en Google Cloud (región `southamerica-west1`, Santiago). La IA es **Gemini en Vertex AI**
(reemplaza a Microsoft Foundry del enunciado original).

## Qué hay en el repositorio

| Carpeta | Contenido |
|---|---|
| `app/` | Backend Python (FastAPI). Una sola imagen con 3 modos (`APP_MODE`): `gestor`, `notificaciones`, `adaptadores`. Incluye 15 tests. |
| `portal/` | Portal web estático (nginx) para ciudadano y funcionario. |
| `terraform/` | Toda la infraestructura: VPC, Cloud SQL, Cloud Run, Cloud Tasks, Storage, Secret Manager, IAM, Artifact Registry, Cloud Build y borde opcional (LB + Cloud Armor). |
| `scripts/` | `deploy.sh`, `destroy.sh`, `smoke_test.py`, `probar_gemini.py`, `run_local.sh`. |

## Qué es real y qué es simulado

| Real | Simulado en la PoC |
|---|---|
| Flujo del trámite (RECIBIDO, EN_REVISION, APROBADO, OBSERVADO, RECHAZADO), folio único, control de duplicados, adjuntos, subsanación, certificado PDF, reporte | ClaveÚnica (RUT con validación módulo 11, sin el proveedor real) |
| Cola con Cloud Tasks, aviso idempotente por historial | GEPOL / B3000 (servicio `adaptadores` con datos sintéticos) |
| Redacción del aviso con Gemini (con validación y plantilla de respaldo) | Envío de mensajes (solo se registra en logs) |
| VPC, subredes, reglas de firewall, Cloud SQL privado, IAM por componente | VPN HA, Cloud NAT y SICOM (no se despliegan en la PoC) |

La IA solo redacta el aviso. Nunca decide el resultado del trámite.

## Requisitos

- Un proyecto de GCP **con facturación activa** y permisos de propietario (o equivalente).
- Cloud Shell (recomendado, ya trae `gcloud` y `terraform`) o una máquina con `gcloud` y Terraform >= 1.5.
- Cuota de Cloud SQL en la región y acceso a Gemini en Vertex AI.

## Despliegue paso a paso (Cloud Shell)

1. Abrir <https://shell.cloud.google.com> y subir o clonar este repositorio.
2. Comprobar Gemini antes de gastar tiempo en el resto:
   ```bash
   gcloud config set project TU_PROYECTO
   gcloud services enable aiplatform.googleapis.com
   pip install google-genai
   python3 scripts/probar_gemini.py --proyecto TU_PROYECTO
   ```
   Si falla, probar otra `vertex_location` o `ia_habilitada=false` (el sistema usa la plantilla fija).
3. Desplegar (ambiente `dev` por defecto, usa `db-f1-micro`):
   ```bash
   chmod +x scripts/*.sh
   ./scripts/deploy.sh TU_PROYECTO dev
   ```
   Demora entre 12 y 20 minutos (Cloud SQL y las construcciones de imágenes son lo más lento).
4. Al terminar se imprimen `url_portal`, `url_api` y el comando de prueba rápida.

### Alternativa: Terraform manual

```bash
cd terraform
terraform init
terraform apply -var-file=envs/dev.tfvars -var="project_id=TU_PROYECTO"
terraform output
terraform output -raw funcionario_api_key
```

Ambientes: `envs/dev.tfvars`, `envs/qa.tfvars`, `envs/prod.tfvars` (cambian tamaño de BD, HA, instancias, borde y protección de datos).

## Cómo ejecutar la prueba de concepto

1. Abrir `url_portal`. Ingresar como ciudadano con un RUT válido, por ejemplo `12.345.678-5`.
2. Crear un trámite, adjuntar un PDF/PNG/JPEG (máximo 5 MB) y guardar el folio.
3. Ingresar como funcionario con la clave de `terraform output -raw funcionario_api_key`, tomar el trámite, consultar antecedentes y decidir (aprobar, observar o rechazar). Aprobar exige al menos un adjunto.
4. Volver al portal como ciudadano: el aviso redactado queda en el historial y, si está aprobado, se descarga el certificado.
5. Prueba automática de punta a punta (19 pasos):
   ```bash
   cd terraform && eval "$(terraform output -raw prueba_rapida)"
   ```
   Debe terminar con `Resultado: 19/19 pasos correctos`. Si dice `plantilla` en todos los avisos, Gemini no respondió (revisar logs de `pdi-notif`).
6. Documentación interactiva de la API: `<url_api>/docs`.

## Ejecución local (sin GCP)

```bash
./scripts/run_local.sh        # SQLite + almacenamiento local + avisos por plantilla
cd app && pip install -r requirements.txt && pytest -q
```

## Ejecución con Docker

Levanta toda la PoC en tu computador con Docker Compose, sin GCP: `gestor`, `notificaciones` y
`adaptadores` (misma imagen de `app/`, cambia `APP_MODE`), el `portal` (nginx) y PostgreSQL 15.
Usa los mismos Dockerfile que Cloud Build, así que el despliegue en Cloud Run no cambia.

```bash
cp .env.example .env            # opcional: claves y puertos (sin .env se usan valores por defecto)
docker compose up --build       # agrega -d para dejarlo en segundo plano
```

| Servicio | URL |
|---|---|
| Portal (ciudadano y funcionario) | <http://localhost:8091> |
| API del gestor (Swagger) | <http://localhost:8090/docs> |
| Notificaciones | <http://localhost:8092/healthz> |
| Adaptadores GEPOL/B3000 simulados | <http://localhost:8093/docs> |
| PostgreSQL | `localhost:5433` (usuario `pdi_app`, clave `pdi_local`, base `pdi`) |

La clave del funcionario es `FUNCIONARIO_API_KEY` (por defecto `clave-local`).

Diferencias con la nube: `LOCAL_MODE=1`, así que no hay Cloud Tasks (el gestor llama directo a
`notificaciones` por HTTP), no hay IAM entre servicios, los adjuntos se guardan en el volumen
`adjuntos` en vez de Cloud Storage y los avisos se redactan por plantilla (sin Gemini).

Logs y estado:

```bash
docker compose ps                        # estado y healthchecks
docker compose logs -f                   # todos los servicios
docker compose logs -f gestor notificaciones
```

Prueba de punta a punta contra el entorno Docker:

```bash
python scripts/smoke_test.py --api http://localhost:8090 --clave clave-local
```

Bajar todo:

```bash
docker compose down        # detiene y borra los contenedores (conserva BD y adjuntos)
docker compose down -v     # además borra los volúmenes (BD y adjuntos)
```

Si un puerto está ocupado, cámbialo en `.env` (por ejemplo `PORTAL_PORT=8095`).

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| 403 al abrir la URL | La organización bloquea `allUsers`. Usar `-var="acceso_publico=false"` y probar con `--id-token "$(gcloud auth print-identity-token)"` o `gcloud run services proxy`. |
| Falla `gcloud builds submit` | Esperar un par de minutos y repetir `terraform apply` (propagación de IAM). Revisar que Cloud Build esté habilitado. |
| Gemini devuelve 404/403 | Cambiar `gemini_model` o `vertex_location`, o poner `ia_habilitada=false`. |
| `destroy` falla al borrar la red | Cloud SQL libera el peering con demora. Esperar ~10 minutos y repetir, o borrar el proyecto. |
| El borde (`habilitar_borde=true`) responde solo por HTTP | Es intencional: sin dominio no hay certificado. |

## Costos

La PoC en `dev` usa Cloud SQL `db-f1-micro`, Cloud Run con escala a cero y Gemini por tokens, por lo que el costo es bajo, pero Cloud SQL cobra mientras exista. **Destruir al terminar:**

```bash
./scripts/destroy.sh TU_PROYECTO dev
```

## Seguridad

- Cloud SQL solo con IP privada y SSL obligatorio. Contraseñas y claves en Secret Manager.
- Una cuenta de servicio por componente con mínimo privilegio.
- Reglas de firewall de la VPC (el equivalente real de los NSG vistos en clases).
- El portal y la API nunca muestran la clave del funcionario ni secretos en logs.
