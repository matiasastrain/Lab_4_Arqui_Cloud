resource "google_sql_database_instance" "db" {
  # Sufijo aleatorio: Cloud SQL no permite reutilizar un nombre por una semana
  name                = "pdi-db-${var.ambiente}-${local.sufijo}"
  database_version    = "POSTGRES_15"
  region              = var.region
  deletion_protection = var.proteger_datos

  settings {
    tier                        = var.db_tier
    edition                     = "ENTERPRISE" # db-f1-micro solo existe en Enterprise
    availability_type           = var.db_alta_disponibilidad ? "REGIONAL" : "ZONAL"
    disk_size                   = var.db_disco_gb
    disk_autoresize             = true
    deletion_protection_enabled = var.proteger_datos
    user_labels                 = local.etiquetas

    ip_configuration {
      ipv4_enabled       = false # sin IP pública
      private_network    = google_compute_network.vpc.id
      allocated_ip_range = google_compute_global_address.psa.name
      ssl_mode           = "ENCRYPTED_ONLY" # SSL obligatorio
    }

    backup_configuration {
      enabled                        = var.db_respaldos
      point_in_time_recovery_enabled = var.db_respaldos
    }
  }

  depends_on = [google_service_networking_connection.psa]
}

resource "google_sql_database" "pdi" {
  name     = "pdi"
  instance = google_sql_database_instance.db.name
}

resource "google_sql_user" "app" {
  name     = "pdi_app"
  instance = google_sql_database_instance.db.name
  password = random_password.db.result
}
