# Cinco servicios en la misma imagen o en el portal estático:
#   gestor           API del ciudadano y del funcionario (snet-app, Direct VPC egress)
#   notif            consume la cola de Cloud Tasks y redacta el aviso con Gemini (snet-app)
#   adaptadores      simula la red institucional de la PDI (GEPOL / B3000)
#   portal           web estática (equivale a la Static Web App del diagrama)

locals {
  env_base = {
    ENV_NAME   = var.environment
    PROJECT_ID = var.project_id
    REGION     = var.region
    PORTAL_URL = local.portal_publico
  }

  env_bd = {
    DB_HOST = google_sql_database_instance.pg.private_ip_address
    DB_PORT = "5432"
    DB_NAME = google_sql_database.pdi.name
    DB_USER = google_sql_user.app.name
  }

  ingress_backend = var.habilitar_borde ? "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER" : "INGRESS_TRAFFIC_ALL"
}

# ---------------------------------------------------------------- gestor de trámites
resource "google_cloud_run_v2_service" "gestor" {
  name                = local.nombres.gestor
  location            = var.region
  ingress             = local.ingress_backend
  deletion_protection = false
  labels              = local.labels

  template {
    service_account = google_service_account.sa["gestor"].email

    scaling {
      min_instance_count = var.run_min_instancias
      max_instance_count = var.run_max_instancias
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY" # solo el tráfico privado (Cloud SQL) entra a la VPC; Google APIs van directo
      network_interfaces {
        network    = google_compute_network.vpc.id
        subnetwork = google_compute_subnetwork.snet["app"].id
        tags       = ["pdi-app"]
      }
    }

    containers {
      image = local.image_app

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.run_cpu
          memory = var.run_memoria
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        http_get {
          path = "/healthz"
        }
        period_seconds    = 5
        timeout_seconds   = 3
        failure_threshold = 24
      }

      dynamic "env" {
        iterator = e
        for_each = merge(local.env_base, local.env_bd, {
          APP_MODE           = "gestor"
          BUCKET_ADJUNTOS    = google_storage_bucket.adjuntos.name
          TASKS_QUEUE        = google_cloud_tasks_queue.avisos.name
          TASKS_SA_EMAIL     = google_service_account.sa["tasks"].email
          NOTIFICACIONES_URL = local.run_url.notif
          ADAPTADORES_URL    = local.run_url.adapt
          CORS_ORIGINS       = "*" # la API usa tokens Bearer (sin cookies); con borde activo el portal y la API comparten origen
        })
        content {
          name  = e.key
          value = e.value
        }
      }

      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.s["db_password"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "JWT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.s["jwt_secret"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "FUNCIONARIO_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.s["funcionario_api_key"].secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    null_resource.build_app,
    google_secret_manager_secret_version.s,
    google_secret_manager_secret_iam_member.gestor_secretos,
    google_storage_bucket_iam_member.gestor_adjuntos,
    google_sql_database.pdi,
    google_sql_user.app,
  ]
}

# ---------------------------------------------------------------- notificaciones (Cloud Tasks -> Gemini)
resource "google_cloud_run_v2_service" "notif" {
  name                = local.nombres.notif
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL" # protegido por IAM: solo sa-tasks puede invocarlo
  deletion_protection = false
  labels              = local.labels

  template {
    service_account = google_service_account.sa["notif"].email

    scaling {
      min_instance_count = 0
      max_instance_count = var.run_max_instancias
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = google_compute_network.vpc.id
        subnetwork = google_compute_subnetwork.snet["app"].id
        tags       = ["pdi-app"]
      }
    }

    containers {
      image = local.image_app

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.run_cpu
          memory = var.run_memoria
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        http_get {
          path = "/healthz"
        }
        period_seconds    = 5
        timeout_seconds   = 3
        failure_threshold = 24
      }

      dynamic "env" {
        iterator = e
        for_each = merge(local.env_base, local.env_bd, {
          APP_MODE        = "notificaciones"
          IA_HABILITADA   = var.ia_habilitada ? "1" : "0"
          VERTEX_LOCATION = var.vertex_location
          GEMINI_MODEL    = var.gemini_model
        })
        content {
          name  = e.key
          value = e.value
        }
      }

      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.s["db_password"].secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    null_resource.build_app,
    google_secret_manager_secret_version.s,
    google_secret_manager_secret_iam_member.notif_db,
    google_project_iam_member.notif_vertex,
    google_sql_database.pdi,
    google_sql_user.app,
  ]
}

# ---------------------------------------------------------------- red institucional simulada
resource "google_cloud_run_v2_service" "adaptadores" {
  name                = local.nombres.adapt
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL" # protegido por IAM: solo el gestor puede invocarlo
  deletion_protection = false
  labels              = local.labels

  template {
    service_account = google_service_account.sa["adapt"].email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = local.image_app

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle = true
      }

      startup_probe {
        http_get {
          path = "/healthz"
        }
        period_seconds    = 5
        timeout_seconds   = 3
        failure_threshold = 24
      }

      env {
        name  = "APP_MODE"
        value = "adaptadores"
      }
    }
  }

  depends_on = [null_resource.build_app]
}

# ---------------------------------------------------------------- portal estático
resource "google_cloud_run_v2_service" "portal" {
  name                = local.nombres.portal
  location            = var.region
  ingress             = local.ingress_backend
  deletion_protection = false
  labels              = local.labels

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = local.image_portal

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle = true
      }

      startup_probe {
        http_get {
          path = "/"
        }
        period_seconds    = 3
        timeout_seconds   = 3
        failure_threshold = 20
      }

      env {
        name  = "API_URL"
        value = local.api_para_portal
      }
      env {
        name  = "ENV_NAME"
        value = var.environment
      }
    }
  }

  depends_on = [null_resource.build_portal]
}
