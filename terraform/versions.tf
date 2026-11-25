terraform {
  required_version = ">= 1.5"

  required_providers {
    google = { source = "hashicorp/google", version = ">= 6.10, < 9.0" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
    null   = { source = "hashicorp/null", version = "~> 3.2" }
    time   = { source = "hashicorp/time", version = "~> 0.12" }
  }

  # Estado remoto en Cloud Storage, separado por ambiente.
  # scripts/deploy.sh entrega bucket y prefix (pdi/<ambiente>) con -backend-config.
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "this" {
  project_id = var.project_id
}

resource "random_id" "sufijo" {
  byte_length = 2
}

locals {
  nombre       = "pdi-tramites-${var.ambiente}"
  sufijo       = random_id.sufijo.hex
  numero       = data.google_project.this.number
  etiquetas    = { proyecto = "pdi-tramites", ambiente = var.ambiente, gestionado-por = "terraform" }
  run_url      = { for s in ["portal", "gestor", "notificaciones", "adaptadores"] : s => "https://pdi-${s}-${var.ambiente}-${local.numero}.${var.region}.run.app" }
}
