import os
from pathlib import Path
import subprocess
import sys
import sqlite3
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_versioned_schema_migration_repeatability_and_immutability(tmp_path):
    database = tmp_path / "migrated.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database}",
        "PYTHONPATH": str(ROOT),
        "AEGIS_ENV": "test",
    }
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-m", "app.manage", "migrate"],
            env=env,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
    with sqlite3.connect(database) as conn:
        assert (
            conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "0002_proactive"
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='trigger'"
            ).fetchone()[0]
            == 4
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='transfers'"
            ).fetchone()[0]
            == 1
        )


@pytest.mark.parametrize(
    "updates",
    [
        {"AGIES_SECRET": "short"},
        {"AEGIS_DEMO_ENABLED": "true"},
        {"DATABASE_URL": "sqlite:///bad.db"},
        {"AEGIS_ALLOWED_ORIGINS": "http://localhost:3000"},
    ],
)
def test_production_configuration_fails_closed(updates):
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "AEGIS_ENV": "production",
        "DATABASE_URL": "postgresql+psycopg://synthetic:unused@localhost/aegis",
        "AGIES_SECRET": "a" * 40,
        "AEGIS_ALLOWED_ORIGINS": "https://aegis.example",
        "AEGIS_DEMO_ENABLED": "false",
        "AEGIS_AI_MODE": "local",
        **updates,
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.config import validate_configuration; validate_configuration()",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def _production_lifespan(monkeypatch, engine, factory):
    from app import main
    from sqlalchemy import text

    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr(main.config, "PRODUCTION", True)
    monkeypatch.setattr(main.config, "DEMO_ENABLED", False)
    monkeypatch.setattr(main.config, "validate_configuration", lambda: None)
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        conn.execute(text("INSERT INTO alembic_version VALUES ('0002_proactive')"))
    return main.app


def test_production_refuses_existing_demo_database_without_deleting_records(
    monkeypatch, db_factory
):
    from sqlalchemy import select, func
    from app.models import User, LedgerEntry
    from fastapi.testclient import TestClient

    engine = db_factory.kw["bind"]
    with db_factory() as db:
        users_before = db.scalar(select(func.count()).select_from(User))
        ledger_before = db.scalar(select(func.count()).select_from(LedgerEntry))
    app = _production_lifespan(monkeypatch, engine, db_factory)
    with pytest.raises(RuntimeError, match="contains synthetic demo identities"):
        with TestClient(app):
            pass
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == users_before
        assert db.scalar(select(func.count()).select_from(LedgerEntry)) == ledger_before


def test_production_clean_migrated_database_initializes_without_demo_users(
    monkeypatch, tmp_path
):
    from sqlalchemy import create_engine, select, func
    from sqlalchemy.orm import sessionmaker
    from app.db import Base
    from app.models import Account, User, Document
    from fastapi.testclient import TestClient

    engine = create_engine(
        f"sqlite:///{tmp_path / 'production-guard.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = _production_lifespan(monkeypatch, engine, factory)
    with TestClient(app):
        pass
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert db.scalar(select(func.count()).select_from(Document)) == 0
        assert db.scalar(select(Account)).number == "INTERNAL_CLEARING"
    engine.dispose()


def test_demo_email_registration_is_reserved_when_demo_disabled(monkeypatch, client):
    from app import main

    monkeypatch.setattr(main.config, "DEMO_ENABLED", False)
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Reserved User",
            "email": "new@aegis.demo",
            "password": "SecurePassword!2026",
        },
    )
    assert response.status_code == 422
    assert "reserved" in response.json()["detail"]
