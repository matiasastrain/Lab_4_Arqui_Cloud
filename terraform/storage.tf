resource "google_storage_bucket" "adjuntos" {
  name                        = "${var.project_id}-pdi-adjuntos-${var.ambiente}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = !var.proteger_datos
  labels                      = local.etiquetas

  versioning { enabled = var.proteger_datos }
  depends_on = [time_sleep.apis]
}
