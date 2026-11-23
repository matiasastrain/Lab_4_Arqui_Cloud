"""Cola de avisos. En GCP es Cloud Tasks; en modo local se procesa en línea."""
import json
import logging

from .config import settings

log = logging.getLogger("pdi.colas")


def encolar_notificacion(historial_id: int, folio: str) -> bool:
    """Publica el evento de cambio de estado. Un fallo aquí no debe romper el trámite."""
    try:
        if settings.local_mode and settings.notificaciones_url:
            # Docker Compose: se llama directo al servicio de notificaciones (sin Cloud Tasks).
            import requests

            r = requests.post(f"{settings.notificaciones_url}/tareas/notificar",
                              json={"historial_id": historial_id, "folio": folio}, timeout=10)
            r.raise_for_status()
            return True

        if settings.local_mode:
            from .db import nueva_sesion
            from .servicios import procesar_notificacion

            with nueva_sesion() as s:
                procesar_notificacion(s, historial_id)
            return True

        from google.cloud import tasks_v2

        cliente = tasks_v2.CloudTasksClient()
        cola = cliente.queue_path(settings.project_id, settings.region, settings.tasks_queue)
        destino = f"{settings.notificaciones_url}/tareas/notificar"
        tarea = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": destino,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"historial_id": historial_id, "folio": folio}).encode(),
                "oidc_token": {
                    "service_account_email": settings.tasks_sa_email,
                    "audience": settings.notificaciones_url,
                },
            }
        }
        cliente.create_task(request={"parent": cola, "task": tarea})
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("No se pudo encolar el aviso del folio %s: %s", folio, exc)
        return False
