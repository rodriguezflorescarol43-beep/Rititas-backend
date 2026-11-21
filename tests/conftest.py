import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.core import firma, security
from backend.app.core.database import get_session
from backend.app.services import medios
from backend.app.main import app
from backend.app.models import entities  # noqa: F401
from backend.app.seed import sembrar


@pytest.fixture(autouse=True)
def aislar_admin(monkeypatch, tmp_path):
    """Contraseña conocida, carpeta de subidas temporal y límite de intentos limpio."""
    monkeypatch.setattr(security, "ADMIN_PASSWORD", "clave-de-prueba")
    monkeypatch.setattr(medios, "UPLOADS_DIR", tmp_path / "subidas")
    monkeypatch.setattr(firma, "RUTA_CLAVE", tmp_path / "clave_firma.pem")
    firma.reiniciar()
    security.limite_login.reiniciar()


@pytest.fixture()
def admin(client):
    r = client.post("/api/admin/login", json={"password": "clave-de-prueba"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def engine():
    motor = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(motor)
    with Session(motor) as s:
        sembrar(s)
    return motor


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(engine):
    def _sesion():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _sesion
    yield TestClient(app)
    app.dependency_overrides.clear()
