# DEV: entorno mínimo para programar y para la demostración de la PoC (Laboratorio 2, Tabla 5).
environment            = "dev"
vpc_cidr               = "10.30.0.0/16"
db_tier                = "db-f1-micro" # el Lab 2 estimó 1 vCPU/3,75 GiB; en la PoC se usa el nivel más barato
db_alta_disponibilidad = false
db_disco_gb            = 10
db_respaldos           = false
proteger_datos         = false
run_min_instancias     = 0
run_max_instancias     = 3
habilitar_borde        = false
