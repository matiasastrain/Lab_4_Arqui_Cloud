resource "random_password" "db" {
  length  = 32
  special = false
}

resource "random_password" "jwt" {
  length  = 48
  special = false
}

resource "random_password" "funcionario" {
  length  = 20
  special = false
}

locals {
  secretos = {
    db-pass         = random_password.db.result
    jwt-secret      = random_password.jwt.result
    funcionario-key = random_password.funcionario.result
  }
}

resource "google_secret_manager_secret" "s" {
  for_each  = local.secretos
  secret_id = "pdi-${each.key}-${var.ambiente}"
  labels    = local.etiquetas
  replication {
    auto {}
  }
  depends_on = [time_sleep.apis]
}

resource "google_secret_manager_secret_version" "s" {
  for_each    = local.secretos
  secret      = google_secret_manager_secret.s[each.key].id
  secret_data = each.value
}
