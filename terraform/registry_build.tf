# ---------------------------------------------------------------- repositorio de imágenes
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "pdi-${local.env}"
  format        = "DOCKER"
  description   = "Imágenes de la PoC PDI (${local.env}). La misma imagen recorre DEV, QA y PROD."
  labels        = local.labels
  depends_on    = [time_sleep.apis_listas]
}

# Bucket donde Cloud Build lee el código fuente que sube gcloud.
resource "google_storage_bucket" "build_src" {
  name                        = "${var.project_id}-pdi-build-${local.env}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true
  labels                      = local.labels

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }
  depends_on = [time_sleep.apis_listas]
}

# Los permisos de IAM tardan en propagarse; sin esta pausa el primer build puede fallar por permisos.
resource "time_sleep" "iam_build" {
  depends_on = [
    google_project_iam_member.build_logs,
    google_artifact_registry_repository_iam_member.build_escribe,
    google_storage_bucket_iam_member.build_lee_fuente,
  ]
  create_duration = "45s"
}

# ---------------------------------------------------------------- construcción de imágenes con Cloud Build
# Se reconstruyen solo cuando cambia el código (el hash del código es la etiqueta de la imagen).
resource "null_resource" "build_app" {
  triggers = {
    imagen = local.image_app
  }

  provisioner "local-exec" {
    command = <<-EOT
      gcloud builds submit "${local.app_dir}" \
        --project="${var.project_id}" \
        --config="${local.app_dir}/cloudbuild.yaml" \
        --service-account="projects/${var.project_id}/serviceAccounts/${google_service_account.sa["build"].email}" \
        --gcs-source-staging-dir="gs://${google_storage_bucket.build_src.name}/source" \
        --substitutions="_IMAGE=${local.image_app}" \
        --quiet
    EOT
  }

  depends_on = [time_sleep.iam_build]
}

resource "null_resource" "build_portal" {
  triggers = {
    imagen = local.image_portal
  }

  provisioner "local-exec" {
    command = <<-EOT
      gcloud builds submit "${local.portal_dir}" \
        --project="${var.project_id}" \
        --config="${local.portal_dir}/cloudbuild.yaml" \
        --service-account="projects/${var.project_id}/serviceAccounts/${google_service_account.sa["build"].email}" \
        --gcs-source-staging-dir="gs://${google_storage_bucket.build_src.name}/source" \
        --substitutions="_IMAGE=${local.image_portal}" \
        --quiet
    EOT
  }

  depends_on = [time_sleep.iam_build]
}
