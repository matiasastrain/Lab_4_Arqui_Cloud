resource "random_id" "sql" {
  byte_length = 2 # el nombre de una instancia de Cloud SQL no se puede reutilizar por ~1 semana tras borrarla
}

resource "google_sql_database_instance" "pg" {
  name                = "pdi-pg-${local.env}-${random_id.sql.hex}"
  region              = var.region
  database_version    = "POSTGRES_15"
  deletion_protection = var.proteger_datos

  settings {
    edition                     = "ENTERPRISE" # obligatorio para tiers db-f1-micro y db-custom-*
    tier                        = var.db_tier
    availability_type           = var.db_alta_disponibilidad ? "REGIONAL" : "ZONAL"
    disk_type                   = "PD_SSD"
    disk_size                   = var.db_disco_gb
    disk_autoresize             = true
    deletion_protection_enabled = var.proteger_datos
    user_labels                 = local.labels

    ip_configuration {
      ipv4_enabled    = false # sin IP pública
      private_network = google_compute_network.vpc.id
      ssl_mode        = "ENCRYPTED_ONLY"
    }

    backup_configuration {
      enabled                        = var.db_respaldos || var.db_alta_disponibilidad
      point_in_time_recovery_enabled = var.db_alta_disponibilidad
      start_time                     = "07:00" # UTC, madrugada en Chile
    }
  }

  depends_on = [google_service_networking_connection.psa]
}

resource "google_sql_database" "pdi" {
  name     = "pdi"
  instance = google_sql_database_instance.pg.name
}

resource "google_sql_user" "app" {
  name     = "pdi_app"
  instance = google_sql_database_instance.pg.name
  password = random_password.db.result
}
