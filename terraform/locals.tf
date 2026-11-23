data "google_project" "this" {
  project_id = var.project_id
}

locals {
  env = var.environment

  labels = {
    app     = "pdi-poc"
    env     = var.environment
    curso   = "tics400"
    gestion = "terraform"
  }

  # Subredes del diagrama (Laboratorio 1): snet-edge .1, snet-app .2, snet-data .3, snet-ops .4, snet-hybrid .5
  subnets  = { edge = 1, app = 2, data = 3, ops = 4, hybrid = 5 }
  psa_cidr = cidrsubnet(var.vpc_cidr, 8, 100) # rango reservado para la IP privada de Cloud SQL

  nombres = {
    gestor = "pdi-gestor-${local.env}"
    notif  = "pdi-notif-${local.env}"
    adapt  = "pdi-adaptadores-${local.env}"
    portal = "pdi-portal-${local.env}"
  }

  # URL determinista de Cloud Run (https://SERVICIO-NUMERO_PROYECTO.REGION.run.app).
  # Se calcula en vez de leerla del recurso para evitar dependencias circulares entre servicios.
  run_url = { for k, n in local.nombres : k => "https://${n}-${data.google_project.this.number}.${var.region}.run.app" }

  portal_publico  = var.habilitar_borde ? "http://${google_compute_global_address.lb[0].address}" : local.run_url.portal
  api_para_portal = var.habilitar_borde ? "/api" : local.run_url.gestor

  repo         = "${var.region}-docker.pkg.dev/${var.project_id}/pdi-${local.env}"
  app_dir      = "${path.module}/../app"
  portal_dir   = "${path.module}/../portal"
  app_hash     = substr(sha1(join("", [for f in sort(tolist(setunion(fileset(local.app_dir, "pdi/*.py"), fileset(local.app_dir, "Dockerfile"), fileset(local.app_dir, "requirements.txt")))) : filesha1("${local.app_dir}/${f}")])), 0, 12)
  portal_hash  = substr(sha1(join("", [for f in sort(tolist(setunion(fileset(local.portal_dir, "index.html"), fileset(local.portal_dir, "app.js"), fileset(local.portal_dir, "styles.css"), fileset(local.portal_dir, "Dockerfile"), fileset(local.portal_dir, "40-config.sh")))) : filesha1("${local.portal_dir}/${f}")])), 0, 12)
  image_app    = "${local.repo}/pdi-app:${local.app_hash}"
  image_portal = "${local.repo}/pdi-portal:${local.portal_hash}"
}
