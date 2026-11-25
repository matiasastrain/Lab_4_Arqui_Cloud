"""API del gestor de trámites (APP_MODE=gestor).

Es el ÚNICO componente que escribe el estado del trámite en Cloud SQL y los
adjuntos en Cloud Storage. Publica los avisos en Cloud Tasks después de
confirmar cada transacción.
"""
from __future__ import annotations

import re
import uuid
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import adaptadores, almacenamiento, certificado, db, logs
from .colas import publicar_aviso
from .config import get_config
from .db import (
    APROBADO, EN_REVISION, ESTADOS_ACTIVOS, ESTADOS_FINALES, OBSERVADO, RECHAZADO, RECIBIDO, TIPOS,
    Adjunto, Historial, Notificacion, Tramite,
)
from .security import (
    CIUDADANO, FUNCIONARIO, Usuario, clave_funcionario_correcta, emitir_token, normalizar_rut,
    requiere_ciudadano, requiere_funcionario, usuario_actual,
)
from .servicios import registrar_cambio

MAX_ADJUNTO = 5 * 1024 * 1024
MAX_ADJUNTOS_POR_TRAMITE = 10
_FIRMAS = {
    b"%PDF-": "application/pdf",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


# --------------------------------------------------------------------------
# Esquemas
# --------------------------------------------------------------------------
class LoginCiudadano(BaseModel):
    rut: str
    nombre: str = Field(min_length=2, max_length=120)
    email: Optional[str] = Field(default=None, max_length=160)
    telefono: Optional[str] = Field(default=None, max_length=20)


class LoginFuncionario(BaseModel):
    clave: str
    usuario: str = Field(default="funcionario", max_length=60)


class NuevoTramite(BaseModel):
    tipo: Literal["CERT_VIAJES", "VIGENCIA_PD"]
    detalle: Optional[str] = Field(default=None, max_length=1000)


class Subsanacion(BaseModel):
    comentario: str = Field(min_length=3, max_length=1000)


class Decision(BaseModel):
    resultado: Literal["APROBADO", "OBSERVADO", "RECHAZADO"]
    observacion: Optional[str] = Field(default=None, max_length=1000)


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def _detectar_tipo(datos: bytes) -> Optional[str]:
    for firma, ct in _FIRMAS.items():
        if datos.startswith(firma):
            return ct
    return None


def _nombre_seguro(nombre: str) -> str:
    base = re.sub(r"[^\w.\-]", "_", nombre or "archivo")[:120]
    return base or "archivo"


def _obtener(s: Session, folio: str, u: Usuario) -> Tramite:
    t = s.scalar(select(Tramite).where(Tramite.folio == folio))
    if t is None:
        raise HTTPException(404, "Trámite no encontrado")
    if u.rol == CIUDADANO and t.rut != u.sub:
        # 404 y no 403 para no revelar la existencia de trámites ajenos
        raise HTTPException(404, "Trámite no encontrado")
    return t


def _resumen(t: Tramite) -> dict:
    return {
        "folio": t.folio,
        "tipo": t.tipo,
        "tipo_nombre": TIPOS[t.tipo]["nombre"],
        "rut": t.rut,
        "nombre": t.nombre,
        "estado": t.estado,
        "funcionario": t.funcionario,
        "creado": t.creado.isoformat(),
        "actualizado": t.actualizado.isoformat(),
    }


def _detalle(s: Session, t: Tramite) -> dict:
    avisos = s.scalars(
        select(Notificacion).where(Notificacion.tramite_id == t.id).order_by(Notificacion.id)
    ).all()
    avisos_por_hist = {n.historial_id: n for n in avisos}
    return {
        **_resumen(t),
        "email": t.email,
        "telefono": t.telefono,
        "detalle": t.detalle,
        "adjuntos": [
            {"id": a.id, "nombre": a.nombre, "content_type": a.content_type, "tamano": a.tamano,
             "creado": a.creado.isoformat()}
            for a in t.adjuntos
        ],
        "historial": [
            {
                "id": h.id,
                "estado_anterior": h.estado_anterior,
                "estado_nuevo": h.estado_nuevo,
                "actor": h.actor,
                "comentario": h.comentario,
                "fecha": h.fecha.isoformat(),
                "aviso": (
                    {"texto": avisos_por_hist[h.id].texto, "origen": avisos_por_hist[h.id].origen,
                     "canal": avisos_por_hist[h.id].canal}
                    if h.id in avisos_por_hist else None
                ),
            }
            for h in t.historial
        ],
        "avisos_generados": len(avisos),
        "eventos": len(t.historial),
    }


def _confirmar_y_avisar(s: Session, *historiales: Historial) -> None:
    ids = [h.id for h in historiales]
    s.commit()
    for hid in ids:  # después del commit, nunca antes
        publicar_aviso(hid)


# --------------------------------------------------------------------------
# Aplicación
# --------------------------------------------------------------------------
def crear_app() -> FastAPI:
    c = get_config()

    @asynccontextmanager
    async def lifespan(_app):
        db.configurar()
        logs.info("Gestor iniciado", ambiente=c.ambiente)
        yield

    app = FastAPI(
        title="PDI - API de trámites migratorios (PoC)",
        version="1.0.0",
        description="Prueba de concepto TICS400. ClaveÚnica, GEPOL, B3000 y la mensajería están simulados.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=c.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz", tags=["sistema"])
    def healthz():
        return {"ok": True, "servicio": "gestor", "ambiente": c.ambiente}

    @app.get("/api/tipos", tags=["sistema"])
    def tipos():
        return [{"codigo": k, "nombre": v["nombre"]} for k, v in TIPOS.items()]

    # ---------------- Autenticación ----------------
    @app.post("/api/auth/ciudadano", tags=["autenticación"])
    def login_ciudadano(d: LoginCiudadano):
        rut = normalizar_rut(d.rut)
        if not rut:
            raise HTTPException(400, "RUT inválido (dígito verificador incorrecto)")
        u = Usuario(rut, CIUDADANO, d.nombre.strip(), d.email, d.telefono)
        return {"token": emitir_token(u), "rol": CIUDADANO, "rut": rut, "nombre": u.nombre}

    @app.post("/api/auth/funcionario", tags=["autenticación"])
    def login_funcionario(d: LoginFuncionario):
        if not clave_funcionario_correcta(d.clave):
            logs.warning("Intento de ingreso de funcionario rechazado")
            raise HTTPException(401, "Clave incorrecta")
        u = Usuario(d.usuario, FUNCIONARIO, d.usuario)
        return {"token": emitir_token(u), "rol": FUNCIONARIO}

    # ---------------- Ciudadano ----------------
    @app.post("/api/tramites", status_code=201, tags=["ciudadano"])
    def crear_tramite(d: NuevoTramite, u: Usuario = Depends(requiere_ciudadano), s: Session = Depends(db.get_session)):
        existente = s.scalar(
            select(Tramite).where(Tramite.rut == u.sub, Tramite.tipo == d.tipo, Tramite.estado.in_(ESTADOS_ACTIVOS))
        )
        if existente:
            raise HTTPException(409, f"Ya existe un trámite en curso de este tipo (folio {existente.folio})")
        t = Tramite(
            tipo=d.tipo, rut=u.sub, nombre=u.nombre, email=u.email, telefono=u.telefono,
            detalle=d.detalle, estado=RECIBIDO,
        )
        s.add(t)
        s.flush()
        t.folio = f"{TIPOS[d.tipo]['prefijo']}-{t.creado.year if t.creado else 2026}-{t.id:06d}"
        h = registrar_cambio(s, t, RECIBIDO, f"ciudadano:{u.sub}", "Trámite ingresado")
        folio = t.folio
        _confirmar_y_avisar(s, h)
        logs.info("Trámite creado", folio=folio, tipo=d.tipo)
        return _detalle(s, t)

    @app.get("/api/tramites", tags=["ciudadano", "funcionario"])
    def listar(
        estado: Optional[str] = Query(default=None),
        u: Usuario = Depends(usuario_actual),
        s: Session = Depends(db.get_session),
    ):
        q = select(Tramite).order_by(Tramite.id.desc()).limit(200)
        if u.rol == CIUDADANO:
            q = q.where(Tramite.rut == u.sub)
        if estado:
            q = q.where(Tramite.estado == estado)
        return [_resumen(t) for t in s.scalars(q).all()]

    @app.get("/api/tramites/{folio}", tags=["ciudadano", "funcionario"])
    def ver(folio: str, u: Usuario = Depends(usuario_actual), s: Session = Depends(db.get_session)):
        return _detalle(s, _obtener(s, folio, u))

    @app.post("/api/tramites/{folio}/adjuntos", status_code=201, tags=["ciudadano"])
    async def subir_adjunto(
        folio: str,
        archivo: UploadFile = File(...),
        u: Usuario = Depends(requiere_ciudadano),
        s: Session = Depends(db.get_session),
    ):
        t = _obtener(s, folio, u)
        if t.estado in ESTADOS_FINALES:
            raise HTTPException(409, "El trámite ya está cerrado")
        if len(t.adjuntos) >= MAX_ADJUNTOS_POR_TRAMITE:
            raise HTTPException(409, "Se alcanzó el máximo de adjuntos")
        datos = await archivo.read(MAX_ADJUNTO + 1)
        if len(datos) > MAX_ADJUNTO:
            raise HTTPException(413, "El archivo supera los 5 MB")
        if not datos:
            raise HTTPException(400, "Archivo vacío")
        ct = _detectar_tipo(datos)  # por contenido, no por la extensión declarada
        if ct is None:
            raise HTTPException(415, "Solo se aceptan archivos PDF, PNG o JPEG")
        nombre = _nombre_seguro(archivo.filename or "archivo")
        ruta = f"tramites/{t.folio}/{uuid.uuid4().hex}-{nombre}"
        almacenamiento.guardar(ruta, datos, ct)
        a = Adjunto(tramite_id=t.id, nombre=nombre, content_type=ct, tamano=len(datos), ruta=ruta)
        s.add(a)
        s.commit()
        logs.info("Adjunto recibido", folio=t.folio, tamano=len(datos), content_type=ct)
        return {"id": a.id, "nombre": nombre, "content_type": ct, "tamano": len(datos)}

    @app.get("/api/tramites/{folio}/adjuntos/{adjunto_id}", tags=["ciudadano", "funcionario"])
    def descargar_adjunto(folio: str, adjunto_id: int, u: Usuario = Depends(usuario_actual), s: Session = Depends(db.get_session)):
        t = _obtener(s, folio, u)
        a = next((x for x in t.adjuntos if x.id == adjunto_id), None)
        if a is None:
            raise HTTPException(404, "Adjunto no encontrado")
        return Response(
            almacenamiento.leer(a.ruta), media_type=a.content_type,
            headers={"Content-Disposition": f'inline; filename="{a.nombre}"'},
        )

    @app.post("/api/tramites/{folio}/subsanar", tags=["ciudadano"])
    def subsanar(folio: str, d: Subsanacion, u: Usuario = Depends(requiere_ciudadano), s: Session = Depends(db.get_session)):
        t = _obtener(s, folio, u)
        if t.estado != OBSERVADO:
            raise HTTPException(409, "Solo se puede subsanar un trámite observado")
        h = registrar_cambio(s, t, EN_REVISION, f"ciudadano:{u.sub}", f"Subsanación: {d.comentario}")
        _confirmar_y_avisar(s, h)
        return _detalle(s, t)

    @app.get("/api/tramites/{folio}/certificado", tags=["ciudadano", "funcionario"])
    def descargar_certificado(folio: str, u: Usuario = Depends(usuario_actual), s: Session = Depends(db.get_session)):
        t = _obtener(s, folio, u)
        if t.estado != APROBADO:
            raise HTTPException(409, "El certificado solo está disponible para trámites aprobados")
        aprobacion = next((h.fecha for h in reversed(t.historial) if h.estado_nuevo == APROBADO), t.actualizado)
        pdf = certificado.generar_pdf(t, aprobacion)
        return Response(
            pdf, media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="certificado-{t.folio}.pdf"'},
        )

    # ---------------- Funcionario ----------------
    @app.post("/api/tramites/{folio}/tomar", tags=["funcionario"])
    def tomar(folio: str, u: Usuario = Depends(requiere_funcionario), s: Session = Depends(db.get_session)):
        t = _obtener(s, folio, u)
        if t.estado != RECIBIDO:
            raise HTTPException(409, f"No se puede tomar un trámite en estado {t.estado}")
        t.funcionario = u.sub
        h = registrar_cambio(s, t, EN_REVISION, f"funcionario:{u.sub}", "Trámite tomado para revisión")
        _confirmar_y_avisar(s, h)
        return _detalle(s, t)

    @app.get("/api/tramites/{folio}/antecedentes", tags=["funcionario"])
    def antecedentes(folio: str, u: Usuario = Depends(requiere_funcionario), s: Session = Depends(db.get_session)):
        t = _obtener(s, folio, u)
        if c.adaptadores_url:
            import requests
            import google.auth.transport.requests
            import google.oauth2.id_token

            # Token de identidad de la cuenta del gestor (autenticación IAM)
            tok = google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), c.adaptadores_url)
            cab = {"Authorization": f"Bearer {tok}"}
            try:
                gepol = requests.get(f"{c.adaptadores_url}/gepol/{t.rut}", headers=cab, timeout=10)
                b3000 = requests.get(f"{c.adaptadores_url}/b3000/{t.rut}", headers=cab, timeout=10)
                gepol.raise_for_status()
                b3000.raise_for_status()
            except requests.RequestException as e:
                logs.error("Fallo en adaptadores", folio=folio, error=str(e)[:300])
                raise HTTPException(502, "Los sistemas de antecedentes no respondieron")
            return {"folio": folio, "gepol": gepol.json(), "b3000": b3000.json()}
        return {"folio": folio, "gepol": adaptadores.consultar_gepol(t.rut), "b3000": adaptadores.consultar_b3000(t.rut)}

    @app.post("/api/tramites/{folio}/decision", tags=["funcionario"])
    def decidir(folio: str, d: Decision, u: Usuario = Depends(requiere_funcionario), s: Session = Depends(db.get_session)):
        t = _obtener(s, folio, u)
        if t.estado != EN_REVISION:
            raise HTTPException(409, f"Solo se decide un trámite en revisión (estado actual {t.estado})")
        if d.resultado == APROBADO and not t.adjuntos:
            raise HTTPException(422, "Para aprobar se requiere al menos un adjunto")
        if d.resultado in (OBSERVADO, RECHAZADO) and not (d.observacion and d.observacion.strip()):
            raise HTTPException(422, "Observar o rechazar requiere indicar el motivo")
        h = registrar_cambio(s, t, d.resultado, f"funcionario:{u.sub}", (d.observacion or "").strip() or None)
        _confirmar_y_avisar(s, h)
        logs.info("Decisión registrada", folio=folio, resultado=d.resultado)
        return _detalle(s, t)

    @app.get("/api/reportes/resumen", tags=["funcionario"])
    def reporte(u: Usuario = Depends(requiere_funcionario), s: Session = Depends(db.get_session)):
        por_estado = dict(s.execute(select(Tramite.estado, func.count()).group_by(Tramite.estado)).all())
        por_tipo = dict(s.execute(select(Tramite.tipo, func.count()).group_by(Tramite.tipo)).all())
        por_origen = dict(s.execute(select(Notificacion.origen, func.count()).group_by(Notificacion.origen)).all())
        total = sum(por_estado.values())
        resueltos = por_estado.get(APROBADO, 0) + por_estado.get(RECHAZADO, 0)
        return {
            "total_tramites": total,
            "por_estado": por_estado,
            "por_tipo": {TIPOS[k]["nombre"]: v for k, v in por_tipo.items()},
            "tasa_aprobacion": round(por_estado.get(APROBADO, 0) / resueltos, 3) if resueltos else None,
            "avisos_por_origen": por_origen,
            "total_avisos": sum(por_origen.values()),
        }

    return app
