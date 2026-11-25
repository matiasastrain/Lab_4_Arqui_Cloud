# Una cuenta de servicio por componente, con permisos mínimos.
locals {
  cuentas = {
    portal         = "Portal web (sin acceso a datos)"
    gestor         = "Gestor de trámites"
    notificaciones = "Servicio de notificaciones"
    adaptadores    = "Adaptadores simulados GEPOL/B3000"
    tareas         = "Identidad OIDC de Cloud Tasks hacia notificaciones"
    build          = "Construcción de imágenes con Cloud Build"
  }
}

resource "google_service_account" "sa" {
  for_each     = local.cuentas
  account_id   = "pdi-${each.key}-${var.ambiente}"
  display_name = each.value
  depends_on   = [time_sleep.apis]
}

# --- Gestor ---
resource "google_storage_bucket_iam_member" "gestor_bucket" {
  bucket = google_storage_bucket.adjuntos.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.sa["gestor"].email}"
}

resource "google_cloud_tasks_queue_iam_member" "gestor_encola" {
  name     = google_cloud_tasks_queue.avisos.name
  location = var.region_tareas
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${google_service_account.sa["gestor"].email}"
}

# El gestor crea tareas firmadas con la identidad sa-tareas
resource "google_service_account_iam_member" "gestor_actua_como_tareas" {
  service_account_id = google_service_account.sa["tareas"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.sa["gestor"].email}"
}

# --- Notificaciones: lee la base y usa Gemini; NO tiene acceso al bucket ---
resource "google_project_iam_member" "notif_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.sa["notificaciones"].email}"
}

# --- Secretos ---
locals {
  acceso_secretos = {
    "gestor-db"   = { cuenta = "gestor", secreto = "db-pass" }
    "gestor-jwt"  = { cuenta = "gestor", secreto = "jwt-secret" }
    "gestor-func" = { cuenta = "gestor", secreto = "funcionario-key" }
    "notif-db"    = { cuenta = "notificaciones", secreto = "db-pass" }
  }
}

resource "google_secret_manager_secret_iam_member" "acceso" {
  for_each  = local.acceso_secretos
  secret_id = google_secret_manager_secret.s[each.value.secreto].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.sa[each.value.cuenta].email}"
}

# --- Invocaciones entre servicios (autenticación IAM) ---
resource "google_cloud_run_v2_service_iam_member" "tareas_invoca_notif" {
  name     = google_cloud_run_v2_service.svc["notificaciones"].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.sa["tareas"].email}"
}

resource "google_cloud_run_v2_service_iam_member" "gestor_invoca_adapt" {
  name     = google_cloud_run_v2_service.svc["adaptadores"].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.sa["gestor"].email}"
}

# --- Construcción de imágenes ---
resource "google_project_iam_member" "build" {
  for_each = toset(["roles/logging.logWriter", "roles/storage.objectViewer", "roles/artifactregistry.writer"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.sa["build"].email}"
}

# Los permisos de IAM tardan en propagarse
resource "time_sleep" "iam" {
  depends_on = [
    google_project_iam_member.build,
    google_secret_manager_secret_iam_member.acceso,
    google_storage_bucket_iam_member.gestor_bucket,
  ]
  create_duration = "60s"
}
