from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from app.models import Automation, AgentRun, Account, LedgerEntry, User, utcnow
from app.query import select, func
from app.services import automations as a, proactive as p


def user(db):
    return db.scalar(select(User).where(User.role == "customer"))


@pytest.mark.parametrize("kind", sorted(a.KINDS))
def test_each_workflow_finishes_without_moving_money(db_factory, kind):
    with db_factory() as db:
        before = {x.id: x.balance_paise for x in db.scalars(select(Account))}
        count = db.scalar(select(func.count()).select_from(LedgerEntry))
        item = a.save(db, user(db), kind, 24)
        run = a.queue(db, user(db), item)
        run_id = run.id
        db.commit()
    assert p.process_next(db_factory)
    with db_factory() as db:
        completed = db.get(AgentRun, run_id)
        assert completed.status == "completed"
        assert completed.output["summary"]
        assert completed.tools
        assert before == {x.id: x.balance_paise for x in db.scalars(select(Account))}
        assert count == db.scalar(select(func.count()).select_from(LedgerEntry))


def test_parallel_dispatchers_queue_a_schedule_once(db_factory):
    with db_factory() as db:
        item = a.save(db, user(db), "security_review", 6)
        item.next_run_at = utcnow() - timedelta(minutes=1)
        item_id = item.id
        db.commit()
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert sum(pool.map(lambda _: a.dispatch_due(db_factory), range(3))) == 1
    with db_factory() as db:
        assert db.get(Automation, item_id).next_run_at > utcnow()
        assert (
            len(
                db.scalars(
                    select(AgentRun).where(AgentRun.kind == "security_review")
                ).all()
            )
            == 1
        )


def test_paused_automation_never_dispatches(db_factory):
    with db_factory() as db:
        a.save(db, user(db), "document_review", 24, False)
        db.commit()
    assert a.dispatch_due(db_factory) == 0


def test_automation_routes_are_tenant_scoped_and_csrf_protected(customer, analyst):
    result = customer.put(
        "/api/automations",
        json={"kind": "security_review", "interval_hours": 24, "enabled": True},
    )
    assert result.status_code == 200, result.text
    item_id = result.json()["id"]
    assert analyst.get("/api/automations").status_code == 403
    other = customer.post(
        "/api/auth/register",
        json={
            "name": "Other Tenant",
            "email": "workflow-other@example.test",
            "password": "DifferentPass!2026",
        },
    )
    assert other.status_code == 201
    customer.headers["X-CSRF-Token"] = other.json()["csrf_token"]
    assert customer.post(f"/api/automations/{item_id}/run").status_code == 404
    assert customer.delete(f"/api/automations/{item_id}").status_code == 404
    customer.headers.pop("X-CSRF-Token")
    assert (
        customer.put("/api/automations", json={"kind": "security_review"}).status_code
        == 403
    )


def test_automation_input_and_operations_role_boundaries(customer, analyst):
    for payload in [
        {"kind": "transfer_money"},
        {"kind": "security_review", "interval_hours": 0},
        {"kind": "security_review", "interval_hours": True},
    ]:
        assert customer.put("/api/automations", json=payload).status_code == 422
    assert customer.get("/api/analyst/operations").status_code == 403
    result = analyst.get("/api/analyst/operations")
    assert result.status_code == 200
    assert result.json()["reconciliation"]["ok"]


def test_specialized_run_preserves_financial_summary(db_factory):
    with db_factory() as db:
        p.enqueue_health_check(db, user(db), "manual_refresh", "first-health")
        db.commit()
    assert p.process_next(db_factory)
    with db_factory() as db:
        original = p.list_insights(db, user(db))["summary"]
        item = a.save(db, user(db), "security_review")
        a.queue(db, user(db), item)
        db.commit()
    assert p.process_next(db_factory)
    with db_factory() as db:
        assert p.list_insights(db, user(db))["summary"] == original
        assert original["income"] == "95000.00"
