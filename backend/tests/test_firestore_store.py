"""Storage invariants exercised against memory and the actual Firestore emulator."""

import subprocess
import sys
from pathlib import Path
from datetime import date
import pytest
from app.db import Session
from app.query import select, IntegrityError, ConcurrentWrite, DatabaseError
from app.models import Account, User, AuditLog, LedgerEntry, SavingsGoal
from app.maintenance import initialize_store, reconcile


def test_runtime_imports_no_sqlalchemy():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            'import app.main,sys; assert not any(k == "sqlalchemy" or k.startswith("sqlalchemy.") for k in sys.modules)',
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_stale_write_cannot_overwrite_newer_balance(db_factory):
    with db_factory() as first, db_factory() as second:
        a = first.scalar(select(Account).where(Account.user_id.is_not(None)))
        b = second.get(Account, a.id)
        a.status = "frozen"
        first.commit()
        b.status = "active"
        b.balance_paise += 1
        with pytest.raises(ConcurrentWrite):
            second.commit()
    with db_factory() as db:
        assert db.get(Account, a.id).status == "frozen"


def test_query_phantom_aborts_entire_business_commit(db_factory):
    with db_factory() as first, db_factory() as second:
        user = first.scalar(select(User).where(User.role == "customer"))
        assert (
            first.scalar(select(User).where(User.email == "phantom@example.test"))
            is None
        )
        second.add(
            User(
                name="Phantom", email="phantom@example.test", password_hash="synthetic"
            )
        )
        second.commit()
        first.add(
            AuditLog(
                user_id=user.id,
                agent="test",
                action="must_not_commit",
                summary="Phantom test",
            )
        )
        with pytest.raises(ConcurrentWrite):
            first.commit()
    with db_factory() as db:
        assert (
            db.scalar(select(AuditLog).where(AuditLog.action == "must_not_commit"))
            is None
        )


def test_unique_email_is_atomic_across_sessions(db_factory):
    with db_factory() as first, db_factory() as second:
        for db in [first, second]:
            db.add(
                User(
                    name="Duplicate",
                    email="duplicate@example.test",
                    password_hash="synthetic",
                )
            )
        first.commit()
        with pytest.raises((IntegrityError, ConcurrentWrite)):
            second.commit()
    with db_factory() as db:
        assert (
            len(
                db.scalars(
                    select(User).where(User.email == "duplicate@example.test")
                ).all()
            )
            == 1
        )


def test_audit_mutation_and_ledger_delete_are_rejected(db_factory):
    with db_factory() as db:
        log = db.scalar(select(AuditLog))
        log.summary = "Changed"
        with pytest.raises(DatabaseError):
            db.commit()
        db.rollback()
        with pytest.raises(DatabaseError):
            db.delete(db.scalar(select(LedgerEntry)))


def test_native_initialization_is_resumable_and_reconciles_without_moving_funds(
    db_factory,
):
    first = initialize_store(db_factory)
    second = initialize_store(db_factory)
    assert first == second
    assert second["schema_version"] == 2
    with db_factory() as db:
        assert reconcile(db)["ok"]


def test_goal_date_round_trips_as_a_date(db_factory):
    with db_factory() as db:
        user = db.scalar(select(User).where(User.role == "customer"))
        goal = SavingsGoal(
            user_id=user.id,
            name="Date check",
            target_paise=10000,
            target_date=date(2027, 1, 1),
        )
        db.add(goal)
        db.commit()
    with db_factory() as db:
        assert db.get(SavingsGoal, goal.id).target_date == date(2027, 1, 1)


def test_foreign_key_and_integer_money_guards_preserve_existing_records(db_factory):
    with db_factory() as db:
        customer = db.scalar(select(User).where(User.role == "customer"))
        db.delete(customer)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.get(User, customer.id) is not None
        account = db.scalar(select(Account).where(Account.user_id == customer.id))
        account.balance_paise = 1.5
        with pytest.raises(IntegrityError): db.commit()
