from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.db import Base
from app.firestore_migration import (
    _encode,
    migrate_sqlite_to_firestore,
)
from app.models import User
from app.seed import seed_demo


class Snapshot:
    def __init__(self, values):
        self.exists = values is not None
        self._values = values

    def to_dict(self):
        return self._values


class Document:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.id = document_id

    def get(self):
        return Snapshot(self.collection.values.get(self.id))


class Collection:
    def __init__(self):
        self.values = {}

    def document(self, document_id):
        return Document(self, document_id)

    def stream(self):
        return [Snapshot(values) for values in self.values.values()]


class Batch:
    def __init__(self):
        self.writes = []

    def set(self, reference, values):
        self.writes.append((reference, values))

    def commit(self):
        for reference, values in self.writes:
            reference.collection.values[reference.id] = values


class Firestore:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, Collection())

    def batch(self):
        return Batch()


@pytest.fixture
def sqlite_source(tmp_path):
    path = tmp_path / "source.db"
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_demo(db)
    yield path
    engine.dispose()


def test_firestore_migration_dry_run_is_read_only_and_counts_every_table(sqlite_source):
    result = migrate_sqlite_to_firestore(sqlite_source)

    assert set(result) == {table.name for table in Base.metadata.sorted_tables}
    assert sum(table["source"] for table in result.values()) > 0
    assert all(table["written"] == 0 for table in result.values())
    assert all(table["skipped_identical"] == 0 for table in result.values())


def test_firestore_migration_imports_all_rows_and_is_resumable(sqlite_source):
    client = Firestore()

    first = migrate_sqlite_to_firestore(sqlite_source, client, apply=True)
    second = migrate_sqlite_to_firestore(sqlite_source, client, apply=True)

    assert sum(table["written"] for table in first.values()) > 0
    assert all(table["skipped_identical"] == 0 for table in first.values())
    assert all(table["written"] == 0 for table in second.values())
    assert sum(table["skipped_identical"] for table in second.values()) == sum(
        table["source"] for table in second.values()
    )
    assert set(client.collections) == {table.name for table in Base.metadata.sorted_tables}


def test_firestore_migration_refuses_to_overwrite_conflicting_data(sqlite_source):
    engine = create_engine(f"sqlite:///{sqlite_source}")
    with engine.connect() as connection:
        user_id = connection.execute(select(User.id).limit(1)).scalar_one()
    engine.dispose()
    client = Firestore()
    client.collection("users").values[user_id] = {"id": user_id, "name": "Conflict"}

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        migrate_sqlite_to_firestore(sqlite_source, client, apply=True)
    assert client.collection("users").values[user_id]["name"] == "Conflict"


def test_firestore_migration_normalizes_dates_and_naive_datetimes():
    assert _encode(date(2026, 10, 16)) == "2026-10-16"
    assert _encode(datetime(2026, 10, 16)) == datetime(
        2026, 10, 16, tzinfo=timezone.utc
    )
    assert _encode(datetime(2026, 10, 16, tzinfo=timezone.utc)) == datetime(
        2026, 10, 16, tzinfo=timezone.utc
    )
