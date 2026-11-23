"""Lógica compartida entre el gestor y el servicio de notificaciones."""
import json
import logging

from sqlalchemy.exc import IntegrityError

from . import ai
from .config import settings
from .db import Historial, Notificacion, Tramite

log = logging.getLogger("pdi.servicios")


def procesar_notificacion(s, historial_id: int) -> dict:
    """Redacta y 'envía' el aviso de un cambio de estado.

    Idempotente: Cloud Tasks reintenta, y historial_id es único en la tabla de avisos.
    El estado usado es el confirmado en la base de datos, no el que viaja en la tarea.
    """
    evento = s.get(Historial, historial_id)
    if evento is None:
        return {"resultado": "omitido", "motivo": "evento inexistente"}
    if s.query(Notificacion).filter_by(historial_id=historial_id).first():
        return {"resultado": "omitido", "motivo": "ya notificado"}

    tramite = s.query(Tramite).filter_by(folio=evento.folio).one()
    texto, origen = ai.redactar_aviso(tramite.tipo, evento.estado, tramite.folio)
    mensaje = f"{texto}\nSeguimiento: {settings.portal_url}/?folio={tramite.folio}"

    aviso = Notificacion(
        historial_id=historial_id,
        folio=tramite.folio,
        estado=evento.estado,
        mensaje=mensaje,
        generado_por=origen,
    )
    s.add(aviso)
    try:
        s.commit()
    except IntegrityError:  # otra réplica ganó la carrera
        s.rollback()
        return {"resultado": "omitido", "motivo": "ya notificado"}

    # En producción aquí se llamaría al proveedor de correo/SMS. En la PoC queda en el log.
    log.info(json.dumps({"evento": "aviso_enviado", "folio": tramite.folio, "estado": evento.estado,
                         "generado_por": origen}))
    return {"resultado": "enviado", "generado_por": origen, "mensaje": mensaje}
