# Cuatro servicios de Cloud Run con salida directa a la VPC (subred snet-app).
locals {
  borde = var.habilitar_borde

  servicios = {
    portal = {
      imagen  = "portal"
      ingress = local.borde ? "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER" : "INGRESS_TRAFFIC_ALL"
      publico = var.acceso_publico || local.borde
      tags    = tolist(["pdi-app"])
      min     = 0
    }
    gestor = {
      imagen  = "app"
      ingress = local.borde ? "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER" : "INGRESS_TRAFFIC_ALL"
      publico = var.acceso_publico || local.borde
      tags    = tolist(["pdi-app", "pdi-gestor"])
      min     = var.run_min_instancias
    }
    notificaciones = {
      imagen  = "app"
      ingress = "INGRESS_TRAFFIC_ALL" # Cloud Tasks llega por Internet con token OIDC
      publico = false
      tags    = tolist(["pdi-app", "pdi-notificaciones"])
      min     = 0
    }
    adaptadores = {
      imagen  = "app"
      ingress = "INGRESS_TRAFFIC_ALL"
      publico = false # solo el gestor (roles/run.invoker)
      tags    = tolist(["pdi-app"])
      min     = 0
    }
  }

  origen_publico = local.borde ? "http://${google_compute_global_address.lb[0].address}" : local.run_url["portal"]

  env = {
    portal = {
      API_URL = local.borde ? "/" : local.run_url["gestor"] # "/" = misma origen detrás del balanceador
    }
    gestor = {
      APP_MODE        = "gestor"
      AMBIENTE        = var.ambiente
      DB_HOST         = google_sql_database_instance.db.private_ip_address
      DB_NAME         = google_sql_database.pdi.name
      DB_USER         = google_sql_user.app.name
      BUCKET          = google_storage_bucket.adjuntos.name
      TASKS_QUEUE     = google_cloud_tasks_queue.avisos.id
      TASKS_SA        = google_service_account.sa["tareas"].email
      NOTIF_URL       = local.run_url["notificaciones"]
      ADAPTADORES_URL = local.run_url["adaptadores"]
      CORS_ORIGINS    = local.origen_publico
    }
    notificaciones = {
      APP_MODE             = "notificaciones"
      AMBIENTE             = var.ambiente
      DB_HOST              = google_sql_database_instance.db.private_ip_address
      DB_NAME              = google_sql_database.pdi.name
      DB_USER              = google_sql_user.app.name
      IA_HABILITADA        = tostring(var.ia_habilitada)
      GOOGLE_CLOUD_PROJECT = var.project_id
      VERTEX_LOCATION      = var.vertex_location
      GEMINI_MODEL         = var.gemini_modelo
    }
    adaptadores = {
      APP_MODE = "adaptadores"
      AMBIENTE = var.ambiente
    }
  }

  secretos_env = {
    portal         = {}
    gestor         = { DB_PASS = "db-pass", JWT_SECRET = "jwt-secret", FUNCIONARIO_API_KEY = "funcionario-key" }
    notificaciones = { DB_PASS = "db-pass" }
    adaptadores    = {}
  }
}

resource "google_cloud_run_v2_service" "svc" {
  for_each = local.servicios

  name                 = "pdi-${each.key}-${var.ambiente}"
  location             = var.region
  ingress              = each.value.ingress
  invoker_iam_disabled = each.value.publico
  deletion_protection  = false
  labels               = local.etiquetas

  template {
    service_account = google_service_account.sa[each.key].email
    timeout         = "60s"

    scaling {
      min_instance_count = each.value.min
      max_instance_count = var.run_max_instancias
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY" # solo el tráfico privado (Cloud SQL) entra a la VPC
      network_interfaces {
        network    = google_compute_network.vpc.id
        subnetwork = google_compute_subnetwork.snet["app"].id
        tags       = each.value.tags
      }
    }

    containers {
      image = local.imagenes[each.value.imagen]

      resources {
        limits   = { cpu = "1", memory = "512Mi" }
        cpu_idle = true
      }

      dynamic "env" {
        for_each = local.env[each.key]
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.secretos_env[each.key]
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.s[env.value].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    null_resource.build,
    time_sleep.iam,
    google_sql_user.app,
    google_sql_database.pdi,
    google_secret_manager_secret_version.s,
  ]
}
