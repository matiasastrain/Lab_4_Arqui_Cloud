"""Configuración de la aplicación.

Todo se lee desde variables de entorno en el momento de usarlo, de modo que
Terraform (Cloud Run) y las pruebas locales configuren la misma imagen sin
cambiar código.
"""
import os
from urllib.parse import quote_plus


def _bool(nombre: str, defecto: str = "0") -> bool:
    return os.getenv(nombre, defecto).strip().lower() in ("1", "true", "yes", "si")


class Settings:
    # --- modo y ambiente -------------------------------------------------
    @property
    def local_mode(self) -> bool:
        """Si es verdadero: sin GCP (SQLite, disco local, tareas en línea, sin IA)."""
        return _bool("LOCAL_MODE")

    @property
    def env_name(self) -> str:
        return os.getenv("ENV_NAME", "local")

    @property
    def project_id(self) -> str:
        return os.getenv("PROJECT_ID", "")

    @property
    def region(self) -> str:
        return os.getenv("REGION", "southamerica-west1")

    # --- base de datos ----------------------------------------------------
    @property
    def database_url(self) -> str:
        directa = os.getenv("DATABASE_URL")
        if directa:
            return directa
        usuario = quote_plus(os.getenv("DB_USER", "pdi_app"))
        clave = quote_plus(os.getenv("DB_PASSWORD", ""))
        host = os.getenv("DB_HOST", "127.0.0.1")
        puerto = os.getenv("DB_PORT", "5432")
        nombre = os.getenv("DB_NAME", "pdi")
        return f"postgresql+psycopg://{usuario}:{clave}@{host}:{puerto}/{nombre}?sslmode=require"

    # --- almacenamiento ---------------------------------------------------
    @property
    def bucket(self) -> str:
        return os.getenv("BUCKET_ADJUNTOS", "")

    @property
    def local_storage_dir(self) -> str:
        return os.getenv("LOCAL_STORAGE_DIR", "/tmp/pdi_local_storage")

    # --- seguridad ----------------------------------------------------------
    @property
    def jwt_secret(self) -> str:
        return os.getenv("JWT_SECRET", "solo-para-desarrollo-local-no-usar-en-la-nube")

    @property
    def funcionario_api_key(self) -> str:
        return os.getenv("FUNCIONARIO_API_KEY", "")

    @property
    def cors_origins(self) -> list[str]:
        crudo = os.getenv("CORS_ORIGINS", "*")
        return [o.strip() for o in crudo.split(",") if o.strip()]

    # --- servicios internos -------------------------------------------------
    @property
    def tasks_queue(self) -> str:
        return os.getenv("TASKS_QUEUE", "")

    @property
    def tasks_sa_email(self) -> str:
        return os.getenv("TASKS_SA_EMAIL", "")

    @property
    def notificaciones_url(self) -> str:
        return os.getenv("NOTIFICACIONES_URL", "").rstrip("/")

    @property
    def adaptadores_url(self) -> str:
        return os.getenv("ADAPTADORES_URL", "").rstrip("/")

    @property
    def portal_url(self) -> str:
        return os.getenv("PORTAL_URL", "https://portal.invalid").rstrip("/")

    # --- IA (Gemini en Vertex AI) ---------------------------------------------
    @property
    def ia_habilitada(self) -> bool:
        return _bool("IA_HABILITADA", "0") and not self.local_mode

    @property
    def vertex_location(self) -> str:
        return os.getenv("VERTEX_LOCATION", "global")

    @property
    def gemini_model(self) -> str:
        return os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


settings = Settings()

TIPOS_TRAMITE = {
    "certificado_viajes": "Certificado de Viajes",
    "vigencia_permanencia_definitiva": "Certificado de Vigencia de Permanencia Definitiva",
}

ESTADOS = ("RECIBIDO", "EN_REVISION", "OBSERVADO", "APROBADO", "RECHAZADO")
ESTADOS_ABIERTOS = ("RECIBIDO", "EN_REVISION", "OBSERVADO")
ESTADOS_FINALES = ("APROBADO", "RECHAZADO")
