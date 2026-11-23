resource "random_password" "db" {
  length  = 24
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
  secreto_ids = ["db_password", "jwt_secret", "funcionario_api_key"]

  # Los valores son sensibles, por eso el for_each recorre solo los nombres.
  secretos = {
    db_password         = random_password.db.result
    jwt_secret          = random_password.jwt.result
    funcionario_api_key = random_password.funcionario.result
  }
}

resource "google_secret_manager_secret" "s" {
  for_each  = toset(local.secreto_ids)
  secret_id = "pdi-${replace(each.key, "_", "-")}-${local.env}"
  labels    = local.labels

  replication {
    auto {}
  }
  depends_on = [time_sleep.apis_listas]
}

resource "google_secret_manager_secret_version" "s" {
  for_each    = toset(local.secreto_ids)
  secret      = google_secret_manager_secret.s[each.key].id
  secret_data = local.secretos[each.key]
}
