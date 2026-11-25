# Artifact Registry + construcción de las dos imágenes con Cloud Build.
# La etiqueta de la imagen es un hash del código: si el código cambia, se
# reconstruye y Cloud Run despliega una nueva revisión.
locals {
  fuentes = {
    app    = abspath("${path.module}/../app")
    portal = abspath("${path.module}/../portal")
  }
  hash_fuentes = {
    for k, dir in local.fuentes : k => substr(sha1(join("", [
      for f in sort(fileset(dir, "**")) : filesha1("${dir}/${f}")
      if length(regexall("(__pycache__|\\.pytest_cache|datos_locales|\\.db$|^tests/|\\.venv)", f)) == 0
    ])), 0, 12)
  }
  registro = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
  imagenes = { for k in keys(local.fuentes) : k => "${local.registro}/${k}:${local.hash_fuentes[k]}" }
}

resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "pdi-${var.ambiente}"
  format        = "DOCKER"
  labels        = local.etiquetas
  depends_on    = [time_sleep.apis]
}

resource "null_resource" "build" {
  for_each = local.fuentes

  triggers = {
    imagen = local.imagenes[each.key]
  }

  provisioner "local-exec" {
    command = join(" ", [
      "gcloud builds submit '${each.value}'",
      "--project='${var.project_id}'",
      "--config='${each.value}/cloudbuild.yaml'",
      "--substitutions=_IMAGE='${local.imagenes[each.key]}'",
      "--service-account='projects/${var.project_id}/serviceAccounts/${google_service_account.sa["build"].email}'",
      "--quiet",
    ])
  }

  depends_on = [time_sleep.iam, google_artifact_registry_repository.repo]
}
