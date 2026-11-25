"""Modelos y acceso a datos (SQLAlchemy 2).

Tablas: tramite, historial, adjunto y notificacion. La notificación es única
por evento del historial (restricción uq_notificacion_historial), lo que hace
idempotente el procesamiento de avisos aunque Cloud Tasks reintente.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import get_config

# Estados del trámite
RECIBIDO = "RECIBIDO"
EN_REVISION = "EN_REVISION"
APROBADO = "APROBADO"
OBSERVADO = "OBSERVADO"
RECHAZADO = "RECHAZADO"
ESTADOS_ACTIVOS = (RECIBIDO, EN_REVISION, OBSERVADO)
ESTADOS_FINALES = (APROBADO, RECHAZADO)

TIPOS = {
    "CERT_VIAJES": {"nombre": "Certificado de Viajes", "prefijo": "CV"},
    "VIGENCIA_PD": {"nombre": "Certificado de Vigencia de Permanencia Definitiva", "prefijo": "PD"},
}


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Tramite(Base):
    __tablename__ = "tramite"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folio: Mapped[Optional[str]] = mapped_column(String(32), unique=True, index=True)
    tipo: Mapped[str] = mapped_column(String(32))
    rut: Mapped[str] = mapped_column(String(12), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[Optional[str]] = mapped_column(String(160))
    telefono: Mapped[Optional[str]] = mapped_column(String(20))
    detalle: Mapped[Optional[str]] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(16), index=True)
    funcionario: Mapped[Optional[str]] = mapped_column(String(60))
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    historial: Mapped[list["Historial"]] = relationship(
        back_populates="tramite", order_by="Historial.id", cascade="all, delete-orphan"
    )
    adjuntos: Mapped[list["Adjunto"]] = relationship(
        back_populates="tramite", order_by="Adjunto.id", cascade="all, delete-orphan"
    )


class Historial(Base):
    __tablename__ = "historial"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tramite_id: Mapped[int] = mapped_column(ForeignKey("tramite.id"), index=True)
    estado_anterior: Mapped[Optional[str]] = mapped_column(String(16))
    estado_nuevo: Mapped[str] = mapped_column(String(16))
    actor: Mapped[str] = mapped_column(String(60))
    comentario: Mapped[Optional[str]] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    tramite: Mapped[Tramite] = relationship(back_populates="historial")


class Adjunto(Base):
    __tablename__ = "adjunto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tramite_id: Mapped[int] = mapped_column(ForeignKey("tramite.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(40))
    tamano: Mapped[int] = mapped_column(Integer)
    ruta: Mapped[str] = mapped_column(String(300))
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    tramite: Mapped[Tramite] = relationship(back_populates="adjuntos")


class Notificacion(Base):
    __tablename__ = "notificacion"
    __table_args__ = (UniqueConstraint("historial_id", name="uq_notificacion_historial"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    historial_id: Mapped[int] = mapped_column(ForeignKey("historial.id"))
    tramite_id: Mapped[int] = mapped_column(ForeignKey("tramite.id"), index=True)
    canal: Mapped[str] = mapped_column(String(10))
    destino: Mapped[str] = mapped_column(String(160))
    texto: Mapped[str] = mapped_column(Text)
    origen: Mapped[str] = mapped_column(String(12))  # gemini | plantilla
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# --------------------------------------------------------------------------
# Motor y sesiones
# --------------------------------------------------------------------------
_engine: Optional[Engine] = None
SessionLocal = sessionmaker(expire_on_commit=False)


def url_desde_entorno() -> str | URL:
    c = get_config()
    if c.database_url:
        return c.database_url
    if c.db_host:
        # Cloud SQL por IP privada con SSL obligatorio (ssl_mode ENCRYPTED_ONLY)
        return URL.create(
            "postgresql+psycopg2",
            username=c.db_user,
            password=c.db_pass,
            host=c.db_host,
            port=5432,
            database=c.db_name,
            query={"sslmode": "require"},
        )
    return "sqlite:///./datos_locales/pdi_local.db"


def configurar(url: str | URL | None = None, crear_tablas: bool = True) -> Engine:
    global _engine
    url = url or url_desde_entorno()
    es_sqlite = str(url).startswith("sqlite")
    if es_sqlite and ":memory:" not in str(url):
        import os

        ruta = str(url).replace("sqlite:///", "")
        os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    kwargs = {"connect_args": {"check_same_thread": False}} if es_sqlite else {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 5,
    }
    _engine = create_engine(url, **kwargs)
    SessionLocal.configure(bind=_engine)
    if crear_tablas:
        Base.metadata.create_all(_engine)
    return _engine


def engine() -> Engine:
    if _engine is None:
        configurar()
    return _engine  # type: ignore[return-value]


def get_session():
    """Dependencia de FastAPI."""
    engine()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
