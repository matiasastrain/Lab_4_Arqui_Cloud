"""Publicación de avisos en Cloud Tasks.

Se llama DESPUÉS de confirmar la transacción, para no avisar un cambio que
luego se revierte. Si la cola falla, se registra el error y el trámite sigue
su curso (el estado es lo importante; el aviso es una consecuencia).

Sin TASKS_QUEUE (modo local o pruebas) el aviso se procesa en línea.
"""
from __future__ import annotations

import json

from . import logs
from .config import get_config

_client = None


def _cliente():
    global _client
    if _client is None:
        from google.cloud import tasks_v2

        _client = tasks_v2.CloudTasksClient()
    return _client


def publicar_aviso(historial_id: int) -> None:
    c = get_config()
    try:
        if not c.tasks_queue:
            from .servicios import procesar_aviso

            procesar_aviso(historial_id)
            return

        from google.cloud import tasks_v2

        tarea = tasks_v2.Task(
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=f"{c.notif_url}/tareas/aviso",
                headers={"Content-Type": "application/json"},
                body=json.dumps({"historial_id": historial_id}).encode(),
                oidc_token=tasks_v2.OidcToken(service_account_email=c.tasks_sa, audience=c.notif_url),
            )
        )
        _cliente().create_task(parent=c.tasks_queue, task=tarea)
        logs.info("Aviso publicado en Cloud Tasks", historial_id=historial_id)
    except Exception as e:
        logs.error("No se pudo publicar el aviso; el trámite continúa", historial_id=historial_id, error=str(e)[:500])
