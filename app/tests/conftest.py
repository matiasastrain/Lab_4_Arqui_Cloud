import os
import sys
import tempfile
from pathlib import Path

# La app vive un nivel arriba: app/pdi
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_tmp = tempfile.mkdtemp(prefix="pdi_test_")
os.environ.update(
    LOCAL_MODE="1",
    APP_MODE="gestor",
    DATABASE_URL=f"sqlite:///{_tmp}/test.db",
    LOCAL_STORAGE_DIR=f"{_tmp}/storage",
    JWT_SECRET="secreto-de-pruebas-con-largo-suficiente-32b",
    FUNCIONARIO_API_KEY="clave-funcionario-pruebas",
    PORTAL_URL="https://portal.test",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from pdi import db, storage  # noqa: E402


@pytest.fixture()
def cliente():
    db.reiniciar_engine()
    storage.reiniciar_almacen()
    from pdi.gestor import app

    db.Base.metadata.drop_all(db.get_engine())
    db.Base.metadata.create_all(db.get_engine())
    with TestClient(app) as c:
        yield c


def rut_valido(cuerpo: int) -> str:
    from pdi.security import digito_verificador

    return f"{cuerpo}-{digito_verificador(cuerpo)}"


@pytest.fixture()
def ciudadano(cliente):
    def _login(cuerpo: int = 12345678):
        r = cliente.post("/auth/ciudadano", json={"rut": rut_valido(cuerpo)})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token']}"}

    return _login


@pytest.fixture()
def funcionario(cliente):
    r = cliente.post("/auth/funcionario", json={"clave": "clave-funcionario-pruebas"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
