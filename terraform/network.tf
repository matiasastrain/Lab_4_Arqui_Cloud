# ---------------------------------------------------------------- VPC y subredes
resource "google_compute_network" "vpc" {
  name                    = "pdi-tramites-${local.env}"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
  depends_on              = [time_sleep.apis_listas]
}

resource "google_compute_subnetwork" "snet" {
  for_each                 = local.subnets
  name                     = "snet-${each.key}-${local.env}"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = cidrsubnet(var.vpc_cidr, 8, each.value)
  private_ip_google_access = true
}

# ---------------------------------------------------------------- reglas de firewall (equivalen a los NSG del diagrama)
# Los servicios de Cloud Run con Direct VPC egress llevan la etiqueta "pdi-app".

resource "google_compute_firewall" "deny_ingress_all" {
  name      = "pdi-${local.env}-deny-ingress-all"
  network   = google_compute_network.vpc.id
  direction = "INGRESS"
  priority  = 65000

  deny {
    protocol = "all"
  }
  source_ranges = ["0.0.0.0/0"]
}

# snet-app solo puede hablar con la base de datos (snet-data / Cloud SQL), por PostgreSQL.
resource "google_compute_firewall" "allow_egress_app_to_data" {
  name      = "pdi-${local.env}-allow-egress-app-data"
  network   = google_compute_network.vpc.id
  direction = "EGRESS"
  priority  = 900

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }
  destination_ranges = [local.psa_cidr]
  target_tags        = ["pdi-app"]
}

# El resto de las redes privadas queda cerrado para la capa de aplicación.
resource "google_compute_firewall" "deny_egress_app_private" {
  name      = "pdi-${local.env}-deny-egress-app-private"
  network   = google_compute_network.vpc.id
  direction = "EGRESS"
  priority  = 1000

  deny {
    protocol = "all"
  }
  destination_ranges = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
  target_tags        = ["pdi-app"]
}

# ---------------------------------------------------------------- acceso privado a Cloud SQL
resource "google_compute_global_address" "psa" {
  name          = "pdi-psa-${local.env}"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  address       = cidrhost(local.psa_cidr, 0)
  prefix_length = tonumber(split("/", local.psa_cidr)[1])
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "psa" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.psa.name]
}
