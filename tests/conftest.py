import os
import tempfile

# La base de pruebas se define ANTES de importar la app
_db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file}"
os.environ["JWT_SECRET"] = "secreto-solo-para-tests-" + "x" * 32

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seeds import SEED_PASSWORD, seed  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed()
    with TestClient(app) as c:
        yield c


def login(client: TestClient, email: str, password: str = SEED_PASSWORD) -> dict:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin(client):
    return login(client, "admin@miniblog.com")


@pytest.fixture()
def editora(client):
    return login(client, "editora@miniblog.com")


@pytest.fixture()
def editor(client):
    return login(client, "editor@miniblog.com")


@pytest.fixture()
def lector(client):
    return login(client, "lector@miniblog.com")
