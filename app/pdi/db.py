"""Modelo de datos (SQLAlchemy). En GCP corre sobre Cloud SQL PostgreSQL."""
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import settings

log = logging.getLogger("pdi.db")


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def como_utc(valor: datetime | None) -> datetime | None:
    """SQLite devuelve fechas sin zona; PostgreSQL con zona. Unificamos en UTC."""
    if valor is None:
        return None
    return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class Tramite(Base):
    __tablename__ = "tramites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folio: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    tipo: Mapped[str] = mapped_column(String(50))
    rut: Mapped[str] = mapped_column(String(12), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160))
    estado: Mapped[str] = mapped_column(String(20), index=True)
    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    historial: Mapped[list["Historial"]] = relationship(
        back_populates="tramite", order_by="Historial.id", cascade="all, delete-orphan"
    )
    adjuntos: Mapped[list["Adjunto"]] = relationship(
        back_populates="tramite", order_by="Adjunto.id", cascade="all, delete-orphan"
    )


class Historial(Base):
    """Cada cambio de estado queda aquí. Es el 'estado oficial' que ve el ciudadano."""

    __tablename__ = "historial"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folio: Mapped[str] = mapped_column(ForeignKey("tramites.folio"), index=True)
    estado: Mapped[str] = mapped_column(String(20))
    detalle: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(60), default="sistema")
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    tramite: Mapped[Tramite] = relationship(back_populates="historial")


class Adjunto(Base):
    __tablename__ = "adjuntos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folio: Mapped[str] = mapped_column(ForeignKey("tramites.folio"), index=True)
    nombre: Mapped[str] = mapped_column(String(160))
    content_type: Mapped[str] = mapped_column(String(80))
    tamano: Mapped[int] = mapped_column(Integer)
    objeto: Mapped[str] = mapped_column(String(300))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    tramite: Mapped[Tramite] = relationship(back_populates="adjuntos")


class Notificacion(Base):
    """Aviso al ciudadano. historial_id es único: Cloud Tasks reintenta y no duplicamos."""

    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    historial_id: Mapped[int] = mapped_column(Integer, unique=True)
    folio: Mapped[str] = mapped_column(String(32), index=True)
    estado: Mapped[str] = mapped_column(String(20))
    canal: Mapped[str] = mapped_column(String(30), default="correo (simulado)")
    mensaje: Mapped[str] = mapped_column(Text)
    generado_por: Mapped[str] = mapped_column(String(30))  # "ia" o "plantilla"
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


_engine = None
_Session = None


def get_engine():
    global _engine, _Session
    if _engine is None:
        url = settings.database_url
        opciones: dict = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            opciones["connect_args"] = {"check_same_thread": False}
        else:
            opciones.update(pool_size=5, max_overflow=5, pool_recycle=1800)
        _engine = create_engine(url, **opciones)
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def reiniciar_engine() -> None:
    """Solo para pruebas: fuerza a recrear el engine con otra URL."""
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    _engine, _Session = None, None


def nueva_sesion():
    get_engine()
    return _Session()


def iniciar_bd(intentos: int = 10, espera: float = 3.0) -> bool:
    """Crea las tablas si no existen. Reintenta porque la BD puede tardar en aceptar conexiones."""
    for n in range(1, intentos + 1):
        try:
            Base.metadata.create_all(get_engine())
            log.info("Base de datos lista")
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("BD no disponible (intento %s/%s): %s", n, intentos, exc)
            time.sleep(espera)
    return False
