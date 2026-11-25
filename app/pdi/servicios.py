"""Lógica compartida entre el gestor y el servicio de notificaciones."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import ai, logs
from .db import Historial, Notificacion, SessionLocal, Tramite, ahora, engine


def registrar_cambio(
    s: Session, t: Tramite, nuevo: str, actor: str, comentario: Optional[str] = None
) -> Historial:
    """Cambia el estado y agrega el evento al historial (sin confirmar)."""
    h = Historial(
        tramite_id=t.id,
        estado_anterior=t.estado if t.historial else None,
        estado_nuevo=nuevo,
        actor=actor,
        comentario=comentario,
    )
    t.estado = nuevo
    t.actualizado = ahora()
    t.historial.append(h)
    s.flush()
    return h


def procesar_aviso(historial_id: int) -> dict:
    """Procesa un aviso de forma idempotente.

    Si ya existe una notificación para ese evento (reintento de Cloud Tasks),
    no se vuelve a enviar. El envío por correo/SMS está SIMULADO: se registra
    en los logs.
    """
    engine()
    with SessionLocal() as s:
        if s.scalar(select(Notificacion).where(Notificacion.historial_id == historial_id)):
            logs.info("Aviso duplicado ignorado", historial_id=historial_id)
            return {"estado": "duplicado"}

        h = s.get(Historial, historial_id)
        if h is None:
            logs.warning("Evento de historial inexistente", historial_id=historial_id)
            return {"estado": "ignorado"}
        t = h.tramite

        texto, origen = ai.redactar_aviso(t.folio, t.tipo, h.estado_nuevo, t.nombre, h.comentario)
        canal, destino = ("email", t.email) if t.email else (("sms", t.telefono) if t.telefono else ("ninguno", "sin-contacto"))

        s.add(Notificacion(
            historial_id=h.id, tramite_id=t.id, canal=canal, destino=destino, texto=texto, origen=origen
        ))
        try:
            s.commit()
        except IntegrityError:
            # Dos entregas simultáneas de la misma tarea: la restricción única gana.
            s.rollback()
            logs.info("Aviso duplicado (carrera) ignorado", historial_id=historial_id)
            return {"estado": "duplicado"}

        logs.info(
            "AVISO ENVIADO (simulado)",
            folio=t.folio, estado=h.estado_nuevo, canal=canal, destino=destino, origen=origen, texto=texto,
        )
        return {"estado": "enviado", "origen": origen}
