"""Servicio de notificaciones (APP_MODE=notificaciones).

Recibe las tareas de Cloud Tasks. No es público: Cloud Run exige un token
OIDC de la cuenta sa-tareas, que es la única con roles/run.invoker.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import db, logs
from .servicios import procesar_aviso


class Tarea(BaseModel):
    historial_id: int


def crear_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app):
        db.configurar(crear_tablas=False)
        yield

    app = FastAPI(title="PDI - Notificaciones", docs_url=None, redoc_url=None, lifespan=lifespan)

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "servicio": "notificaciones"}

    @app.post("/tareas/aviso")
    def tarea_aviso(t: Tarea):
        try:
            return procesar_aviso(t.historial_id)
        except Exception as e:
            # 500 => Cloud Tasks reintenta con backoff
            logs.error("Error procesando aviso", historial_id=t.historial_id, error=str(e)[:500])
            raise HTTPException(500, "Error transitorio")

    return app
