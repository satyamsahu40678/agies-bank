import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Configure the test process before application imports can load project .env.
# Tests use disposable fixture databases and must never call paid providers or
# inherit production/session settings from a developer's configured workspace.
os.environ.update(
    {
        "AEGIS_ENV": "test",
        "AEGIS_DEMO_ENABLED": "true",
        "DATABASE_URL": "sqlite://",
        "AEGIS_STORAGE_BACKEND": "memory",
        "AEGIS_WORKER_ENABLED": "false",
        "AGIES_SECRET": "agies-test-session-secret-never-use-in-production",
        "AEGIS_ALLOWED_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
        "AEGIS_AI_PROVIDER": "local",
        "AEGIS_AI_MODE": "local",
        "AEGIS_KYC_VISION": "local",
    }
)
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db, SessionFactory, MemoryBackend, FirestoreBackend
from app.seed import seed_demo


@pytest.fixture
def db_factory(tmp_path):
    if os.getenv("AEGIS_TEST_FIRESTORE") == "true":
        if not os.getenv("FIRESTORE_EMULATOR_HOST"):
            pytest.fail("AEGIS_TEST_FIRESTORE requires a local FIRESTORE_EMULATOR_HOST")
        import uuid
        factory = SessionFactory(FirestoreBackend(project="demo-test-" + uuid.uuid4().hex[:12]))
    else:
        factory = SessionFactory(MemoryBackend())
    with factory() as db:
        seed_demo(db)
    yield factory


@pytest.fixture
def client(db_factory, monkeypatch):
    from app import main
    monkeypatch.setenv("AEGIS_WORKER_ENABLED", "true")
    monkeypatch.setattr(main, "SessionLocal", db_factory)
    def override():
        with db_factory() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise
    app.dependency_overrides[get_db] = override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def customer(client):
    result = client.post(
        "/api/auth/login",
        json={"email": "customer@aegis.demo", "password": "AegisDemo!2026"},
    )
    assert result.status_code == 200, result.text
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    return client


@pytest.fixture
def analyst(client):
    # Independent cookie jar allows customer and analyst in the same test.
    c = TestClient(app)
    result = c.post(
        "/api/auth/login",
        json={"email": "analyst@aegis.demo", "password": "AegisAnalyst!2026"},
    )
    assert result.status_code == 200, result.text
    c.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    yield c
    c.close()


def seed_records(db, records):
    """Bounded native fixture writes for complete-ledger aggregation regressions."""
    for start in range(0, len(records), 250):
        writes = {r.__collection__ + "/" + r.id: r.to_dict() for r in records[start:start+250]}
        db.backend.commit({}, writes)
