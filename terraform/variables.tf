variable "project_id" {
  description = "ID del proyecto de GCP donde se despliega la prueba de concepto."
  type        = string
}

variable "region" {
  description = "Región de GCP. Santiago mantiene los datos migratorios en Chile (Ley 21.719)."
  type        = string
  default     = "southamerica-west1"
}

variable "environment" {
  description = "Ambiente: dev, qa o prod. Mismo código, distinta parametrización (Laboratorio 2)."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "qa", "prod"], var.environment)
    error_message = "environment debe ser dev, qa o prod."
  }
}

variable "vpc_cidr" {
  description = "Rango de la VPC. Laboratorio 2: PROD 10.10.0.0/16, QA 10.20.0.0/16, DEV 10.30.0.0/16."
  type        = string
  default     = "10.30.0.0/16"
}

# ------------------------------------------------------------ base de datos
variable "db_tier" {
  description = "Tamaño de Cloud SQL. db-f1-micro es el más barato; PROD usa db-custom-2-8192."
  type        = string
  default     = "db-f1-micro"
}

variable "db_alta_disponibilidad" {
  description = "true = réplica en otra zona (availability_type REGIONAL)."
  type        = bool
  default     = false
}

variable "db_disco_gb" {
  type    = number
  default = 10
}

variable "db_respaldos" {
  description = "Respaldos automáticos diarios (siempre activos si hay alta disponibilidad)."
  type        = bool
  default     = false
}

variable "proteger_datos" {
  description = "true = protege contra borrado la base y el bucket de adjuntos (usar en PROD)."
  type        = bool
  default     = false
}

# ------------------------------------------------------------ cómputo
variable "run_min_instancias" {
  description = "Instancias mínimas de Cloud Run. 0 apaga todo sin tráfico (más barato, con arranque en frío)."
  type        = number
  default     = 0
}

variable "run_max_instancias" {
  type    = number
  default = 3
}

variable "run_cpu" {
  type    = string
  default = "1"
}

variable "run_memoria" {
  type    = string
  default = "512Mi"
}

variable "acceso_publico" {
  description = "true = portal y API invocables sin autenticación de Google (la API exige su propio token). Si la organización lo bloquea, usar false."
  type        = bool
  default     = true
}

# ------------------------------------------------------------ borde (WAF)
variable "habilitar_borde" {
  description = "true = balanceador HTTP(S) global con Cloud Armor delante del portal y la API. Agrega costo fijo mientras exista."
  type        = bool
  default     = false
}

variable "limite_solicitudes_por_minuto" {
  description = "Límite de tasa por IP en Cloud Armor."
  type        = number
  default     = 300
}

# ------------------------------------------------------------ IA
variable "ia_habilitada" {
  description = "true = el servicio de notificaciones usa Gemini; false = solo plantillas fijas."
  type        = bool
  default     = true
}

variable "vertex_location" {
  description = "Ubicación del endpoint de Vertex AI. 'global' tiene la mejor disponibilidad, pero no garantiza procesamiento dentro de Chile."
  type        = string
  default     = "global"
}

variable "gemini_model" {
  description = "Modelo de Gemini en Vertex AI. Verificar vigencia en la página de ciclo de vida de modelos."
  type        = string
  default     = "gemini-3.5-flash-lite"
}

variable "force_destroy" {
  description = "true = permite borrar los buckets aunque tengan archivos (útil para terraform destroy en la PoC)."
  type        = bool
  default     = true
}
