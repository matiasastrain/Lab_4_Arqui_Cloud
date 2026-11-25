# Borde opcional: balanceador HTTP global + Cloud Armor (solo con habilitar_borde = true).
# El portal y la API quedan detrás del balanceador (misma origen, sin contenido mixto)
# y sus URL *.run.app dejan de aceptar tráfico directo (ingress interno + balanceador),
# por lo que Cloud Armor no se puede saltar.
locals {
  borde_backends = var.habilitar_borde ? toset(["portal", "gestor"]) : toset([])
}

resource "google_compute_global_address" "lb" {
  count      = var.habilitar_borde ? 1 : 0
  name       = "${local.nombre}-lb-ip"
  depends_on = [time_sleep.apis]
}

resource "google_compute_security_policy" "armor" {
  count       = var.habilitar_borde ? 1 : 0
  name        = "${local.nombre}-armor"
  description = "WAF: inyección SQL, XSS y límite de tasa por IP"

  rule {
    action      = "deny(403)"
    priority    = 1000
    description = "Inyección SQL (OWASP CRS)"
    match {
      expr { expression = "evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1})" }
    }
  }

  rule {
    action      = "deny(403)"
    priority    = 1001
    description = "Cross-site scripting (OWASP CRS)"
    match {
      expr { expression = "evaluatePreconfiguredWaf('xss-v33-stable', {'sensitivity': 1})" }
    }
  }

  rule {
    action      = "throttle"
    priority    = 2000
    description = "Máximo 120 solicitudes por minuto por IP"
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = 120
        interval_sec = 60
      }
    }
  }

  rule {
    action      = "allow"
    priority    = 2147483647
    description = "Regla por defecto"
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
  }
}

resource "google_compute_region_network_endpoint_group" "neg" {
  for_each              = local.borde_backends
  name                  = "${local.nombre}-neg-${each.key}"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = google_cloud_run_v2_service.svc[each.key].name
  }
}

resource "google_compute_backend_service" "be" {
  for_each              = local.borde_backends
  name                  = "${local.nombre}-be-${each.key}"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTPS"
  security_policy       = google_compute_security_policy.armor[0].id
  backend {
    group = google_compute_region_network_endpoint_group.neg[each.key].id
  }
}

resource "google_compute_url_map" "lb" {
  count           = var.habilitar_borde ? 1 : 0
  name            = "${local.nombre}-urlmap"
  default_service = google_compute_backend_service.be["portal"].id

  host_rule {
    hosts        = ["*"]
    path_matcher = "rutas"
  }

  path_matcher {
    name            = "rutas"
    default_service = google_compute_backend_service.be["portal"].id
    path_rule {
      paths   = ["/api/*", "/docs", "/openapi.json", "/healthz"]
      service = google_compute_backend_service.be["gestor"].id
    }
  }
}

resource "google_compute_target_http_proxy" "lb" {
  count   = var.habilitar_borde ? 1 : 0
  name    = "${local.nombre}-http-proxy"
  url_map = google_compute_url_map.lb[0].id
}

resource "google_compute_global_forwarding_rule" "lb" {
  count                 = var.habilitar_borde ? 1 : 0
  name                  = "${local.nombre}-http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  target                = google_compute_target_http_proxy.lb[0].id
  ip_address            = google_compute_global_address.lb[0].id
  port_range            = "80"
}
