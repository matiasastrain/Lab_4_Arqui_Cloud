resource "google_cloud_tasks_queue" "avisos" {
  # Sufijo aleatorio: un nombre de cola borrado no se puede reutilizar por 7 días
  name     = "pdi-avisos-${var.ambiente}-${local.sufijo}"
  location = var.region_tareas

  rate_limits {
    max_dispatches_per_second = 10
    max_concurrent_dispatches = 5
  }

  retry_config {
    max_attempts       = 8
    min_backoff        = "5s"
    max_backoff        = "300s"
    max_doublings      = 4
    max_retry_duration = "3600s"
  }

  depends_on = [time_sleep.apis]
}
