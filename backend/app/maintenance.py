"""Idempotent cutover validation and read-only ledger reconciliation."""

from collections import defaultdict

from .db import SCHEMA_VERSION, SessionLocal
from .models import Account, LedgerEntry
from .query import IntegrityError, Record, select


def verify_schema(factory=SessionLocal):
    """Gate an ordinary rollout without running offline maintenance on writers."""
    with factory() as db:
        marker = db.backend.read("_system/schema")[0]
        if not marker or marker.get("version") != SCHEMA_VERSION:
            raise IntegrityError(
                "Firestore schema is incompatible. Stop writers and initialize the schema offline before deploying."
            )
    return {"schema_version": SCHEMA_VERSION, "mode": "read_only"}


def reconcile(db):
    totals = defaultdict(int)
    invalid = []
    for entry in db.scalars(select(LedgerEntry)):
        if entry.status != "posted":
            continue
        if entry.direction not in {"credit", "debit"} or entry.amount_paise <= 0:
            invalid.append(entry.id)
        totals[entry.account_id] += entry.amount_paise * (
            1 if entry.direction == "credit" else -1
        )
    accounts = db.scalars(select(Account)).all()
    mismatches = [a.id for a in accounts if totals.pop(a.id, 0) != a.balance_paise]
    mismatches.extend(totals)
    return {
        "ok": not mismatches
        and not invalid
        and sum(a.balance_paise for a in accounts) == 0,
        "accounts_checked": len(accounts),
        "mismatched_account_ids": mismatches,
        "invalid_entry_ids": invalid,
        "total_balance_paise": sum(a.balance_paise for a in accounts),
    }


def initialize_store(factory=SessionLocal):
    """Run with writers stopped after import. Never overwrite bank documents.

    Validate all records before reserving unique values. The reservations and
    schema marker are resumable; conflicting reservations fail closed.
    """
    with factory() as db:
        records = []
        for model in Record.registry.values():
            records.extend(db.scalars(select(model)).all())
        seen = {}
        for record in records:
            db._validate(record)
            path = f"{record.__collection__}/{record.id}"
            for key in db._reservations(record, record.to_dict()):
                if key in seen and seen[key] != path:
                    raise IntegrityError(
                        "Imported data contains duplicate unique records"
                    )
                seen[key] = path
        report = reconcile(db)
        if not report["ok"]:
            raise IntegrityError(
                "Ledger reconciliation failed; source and target records were preserved"
            )
        for key, owner in seen.items():
            current, version = db.backend.read(key)
            if current and current.get("owner") != owner:
                raise IntegrityError("Unique reservation conflict; records preserved")
            if not current:
                _, owner_version = db.backend.read(owner)
                db.backend.commit(
                    {key: version, owner: owner_version}, {key: {"owner": owner}}
                )
        for collection in Record.registry:
            path = "_revisions/" + collection
            current, version = db.backend.read(path)
            if current is None:
                db.backend.commit({path: version}, {path: {"token": "initialized"}})
        path = "_system/schema"
        _, version = db.backend.read(path)
        db.backend.commit(
            {path: version},
            {path: {"version": SCHEMA_VERSION, "records_validated": len(records)}},
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "records_validated": len(records),
            "reconciliation": report,
        }
