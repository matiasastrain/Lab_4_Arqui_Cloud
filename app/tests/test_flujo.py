"""15 pruebas automáticas del flujo completo (SQLite + disco, avisos en línea)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PDF = b"%PDF-1.4\n%prueba\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
CLAVE = "clave-pruebas"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "adj"))
    monkeypatch.setenv("FUNCIONARIO_API_KEY", CLAVE)
    monkeypatch.setenv("IA_HABILITADA", "false")
    for v in ("TASKS_QUEUE", "BUCKET", "ADAPTADORES_URL", "DB_HOST"):
        monkeypatch.delenv(v, raising=False)
    from pdi.config import reset_config
    reset_config()
    from fastapi.testclient import TestClient
    from pdi.gestor import crear_app
    with TestClient(crear_app()) as c:
        yield c


def _ciudadano(c, rut="12.345.678-5", nombre="Ana Pérez"):
    r = c.post("/api/auth/ciudadano", json={"rut": rut, "nombre": nombre, "email": "ana@example.com"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _funcionario(c):
    r = c.post("/api/auth/funcionario", json={"clave": CLAVE})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _crear(c, h, tipo="CERT_VIAJES"):
    r = c.post("/api/tramites", json={"tipo": tipo}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["folio"]


def _adjuntar(c, h, folio, datos=PDF, nombre="doc.pdf"):
    return c.post(f"/api/tramites/{folio}/adjuntos", files={"archivo": (nombre, datos, "application/pdf")}, headers=h)


# 1
def test_validacion_rut():
    from pdi.security import normalizar_rut, rut_valido
    assert normalizar_rut("12.345.678-5") == "12345678-5"
    assert rut_valido("11111111-1")
    assert not rut_valido("12.345.678-9")
    assert not rut_valido("abc")


# 2
def test_login_rut_invalido(client):
    r = client.post("/api/auth/ciudadano", json={"rut": "12345678-9", "nombre": "X Y"})
    assert r.status_code == 400


# 3
def test_crear_tramite_entrega_folio_y_aviso(client):
    h = _ciudadano(client)
    folio = _crear(client, h)
    assert folio.startswith("CV-")
    d = client.get(f"/api/tramites/{folio}", headers=h).json()
    assert d["estado"] == "RECIBIDO"
    assert d["avisos_generados"] == 1 and folio in d["historial"][0]["aviso"]["texto"]


# 4
def test_control_de_duplicados(client):
    h = _ciudadano(client)
    _crear(client, h)
    assert client.post("/api/tramites", json={"tipo": "CERT_VIAJES"}, headers=h).status_code == 409
    assert _crear(client, h, "VIGENCIA_PD").startswith("PD-")


# 5
def test_adjunto_tipo_invalido(client):
    h = _ciudadano(client)
    folio = _crear(client, h)
    assert _adjuntar(client, h, folio, b"hola mundo", "x.pdf").status_code == 415


# 6
def test_adjunto_mayor_a_5mb(client):
    h = _ciudadano(client)
    folio = _crear(client, h)
    grande = PDF + b"0" * (5 * 1024 * 1024)
    assert _adjuntar(client, h, folio, grande).status_code == 413


# 7
def test_adjunto_valido_png(client):
    h = _ciudadano(client)
    folio = _crear(client, h)
    r = _adjuntar(client, h, folio, b"\x89PNG\r\n\x1a\n" + b"0" * 50, "foto.png")
    assert r.status_code == 201 and r.json()["content_type"] == "image/png"


# 8
def test_ciudadano_no_ve_tramite_ajeno(client):
    folio = _crear(client, _ciudadano(client))
    otro = _ciudadano(client, "11.111.111-1", "Otro Ciudadano")
    assert client.get(f"/api/tramites/{folio}", headers=otro).status_code == 404
    assert client.get("/api/tramites", headers=otro).json() == []


# 9
def test_funcionario_clave_incorrecta_y_roles(client):
    assert client.post("/api/auth/funcionario", json={"clave": "mala"}).status_code == 401
    h = _ciudadano(client)
    folio = _crear(client, h)
    assert client.post(f"/api/tramites/{folio}/tomar", headers=h).status_code == 403


# 10
def test_aprobar_requiere_adjunto(client):
    h = _ciudadano(client)
    folio = _crear(client, h)
    f = _funcionario(client)
    client.post(f"/api/tramites/{folio}/tomar", headers=f)
    r = client.post(f"/api/tramites/{folio}/decision", json={"resultado": "APROBADO"}, headers=f)
    assert r.status_code == 422


# 11
def test_flujo_aprobacion_certificado_y_reporte(client):
    h = _ciudadano(client)
    folio = _crear(client, h)
    assert _adjuntar(client, h, folio).status_code == 201
    f = _funcionario(client)
    assert client.post(f"/api/tramites/{folio}/tomar", headers=f).json()["estado"] == "EN_REVISION"
    ant = client.get(f"/api/tramites/{folio}/antecedentes", headers=f).json()
    assert ant["gepol"]["sintetico"] and ant["b3000"]["sistema"] == "B3000"
    d = client.post(f"/api/tramites/{folio}/decision", json={"resultado": "APROBADO"}, headers=f).json()
    assert d["estado"] == "APROBADO" and d["avisos_generados"] == 3
    pdf = client.get(f"/api/tramites/{folio}/certificado", headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    rep = client.get("/api/reportes/resumen", headers=f).json()
    assert rep["por_estado"]["APROBADO"] == 1 and rep["total_avisos"] == 3


# 12
def test_observar_y_subsanar(client):
    h = _ciudadano(client)
    folio = _crear(client, h)
    f = _funcionario(client)
    client.post(f"/api/tramites/{folio}/tomar", headers=f)
    r = client.post(f"/api/tramites/{folio}/decision", json={"resultado": "OBSERVADO", "observacion": "Falta pasaporte"}, headers=f)
    assert r.json()["estado"] == "OBSERVADO"
    assert client.get(f"/api/tramites/{folio}/certificado", headers=h).status_code == 409
    r = client.post(f"/api/tramites/{folio}/subsanar", json={"comentario": "Adjunto pasaporte"}, headers=h)
    assert r.json()["estado"] == "EN_REVISION"


# 13
def test_rechazo_requiere_motivo(client):
    h = _ciudadano(client)
    folio = _crear(client, h)
    f = _funcionario(client)
    client.post(f"/api/tramites/{folio}/tomar", headers=f)
    assert client.post(f"/api/tramites/{folio}/decision", json={"resultado": "RECHAZADO"}, headers=f).status_code == 422
    r = client.post(f"/api/tramites/{folio}/decision", json={"resultado": "RECHAZADO", "observacion": "No corresponde"}, headers=f)
    assert r.json()["estado"] == "RECHAZADO"
    # cerrado: ya no se aceptan adjuntos y se puede iniciar uno nuevo del mismo tipo
    assert _adjuntar(client, h, folio).status_code == 409
    _crear(client, h)


# 14
def test_aviso_idempotente(client):
    from sqlalchemy import func, select
    from pdi.db import Notificacion, SessionLocal
    from pdi.servicios import procesar_aviso
    h = _ciudadano(client)
    folio = _crear(client, h)
    hid = client.get(f"/api/tramites/{folio}", headers=h).json()["historial"][0]["id"]
    assert procesar_aviso(hid)["estado"] == "duplicado"  # reintento de Cloud Tasks
    with SessionLocal() as s:
        assert s.scalar(select(func.count()).select_from(Notificacion)) == 1


# 15
def test_validacion_salida_ia():
    from pdi.ai import plantilla, validar
    folio = "CV-2026-000001"
    assert validar(f"Su trámite {folio} fue aprobado.", folio)
    assert not validar("Su trámite fue aprobado.", folio)                      # sin folio
    assert not validar(f"Folio {folio}, revise https://pdi.cl", folio)         # con enlace
    assert not validar(f"Folio {folio} " + "x" * 400, folio)                   # muy largo
    assert validar(plantilla(folio, "CERT_VIAJES", "OBSERVADO", "Ana", "Falta pasaporte"), folio)
