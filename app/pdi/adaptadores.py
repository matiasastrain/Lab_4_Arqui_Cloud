"""Adaptador simulado de la red institucional de la PDI (GEPOL y B3000).

En el diseño real, el gestor llega a estas bases por una VPN, el firewall perimetral,
la DMZ y el firewall interno, y nunca por SQL directo. En la prueba de concepto esa
red se simula con este servicio: expone una API autenticada (Cloud Run con IAM) y
responde datos sintéticos y deterministas calculados a partir del RUT.
"""
import hashlib
from datetime import date, timedelta

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="PDI PoC - Adaptadores simulados (GEPOL / B3000)")

PASOS = ["Paso Los Libertadores", "Aeropuerto AMB", "Paso Chacalluta", "Paso Cardenal Samoré", "Aeropuerto Cerro Moreno"]


class Consulta(BaseModel):
    rut: str
    tipo: str


def consulta_sintetica(rut: str, tipo: str) -> dict:
    semilla = int(hashlib.sha256(rut.encode()).hexdigest(), 16)
    resultado: dict = {"fuente": "GEPOL/B3000 (simulado)", "sintetico": True, "rut": rut, "tipo": tipo}
    if tipo == "certificado_viajes":
        base = date(2024, 1, 10)
        movimientos = []
        for i in range(semilla % 5 + 2):
            fecha = base + timedelta(days=(semilla >> (i * 3)) % 60 + i * 75)
            movimientos.append(
                {
                    "fecha": fecha.isoformat(),
                    "movimiento": "salida" if i % 2 == 0 else "ingreso",
                    "paso": PASOS[(semilla >> i) % len(PASOS)],
                }
            )
        resultado["movimientos"] = movimientos
    else:
        vigente = semilla % 5 != 0
        resultado["permanencia_definitiva"] = {
            "vigente": vigente,
            "resolucion": f"RES-{semilla % 90000 + 10000}",
            "observacion": "" if vigente else "Sin registro vigente (dato sintético)",
        }
    return resultado


@app.get("/healthz")
def healthz():
    return {"estado": "ok", "servicio": "adaptadores"}


@app.post("/v1/consulta")
def consulta(c: Consulta):
    return consulta_sintetica(c.rut, c.tipo)
