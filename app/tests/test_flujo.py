"""Pruebas del flujo completo de la PoC en modo local (sin GCP)."""
import pytest

from pdi import ai
from pdi.security import digito_verificador, normalizar_rut, validar_rut

PDF = b"%PDF-1.4 prueba"
NUEVO = {"tipo": "certificado_viajes", "nombre": "Ana Pérez Soto", "email": "ana@example.com"}


def _crear(cliente, h, **extra):
    r = cliente.post("/tramites", json={**NUEVO, **extra}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["folio"]


def _adjuntar(cliente, h, folio):
    return cliente.post(f"/tramites/{folio}/adjuntos", headers=h,
                        files={"archivo": ("cedula.pdf", PDF, "application/pdf")})


# ------------------------------------------------------------------ RUT
def test_rut_modulo_11():
    assert digito_verificador(12345678) == "5"
    assert validar_rut("12.345.678-5")
    assert not validar_rut("12.345.678-9")
    assert normalizar_rut("12.345.678-5") == "12345678-5"
    assert not validar_rut("abc")


# ------------------------------------------------------------------ acceso
def test_login_rechaza_rut_invalido(cliente):
    assert cliente.post("/auth/ciudadano", json={"rut": "11111111-9"}).status_code == 422


def test_login_funcionario_clave_incorrecta(cliente):
    assert cliente.post("/auth/funcionario", json={"clave": "mala"}).status_code == 401


def test_endpoints_exigen_token_y_rol(cliente, ciudadano):
    assert cliente.get("/mis-tramites").status_code == 401
    assert cliente.get("/funcionario/tramites", headers=ciudadano()).status_code == 403


# ------------------------------------------------------------------ flujo feliz + observación
def test_flujo_completo_con_observacion(cliente, ciudadano, funcionario):
    h = ciudadano()
    folio = _crear(cliente, h)
    assert folio.startswith("PDI-")

    # solicitud incompleta: sin adjuntos no se puede aprobar
    assert cliente.post(f"/funcionario/tramites/{folio}/tomar", headers=funcionario).status_code == 200
    r = cliente.post(f"/funcionario/tramites/{folio}/decision", headers=funcionario,
                     json={"decision": "aprobar"})
    assert r.status_code == 422

    # el funcionario observa, el ciudadano subsana y adjunta
    r = cliente.post(f"/funcionario/tramites/{folio}/decision", headers=funcionario,
                     json={"decision": "observar", "comentario": "Falta copia de la cédula"})
    assert r.json()["estado"] == "OBSERVADO"
    assert _adjuntar(cliente, h, folio).status_code == 201
    r = cliente.post(f"/tramites/{folio}/subsanar", headers=h, json={"comentario": "Adjunté la cédula"})
    assert r.json()["estado"] == "RECIBIDO"

    # antecedentes simulados y aprobación
    cliente.post(f"/funcionario/tramites/{folio}/tomar", headers=funcionario)
    ant = cliente.post(f"/funcionario/tramites/{folio}/antecedentes", headers=funcionario).json()
    assert ant["sintetico"] is True and ant["movimientos"]
    r = cliente.post(f"/funcionario/tramites/{folio}/decision", headers=funcionario,
                     json={"decision": "aprobar", "comentario": "Todo en orden"})
    assert r.json()["estado"] == "APROBADO"

    # certificado descargable y aviso por cada cambio de estado
    pdf = cliente.get(f"/tramites/{folio}/certificado", headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    detalle = cliente.get(f"/tramites/{folio}", headers=h).json()
    estados_avisados = [a["estado"] for a in detalle["avisos"]]
    assert estados_avisados == ["RECIBIDO", "EN_REVISION", "OBSERVADO", "RECIBIDO", "EN_REVISION", "APROBADO"]
    assert all(a["generado_por"] == "plantilla" for a in detalle["avisos"])  # IA apagada en modo local
    assert all(folio in a["mensaje"] and "portal.test" in a["mensaje"] for a in detalle["avisos"])

    rep = cliente.get("/funcionario/reportes/resumen", headers=funcionario).json()
    assert rep["total_tramites"] == 1 and rep["por_estado"]["APROBADO"] == 1
    assert rep["tramites_con_reproceso"] == 1 and rep["tasa_reproceso_pct"] == 100.0


# ------------------------------------------------------------------ reglas de negocio
def test_duplicados_se_bloquean(cliente, ciudadano):
    h = ciudadano()
    folio = _crear(cliente, h)
    r = cliente.post("/tramites", json=NUEVO, headers=h)
    assert r.status_code == 409 and folio in r.json()["detail"]
    # otro tipo de trámite sí se permite
    _crear(cliente, h, tipo="vigencia_permanencia_definitiva")


@pytest.mark.parametrize("cambio", [{"tipo": "otro"}, {"email": "no-es-correo"}, {"nombre": "A"}])
def test_validaciones_preliminares(cliente, ciudadano, cambio):
    r = cliente.post("/tramites", json={**NUEVO, **cambio}, headers=ciudadano())
    assert r.status_code == 422


def test_un_ciudadano_no_ve_tramites_ajenos(cliente, ciudadano):
    folio = _crear(cliente, ciudadano(12345678))
    assert cliente.get(f"/tramites/{folio}", headers=ciudadano(11111111)).status_code == 404


def test_adjuntos_validan_tipo_y_tamano(cliente, ciudadano):
    h = ciudadano()
    folio = _crear(cliente, h)
    r = cliente.post(f"/tramites/{folio}/adjuntos", headers=h, files={"archivo": ("x.exe", b"MZ", "application/x-msdownload")})
    assert r.status_code == 422
    grande = b"0" * (5 * 1024 * 1024 + 1)
    r = cliente.post(f"/tramites/{folio}/adjuntos", headers=h, files={"archivo": ("g.pdf", grande, "application/pdf")})
    assert r.status_code == 413


def test_no_se_decide_sin_revision(cliente, ciudadano, funcionario):
    folio = _crear(cliente, ciudadano())
    r = cliente.post(f"/funcionario/tramites/{folio}/decision", headers=funcionario, json={"decision": "rechazar", "comentario": "motivo"})
    assert r.status_code == 409


# ------------------------------------------------------------------ IA con respaldo
def test_ia_valida_salida_y_cae_a_plantilla(monkeypatch):
    monkeypatch.setenv("IA_HABILITADA", "1")
    monkeypatch.setenv("LOCAL_MODE", "0")  # la IA solo se usa fuera del modo local

    monkeypatch.setattr(ai, "_llamar_modelo", lambda p: "Tu solicitud PDI-2026-000001 fue aprobada.")
    texto, origen = ai.redactar_aviso("certificado_viajes", "APROBADO", "PDI-2026-000001")
    assert origen == "ia" and "PDI-2026-000001" in texto

    # salida sin folio o con enlace: se descarta
    monkeypatch.setattr(ai, "_llamar_modelo", lambda p: "Entra a http://malo.example y paga.")
    assert ai.redactar_aviso("certificado_viajes", "APROBADO", "PDI-2026-000001")[1] == "plantilla"

    # falla del modelo: plantilla
    def falla(_):
        raise TimeoutError("sin respuesta")

    monkeypatch.setattr(ai, "_llamar_modelo", falla)
    assert ai.redactar_aviso("certificado_viajes", "APROBADO", "PDI-2026-000001")[1] == "plantilla"


def test_prompt_no_lleva_datos_personales():
    p = ai.construir_prompt("certificado_viajes", "APROBADO", "PDI-2026-000001")
    assert "PDI-2026-000001" in p and "@" not in p and "-5" not in p


def test_adaptador_es_determinista():
    from pdi.adaptadores import consulta_sintetica

    a = consulta_sintetica("12345678-5", "certificado_viajes")
    assert a == consulta_sintetica("12345678-5", "certificado_viajes")
    assert "permanencia_definitiva" in consulta_sintetica("12345678-5", "vigencia_permanencia_definitiva")
