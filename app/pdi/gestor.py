"""Gestor de trámites: API del ciudadano y del funcionario (Cloud Run)."""
import logging
import re
import uuid
from contextlib import asynccontextmanager
from typing import Literal

import requests
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from . import adaptadores
from .certificado import generar_certificado_pdf
from .colas import encolar_notificacion
from .config import ESTADOS, ESTADOS_ABIERTOS, TIPOS_TRAMITE, settings
from .db import Adjunto, Historial, Notificacion, Tramite, ahora, como_utc, iniciar_bd, nueva_sesion
from .security import (EMAIL_RE, Usuario, clave_funcionario_valida, crear_token, normalizar_rut,
                       solo_ciudadano, solo_funcionario, usuario_actual, validar_rut)
from .storage import get_almacen

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pdi.gestor")

MAX_ADJUNTO = 5 * 1024 * 1024
MAX_ADJUNTOS_POR_TRAMITE = 8
TIPOS_ARCHIVO = {"application/pdf", "image/png", "image/jpeg"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    iniciar_bd()
    yield


app = FastAPI(title="PDI PoC - Gestor de trámites", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_sesion():
    with nueva_sesion() as s:
        yield s


# ------------------------------------------------------------------ esquemas
class LoginCiudadano(BaseModel):
    rut: str


class LoginFuncionario(BaseModel):
    clave: str


class TramiteIn(BaseModel):
    tipo: str
    nombre: str = Field(min_length=3, max_length=120)
    email: str = Field(max_length=160)


class Subsanacion(BaseModel):
    comentario: str = Field(min_length=3, max_length=500)


class Decision(BaseModel):
    decision: Literal["aprobar", "observar", "rechazar"]
    comentario: str = Field(default="", max_length=500)


# ------------------------------------------------------------------ utilidades
def _cambiar_estado(s, t: Tramite, nuevo: str, detalle: str, actor: str) -> Historial:
    """Cambia el estado, deja el historial y publica el evento para el aviso.

    El evento se publica DESPUÉS de confirmar la transacción: así el aviso siempre
    parte de un estado que ya quedó guardado.
    """
    assert nuevo in ESTADOS
    t.estado = nuevo
    t.actualizado_en = ahora()
    ev = Historial(folio=t.folio, estado=nuevo, detalle=detalle, actor=actor)
    s.add(ev)
    s.flush()
    return ev


def _publicar(s, ev: Historial) -> None:
    s.commit()
    encolar_notificacion(ev.id, ev.folio)


def _tramite(s, folio: str) -> Tramite:
    t = s.execute(select(Tramite).where(Tramite.folio == folio)).scalar_one_or_none()
    if t is None:
        raise HTTPException(404, "Folio no encontrado")
    return t


def _puede_ver(u: Usuario, t: Tramite) -> None:
    if u.rol == "funcionario":
        return
    if t.rut != u.sub:
        # 404 y no 403: no revelamos si el folio existe para otra persona
        raise HTTPException(404, "Folio no encontrado")


def _resumen(t: Tramite) -> dict:
    return {
        "folio": t.folio,
        "tipo": t.tipo,
        "tipo_nombre": TIPOS_TRAMITE.get(t.tipo, t.tipo),
        "estado": t.estado,
        "nombre": t.nombre,
        "rut": t.rut,
        "creado_en": como_utc(t.creado_en).isoformat(),
        "actualizado_en": como_utc(t.actualizado_en).isoformat(),
    }


def _detalle(s, t: Tramite) -> dict:
    avisos = s.execute(select(Notificacion).where(Notificacion.folio == t.folio)
                       .order_by(Notificacion.id)).scalars().all()
    return {
        **_resumen(t),
        "email": t.email,
        "observacion": t.observacion,
        "historial": [
            {"estado": h.estado, "detalle": h.detalle, "actor": h.actor, "fecha": como_utc(h.fecha).isoformat()}
            for h in t.historial
        ],
        "adjuntos": [{"nombre": a.nombre, "tamano": a.tamano, "content_type": a.content_type} for a in t.adjuntos],
        "avisos": [
            {"estado": n.estado, "canal": n.canal, "mensaje": n.mensaje, "generado_por": n.generado_por,
             "fecha": como_utc(n.fecha).isoformat()}
            for n in avisos
        ],
    }


# ------------------------------------------------------------------ salud y acceso
@app.get("/healthz")
def healthz():
    return {"estado": "ok", "servicio": "gestor", "ambiente": settings.env_name}


@app.post("/auth/ciudadano")
def login_ciudadano(d: LoginCiudadano):
    """Simula ClaveÚnica: acepta cualquier RUT con dígito verificador correcto."""
    if not validar_rut(d.rut):
        raise HTTPException(422, "RUT inválido")
    rut = normalizar_rut(d.rut)
    return {"token": crear_token(rut, "ciudadano"), "rut": rut, "rol": "ciudadano"}


@app.post("/auth/funcionario")
def login_funcionario(d: LoginFuncionario):
    if not clave_funcionario_valida(d.clave):
        raise HTTPException(401, "Clave incorrecta")
    return {"token": crear_token("funcionario", "funcionario"), "rol": "funcionario"}


# ------------------------------------------------------------------ ciudadano
@app.post("/tramites", status_code=201)
def crear_tramite(d: TramiteIn, u: Usuario = Depends(solo_ciudadano), s=Depends(get_sesion)):
    # RF-05: validaciones preliminares
    if d.tipo not in TIPOS_TRAMITE:
        raise HTTPException(422, f"Tipo de trámite inválido. Opciones: {', '.join(TIPOS_TRAMITE)}")
    if not EMAIL_RE.match(d.email):
        raise HTTPException(422, "Correo electrónico inválido")
    # RF-06: control de solicitudes duplicadas antes de crear un folio nuevo
    abierto = s.execute(select(Tramite).where(Tramite.rut == u.sub, Tramite.tipo == d.tipo,
                                              Tramite.estado.in_(ESTADOS_ABIERTOS))).scalars().first()
    if abierto:
        raise HTTPException(409, f"Ya existe una solicitud abierta de este trámite: folio {abierto.folio}")

    # RF-07: folio único. Se asigna con el id de la fila dentro de la misma transacción.
    t = Tramite(folio=f"TMP-{uuid.uuid4().hex[:12]}", tipo=d.tipo, rut=u.sub, nombre=d.nombre.strip(),
                email=d.email.strip(), estado="RECIBIDO")
    s.add(t)
    s.flush()
    t.folio = f"PDI-{ahora().year}-{t.id:06d}"
    ev = _cambiar_estado(s, t, "RECIBIDO", "Solicitud recibida", "ciudadano")
    _publicar(s, ev)
    return _resumen(t)


@app.get("/mis-tramites")
def mis_tramites(u: Usuario = Depends(solo_ciudadano), s=Depends(get_sesion)):
    filas = s.execute(select(Tramite).where(Tramite.rut == u.sub).order_by(Tramite.id.desc())).scalars().all()
    return [_resumen(t) for t in filas]


@app.get("/tramites/{folio}")
def ver_tramite(folio: str, u: Usuario = Depends(usuario_actual), s=Depends(get_sesion)):
    t = _tramite(s, folio)
    _puede_ver(u, t)
    return _detalle(s, t)


@app.post("/tramites/{folio}/adjuntos", status_code=201)
async def subir_adjunto(folio: str, archivo: UploadFile = File(...), u: Usuario = Depends(solo_ciudadano),
                        s=Depends(get_sesion)):
    t = _tramite(s, folio)
    _puede_ver(u, t)
    if t.estado not in ("RECIBIDO", "OBSERVADO"):
        raise HTTPException(409, f"No se pueden agregar adjuntos en estado {t.estado}")
    if len(t.adjuntos) >= MAX_ADJUNTOS_POR_TRAMITE:
        raise HTTPException(422, f"Máximo {MAX_ADJUNTOS_POR_TRAMITE} adjuntos por trámite")
    if archivo.content_type not in TIPOS_ARCHIVO:
        raise HTTPException(422, "Solo se aceptan PDF, PNG o JPEG")
    datos = await archivo.read(MAX_ADJUNTO + 1)
    if not datos:
        raise HTTPException(422, "Archivo vacío")
    if len(datos) > MAX_ADJUNTO:
        raise HTTPException(413, "El archivo supera los 5 MB")

    nombre = re.sub(r"[^A-Za-z0-9._-]", "_", archivo.filename or "adjunto")[:80]
    objeto = f"adjuntos/{folio}/{uuid.uuid4().hex[:8]}-{nombre}"
    get_almacen().guardar(objeto, datos, archivo.content_type)
    s.add(Adjunto(folio=folio, nombre=nombre, content_type=archivo.content_type, tamano=len(datos), objeto=objeto))
    s.add(Historial(folio=folio, estado=t.estado, detalle=f"Adjunto recibido: {nombre}", actor="ciudadano"))
    s.commit()
    return {"folio": folio, "adjunto": nombre, "tamano": len(datos)}


@app.post("/tramites/{folio}/subsanar")
def subsanar(folio: str, d: Subsanacion, u: Usuario = Depends(solo_ciudadano), s=Depends(get_sesion)):
    t = _tramite(s, folio)
    _puede_ver(u, t)
    if t.estado != "OBSERVADO":
        raise HTTPException(409, "Solo se puede subsanar una solicitud observada")
    t.observacion = None
    ev = _cambiar_estado(s, t, "RECIBIDO", f"Subsanación del ciudadano: {d.comentario}", "ciudadano")
    _publicar(s, ev)
    return _resumen(t)


@app.get("/tramites/{folio}/certificado")
def descargar_certificado(folio: str, u: Usuario = Depends(usuario_actual), s=Depends(get_sesion)):
    t = _tramite(s, folio)
    _puede_ver(u, t)
    if t.estado != "APROBADO":
        raise HTTPException(409, "El certificado solo existe cuando el trámite está aprobado")
    pdf = get_almacen().leer(f"certificados/{folio}.pdf")
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{folio}.pdf"'})


# ------------------------------------------------------------------ funcionario
@app.get("/funcionario/tramites")
def listar(estado: str | None = None, _: Usuario = Depends(solo_funcionario), s=Depends(get_sesion)):
    consulta = select(Tramite).order_by(Tramite.id.desc()).limit(100)
    if estado:
        if estado not in ESTADOS:
            raise HTTPException(422, f"Estado inválido. Opciones: {', '.join(ESTADOS)}")
        consulta = consulta.where(Tramite.estado == estado)
    return [_resumen(t) for t in s.execute(consulta).scalars().all()]


@app.post("/funcionario/tramites/{folio}/tomar")
def tomar(folio: str, _: Usuario = Depends(solo_funcionario), s=Depends(get_sesion)):
    t = _tramite(s, folio)
    if t.estado != "RECIBIDO":
        raise HTTPException(409, f"Solo se puede tomar una solicitud en estado RECIBIDO (actual: {t.estado})")
    ev = _cambiar_estado(s, t, "EN_REVISION", "Solicitud tomada por un funcionario", "funcionario")
    _publicar(s, ev)
    return _resumen(t)


def _consultar_antecedentes(rut: str, tipo: str) -> dict:
    """Consulta a la red institucional (simulada). El gestor nunca accede a las bases por SQL."""
    url = settings.adaptadores_url
    if not url:
        if settings.local_mode:
            return adaptadores.consulta_sintetica(rut, tipo)
        raise HTTPException(503, "Adaptador institucional no configurado")
    try:
        cabeceras = {}
        if not settings.local_mode:  # en local (Docker Compose) no hay IAM de Cloud Run
            import google.auth.transport.requests as ga_requests
            from google.oauth2 import id_token

            cabeceras["Authorization"] = f"Bearer {id_token.fetch_id_token(ga_requests.Request(), url)}"
        r = requests.post(f"{url}/v1/consulta", json={"rut": rut, "tipo": tipo},
                          headers=cabeceras, timeout=10)
        r.raise_for_status()
        return r.json()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        log.error("Falla al consultar el adaptador institucional: %s", exc)
        raise HTTPException(502, "No se pudo consultar la red institucional") from None


@app.post("/funcionario/tramites/{folio}/antecedentes")
def antecedentes(folio: str, _: Usuario = Depends(solo_funcionario), s=Depends(get_sesion)):
    t = _tramite(s, folio)
    resultado = _consultar_antecedentes(t.rut, t.tipo)
    s.add(Historial(folio=folio, estado=t.estado, detalle="Consulta de antecedentes (GEPOL/B3000 simulados)",
                    actor="funcionario"))
    s.commit()
    return resultado


@app.post("/funcionario/tramites/{folio}/decision")
def decidir(folio: str, d: Decision, _: Usuario = Depends(solo_funcionario), s=Depends(get_sesion)):
    """Decide una persona: el sistema valida y ordena, pero aprobar, observar o rechazar es del funcionario."""
    t = _tramite(s, folio)
    if t.estado != "EN_REVISION":
        raise HTTPException(409, f"La solicitud debe estar EN_REVISION para decidir (actual: {t.estado})")

    if d.decision == "aprobar":
        if not t.adjuntos:
            raise HTTPException(422, "Solicitud incompleta: no tiene adjuntos")
        pdf = generar_certificado_pdf(t)
        get_almacen().guardar(f"certificados/{folio}.pdf", pdf, "application/pdf")
        t.resuelto_en = ahora()
        ev = _cambiar_estado(s, t, "APROBADO", d.comentario or "Solicitud aprobada, certificado emitido", "funcionario")
    else:
        if len(d.comentario.strip()) < 5:
            raise HTTPException(422, "Debes indicar el motivo (mínimo 5 caracteres)")
        if d.decision == "observar":
            t.observacion = d.comentario.strip()
            ev = _cambiar_estado(s, t, "OBSERVADO", d.comentario.strip(), "funcionario")
        else:
            t.resuelto_en = ahora()
            ev = _cambiar_estado(s, t, "RECHAZADO", d.comentario.strip(), "funcionario")
    _publicar(s, ev)
    return _resumen(t)


@app.get("/funcionario/reportes/resumen")
def reporte(_: Usuario = Depends(solo_funcionario), s=Depends(get_sesion)):
    """RF-14: volumen, tiempos y reprocesos, obtenidos con consultas SQL (sin data warehouse)."""
    por_estado = {e: 0 for e in ESTADOS}
    for estado, n in s.execute(select(Tramite.estado, func.count()).group_by(Tramite.estado)).all():
        por_estado[estado] = n
    total = sum(por_estado.values())

    horas = []
    for creado, resuelto in s.execute(select(Tramite.creado_en, Tramite.resuelto_en)
                                      .where(Tramite.resuelto_en.is_not(None))).all():
        horas.append((como_utc(resuelto) - como_utc(creado)).total_seconds() / 3600)

    con_observacion = s.execute(select(func.count(func.distinct(Historial.folio)))
                                .where(Historial.estado == "OBSERVADO")).scalar_one()
    return {
        "total_tramites": total,
        "por_estado": por_estado,
        "tiempo_promedio_resolucion_horas": round(sum(horas) / len(horas), 4) if horas else None,
        "tramites_con_reproceso": con_observacion,
        "tasa_reproceso_pct": round(100 * con_observacion / total, 1) if total else 0.0,
    }
