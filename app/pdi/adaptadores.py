"""Adaptadores SIMULADOS de GEPOL y B3000 (APP_MODE=adaptadores).

Devuelven datos sintéticos y deterministas a partir del RUT. En producción
este servicio sería el único punto que habla con los sistemas de la PDI a
través de la VPN (subred snet-hybrid). Solo lo invoca el gestor con IAM.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException

from .security import normalizar_rut

_PAISES = ["Argentina", "Perú", "Bolivia", "Brasil", "Colombia", "Estados Unidos", "España", "Uruguay"]
_PASOS = ["Aeropuerto AMB Santiago", "Paso Los Libertadores", "Chacalluta", "Aeropuerto Iquique", "Paso Cardenal Samoré"]


def _rng(rut: str, sistema: str) -> random.Random:
    semilla = int(hashlib.sha256(f"{sistema}:{rut}".encode()).hexdigest()[:12], 16)
    return random.Random(semilla)


def consultar_gepol(rut: str) -> dict:
    r = _rng(rut, "gepol")
    hoy = date(2026, 11, 1)
    movimientos = []
    for _ in range(r.randint(2, 6)):
        salida = hoy - timedelta(days=r.randint(30, 1500))
        pais = r.choice(_PAISES)
        paso = r.choice(_PASOS)
        movimientos.append({"fecha": salida.isoformat(), "tipo": "SALIDA", "paso": paso, "pais": pais})
        movimientos.append({"fecha": (salida + timedelta(days=r.randint(3, 25))).isoformat(), "tipo": "ENTRADA", "paso": paso, "pais": pais})
    movimientos.sort(key=lambda m: m["fecha"], reverse=True)
    return {
        "sistema": "GEPOL",
        "sintetico": True,
        "rut": rut,
        "movimientos_migratorios": movimientos,
        "alertas": [],
    }


def consultar_b3000(rut: str) -> dict:
    r = _rng(rut, "b3000")
    vigente = r.random() > 0.15
    return {
        "sistema": "B3000",
        "sintetico": True,
        "rut": rut,
        "permanencia_definitiva": {
            "vigente": vigente,
            "resolucion": f"RES-{r.randint(10000, 99999)}-{r.randint(2015, 2025)}",
            "fecha_otorgamiento": (date(2026, 1, 1) - timedelta(days=r.randint(200, 3000))).isoformat(),
        },
        "orden_de_detencion": False,
        "arraigo": False,
    }


def crear_app() -> FastAPI:
    app = FastAPI(title="PDI - Adaptadores simulados (GEPOL / B3000)", docs_url=None, redoc_url=None)

    def _rut(rut: str) -> str:
        n = normalizar_rut(rut)
        if not n:
            raise HTTPException(400, "RUT inválido")
        return n

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "servicio": "adaptadores"}

    @app.get("/gepol/{rut}")
    def gepol(rut: str):
        return consultar_gepol(_rut(rut))

    @app.get("/b3000/{rut}")
    def b3000(rut: str):
        return consultar_b3000(_rut(rut))

    return app
