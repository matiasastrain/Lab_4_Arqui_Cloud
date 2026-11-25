locals {
  url_publica_api = var.habilitar_borde ? "http://${google_compute_global_address.lb[0].address}" : local.run_url["gestor"]
  necesita_token  = !var.acceso_publico && !var.habilitar_borde
}

output "url_portal" {
  description = "URL del portal (ciudadano y funcionario)"
  value       = local.origen_publico
}

output "url_api" {
  description = "URL de la API del gestor (documentación interactiva en /docs)"
  value       = local.url_publica_api
}

output "url_docs" {
  value = "${local.url_publica_api}/docs"
}

output "urls_cloud_run" {
  value = { for k, s in google_cloud_run_v2_service.svc : k => s.uri }
}

output "cloud_sql_ip_privada" {
  value = google_sql_database_instance.db.private_ip_address
}

output "funcionario_api_key" {
  description = "Clave del panel del funcionario"
  value       = random_password.funcionario.result
  sensitive   = true
}

output "prueba_rapida" {
  description = "Prueba de punta a punta (ejecutar desde la carpeta terraform con eval)"
  value = join(" ", compact([
    "python3 '${abspath("${path.module}/../scripts/e2e.py")}'",
    "--api '${local.url_publica_api}'",
    "--clave \"$(terraform output -raw funcionario_api_key)\"",
    local.necesita_token ? "--id-token \"$(gcloud auth print-identity-token)\"" : "",
  ]))
}
