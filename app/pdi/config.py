"""Configuración leída desde variables de entorno.

En Cloud Run las variables las define Terraform (run.tf). En modo local
(scripts/run_local.sh) casi todas quedan vacías y el código usa los
reemplazos locales: SQLite, disco y procesamiento de avisos en línea.
"""
import os
from functools import lru_cache


class Config:
    def __init__(self) -> None:
        e = os.environ.get
        self.app_mode = e("APP_MODE", "gestor")
        self.ambiente = e("AMBIENTE", "local")

        # Base de datos
        self.database_url = e("DATABASE_URL", "")
        self.db_host = e("DB_HOST", "")
        self.db_name = e("DB_NAME", "pdi")
        self.db_user = e("DB_USER", "pdi_app")
        self.db_pass = e("DB_PASS", "")

        # Seguridad
        self.jwt_secret = e("JWT_SECRET", "secreto-local-solo-para-desarrollo")
        self.funcionario_api_key = e("FUNCIONARIO_API_KEY", "funcionario-local")
        self.cors_origins = [o for o in e("CORS_ORIGINS", "*").split(",") if o]

        # Almacenamiento de adjuntos
        self.bucket = e("BUCKET", "")
        self.storage_dir = e("STORAGE_DIR", "./datos_locales/adjuntos")

        # Cola de avisos (Cloud Tasks)
        self.tasks_queue = e("TASKS_QUEUE", "")  # projects/P/locations/R/queues/Q
        self.tasks_sa = e("TASKS_SA", "")
        self.notif_url = e("NOTIF_URL", "")

        # Servicio de adaptadores (GEPOL / B3000 simulados)
        self.adaptadores_url = e("ADAPTADORES_URL", "")

        # IA (Gemini en Vertex AI)
        self.ia_habilitada = e("IA_HABILITADA", "false").lower() == "true"
        self.gcp_project = e("GOOGLE_CLOUD_PROJECT", "")
        self.vertex_location = e("VERTEX_LOCATION", "global")
        self.gemini_model = e("GEMINI_MODEL", "gemini-3.5-flash-lite")


@lru_cache
def get_config() -> Config:
    return Config()


def reset_config() -> None:
    """Usado por las pruebas para releer el entorno."""
    get_config.cache_clear()
