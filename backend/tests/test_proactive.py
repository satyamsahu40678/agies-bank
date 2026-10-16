from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import time

import pytest
from fastapi import HTTPException
from app.query import func, select, update

from app.models import (
    Account,
    AgentRun,
    AuditLog,
    FinancialInsight,
    LedgerEntry,
    SavingsGoal,
    User,
    utcnow,
)
from app.services import proactive as p
from app.services import firestore_notifications as firestore


def customer_user(db):
    return db.scalar(select(User).where(User.email == "customer@aegis.demo"))


def second_customer(db):
    user = User(
        name="Other Customer",
        email="other@test.example",
        password_hash="not-a-login-hash",
        role="customer",
    )
    db.add(user)
    db.flush()
    db.add(
        Account(
            user_id=user.id,
            number="AEGIS_SECOND",
            balance_paise=0,
            status="active",
            kyc_status="not_started",
        )
    )
    db.flush()
    return user


def test_goals_record_plans_without_moving_money(db_factory):
    with db_factory() as db:
        user = customer_user(db)
        balances = [
            (a.id, a.balance_paise)
            for a in db.scalars(select(Account).order_by(Account.id))
        ]
        count = db.scalar(select(func.count()).select_from(LedgerEntry))
        goal = p.create_goal(
            db,
            user,
            {
                "name": "Emergency savings",
                "target_amount": "100000.01",
                "saved_amount": "1200.01",
                "target_date": (date.today() + timedelta(days=90)).isoformat(),
            },
        )
        assert goal["target_amount"] == "100000.01"
        assert goal["saved_amount"] == "1200.01"
        assert goal["monthly_contribution"] == "32933.34"
        assert goal["planning_only"] is True
        db.commit()
        changed = p.update_goal(db, user, goal["id"], {"saved_amount": "100000.01"})
        assert changed["status"] == "completed"
        assert changed["progress_percent"] == 100
        assert changed["monthly_contribution"] == "0.00"
        assert balances == [
            (a.id, a.balance_paise)
            for a in db.scalars(select(Account).order_by(Account.id))
        ]
        assert count == db.scalar(select(func.count()).select_from(LedgerEntry))
        assert p.delete_goal(db, user, goal["id"]) == {"deleted": True}
        db.commit()
        assert p.list_goals(db, user) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Bad", "target_amount": "0"},
        {"name": "Bad", "target_amount": "1.001"},
        {"name": "Bad", "target_amount": "100", "saved_amount": "100.01"},
        {"name": "Bad", "target_amount": "100", "target_date": "2020-01-01"},
        {"name": "Bad", "target_amount": "100", "status": "completed"},
        {"name": "\x00", "target_amount": "100"},
        {"name": "Bad", "target_amount": "NaN"},
        {"name": "Bad", "target_amount": "100", "user_id": "different-tenant"},
    ],
)
def test_goal_validation(db_factory, payload):
    with db_factory() as db:
        with pytest.raises(HTTPException) as exc:
            p.create_goal(db, customer_user(db), payload)
        assert exc.value.status_code == 422
        assert db.scalar(select(func.count()).select_from(SavingsGoal)) == 0


def test_tenant_and_role_isolation(db_factory):
    with db_factory() as db:
        user = customer_user(db)
        other = second_customer(db)
        analyst = db.scalar(select(User).where(User.role == "analyst"))
        goal = p.create_goal(db, user, {"name": "Private", "target_amount": "100"})
        run = p.enqueue_health_check(db, user, "transfer", "private-transfer")
        db.commit()
        assert p.list_goals(db, other) == []
        assert p.list_runs(db, other) == []
        for operation in [
            lambda: p.update_goal(db, other, goal["id"], {"name": "Hijacked"}),
            lambda: p.delete_goal(db, other, goal["id"]),
            lambda: p.retry_run(db, other, run.id),
        ]:
            with pytest.raises(HTTPException) as exc:
                operation()
            assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            p.enqueue_health_check(db, analyst, "login")
        assert exc.value.status_code == 403
        p.enqueue_health_check(db, other, "login")
        db.commit()
    # Drain all staged work and ensure insights remain scoped.
    while p.process_next(db_factory):
        pass
    with db_factory() as db:
        user, other = (
            customer_user(db),
            db.scalar(select(User).where(User.email == "other@test.example")),
        )
        items = p.list_insights(db, user)["items"]
        assert items
        with pytest.raises(HTTPException) as exc:
            p.dismiss_insight(db, other, items[0]["id"])
        assert exc.value.status_code == 404
        assert all(
            "Private" not in row["message"]
            for row in p.list_insights(db, other)["items"]
        )


def test_enqueue_deduplicates_and_stale_reads_reuse_fresh_completed_run(db_factory):
    with db_factory() as db:
        user = customer_user(db)
        first = p.enqueue_health_check(db, user, "transfer", "transfer-123")
        again = p.enqueue_health_check(db, user, "transfer", "transfer-123")
        assert first.id == again.id
        assert (
            p.enqueue_health_check(db, user, "overview", stale_only=True).id == first.id
        )
        db.commit()
    assert p.process_next(db_factory)
    with db_factory() as db:
        user = customer_user(db)
        assert p.enqueue_health_check(db, user, "login", stale_only=True).id == first.id
        assert db.scalar(select(func.count()).select_from(AgentRun)) == 1
        result = p.list_insights(db, user)
        assert result["latest_run"]["status"] == "completed"
        assert result["latest_run"]["tools"] == list(p.TOOLS)
        assert result["summary"]["income"] == "95000.00"
        assert result["summary"]["expenses"] == "49519.50"
        assert result["summary"]["net_cashflow"] == "45480.50"
        assert result["summary"]["monthly_emi_capacity"] == "15918.17"
        assert all("No money" not in row["title"] for row in result["items"])


def test_firestore_notifications_are_post_commit_and_customer_ids_are_hashed(
    db_factory, monkeypatch
):
    monkeypatch.setenv("FIRESTORE_AGENT_NOTIFICATIONS", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    writes = []

    def firestore_request(path, payload):
        writes.append((path, payload))
        return {}

    monkeypatch.setattr(firestore, "_request", firestore_request)
    with db_factory() as db:
        user = customer_user(db)
        raw_user_id = user.id
        run = p.enqueue_health_check(db, user, "login", "firestore-projection-test")
        run_id = run.id
        db.commit()

    assert p.process_next(db_factory)
    assert writes and writes[0][0] == ":commit"
    serialized = str(writes[0][1])
    assert raw_user_id not in serialized
    assert "/agent_notifications/" in serialized
    with db_factory() as db:
        completed = db.get(AgentRun, run_id)
        assert completed.status == "completed"


def test_firestore_projection_failure_does_not_fail_completed_agent_run(
    db_factory, monkeypatch
):
    monkeypatch.setenv("FIRESTORE_AGENT_NOTIFICATIONS", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setattr(
        firestore,
        "_request",
        lambda *_: (_ for _ in ()).throw(RuntimeError("private failure text")),
    )
    with db_factory() as db:
        run = p.enqueue_health_check(db, customer_user(db), "login", "firestore-failure-test")
        run_id = run.id
        db.commit()
    assert p.process_next(db_factory)
    with db_factory() as db:
        completed = db.get(AgentRun, run_id)
        assert completed.status == "completed"
        assert completed.error is None


def test_concurrent_claims_never_duplicate_or_parallelize_one_customer(db_factory):
    with db_factory() as db:
        user = customer_user(db)
        for key in ["a", "b", "c"]:
            p.enqueue_health_check(db, user, "transfer", key)
        db.commit()

    def claim():
        with db_factory() as db:
            run = p.claim_next_run(db)
            db.commit()
            return run.id if run else None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: claim(), range(4)))
    claimed = [value for value in results if value]
    assert len(claimed) == 1
    with db_factory() as db:
        run = db.get(AgentRun, claimed[0])
        assert run.attempts == 1
        assert run.status == "running"
        assert run.lease_token
        assert p.claim_next_run(db) is None


def test_expired_lease_is_recovered_and_last_attempt_becomes_failed(db_factory):
    with db_factory() as db:
        user = customer_user(db)
        run = p.enqueue_health_check(db, user, "login")
        db.commit()
        first = p.claim_next_run(db)
        first_token = first.lease_token
        db.commit()
        db.execute(
            update(AgentRun)
            .where(AgentRun.id == run.id)
            .values(lease_expires_at=utcnow() - timedelta(seconds=1))
        )
        db.commit()
        second = p.claim_next_run(db)
        assert second.id == first.id
        assert second.attempts == 2
        assert second.lease_token != first_token
        db.commit()
        with pytest.raises(p.LostLease):
            p._execute(db, run.id, first_token)
        db.rollback()
        db.execute(
            update(AgentRun)
            .where(AgentRun.id == run.id)
            .values(attempts=3, lease_expires_at=utcnow() - timedelta(seconds=1))
        )
        db.commit()
        assert p.claim_next_run(db) is None
        db.commit()
        db.expire_all()
        assert db.get(AgentRun, run.id).status == "failed"


def test_worker_failure_rolls_back_outputs_and_retries_are_bounded(
    db_factory, monkeypatch
):
    with db_factory() as db:
        run = p.enqueue_health_check(db, customer_user(db), "login")
        db.commit()

    def fail(db, user, run):
        db.add(
            FinancialInsight(
                user_id=user.id,
                run_id=run.id,
                kind="bad",
                key="bad",
                fingerprint="bad",
                severity="info",
                title="Bad",
                message="Bad",
                action_label="Bad",
                action_path="/dashboard",
            )
        )
        raise ValueError("token=TOP_SECRET customer data must never leak")

    monkeypatch.setattr(p, "_health_plan", fail)
    for attempt in range(3):
        assert p.process_next(db_factory)
        with db_factory() as db:
            stored = db.get(AgentRun, run.id)
            assert stored.attempts == attempt + 1
            assert stored.status == ("failed" if attempt == 2 else "queued")
            assert "TOP_SECRET" not in stored.error
            assert db.scalar(select(func.count()).select_from(FinancialInsight)) == 0
            stored.available_at = utcnow() - timedelta(seconds=1)
            db.commit()
    assert not p.process_next(db_factory)
    with db_factory() as db:
        user = customer_user(db)
        retried = p.retry_run(db, user, run.id)
        assert retried["status"] == "queued"
        assert retried["attempts"] == 0
        with pytest.raises(HTTPException) as exc:
            p.retry_run(db, user, run.id)
        assert exc.value.status_code == 409
        db.commit()


def test_budget_recurring_and_goal_insights_use_real_ledger_and_preserve_financial_state(
    db_factory,
):
    with db_factory() as db:
        user = customer_user(db)
        account = db.scalar(select(Account).where(Account.user_id == user.id))
        from app.models import Budget

        budget = db.scalar(
            select(Budget).where(
                Budget.user_id == user.id, Budget.category == "groceries"
            )
        )
        budget.limit_paise = 1000000
        for days in (62, 32, 2):
            db.add(
                LedgerEntry(
                    account_id=account.id,
                    amount_paise=49900,
                    direction="debit",
                    description="Cloud Music Subscription",
                    category="subscriptions",
                    balance_after_paise=account.balance_paise,
                    created_at=utcnow() - timedelta(days=days),
                )
            )
        p.create_goal(
            db,
            user,
            {
                "name": "Trip",
                "target_amount": "900000",
                "target_date": (date.today() + timedelta(days=30)).isoformat(),
            },
        )
        balance = account.balance_paise
        ledger_count = db.scalar(select(func.count()).select_from(LedgerEntry))
        db.commit()
    assert p.process_next(db_factory)
    with db_factory() as db:
        user = customer_user(db)
        result = p.list_insights(db, user)
        budget = next(
            row
            for row in result["items"]
            if row["kind"] == "budget" and row["metrics"]["category"] == "groceries"
        )
        assert budget["severity"] == "critical"
        assert budget["metrics"]["spent"] == "14820.50"
        recurring = next(row for row in result["items"] if row["kind"] == "recurring")
        assert recurring["metrics"]["cadence"] == "monthly"
        assert recurring["metrics"]["amount"] == "499.00"
        goal = next(row for row in result["items"] if row["kind"] == "goal")
        assert goal["metrics"]["affordable"] is False
        assert goal["severity"] == "warning"
        assert (
            db.scalar(select(Account).where(Account.user_id == user.id)).balance_paise
            == balance
        )
        assert db.scalar(select(func.count()).select_from(LedgerEntry)) == ledger_count
        audit_rows = db.scalars(
            select(AuditLog).where(
                AuditLog.trace_id == result["latest_run"]["trace_id"]
            )
        ).all()
        assert set(tool for row in audit_rows for tool in row.tools) == set(p.TOOLS)


def test_dismissal_survives_unchanged_refresh_and_resolves_removed_conditions(
    db_factory,
):
    with db_factory() as db:
        user = customer_user(db)
        p.enqueue_health_check(db, user, "login", "initial")
        db.commit()
    p.process_next(db_factory)
    with db_factory() as db:
        user = customer_user(db)
        insight = db.scalar(
            select(FinancialInsight).where(
                FinancialInsight.user_id == user.id, FinancialInsight.kind == "cashflow"
            )
        )
        p.dismiss_insight(db, user, insight.id)
        p.enqueue_health_check(db, user, "transfer", "unchanged")
        db.commit()
    p.process_next(db_factory)
    with db_factory() as db:
        assert db.get(FinancialInsight, insight.id).status == "dismissed"
        from app.models import Budget

        db.scalar(
            select(Budget).where(Budget.category == "housing")
        ).limit_paise = 4000000
        p.enqueue_health_check(db, customer_user(db), "budget_changed", "revised")
        db.commit()
    p.process_next(db_factory)
    with db_factory() as db:
        housing = db.scalar(
            select(FinancialInsight).where(
                FinancialInsight.kind == "budget", FinancialInsight.key == "housing"
            )
        )
        assert housing.status == "resolved"


def test_worker_lifecycle_is_interruptible(db_factory):
    worker = p.start_worker(db_factory, poll_seconds=30)
    time.sleep(0.02)
    started = time.monotonic()
    worker.stop(timeout=2)
    assert not worker.thread.is_alive()
    assert time.monotonic() - started < 2


def test_refresh_starts_a_new_run_after_completion_and_coalesces_pending(db_factory):
    with db_factory() as db:
        user = customer_user(db)
        first = p.refresh_insights(db, user)
        assert p.refresh_insights(db, user)["id"] == first["id"]
        db.commit()
    assert p.process_next(db_factory)
    with db_factory() as db:
        second = p.refresh_insights(db, customer_user(db))
        assert second["id"] != first["id"]
        assert second["status"] == "queued"
        assert p.refresh_insights(db, customer_user(db))["id"] == second["id"]
        db.commit()


def test_pending_queue_is_bounded_per_customer(db_factory):
    with db_factory() as db:
        user = customer_user(db)
        for number in range(105):
            p.enqueue_health_check(db, user, "transfer", f"event-{number}")
        db.commit()
        assert (
            db.scalar(
                select(func.count())
                .select_from(AgentRun)
                .where(AgentRun.user_id == user.id)
            )
            == 100
        )


def test_http_goals_crud_keeps_ledger_and_balances_unchanged(customer, db_factory):
    with db_factory() as db:
        balances = [
            (account.id, account.balance_paise)
            for account in db.scalars(select(Account).order_by(Account.id))
        ]
        ledger_count = db.scalar(select(func.count()).select_from(LedgerEntry))
    response = customer.post(
        "/api/goals",
        json={
            "name": "Home deposit",
            "target_amount": "150000.75",
            "saved_amount": "12500.50",
        },
    )
    assert response.status_code == 201, response.text
    goal = response.json()
    assert goal["planning_only"] is True
    assert goal["saved_amount"] == "12500.50"
    listing = customer.get("/api/goals")
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == goal["id"]
    changed = customer.patch(
        "/api/goals/" + goal["id"], json={"saved_amount": "150000.75"}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["status"] == "completed"
    # Customers can correct their own planning record after completion.
    reopened = customer.patch(
        "/api/goals/" + goal["id"], json={"saved_amount": "12500.50"}
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "active"
    malformed = customer.patch(
        "/api/goals/" + goal["id"], json={"saved_amount": "150001"}
    )
    assert malformed.status_code == 422
    assert customer.delete("/api/goals/" + goal["id"]).json() == {"deleted": True}
    assert customer.get("/api/goals").json() == []
    with db_factory() as db:
        assert balances == [
            (account.id, account.balance_paise)
            for account in db.scalars(select(Account).order_by(Account.id))
        ]
        assert ledger_count == db.scalar(select(func.count()).select_from(LedgerEntry))


def test_http_financial_review_runs_in_background_and_supports_dismissal(customer):
    response = customer.post("/api/insights/refresh")
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        runs = customer.get("/api/agent-runs").json()
        run = next(row for row in runs if row["id"] == run_id)
        if run["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert run["status"] == "completed", run
    assert run["tools"] == list(p.TOOLS)
    assert len(run["decisions"]) == 3
    assert len(run["trace_id"]) == 32
    insights = customer.get("/api/insights")
    assert insights.status_code == 200, insights.text
    body = insights.json()
    assert body["summary"]["income"] == "95000.00"
    assert body["items"]
    item = body["items"][0]
    dismissed = customer.post(f"/api/insights/{item['id']}/dismiss")
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"
    assert item["id"] not in [
        row["id"] for row in customer.get("/api/insights").json()["items"]
    ]
    fresh = customer.post("/api/insights/refresh")
    assert fresh.status_code == 202
    assert fresh.json()["id"] != run_id


def test_http_other_customer_cannot_read_or_change_goals_insights_or_runs(
    customer, db_factory
):
    from fastapi.testclient import TestClient
    from app.main import app

    # Stop asynchronous execution while preparing a failed run for precise authorization checks.
    app.state.proactive_worker.stop()
    goal = customer.post(
        "/api/goals", json={"name": "Private goal", "target_amount": "1000"}
    ).json()
    with db_factory() as db:
        user = customer_user(db)
        run = p.enqueue_health_check(db, user, "manual_refresh", "private")
        run.status = "failed"
        run.error = "Unavailable"
        db.add(
            FinancialInsight(
                user_id=user.id,
                run_id=run.id,
                kind="cashflow",
                key="private",
                fingerprint="private",
                severity="info",
                title="Private item",
                message="Owner guidance",
                action_label="Review",
                action_path="/dashboard",
            )
        )
        db.commit()
        insight = db.scalar(
            select(FinancialInsight).where(FinancialInsight.key == "private")
        )
    with TestClient(app) as other:
        # A separate lifespan would rebind startup; this app is still backed by the fixture database.
        registered = other.post(
            "/api/auth/register",
            json={
                "name": "Other Customer",
                "email": "isolated@test.example",
                "password": "AnotherPass!2026",
            },
        )
        assert registered.status_code == 201, registered.text
        other.headers["X-CSRF-Token"] = registered.json()["csrf_token"]
        assert other.get("/api/goals").json() == []
        assert all(row["id"] != run.id for row in other.get("/api/agent-runs").json())
        assert all(
            row["id"] != insight.id
            for row in other.get("/api/insights").json()["items"]
        )
        for response in [
            other.patch("/api/goals/" + goal["id"], json={"name": "Hijacked goal"}),
            other.delete("/api/goals/" + goal["id"]),
            other.post("/api/insights/" + insight.id + "/dismiss"),
            other.post("/api/agent-runs/" + run.id + "/retry"),
        ]:
            assert response.status_code == 404, response.text


def test_http_customer_routes_require_auth_role_and_csrf(client, analyst):
    routes = ["/api/insights", "/api/agent-runs", "/api/goals"]
    for route in routes:
        assert client.get(route).status_code == 401
        assert analyst.get(route).status_code == 403
    assert analyst.post("/api/insights/refresh").status_code == 403
    login = client.post(
        "/api/auth/login",
        json={"email": "customer@aegis.demo", "password": "AegisDemo!2026"},
    )
    assert login.status_code == 200
    assert client.post("/api/insights/refresh").status_code == 403
    assert (
        client.post(
            "/api/goals", json={"name": "No CSRF", "target_amount": "10"}
        ).status_code
        == 403
    )
    assert (
        client.patch("/api/goals/not-owned", json={"name": "No CSRF"}).status_code
        == 403
    )
    assert client.delete("/api/goals/not-owned").status_code == 403


def test_financial_totals_are_complete_even_when_recurring_history_is_capped(
    db_factory,
):
    with db_factory() as db:
        user = customer_user(db)
        account = db.scalar(select(Account).where(Account.user_id == user.id))
        now = utcnow()
        # A high-volume account places salary and housing beyond the recurring-history sample.
        # Seed high-volume history in bounded native Firestore transactions.
        # This fixture deliberately bypasses balance reconciliation; it tests exact totals.
        for start in range(0, 10000, 250):
            batch = {}
            for _ in range(start, start + 250):
                entry = LedgerEntry(account_id=account.id, amount_paise=1,
                    direction="debit", description="Daily small debit", category="other",
                    balance_after_paise=account.balance_paise, created_at=now - timedelta(hours=2))
                batch["ledger_entries/" + entry.id] = entry.to_dict()
            db.backend.commit({}, batch)
        db.add(
            LedgerEntry(
                account_id=account.id,
                amount_paise=1000000,
                direction="credit",
                description="Older posted income",
                category="salary",
                balance_after_paise=account.balance_paise,
                created_at=now - timedelta(days=29),
            )
        )
        p.enqueue_health_check(db, user, "manual_refresh", "full-history")
        db.commit()
    assert p.process_next(db_factory)
    with db_factory() as db:
        result = p.list_insights(db, customer_user(db))
        assert result["summary"]["income"] == "105000.00"
        assert result["summary"]["expenses"] == "49619.50"
        assert result["summary"]["net_cashflow"] == "55380.50"
        housing = next(
            row
            for row in result["items"]
            if row["kind"] == "budget" and row["metrics"]["category"] == "housing"
        )
        assert housing["metrics"]["spent"] == "28000.00"
        assert "10,000 entries" in result["summary"]["source"]
