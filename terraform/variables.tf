variable "project_id" {
  description = "ID del proyecto de Google Cloud"
  type        = string
}

variable "ambiente" {
  description = "dev, qa o prod"
  type        = string
  validation {
    condition     = contains(["dev", "qa", "prod"], var.ambiente)
    error_message = "ambiente debe ser dev, qa o prod."
  }
}

variable "region" {
  description = "Región principal (Santiago por defecto)"
  type        = string
  default     = "southamerica-west1"
}

variable "vpc_cidr" {
  description = "Rango de la VPC; se divide en subredes /20"
  type        = string
}

variable "db_tier" {
  type    = string
  default = "db-f1-micro"
}

variable "db_alta_disponibilidad" {
  type    = bool
  default = false
}

variable "db_disco_gb" {
  type    = number
  default = 10
}

variable "db_respaldos" {
  type    = bool
  default = false
}

variable "proteger_datos" {
  description = "Protección contra borrado de Cloud SQL y del bucket"
  type        = bool
  default     = false
}

variable "run_min_instancias" {
  type    = number
  default = 0
}

variable "run_max_instancias" {
  type    = number
  default = 3
}

variable "habilitar_borde" {
  description = "Crea el balanceador HTTP global con Cloud Armor delante del portal y la API"
  type        = bool
  default     = false
}

variable "acceso_publico" {
  description = "Permite abrir el portal y la API sin autenticación de Google. Si la organización lo bloquea, usar false."
  type        = bool
  default     = true
}

variable "ia_habilitada" {
  type    = bool
  default = true
}

variable "gemini_modelo" {
  description = "Modelo de Gemini en Vertex AI (verificar con scripts/probar_gemini.py)"
  type        = string
  default     = "gemini-3.5-flash-lite"
}

variable "vertex_location" {
  type    = string
  default = "global"
}

variable "region_tareas" {
  description = "Región de Cloud Tasks (no está disponible en southamerica-west1)"
  type        = string
  default     = "southamerica-east1"
}
