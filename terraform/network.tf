# VPC con cinco subredes /20. Las reglas de firewall cumplen el papel de los NSG.
locals {
  subredes = {
    edge   = cidrsubnet(var.vpc_cidr, 4, 0) # reservada: el balanceador global no ocupa subred
    app    = cidrsubnet(var.vpc_cidr, 4, 1) # salida directa a la VPC de Cloud Run
    data   = cidrsubnet(var.vpc_cidr, 4, 2) # reservada para datos futuros (p. ej. caché)
    ops    = cidrsubnet(var.vpc_cidr, 4, 3) # reservada para herramientas de operación
    hybrid = cidrsubnet(var.vpc_cidr, 4, 4) # VPN HA hacia SICOM/GEPOL (no desplegada en la PoC)
  }
  # Rango asignado a Cloud SQL por Private Service Access (zona de datos efectiva)
  rango_psa = cidrsubnet(var.vpc_cidr, 4, 8)
  privados  = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
}

resource "google_compute_network" "vpc" {
  name                    = local.nombre
  auto_create_subnetworks = false
  depends_on              = [time_sleep.apis]
}

resource "google_compute_subnetwork" "snet" {
  for_each                 = local.subredes
  name                     = "snet-${each.key}-${var.ambiente}"
  ip_cidr_range            = each.value
  region                   = var.region
  network                  = google_compute_network.vpc.id
  private_ip_google_access = true
}

# --- Private Service Access para Cloud SQL ---
resource "google_compute_global_address" "psa" {
  name          = "${local.nombre}-psa"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  address       = split("/", local.rango_psa)[0]
  prefix_length = tonumber(split("/", local.rango_psa)[1])
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "psa" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.psa.name]
  deletion_policy         = "ABANDON" # evita el error de borrado mientras Cloud SQL libera el peering
}

# --- Reglas de firewall (equivalentes a los NSG) ---
resource "google_compute_firewall" "deny_ingress" {
  name          = "${local.nombre}-deny-all-ingress"
  network       = google_compute_network.vpc.id
  direction     = "INGRESS"
  priority      = 65000
  source_ranges = ["0.0.0.0/0"]
  deny { protocol = "all" }
  description = "Denegar todo ingreso a la VPC. El ingreso a Cloud Run lo controlan 'ingress' e IAM."
}

resource "google_compute_firewall" "app_a_db" {
  name               = "${local.nombre}-allow-app-db"
  network            = google_compute_network.vpc.id
  direction          = "EGRESS"
  priority           = 1000
  target_tags        = ["pdi-gestor", "pdi-notificaciones"]
  destination_ranges = [local.rango_psa]
  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }
  description = "Solo gestor y notificaciones llegan a PostgreSQL (5432)."
}

resource "google_compute_firewall" "app_deny_privados" {
  name               = "${local.nombre}-deny-app-privados"
  network            = google_compute_network.vpc.id
  direction          = "EGRESS"
  priority           = 2000
  target_tags        = ["pdi-app"]
  destination_ranges = local.privados
  deny { protocol = "all" }
  description = "Bloquea el movimiento lateral de las aplicaciones hacia otros rangos privados."
}
