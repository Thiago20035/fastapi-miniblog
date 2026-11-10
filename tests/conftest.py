import os
import tempfile

# La base de pruebas se define ANTES de importar la app
_db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file}"
os.environ["JWT_SECRET"] = "secreto-solo-para-tests-" + "x" * 32
os.environ["AI_BRAIN"] = "offline"  # los tests nunca llaman a la API de Claude

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seeds import SEED_PASSWORD, seed  # noqa: E402


@pytest.fixture()
def keys():
    """Recrea la base con los seeds y devuelve las claves de los agentes del sitio."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return seed()["keys"]


@pytest.fixture()
def client(keys):
    with TestClient(app) as c:
        yield c


def login(client: TestClient, email: str, password: str = SEED_PASSWORD) -> dict:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def as_agent(keys: dict, handle: str) -> dict:
    return {"X-Agent-Key": keys[handle]}


@pytest.fixture()
def admin(client):
    return login(client, "admin@miniblog.com")


@pytest.fixture()
def moderadora(client):
    return login(client, "moderadora@miniblog.com")


@pytest.fixture()
def familia(client):
    return login(client, "familia@miniblog.com")
