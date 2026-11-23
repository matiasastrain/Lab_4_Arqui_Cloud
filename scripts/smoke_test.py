#!/usr/bin/env python3
"""Prueba de punta a punta de la PoC contra lo desplegado (o contra el modo local).

Recorre el flujo completo: ingreso, solicitud, control de duplicados, solicitud incompleta,
adjunto, consulta de antecedentes, observación, subsanación, aprobación, certificado,
avisos redactados por IA y reporte de gestión.

Uso:
  python3 smoke_test.py --api https://pdi-gestor-dev-XXXX.southamerica-west1.run.app --clave "$(terraform output -raw funcionario_api_key)"

Si la organización bloquea el acceso público a Cloud Run, agrega:
  --id-token "$(gcloud auth print-identity-token)"
"""
import argparse
import random
import sys
import time

import requests

OK, FALLA = "OK   ", "FALLA"
resultados: list[tuple[str, bool, str]] = []


def digito_verificador(cuerpo: int) -> str:
    suma, factor = 0, 2
    for d in reversed(str(cuerpo)):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    return "0" if resto == 11 else "K" if resto == 10 else str(resto)


def paso(nombre: str, condicion: bool, detalle: str = "") -> None:
    resultados.append((nombre, condicion, detalle))
    print(f"[{OK if condicion else FALLA}] {nombre}" + (f"  ->  {detalle}" if detalle else ""))
    if not condicion:
        resumen()
        sys.exit(1)


def resumen() -> None:
    buenos = sum(1 for _, c, _ in resultados if c)
    print(f"\nResultado: {buenos}/{len(resultados)} pasos correctos")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True, help="URL base de la API del gestor")
    ap.add_argument("--clave", required=True, help="Clave del funcionario")
    ap.add_argument("--id-token", default="", help="Token de identidad de Google, si Cloud Run exige autenticación")
    ap.add_argument("--espera-avisos", type=int, default=90, help="Segundos máximos esperando los avisos")
    a = ap.parse_args()
    base = a.api.rstrip("/")

    s = requests.Session()
    if a.id_token:  # Cloud Run lee este encabezado y deja Authorization libre para la app
        s.headers["X-Serverless-Authorization"] = f"Bearer {a.id_token}"

    def llamar(metodo, ruta, token=None, **kw):
        h = {"Authorization": f"Bearer {token}"} if token else {}
        return s.request(metodo, base + ruta, headers=h, timeout=60, **kw)

    r = llamar("GET", "/docs")
    paso("Gestor responde /docs", r.status_code == 200, r.text.strip())

    cuerpo = random.randint(10_000_000, 25_000_000)
    rut = f"{cuerpo}-{digito_verificador(cuerpo)}"
    r = llamar("POST", "/auth/ciudadano", json={"rut": rut})
    paso("Ingreso del ciudadano (ClaveÚnica simulada)", r.status_code == 200, f"RUT {rut}")
    tc = r.json()["token"]
    r = llamar("POST", "/auth/ciudadano", json={"rut": f"{cuerpo}-{'0' if digito_verificador(cuerpo) != '0' else '1'}"})
    paso("RUT con dígito verificador incorrecto es rechazado", r.status_code == 422)

    r = llamar("POST", "/auth/funcionario", json={"clave": a.clave})
    paso("Ingreso del funcionario", r.status_code == 200, "clave correcta" if r.ok else r.text)
    tf = r.json()["token"]
    r = llamar("GET", "/funcionario/tramites", token=tc)
    paso("El ciudadano no accede al panel del funcionario (403)", r.status_code == 403)

    nuevo = {"tipo": "certificado_viajes", "nombre": "Ana Pérez Soto", "email": "ana@example.com"}
    r = llamar("POST", "/tramites", token=tc, json=nuevo)
    paso("Crear solicitud (RF-01/RF-07: folio único)", r.status_code == 201, r.json().get("folio", r.text))
    folio = r.json()["folio"]
    r = llamar("POST", "/tramites", token=tc, json=nuevo)
    paso("Solicitud duplicada es bloqueada (RF-06)", r.status_code == 409, r.json().get("detail", ""))

    r = llamar("POST", f"/funcionario/tramites/{folio}/tomar", token=tf)
    paso("El funcionario toma la solicitud", r.status_code == 200 and r.json()["estado"] == "EN_REVISION")
    r = llamar("POST", f"/funcionario/tramites/{folio}/decision", token=tf, json={"decision": "aprobar"})
    paso("No se aprueba una solicitud incompleta (sin adjuntos)", r.status_code == 422, r.json().get("detail", ""))

    r = llamar("POST", f"/funcionario/tramites/{folio}/decision", token=tf,
               json={"decision": "observar", "comentario": "Falta copia de la cédula de identidad"})
    paso("El funcionario observa la solicitud", r.status_code == 200 and r.json()["estado"] == "OBSERVADO")

    pdf = b"%PDF-1.4\n% adjunto de prueba (dato sintetico)\n"
    r = llamar("POST", f"/tramites/{folio}/adjuntos", token=tc, files={"archivo": ("cedula.pdf", pdf, "application/pdf")})
    paso("El ciudadano sube el adjunto a Cloud Storage", r.status_code == 201, f"{r.json().get('tamano', '?')} bytes")
    r = llamar("POST", f"/tramites/{folio}/subsanar", token=tc, json={"comentario": "Adjunté la cédula"})
    paso("El ciudadano subsana la observación", r.status_code == 200 and r.json()["estado"] == "RECIBIDO")

    r = llamar("POST", f"/funcionario/tramites/{folio}/tomar", token=tf)
    paso("El funcionario retoma la solicitud", r.status_code == 200)
    r = llamar("POST", f"/funcionario/tramites/{folio}/antecedentes", token=tf)
    paso("Consulta de antecedentes por el adaptador institucional (simulado)",
         r.status_code == 200 and r.json().get("sintetico") is True, r.json().get("fuente", r.text[:80]))
    r = llamar("POST", f"/funcionario/tramites/{folio}/decision", token=tf, json={"decision": "aprobar", "comentario": "Todo en orden"})
    paso("El funcionario aprueba", r.status_code == 200 and r.json()["estado"] == "APROBADO")

    r = llamar("GET", f"/tramites/{folio}/certificado", token=tc)
    paso("El ciudadano descarga el certificado PDF", r.status_code == 200 and r.content.startswith(b"%PDF"), f"{len(r.content)} bytes")

    # Los avisos llegan por Cloud Tasks: se espera a que estén los 6 cambios de estado.
    esperados, limite, detalle = 6, time.time() + a.espera_avisos, {}
    while time.time() < limite:
        detalle = llamar("GET", f"/tramites/{folio}", token=tc).json()
        if len(detalle["avisos"]) >= esperados:
            break
        time.sleep(3)
    avisos = detalle.get("avisos", [])
    paso("Cloud Tasks entregó un aviso por cada cambio de estado", len(avisos) == esperados, f"{len(avisos)} de {esperados}")
    origenes = sorted({x["generado_por"] for x in avisos})
    nota = "" if "ia" in origenes else "  (ATENCIÓN: Gemini no respondió; revisa los logs de pdi-notif y ejecuta probar_gemini.py)"
    paso("Avisos redactados (ia = Gemini, plantilla = respaldo)", True, ", ".join(origenes) + nota)
    print(f"        Ejemplo de aviso ({avisos[-1]['estado']}): {avisos[-1]['mensaje'].splitlines()[0]}")

    r = llamar("GET", "/funcionario/reportes/resumen", token=tf)
    rep = r.json()
    paso("Reporte de gestión (RF-14)", r.status_code == 200, f"total={rep['total_tramites']}, reprocesos={rep['tramites_con_reproceso']}")
    resumen()


if __name__ == "__main__":
    main()
