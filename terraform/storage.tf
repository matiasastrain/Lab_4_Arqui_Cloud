# Adjuntos y certificados: almacenamiento de objetos privado (no se guardan en la base).
resource "google_storage_bucket" "adjuntos" {
  name                        = "${var.project_id}-pdi-adjuntos-${local.env}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy
  labels                      = local.labels

  versioning {
    enabled = var.proteger_datos
  }
  depends_on = [time_sleep.apis_listas]
}
