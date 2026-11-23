# Borde opcional (habilitar_borde = true): balanceador HTTP global + Cloud Armor delante del portal y de la API.
# Equivale a la zona snet-edge del diagrama. Sin dominio no hay certificado, por eso la PoC usa HTTP;
# en producción se agrega un dominio, un certificado administrado y la redirección a HTTPS.

resource "google_compute_global_address" "lb" {
  count      = var.habilitar_borde ? 1 : 0
  name       = "pdi-lb-ip-${local.env}"
  depends_on = [time_sleep.apis_listas]
}

resource "google_compute_security_policy" "waf" {
  count       = var.habilitar_borde ? 1 : 0
  name        = "pdi-waf-${local.env}"
  description = "Cloud Armor: reglas OWASP y límite de tasa por IP (cambio M1 del Laboratorio 2)"
  type        = "CLOUD_ARMOR"

  rule {
    description = "Bloquea inyección SQL"
    action      = "deny(403)"
    priority    = 1000
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('sqli-v33-stable')"
      }
    }
  }

  rule {
    description = "Bloquea XSS"
    action      = "deny(403)"
    priority    = 1001
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('xss-v33-stable')"
      }
    }
  }

  rule {
    description = "Límite de tasa por IP"
    action      = "throttle"
    priority    = 2000
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = var.limite_solicitudes_por_minuto
        interval_sec = 60
      }
    }
  }

  rule {
    description = "Regla por defecto: permitir"
    action      = "allow"
    priority    = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }
}

resource "google_compute_region_network_endpoint_group" "neg_portal" {
  count                 = var.habilitar_borde ? 1 : 0
  name                  = "pdi-neg-portal-${local.env}"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = google_cloud_run_v2_service.portal.name
  }
}

resource "google_compute_region_network_endpoint_group" "neg_gestor" {
  count                 = var.habilitar_borde ? 1 : 0
  name                  = "pdi-neg-gestor-${local.env}"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = google_cloud_run_v2_service.gestor.name
  }
}

resource "google_compute_backend_service" "portal" {
  count                 = var.habilitar_borde ? 1 : 0
  name                  = "pdi-be-portal-${local.env}"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  security_policy       = google_compute_security_policy.waf[0].id

  backend {
    group = google_compute_region_network_endpoint_group.neg_portal[0].id
  }
}

resource "google_compute_backend_service" "gestor" {
  count                 = var.habilitar_borde ? 1 : 0
  name                  = "pdi-be-gestor-${local.env}"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  security_policy       = google_compute_security_policy.waf[0].id

  backend {
    group = google_compute_region_network_endpoint_group.neg_gestor[0].id
  }
}

# /api/* va al gestor (se quita el prefijo /api) y el resto al portal: mismo origen, sin CORS.
resource "google_compute_url_map" "lb" {
  count           = var.habilitar_borde ? 1 : 0
  name            = "pdi-urlmap-${local.env}"
  default_service = google_compute_backend_service.portal[0].id

  host_rule {
    hosts        = ["*"]
    path_matcher = "principal"
  }

  path_matcher {
    name            = "principal"
    default_service = google_compute_backend_service.portal[0].id

    path_rule {
      paths = ["/api/*"]
      route_action {
        url_rewrite {
          path_prefix_rewrite = "/"
        }
        weighted_backend_services {
          backend_service = google_compute_backend_service.gestor[0].id
          weight          = 100
        }
      }
    }
  }
}

resource "google_compute_target_http_proxy" "lb" {
  count   = var.habilitar_borde ? 1 : 0
  name    = "pdi-proxy-${local.env}"
  url_map = google_compute_url_map.lb[0].id
}

resource "google_compute_global_forwarding_rule" "lb" {
  count                 = var.habilitar_borde ? 1 : 0
  name                  = "pdi-fr-${local.env}"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_protocol           = "TCP"
  port_range            = "80"
  ip_address            = google_compute_global_address.lb[0].address
  target                = google_compute_target_http_proxy.lb[0].id
}
