# Cola de eventos de cambio de estado: separa el aviso del trámite principal y permite reintentos.
resource "google_cloud_tasks_queue" "avisos" {
  name     = "pdi-avisos-${local.env}"
  location = var.tasks_region

  retry_config {
    max_attempts = 5
    min_backoff  = "5s"
    max_backoff  = "60s"
  }

  depends_on = [time_sleep.apis_listas]
}
