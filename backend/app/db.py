"""Firestore unit of work with atomic, conditional commits.

Every collection read has a revision guard. Native Commit preconditions check
those guards and document write versions atomically. Revisions prevent phantom
inserts/deletes; hashed reservations enforce uniqueness. Ledger, audit, balances
and jobs commit together. Provider calls happen before the short atomic commit.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime
from threading import RLock

from .query import (
    ConcurrentWrite,
    DatabaseError,
    Expr,
    Field,
    IntegrityError,
    Query,
    Record,
    Result,
    project,
    select,
    value,
)

IMMUTABLE = {"ledger_entries", "audit_logs"}
SCHEMA_VERSION = 2


def encode(data):
    if isinstance(data, datetime):
        return data
    if isinstance(data, date):
        return data.isoformat()
    if isinstance(data, dict):
        return {k: encode(v) for k, v in data.items()}
    if isinstance(data, list):
        return [encode(v) for v in data]
    return data


class MemoryBackend:
    """Explicit development/test backend; never a cloud fallback."""

    def __init__(self):
        self.lock, self.docs, self.versions, self.counter = RLock(), {}, {}, 0

    def read(self, path):
        with self.lock:
            return deepcopy(self.docs.get(path)), self.versions.get(path)

    def query(self, collection, predicate=None):
        with self.lock:
            return [
                (p.split("/", 1)[1], deepcopy(d), self.versions[p])
                for p, d in self.docs.items()
                if p.startswith(collection + "/")
            ]

    def commit(self, expected, writes):
        with self.lock:
            for path, version in expected.items():
                if self.versions.get(path) != version:
                    raise ConcurrentWrite("Concurrent change; retry the operation")
            for path, data in writes.items():
                self.counter += 1
                if data is None:
                    self.docs.pop(path, None)
                    self.versions.pop(path, None)
                else:
                    self.docs[path], self.versions[path] = deepcopy(data), self.counter
            return {p: self.versions.get(p) for p in writes}

    def ping(self):
        return True


class FirestoreBackend:
    def __init__(self, *, project=None, database=None):
        from google.auth.credentials import AnonymousCredentials
        from google.cloud import firestore

        project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project:
            raise RuntimeError("Firestore requires GOOGLE_CLOUD_PROJECT")
        credentials = (
            AnonymousCredentials() if os.getenv("FIRESTORE_EMULATOR_HOST") else None
        )
        self.client = firestore.Client(
            project=project,
            database=database or os.getenv("FIRESTORE_DATABASE", "(default)"),
            credentials=credentials,
        )

    def read(self, path):
        snap = self.client.document(path).get(timeout=15)
        return (snap.to_dict(), snap.update_time) if snap.exists else (None, None)

    def query(self, collection, predicate=None):
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self.client.collection(collection)
        if predicate:
            name, operator, val = predicate
            query = query.where(filter=FieldFilter(name, operator, encode(val)))
        return [(s.id, s.to_dict(), s.update_time) for s in query.stream(timeout=20)]

    def commit(self, expected, writes):
        from google.api_core.exceptions import (
            Aborted,
            AlreadyExists,
            FailedPrecondition,
            NotFound,
        )
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP, LastUpdateOption

        # A conditional atomic Commit avoids read-lock upgrades under contention.
        # Every collection read (including point reads) has a revision guard.
        # Updating those guards with their observed update_time validates the
        # whole read set and prevents phantoms, without locking ledger history.
        staged = dict(writes)
        for path in expected:
            if path.startswith("_revisions/") and path not in staged:
                staged[path] = {"checked_at": SERVER_TIMESTAMP}
        if len(staged) > 450:
            raise DatabaseError("Transaction exceeds the bounded write limit")
        batch = self.client.batch()
        paths = []
        for path, data in staged.items():
            ref, version = self.client.document(path), expected.get(path)
            if data is None:
                if version is None:
                    continue
                batch.delete(ref, option=LastUpdateOption(version))
            elif path not in expected:
                # Explicit unconditional writes are only used by offline
                # maintenance and fixture loaders, never a business session.
                batch.set(ref, encode(data))
            elif version is None:
                batch.create(ref, encode(data))
            else:
                batch.update(ref, encode(data), option=LastUpdateOption(version))
            paths.append(path)
        try:
            results = batch.commit(retry=None, timeout=25)
            return {p: r.update_time for p, r in zip(paths, results)}
        except (Aborted, FailedPrecondition, AlreadyExists, NotFound) as exc:
            raise ConcurrentWrite("Concurrent change; retry the operation") from exc

    def ping(self):
        self.read("_system/schema")
        return True


def _predicate(conditions):
    candidates = []

    def visit(expr):
        if not isinstance(expr, Expr):
            return
        if expr.op == "and":
            for arg in expr.args:
                visit(arg)
        if (
            expr.op == "eq"
            and isinstance(expr.args[0], Field)
            and not isinstance(expr.args[1], Expr)
        ):
            candidates.append((expr.args[0].name, "==", expr.args[1]))
        if (
            expr.op == "in"
            and isinstance(expr.args[0], Field)
            and 0 < len(expr.args[1]) <= 30
        ):
            candidates.append((expr.args[0].name, "in", list(expr.args[1])))

    for condition in conditions:
        visit(condition)
    return (
        min(
            candidates,
            key=lambda c: (
                c[0] not in {"user_id", "account_id", "document_id"},
                c[0] != "id",
            ),
        )
        if candidates
        else None
    )


class Session:
    def __init__(self, backend):
        self.backend = backend
        self.rollback()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self.rollback()

    def rollback(self):
        self.identity, self.original, self.expected, self.deleted, self.raw = (
            {},
            {},
            {},
            set(),
            {},
        )

    def _read(self, path):
        if path not in self.raw:
            data, version = self.backend.read(path)
            self.raw[path], self.expected[path] = data, version
        return self.raw[path]

    def _epoch(self, collection):
        self._read("_revisions/" + collection)

    def _track(self, model, key, data, version):
        path = f"{model.__collection__}/{key}"
        if path not in self.identity:
            self.identity[path] = model(
                **{k: v for k, v in data.items() if k in model.__fields__}
            )
            self.original[path], self.expected[path], self.raw[path] = (
                self.identity[path].to_dict(),
                version,
                data,
            )
        elif self.identity[path].to_dict() == self.original[path]:
            for name, val in data.items():
                if name in model.__fields__:
                    setattr(self.identity[path], name, val)
            self.original[path], self.expected[path], self.raw[path] = (
                self.identity[path].to_dict(),
                version,
                data,
            )
        return self.identity[path]

    def get(self, model, key):
        self._epoch(model.__collection__)
        path = f"{model.__collection__}/{key}"
        if path in self.deleted:
            return None
        if path in self.identity:
            if self.identity[path].to_dict() != self.original[path] or path in self.raw:
                return self.identity[path]
            data, version = self.backend.read(path)
            if data is None:
                return None
            return self._track(model, str(key), data, version)
        data = self._read(path)
        return (
            self._track(model, str(key), data, self.expected[path])
            if data is not None
            else None
        )

    def add(self, record):
        if not record.id:
            raise IntegrityError("Record ID is required")
        self._epoch(record.__collection__)
        path = f"{record.__collection__}/{record.id}"
        if path not in self.identity:
            if self._read(path) is not None:
                raise IntegrityError("Record already exists")
            self.identity[path], self.original[path] = record, None
        self.deleted.discard(path)

    def add_all(self, records):
        for record in records:
            self.add(record)

    def delete(self, record):
        if record.__collection__ in IMMUTABLE:
            raise DatabaseError("Append-only evidence cannot be deleted")
        self.deleted.add(f"{record.__collection__}/{record.id}")

    def _records(self, query):
        model = query.model
        if model is None:
            raise ValueError("A datastore collection is required")
        collection = model.__collection__
        self._epoch(collection)
        loaded = set()
        for key, data, version in self.backend.query(
            collection, _predicate(query.conditions)
        ):
            self._track(model, key, data, version)
            loaded.add(f"{collection}/{key}")
        return [
            r
            for path, r in self.identity.items()
            if path.startswith(collection + "/")
            and path not in self.deleted
            and (
                path in loaded
                or self.original[path] is None
                or r.to_dict() != self.original[path]
            )
            and query.matches(r)
        ]

    def execute(self, query, **_):
        if not isinstance(query, Query):
            raise DatabaseError("Only datastore query specifications are accepted")
        rows = self._records(query)
        if query.operation == "select":
            return project(query, rows)
        if query.model.__collection__ in IMMUTABLE:
            raise DatabaseError("Append-only evidence cannot be changed")
        output = []
        for record in rows:
            if query.operation == "delete":
                self.delete(record)
            else:
                changes = {
                    name: value(expr, record) for name, expr in query.changes.items()
                }
                for name, val in changes.items():
                    setattr(record, name, val)
            if query.returned:
                output.append(tuple(value(c, record) for c in query.returned))
        return Result(output, rowcount=len(rows))

    def scalars(self, query):
        return Result(
            [r[0] if isinstance(r, tuple) else r for r in self.execute(query)]
        )

    def scalar(self, query):
        return self.execute(query).scalar()

    def refresh(self, record):
        return record

    def expire_all(self):
        if not self._changes():
            self.rollback()

    @contextmanager
    def begin_nested(self):
        saved = (
            dict(self.identity),
            deepcopy(self.original),
            dict(self.expected),
            set(self.deleted),
            deepcopy(self.raw),
        )
        try:
            yield self
        except Exception:
            self.identity, self.original, self.expected, self.deleted, self.raw = saved
            raise

    def _changes(self):
        return {
            p: None if p in self.deleted else r.to_dict()
            for p, r in self.identity.items()
            if p in self.deleted
            or self.original[p] is None
            or r.to_dict() != self.original[p]
        }

    def _validate(self, record):
        data, collection = record.to_dict(), record.__collection__
        for name, field in record.__fields__.items():
            if data[name] is None and not field.nullable:
                raise IntegrityError(f"{collection}.{name} is required")
            if (
                data[name] is not None
                and field.kind.split(" | ")[0] == "int"
                and (
                    type(data[name]) is not int
                    or not -(1 << 63) <= data[name] < (1 << 63)
                )
            ):
                raise IntegrityError("Integer fields require signed 64-bit integers")
        for name, reference in record.__references__.items():
            if data[name] is not None and not self.get(
                Record.registry[reference.split(".")[0]], data[name]
            ):
                raise IntegrityError("Referenced record does not exist")
        if (
            collection == "accounts"
            and data["user_id"] is not None
            and data["balance_paise"] < 0
        ):
            raise IntegrityError("Customer balances cannot be negative")
        if collection in {"ledger_entries", "transfers"} and data["amount_paise"] <= 0:
            raise IntegrityError("Amounts must be positive integer paise")
        if collection == "budgets" and data["limit_paise"] < 0:
            raise IntegrityError("Budget cannot be negative")
        if collection == "savings_goals" and (
            not 0 <= data["saved_paise"] <= data["target_paise"]
            or data["target_paise"] <= 0
            or data["status"] not in {"active", "paused", "completed"}
        ):
            raise IntegrityError("Invalid savings goal")
        if collection == "agent_runs" and (
            data["status"] not in {"queued", "running", "completed", "failed"}
            or not 1 <= data["max_attempts"] <= 5
            or not 0 <= data["manual_retries"] <= 3
            or data["attempts"] < 0
        ):
            raise IntegrityError("Invalid bounded agent job")
        if collection == "financial_insights" and (
            data["status"] not in {"active", "dismissed", "resolved"}
            or data["severity"] not in {"info", "warning", "critical"}
        ):
            raise IntegrityError("Invalid financial insight")
        if collection == "automations" and (
            data["kind"]
            not in {
                "financial_health",
                "security_review",
                "document_review",
                "savings_coach",
            }
            or not 1 <= data["interval_hours"] <= 168
        ):
            raise IntegrityError("Invalid automation schedule")

    def _reservations(self, record, data):
        if data is None:
            return set()
        result = set()
        for names in record.__unique__:
            values = [data[n] for n in names]
            if any(v is None for v in values):
                continue
            payload = json.dumps(
                [record.__collection__, names, values], sort_keys=True, default=str
            )
            result.add("_unique/" + hashlib.sha256(payload.encode()).hexdigest())
        return result

    def flush(self):
        seen = {}
        for path, data in self._changes().items():
            record = self.identity[path]
            if data is None:
                for model in Record.registry.values():
                    for name, reference in model.__references__.items():
                        if reference == record.__collection__ + ".id" and self.scalar(
                            select(model).where(getattr(model, name) == record.id)
                        ):
                            raise IntegrityError("Referenced records cannot be deleted")
                continue
            self._validate(record)
            for key in self._reservations(record, data):
                reservation = self._read(key)
                if (reservation and reservation["owner"] != path) or (
                    key in seen and seen[key] != path
                ):
                    raise IntegrityError("A unique record already exists")
                seen[key] = path

    def commit(self):
        self.flush()
        changes = self._changes()
        if not changes:
            self.raw = {}
            self.expected = {
                p: v for p, v in self.expected.items() if p in self.identity
            }
            return
        writes = {}
        for path, data in changes.items():
            record, old = self.identity[path], self.original[path]
            collection = record.__collection__
            if collection in IMMUTABLE and old is not None:
                raise DatabaseError("Append-only evidence cannot be changed")
            self._epoch(collection)
            for key in self._reservations(record, old) - self._reservations(
                record, data
            ):
                reservation = self._read(key)
                if reservation and reservation["owner"] == path:
                    writes[key] = None
            for key in self._reservations(record, data):
                reservation = self._read(key)
                if reservation and reservation["owner"] != path:
                    raise IntegrityError("A unique record already exists")
                if key in writes and writes[key] and writes[key]["owner"] != path:
                    raise IntegrityError("Duplicate unique records")
                writes[key] = {"owner": path}
            writes[path] = (
                dict(data, _aegis_schema_version=SCHEMA_VERSION)
                if data is not None
                else None
            )
            writes["_revisions/" + collection] = {
                "token": __import__("uuid").uuid4().hex
            }
        if len(writes) > 450:
            raise DatabaseError("Transaction exceeds the bounded write limit")
        versions = self.backend.commit(dict(self.expected), writes)
        for path in self.deleted:
            self.identity.pop(path, None)
            self.original.pop(path, None)
        self.deleted, self.raw = set(), {}
        self.original = {p: r.to_dict() for p, r in self.identity.items()}
        self.expected = {
            p: versions.get(p, self.expected.get(p)) for p in self.identity
        }

    def ping(self):
        return self.backend.ping()


class SessionFactory:
    def __init__(self, backend):
        self.backend = backend

    def __call__(self):
        return Session(self.backend)


_backend = None


def default_backend():
    global _backend
    if _backend is None:
        mode = os.getenv("AEGIS_STORAGE_BACKEND", "firestore")
        if mode == "memory":
            _backend = MemoryBackend()
        elif mode == "firestore":
            _backend = FirestoreBackend()
        else:
            raise RuntimeError("AEGIS_STORAGE_BACKEND must be firestore or memory")
    return _backend


def SessionLocal():
    return Session(default_backend())


def get_db():
    with SessionLocal() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise
