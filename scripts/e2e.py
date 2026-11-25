#!/usr/bin/env python3
"""Prueba de punta a punta de 19 pasos contra la API desplegada (o local).

Solo usa la biblioteca estándar, así corre en Cloud Shell sin instalar nada.

  python3 scripts/e2e.py --api URL --clave CLAVE_FUNCIONARIO [--id-token TOKEN]

--id-token se usa cuando el servicio no es público (acceso_publico = false):
se envía en X-Serverless-Authorization para que Cloud Run lo valide, y el
encabezado Authorization queda libre para el JWT de la aplicación.
"""
import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
import uuid

PDF = b"%PDF-1.4\n% PoC TICS400\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def rut_aleatorio() -> str:
    cuerpo = random.randint(10_000_000, 25_000_000)
    suma, factor = 0, 2
    for d in reversed(str(cuerpo)):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    dv = {11: "0", 10: "K"}.get(11 - suma % 11, str(11 - suma % 11))
    return f"{cuerpo}-{dv}"


class Cliente:
    def __init__(self, base, id_token=None):
        self.base = base.rstrip("/")
        self.id_token = id_token

    def pedir(self, metodo, ruta, token=None, json_body=None, archivo=None):
        cab = {}
        if self.id_token:
            cab["X-Serverless-Authorization"] = f"Bearer {self.id_token}"
        if token:
            cab["Authorization"] = f"Bearer {token}"
        datos = None
        if json_body is not None:
            datos = json.dumps(json_body).encode()
            cab["Content-Type"] = "application/json"
        elif archivo is not None:
            nombre, contenido, ct = archivo
            limite = uuid.uuid4().hex
            datos = (
                f"--{limite}\r\nContent-Disposition: form-data; name=\"archivo\"; filename=\"{nombre}\"\r\n"
                f"Content-Type: {ct}\r\n\r\n"
            ).encode() + contenido + f"\r\n--{limite}--\r\n".encode()
            cab["Content-Type"] = f"multipart/form-data; boundary={limite}"
        req = urllib.request.Request(self.base + ruta, data=datos, headers=cab, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                cuerpo = r.read()
                return r.status, cuerpo
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def json(self, *a, **k):
        st, cuerpo = self.pedir(*a, **k)
        try:
            return st, json.loads(cuerpo or b"null")
        except ValueError:
            return st, cuerpo


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api", required=True)
    p.add_argument("--clave", required=True)
    p.add_argument("--id-token", default=None)
    p.add_argument("--espera", type=int, default=180, help="segundos máximos esperando los avisos")
    a = p.parse_args()
    c = Cliente(a.api, a.id_token)

    pasos = []
    ctx = {}

    def paso(nombre):
        def deco(fn):
            pasos.append((nombre, fn))
            return fn
        return deco

    def esperar(cond, msg):
        if not cond:
            raise AssertionError(msg)

    @paso("API disponible (/api/tipos)")
    def _():
        # /healthz no sirve en *.run.app: Google reserva las rutas terminadas en "z"
        st, r = c.json("GET", "/api/tipos")
        esperar(st == 200 and len(r) == 2, f"la API respondió {st} {str(r)[:200]}")

    @paso("RUT con dígito verificador incorrecto es rechazado")
    def _():
        st, _r = c.json("POST", "/api/auth/ciudadano", json_body={"rut": "12345678-9", "nombre": "Prueba"})
        esperar(st == 400, f"se esperaba 400 y llegó {st}")

    @paso("Ingreso de dos ciudadanos (ClaveÚnica simulada)")
    def _():
        for k in ("c1", "c2"):
            st, r = c.json("POST", "/api/auth/ciudadano", json_body={
                "rut": rut_aleatorio(), "nombre": f"Ciudadano E2E {k.upper()}", "email": f"{k}@example.com"})
            esperar(st == 200, f"login {k}: {st} {r}")
            ctx[k] = r["token"]

    @paso("Crear trámite A (Certificado de Viajes) y recibir folio")
    def _():
        st, r = c.json("POST", "/api/tramites", ctx["c1"], {"tipo": "CERT_VIAJES", "detalle": "Viaje E2E"})
        esperar(st == 201 and r["folio"], f"{st} {r}")
        ctx["A"] = r["folio"]

    @paso("Trámite duplicado es rechazado (409)")
    def _():
        st, _r = c.json("POST", "/api/tramites", ctx["c1"], {"tipo": "CERT_VIAJES"})
        esperar(st == 409, f"se esperaba 409 y llegó {st}")

    @paso("Adjunto con formato no permitido es rechazado (415)")
    def _():
        st, _r = c.json("POST", f"/api/tramites/{ctx['A']}/adjuntos", ctx["c1"], archivo=("nota.pdf", b"texto plano", "application/pdf"))
        esperar(st == 415, f"se esperaba 415 y llegó {st}")

    @paso("Subir adjunto PDF al trámite A")
    def _():
        st, r = c.json("POST", f"/api/tramites/{ctx['A']}/adjuntos", ctx["c1"], archivo=("pasaporte.pdf", PDF, "application/pdf"))
        esperar(st == 201, f"{st} {r}")

    @paso("Crear trámite B (Vigencia PD) y trámite C (otro ciudadano)")
    def _():
        st, r = c.json("POST", "/api/tramites", ctx["c1"], {"tipo": "VIGENCIA_PD"})
        esperar(st == 201, f"B: {st} {r}")
        ctx["B"] = r["folio"]
        st, r = c.json("POST", "/api/tramites", ctx["c2"], {"tipo": "CERT_VIAJES"})
        esperar(st == 201, f"C: {st} {r}")
        ctx["C"] = r["folio"]

    @paso("Clave de funcionario incorrecta es rechazada (401)")
    def _():
        st, _r = c.json("POST", "/api/auth/funcionario", json_body={"clave": "incorrecta"})
        esperar(st == 401, f"se esperaba 401 y llegó {st}")

    @paso("Ingreso del funcionario")
    def _():
        st, r = c.json("POST", "/api/auth/funcionario", json_body={"clave": a.clave, "usuario": "funcionario-e2e"})
        esperar(st == 200, f"{st} {r}")
        ctx["f"] = r["token"]

    @paso("Funcionario toma los tres trámites (EN_REVISION)")
    def _():
        for k in ("A", "B", "C"):
            st, r = c.json("POST", f"/api/tramites/{ctx[k]}/tomar", ctx["f"])
            esperar(st == 200 and r["estado"] == "EN_REVISION", f"{k}: {st} {r}")

    @paso("Consultar antecedentes GEPOL y B3000 (servicio de adaptadores)")
    def _():
        st, r = c.json("GET", f"/api/tramites/{ctx['A']}/antecedentes", ctx["f"])
        esperar(st == 200 and r["gepol"]["sistema"] == "GEPOL" and r["b3000"]["sistema"] == "B3000", f"{st} {r}")

    @paso("Aprobar sin adjunto es rechazado (422)")
    def _():
        st, _r = c.json("POST", f"/api/tramites/{ctx['B']}/decision", ctx["f"], {"resultado": "APROBADO"})
        esperar(st == 422, f"se esperaba 422 y llegó {st}")

    @paso("Aprobar trámite A")
    def _():
        st, r = c.json("POST", f"/api/tramites/{ctx['A']}/decision", ctx["f"], {"resultado": "APROBADO"})
        esperar(st == 200 and r["estado"] == "APROBADO", f"{st} {r}")

    @paso("Observar trámite B")
    def _():
        st, r = c.json("POST", f"/api/tramites/{ctx['B']}/decision", ctx["f"],
                       {"resultado": "OBSERVADO", "observacion": "Falta copia del documento de identidad"})
        esperar(st == 200 and r["estado"] == "OBSERVADO", f"{st} {r}")

    @paso("Ciudadano subsana el trámite B")
    def _():
        st, _r = c.json("POST", f"/api/tramites/{ctx['B']}/adjuntos", ctx["c1"], archivo=("cedula.pdf", PDF, "application/pdf"))
        esperar(st == 201, f"adjunto: {st}")
        st, r = c.json("POST", f"/api/tramites/{ctx['B']}/subsanar", ctx["c1"], {"comentario": "Se adjunta la copia solicitada"})
        esperar(st == 200 and r["estado"] == "EN_REVISION", f"{st} {r}")

    @paso("Rechazar trámite C con motivo")
    def _():
        st, r = c.json("POST", f"/api/tramites/{ctx['C']}/decision", ctx["f"],
                       {"resultado": "RECHAZADO", "observacion": "Antecedentes no corresponden al solicitante"})
        esperar(st == 200 and r["estado"] == "RECHAZADO", f"{st} {r}")

    @paso("Descargar certificado PDF de A (y otro ciudadano no puede verlo)")
    def _():
        st, cuerpo = c.pedir("GET", f"/api/tramites/{ctx['A']}/certificado", ctx["c1"])
        esperar(st == 200 and cuerpo.startswith(b"%PDF"), f"certificado: {st}")
        st, _ = c.pedir("GET", f"/api/tramites/{ctx['A']}", ctx["c2"])
        esperar(st == 404, f"acceso ajeno: se esperaba 404 y llegó {st}")

    @paso("Reporte resumen y avisos generados para todos los eventos")
    def _():
        st, rep = c.json("GET", "/api/reportes/resumen", ctx["f"])
        esperar(st == 200 and rep["total_tramites"] >= 3, f"reporte: {st} {rep}")
        limite = time.time() + a.espera
        pendientes = {}
        while True:
            pendientes = {}
            origenes = []
            for k in ("A", "B", "C"):
                _st, r = c.json("GET", f"/api/tramites/{ctx[k]}", ctx["f"])
                if r["avisos_generados"] < r["eventos"]:
                    pendientes[k] = f"{r['avisos_generados']}/{r['eventos']}"
                origenes += [h["aviso"]["origen"] for h in r["historial"] if h["aviso"]]
            if not pendientes or time.time() > limite:
                break
            time.sleep(5)
        esperar(not pendientes, f"avisos pendientes tras {a.espera}s: {pendientes}")
        ctx["origenes"] = origenes

    print(f"Prueba de punta a punta contra {a.api}\n")
    ok = 0
    for i, (nombre, fn) in enumerate(pasos, 1):
        try:
            fn()
            ok += 1
            print(f"  [{i:2d}/{len(pasos)}] OK    {nombre}")
        except Exception as e:
            print(f"  [{i:2d}/{len(pasos)}] FALLA {nombre}\n           -> {e}")
            if i <= 10:  # sin login no tiene sentido seguir
                break

    print()
    if "A" in ctx:
        print(f"Folios creados: A={ctx.get('A')}  B={ctx.get('B')}  C={ctx.get('C')}")
    if ctx.get("origenes"):
        g = ctx["origenes"].count("gemini")
        t = ctx["origenes"].count("plantilla")
        print(f"Origen de los avisos: gemini={g}  plantilla={t}")
        if g == 0:
            print("  Todos los avisos salieron con plantilla: Gemini no respondió o la IA está desactivada.")
            print("  Revise los logs del servicio pdi-notificaciones-<ambiente>.")
    print(f"\nResultado: {ok}/{len(pasos)} pasos correctos")
    sys.exit(0 if ok == len(pasos) else 1)


if __name__ == "__main__":
    main()
