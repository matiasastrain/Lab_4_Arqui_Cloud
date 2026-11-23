# QA: réplica reducida de PROD (Laboratorio 2): balanceador y Cloud Armor activos, base en una zona.
environment            = "qa"
vpc_cidr               = "10.20.0.0/16"
db_tier                = "db-custom-2-8192"
db_alta_disponibilidad = false
db_disco_gb            = 50
db_respaldos           = true
proteger_datos         = false
run_min_instancias     = 0
run_max_instancias     = 5
habilitar_borde        = true
