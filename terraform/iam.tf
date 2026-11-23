# Una cuenta de servicio por componente, con el mínimo privilegio (principio del Laboratorio 1).
locals {
  cuentas = {
    gestor = "sa-gestor-${local.env}"
    notif  = "sa-notif-${local.env}"
    adapt  = "sa-adaptadores-${local.env}"
    tasks  = "sa-tasks-${local.env}"
    build  = "sa-build-${local.env}"
  }
}

resource "google_service_account" "sa" {
  for_each     = local.cuentas
  account_id   = each.value
  display_name = "PDI PoC ${each.key} (${local.env})"
  depends_on   = [time_sleep.apis_listas]
}

# ---------------------------------------------------------------- gestor
resource "google_storage_bucket_iam_member" "gestor_adjuntos" {
  bucket = google_storage_bucket.adjuntos.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.sa["gestor"].email}"
}

resource "google_project_iam_member" "gestor_tasks" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.sa["gestor"].email}"
}

# Para crear tareas con token OIDC de sa-tasks, el gestor debe poder "actuar como" esa cuenta.
resource "google_service_account_iam_member" "gestor_actas_tasks" {
  service_account_id = google_service_account.sa["tasks"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.sa["gestor"].email}"
}

resource "google_secret_manager_secret_iam_member" "gestor_secretos" {
  for_each  = toset(local.secreto_ids)
  secret_id = google_secret_manager_secret.s[each.key].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.sa["gestor"].email}"
}

resource "google_cloud_run_v2_service_iam_member" "gestor_invoca_adaptadores" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.adaptadores.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.sa["gestor"].email}"
}

# ---------------------------------------------------------------- notificaciones
resource "google_secret_manager_secret_iam_member" "notif_db" {
  secret_id = google_secret_manager_secret.s["db_password"].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.sa["notif"].email}"
}

resource "google_project_iam_member" "notif_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.sa["notif"].email}"
}

# ---------------------------------------------------------------- Cloud Tasks -> notificaciones
resource "google_cloud_run_v2_service_iam_member" "tasks_invoca_notif" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.notif.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.sa["tasks"].email}"
}

# ---------------------------------------------------------------- construcción de imágenes
resource "google_project_iam_member" "build_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.sa["build"].email}"
}

resource "google_artifact_registry_repository_iam_member" "build_escribe" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.repo.repository_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.sa["build"].email}"
}

resource "google_storage_bucket_iam_member" "build_lee_fuente" {
  bucket = google_storage_bucket.build_src.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.sa["build"].email}"
}

# ---------------------------------------------------------------- acceso público (la API exige su propio token)
locals {
  servicios_publicos = var.acceso_publico ? {
    portal = google_cloud_run_v2_service.portal.name
    gestor = google_cloud_run_v2_service.gestor.name
  } : {}
}

resource "google_cloud_run_v2_service_iam_member" "publico" {
  for_each = local.servicios_publicos
  project  = var.project_id
  location = var.region
  name     = each.value
  role     = "roles/run.invoker"
  member   = "allUsers"
}
