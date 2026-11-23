# PROD: alta disponibilidad, instancia mínima, borde con WAF y protección contra borrado (Laboratorio 2).
environment            = "prod"
vpc_cidr               = "10.10.0.0/16"
db_tier                = "db-custom-2-8192"
db_alta_disponibilidad = true
db_disco_gb            = 100
db_respaldos           = true
proteger_datos         = true
force_destroy          = false
run_min_instancias     = 1
run_max_instancias     = 10
run_cpu                = "1"
run_memoria            = "2Gi"
habilitar_borde        = true
