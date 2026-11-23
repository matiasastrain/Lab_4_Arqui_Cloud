output "url_portal" {
  description = "URL del portal (abrir en el navegador). Con borde activo es la IP del balanceador."
  value       = local.portal_publico
}

output "url_api" {
  description = "URL base de la API del gestor. La documentación interactiva está en /docs."
  value       = var.habilitar_borde ? "${local.portal_publico}/api" : google_cloud_run_v2_service.gestor.uri
}

output "url_gestor_cloud_run" {
  description = "URL directa del gestor en Cloud Run."
  value       = google_cloud_run_v2_service.gestor.uri
}

output "funcionario_api_key" {
  description = "Clave del funcionario para ingresar al panel (terraform output -raw funcionario_api_key)."
  value       = random_password.funcionario.result
  sensitive   = true
}

output "ip_privada_base_de_datos" {
  value = google_sql_database_instance.pg.private_ip_address
}

output "bucket_adjuntos" {
  value = google_storage_bucket.adjuntos.name
}

output "imagen_app" {
  value = local.image_app
}

output "prueba_rapida" {
  description = "Comando para ejecutar la prueba de punta a punta contra lo desplegado."
  value       = "python3 ../scripts/smoke_test.py --api ${var.habilitar_borde ? "${local.portal_publico}/api" : google_cloud_run_v2_service.gestor.uri} --clave \"$(terraform output -raw funcionario_api_key)\""
}
