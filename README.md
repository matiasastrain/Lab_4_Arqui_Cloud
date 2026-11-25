# PoC PDI Trámites Migratorios en Google Cloud (TICS400, Laboratorio 3)

Prueba de concepto + Infraestructura como código (Terraform) para el caso PDI Migraciones.
Todo corre en Google Cloud (región `southamerica-west1`, Santiago). La IA es **Gemini en Vertex AI**
(reemplaza a Microsoft Foundry del enunciado original).

**Ambiente de ejemplo (DEV):**

- Portal: <https://pdi-portal-dev-617402588995.southamerica-west1.run.app>
- API (Swagger): <https://pdi-gestor-dev-617402588995.southamerica-west1.run.app/docs>

## Qué hay en el repositorio

| Carpeta | Contenido |
|---|---|
| `app/` | Backend Python (FastAPI). Una sola imagen con 3 modos (`APP_MODE`): `gestor`, `notificaciones`, `adaptadores`. Incluye 15 tests. |
| `portal/` | Portal web estático (nginx) para ciudadano y funcionario. |
| `terraform/` | Toda la infraestructura: VPC, Cloud SQL, Cloud Run, Cloud Tasks, Storage, Secret Manager, IAM, Artifact Registry, Cloud Build y borde opcional (LB + Cloud Armor). |
| `scripts/` | `deploy.sh`, `destroy.sh`, `e2e.py` (prueba de 19 pasos), `probar_gemini.py`, `run_local.sh`. |
| `docs/` | Informe del laboratorio. |

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
- Cloud Shell (recomendado, trae `gcloud` y `python3`) o una máquina con `gcloud`, Python 3 y Terraform >= 1.5.
- Cuota de Cloud SQL en la región y acceso a Gemini en Vertex AI.

Si Cloud Shell no trae Terraform (`terraform version` no responde), instalarlo en `~/bin`, que se conserva entre sesiones:

```bash
mkdir -p ~/bin && cd /tmp && wget -q https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_linux_amd64.zip && unzip -o terraform_1.9.8_linux_amd64.zip terraform -d ~/bin && echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc && export PATH="$HOME/bin:$PATH" && terraform version
```

## Despliegue paso a paso (Cloud Shell)

Los comandos usan el ID de nuestro proyecto, `pdi-cloud-515801`. Para desplegar en otro proyecto, reemplazarlo por el ID correspondiente.

1. Abrir <https://shell.cloud.google.com> y clonar este repositorio (o subirlo con **⋮ → Upload**):
   ```bash
   git clone https://github.com/matiasastrain/Lab_4_Arqui_Cloud.git pdi-poc && cd pdi-poc
   ```
2. Comprobar Gemini antes de gastar tiempo en el resto:
   ```bash
   gcloud config set project pdi-cloud-515801
   gcloud services enable aiplatform.googleapis.com
   pip install --user google-genai
   python3 scripts/probar_gemini.py --proyecto pdi-cloud-515801
   ```
   Si el modelo no responde, el script sugiere otro (`-var=gemini_modelo=...`). También se puede usar otra
   `vertex_location` o `ia_habilitada=false` (el sistema usa la plantilla fija).
3. Desplegar (ambiente `dev` por defecto, usa `db-f1-micro`):
   ```bash
   chmod +x scripts/*.sh
   ./scripts/deploy.sh pdi-cloud-515801 dev
   ```
   Demora entre 12 y 20 minutos (Cloud SQL y las construcciones de imágenes son lo más lento).
   El script crea el bucket del estado de Terraform (`pdi-cloud-515801-tfstate-pdi`, un prefijo por ambiente).
4. Al terminar se imprimen `url_portal`, `url_api`, `url_docs` y el comando de prueba rápida.

### Alternativa: Terraform manual

El bucket de estado debe existir (lo crea `deploy.sh` la primera vez).

```bash
cd terraform
terraform init -backend-config="bucket=pdi-cloud-515801-tfstate-pdi" -backend-config="prefix=pdi/dev"
terraform apply -var-file=envs/dev.tfvars -var="project_id=pdi-cloud-515801"
terraform output
terraform output -raw funcionario_api_key
```

Ambientes: `envs/dev.tfvars`, `envs/qa.tfvars`, `envs/prod.tfvars` (cambian tamaño de BD, HA, instancias, borde y protección de datos).

### Opciones

Se agregan al final de `deploy.sh` o de `terraform apply`, por ejemplo `./scripts/deploy.sh pdi-cloud-515801 dev -var=acceso_publico=false`.

| Variable | Uso |
|---|---|
| `acceso_publico=false` | Si la organización bloquea el acceso público a Cloud Run. |
| `habilitar_borde=true` | Balanceador HTTP + Cloud Armor delante del portal y la API (solo HTTP, sin dominio no hay certificado). |
| `ia_habilitada=false` | Desactiva Gemini; todos los avisos usan la plantilla. |
| `gemini_modelo`, `vertex_location` | Modelo y ubicación de Vertex AI. |
| `region` | Región principal, por defecto `southamerica-west1`. |
| `region_tareas` | Región de Cloud Tasks, por defecto `southamerica-east1` (Cloud Tasks no existe en Santiago). |

## Cómo ejecutar la prueba de concepto

1. Abrir `url_portal`. Ingresar como ciudadano con un RUT válido, por ejemplo `12.345.678-5`.
2. Crear un trámite, adjuntar un PDF/PNG/JPEG (máximo 5 MB) y guardar el folio.
3. Ingresar como funcionario con la clave de `terraform output -raw funcionario_api_key`, tomar el trámite, consultar antecedentes y decidir (aprobar, observar o rechazar). Aprobar exige al menos un adjunto; observar y rechazar exigen un motivo.
4. Volver al portal como ciudadano: el aviso redactado queda en el historial y, si está aprobado, se descarga el certificado. Un trámite observado se corrige con **Enviar subsanación**.
5. Prueba automática de punta a punta (19 pasos):
   ```bash
   cd terraform && eval "$(terraform output -raw prueba_rapida)"
   ```
   Debe terminar con `Resultado: 19/19 pasos correctos`. Si dice `plantilla` en todos los avisos, Gemini no respondió (revisar logs de `pdi-notificaciones-dev`).
6. Documentación interactiva de la API: `<url_api>/docs`.

## Ejecución local (sin GCP)

```bash
./scripts/run_local.sh        # SQLite + almacenamiento local + avisos por plantilla
```

Portal en <http://localhost:8080>, API en <http://localhost:8000/docs>, clave del funcionario `funcionario-local`. En otra terminal:

```bash
python3 scripts/e2e.py --api http://localhost:8000 --clave funcionario-local
cd app && pip install -r requirements-dev.txt && python3 -m pytest -q
```

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `command not found: terraform` | El comando se ejecutó fuera de Cloud Shell, o Cloud Shell no trae Terraform. Instalarlo como se indica en Requisitos. |
| `connection refused` hacia `*.googleapis.com` durante el apply | Corte de red pasajero de Cloud Shell. Repetir `deploy.sh`: Terraform retoma desde donde quedó. |
| `Location 'southamerica-west1' is not a valid location` (Cloud Tasks) | Resuelto con `region_tareas = southamerica-east1`. |
| `/healthz` responde 404 de Google en `*.run.app` | Google reserva las rutas terminadas en "z". Usar `/api/tipos` o `/docs` para comprobar la API. |
| 403 al abrir la URL | La organización bloquea el acceso público. Usar `-var=acceso_publico=false`; la prueba rápida agrega `--id-token "$(gcloud auth print-identity-token)"` sola. |
| Falla `gcloud builds submit` | Esperar un par de minutos y repetir el despliegue (propagación de IAM). |
| Gemini devuelve 404/403 | Cambiar `gemini_modelo` o `vertex_location`, o poner `ia_habilitada=false`. |
| `destroy` falla al borrar la red | Cloud SQL libera el peering con demora. Esperar ~10 minutos y repetir. |
| Cloud Shell se reinició | `export PATH="$HOME/bin:$PATH"` y, en `terraform/`, repetir el `terraform init` con `-backend-config`. |

## Costos

La PoC en `dev` usa Cloud SQL `db-f1-micro`, Cloud Run con escala a cero y Gemini por tokens, por lo que el costo es bajo, pero Cloud SQL cobra mientras exista. **Destruir al terminar la revisión:**

```bash
./scripts/destroy.sh pdi-cloud-515801 dev
```

## Seguridad

- Cloud SQL solo con IP privada y SSL obligatorio. Contraseñas y claves en Secret Manager.
- Una cuenta de servicio por componente con mínimo privilegio. Notificaciones y adaptadores no son públicos: solo los invocan Cloud Tasks (OIDC) y el gestor, respectivamente.
- Reglas de firewall de la VPC (el equivalente real de los NSG vistos en clases) sobre la salida directa de Cloud Run, con etiquetas de red por servicio.
- El estado de Terraform contiene los valores generados, por eso su bucket es privado.
- El portal y la API nunca muestran la clave del funcionario ni secretos en logs.
