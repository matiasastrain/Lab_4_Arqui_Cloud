"""Servicio de notificaciones. Lo invoca Cloud Tasks con un token OIDC (Cloud Run exige IAM)."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from .db import iniciar_bd, nueva_sesion
from .servicios import procesar_notificacion

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    iniciar_bd()
    yield


app = FastAPI(title="PDI PoC - Notificaciones", lifespan=lifespan)


class Tarea(BaseModel):
    historial_id: int
    folio: str = ""


@app.get("/healthz")
def healthz():
    return {"estado": "ok", "servicio": "notificaciones"}


@app.post("/tareas/notificar")
def notificar(t: Tarea):
    with nueva_sesion() as s:
        return procesar_notificacion(s, t.historial_id)
