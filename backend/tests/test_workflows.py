from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import hashlib
import io
from datetime import timedelta
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, func, text, update
from sqlalchemy.exc import DatabaseError
import pytest
from app.main import app
from app.models import Account, LedgerEntry, Transfer, AuthSession, utcnow, AuditLog


def payload(client, amount="100.00", key="unique-key-123"):
    b = client.get("/api/beneficiaries").json()[0]
    return {
        "beneficiary_id": b["id"],
        "amount": amount,
        "description": "Test transfer",
        "idempotency_key": key,
    }


def balance(client):
    return Decimal(client.get("/api/overview").json()["account"]["balance"])


def image():
    out = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(out, format="PNG")
    return out.getvalue()


def kyc(client, **fields):
    defaults = {
        "full_name": "Satyam Sahu",
        "date_of_birth": "1995-06-15",
        "id_number": "ID1234567",
        "country": "IN",
    }
    defaults.update(fields)
    return client.post(
        "/api/kyc",
        data=defaults,
        files={
            "document": ("id.png", image(), "image/png"),
            "selfie": ("selfie.png", image(), "image/png"),
        },
    )


def test_authentication_csrf_and_roles(client, customer, analyst):
    assert customer.get("/api/overview").status_code == 200
    assert customer.get("/api/analyst/cases").status_code == 403
    assert analyst.get("/api/overview").status_code == 403
    customer.headers.pop("X-CSRF-Token")
    assert customer.post("/api/transfers", json=payload(customer)).status_code == 403
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "customer@aegis.demo", "password": "wrong"},
        ).status_code
        == 401
    )


def test_seed_balance_and_double_entry_conservation(customer, db_factory):
    assert balance(customer) == Decimal("225480.50")
    with db_factory() as db:
        assert sum(a.balance_paise for a in db.scalars(select(Account))) == 0
        rows = db.scalars(select(LedgerEntry)).all()
        assert (
            sum(
                e.amount_paise if e.direction == "credit" else -e.amount_paise
                for e in rows
            )
            == 0
        )


def test_atomic_transfer_and_idempotency(customer, db_factory):
    before = balance(customer)
    data = payload(customer, "125.45")
    r = customer.post("/api/transfers", json=data)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "posted"
    assert customer.post("/api/transfers", json=data).json()["id"] == r.json()["id"]
    assert balance(customer) == before - Decimal("125.45")
    assert (
        customer.post("/api/transfers", json=data | {"amount": "126.00"}).status_code
        == 409
    )
    with db_factory() as db:
        assert sum(a.balance_paise for a in db.scalars(select(Account))) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(LedgerEntry)
                .where(LedgerEntry.transfer_id == r.json()["id"])
            )
            == 2
        )


@pytest.mark.parametrize("amount", ["0", "-1", "0.001", "100000001"])
def test_invalid_amounts(customer, amount):
    assert (
        customer.post("/api/transfers", json=payload(customer, amount)).status_code
        == 422
    )


def test_no_overdraft_or_unowned_beneficiary(customer):
    assert (
        customer.post("/api/transfers", json=payload(customer, "225481")).status_code
        == 409
    )
    assert (
        customer.post(
            "/api/transfers", json=payload(customer) | {"beneficiary_id": "missing"}
        ).status_code
        == 404
    )


def test_step_up_and_context_escalation(customer):
    before = balance(customer)
    result = customer.post("/api/transfers", json=payload(customer, "30000")).json()
    assert result["status"] == "pending_step_up", result
    assert balance(customer) == before
    assert (
        customer.post(
            f"/api/transfers/{result['id']}/step-up", json={"password": "wrong"}
        ).status_code
        == 401
    )
    done = customer.post(
        f"/api/transfers/{result['id']}/step-up", json={"password": "AegisDemo!2026"}
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "posted"
    assert balance(customer) == before - Decimal("30000")
    assert (
        customer.post(
            f"/api/transfers/{result['id']}/step-up",
            json={"password": "AegisDemo!2026"},
        ).json()["status"]
        == "posted"
    )
    assert balance(customer) == before - Decimal("30000")


def test_new_context_cannot_bypass_step_up(customer):
    result = customer.post("/api/transfers", json=payload(customer, "30000")).json()
    before = balance(customer)
    assert (
        customer.post(
            "/api/simulator/events", json={"scenario": "impossible_travel"}
        ).json()["event"]["risk_score"]
        >= 70
    )
    done = customer.post(
        f"/api/transfers/{result['id']}/step-up", json={"password": "AegisDemo!2026"}
    )
    assert done.json()["status"] == "held", done.text
    assert balance(customer) == before


def test_held_approval_and_double_resolution(customer, analyst):
    before = balance(customer)
    result = customer.post("/api/transfers", json=payload(customer, "125000")).json()
    assert result["status"] == "held", result
    assert balance(customer) == before
    detail = analyst.get(f"/api/analyst/cases/{result['case_id']}").json()
    assert detail["account"]["balance"] == str(before)
    approved = analyst.post(
        f"/api/analyst/cases/{result['case_id']}/resolve",
        json={
            "decision": "approve",
            "reason": "Customer verified with branch evidence",
        },
    )
    assert approved.status_code == 200, approved.text
    assert balance(customer) == before - Decimal("125000")
    assert (
        analyst.post(
            f"/api/analyst/cases/{result['case_id']}/resolve",
            json={"decision": "approve", "reason": "Duplicate attempt"},
        ).status_code
        == 409
    )


def test_held_rejection_does_not_move_money(customer, analyst):
    before = balance(customer)
    result = customer.post("/api/transfers", json=payload(customer, "125000")).json()
    r = analyst.post(
        f"/api/analyst/cases/{result['case_id']}/resolve",
        json={"decision": "reject", "reason": "Customer denied activity"},
    )
    assert r.status_code == 200
    assert balance(customer) == before
    assert customer.get("/api/transactions").json()[0]["status"] == "rejected"


def test_freeze_and_approval_balance_recheck(customer, analyst):
    overview = customer.get("/api/overview").json()
    account_id = overview["account"]["id"]
    held = customer.post("/api/transfers", json=payload(customer, "125000")).json()
    assert (
        analyst.post(
            f"/api/analyst/accounts/{account_id}/status",
            json={"status": "frozen", "reason": "Potential account takeover"},
        ).status_code
        == 200
    )
    assert customer.post("/api/transfers", json=payload(customer)).status_code == 409
    assert (
        analyst.post(
            f"/api/analyst/cases/{held['case_id']}/resolve",
            json={"decision": "approve", "reason": "Attempt while account frozen"},
        ).status_code
        == 409
    )
    assert (
        analyst.get(f"/api/analyst/cases/{held['case_id']}").json()["case"]["status"]
        == "open"
    )
    assert (
        analyst.post(
            f"/api/analyst/accounts/{account_id}/status",
            json={"status": "active", "reason": "Risk cleared after investigation"},
        ).status_code
        == 200
    )
    assert (
        analyst.post(
            f"/api/analyst/cases/{held['case_id']}/resolve",
            json={"decision": "approve", "reason": "Risk cleared after investigation"},
        ).status_code
        == 200
    )


def test_event_simulator_and_alert_response(customer, analyst):
    result = customer.post(
        "/api/simulator/events", json={"scenario": "impossible_travel"}
    ).json()
    assert result["case"]["status"] == "open"
    assert any(s["name"] == "impossible_travel" for s in result["event"]["signals"])
    customer.post("/api/simulator/events", json={"scenario": "routine_login"})
    transfer = customer.post("/api/transfers", json=payload(customer)).json()
    assert (
        transfer["status"] == "held"
    )  # Routine login cannot erase active high-risk evidence.
    alert = customer.get("/api/overview").json()["alerts"][0]
    assert (
        customer.post(
            f"/api/alerts/{alert['id']}/respond", json={"recognized": False}
        ).status_code
        == 200
    )
    assert customer.get("/api/overview").json()["account"]["status"] == "frozen"
    assert (
        customer.post(
            f"/api/alerts/{alert['id']}/respond", json={"recognized": True}
        ).status_code
        == 409
    )


def test_velocity_burst_is_governed(customer):
    before = balance(customer)
    result = customer.post("/api/simulator/events", json={"scenario": "velocity_burst"})
    assert result.status_code == 200, result.text
    assert result.json()["transfer"]["status"] == "held"
    assert result.json()["case"]["kind"] == "transfer"
    assert balance(customer) == before - Decimal(
        "300"
    )  # Three low-risk attempts settled; later attempts gated.


def test_kyc_approved_and_review(customer, analyst):
    response = kyc(customer)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "approved"
    response = kyc(customer, full_name="Different Name", country="GB")
    assert response.status_code == 201
    assert response.json()["status"] == "review"
    case = next(
        c
        for c in analyst.get("/api/analyst/cases").json()
        if c["kyc_id"] == response.json()["id"]
    )
    assert (
        analyst.post(
            f"/api/analyst/cases/{case['id']}/resolve",
            json={"decision": "reject", "reason": "Identity mismatch not resolved"},
        ).status_code
        == 200
    )
    assert customer.get("/api/kyc").json()["status"] == "rejected"


def test_kyc_rejects_invalid_images(customer):
    r = customer.post(
        "/api/kyc",
        data={
            "full_name": "Satyam Sahu",
            "date_of_birth": "1995-06-15",
            "id_number": "ID1234567",
            "country": "IN",
        },
        files={
            "document": ("id.png", b"fake", "image/png"),
            "selfie": ("selfie.png", image(), "image/png"),
        },
    )
    assert r.status_code == 422


def test_kyc_requires_analyst_for_sanctions_fixture(customer):
    r = kyc(customer, id_number="TESTBLOCK123")
    assert r.json()["status"] == "review" and r.json()["risk_score"] >= 70


def test_budgets_documents_chat_and_audit(customer):
    budget = customer.put("/api/budgets/groceries", json={"limit_amount": "22000"})
    assert budget.status_code == 200
    assert budget.json()["limit_amount"] == "22000.00"
    upload = customer.post(
        "/api/documents",
        data={"title": "Private Loan Note"},
        files={
            "file": (
                "terms.txt",
                b"Loan repayment deadline is 15 November. Cooling off is 14 days.",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    answer = customer.post(
        "/api/documents/query",
        json={
            "question": "What is the repayment deadline?",
            "document_id": upload.json()["id"],
        },
    )
    assert answer.status_code == 200 and answer.json()["citations"], answer.text
    chat = customer.post("/api/chat", json={"message": "Show my balance"})
    assert chat.status_code == 200, chat.text
    assert chat.json()["tools"] and chat.json()["trace_id"]
    history = customer.get("/api/chat").json()
    assert [x["role"] for x in history] == ["user", "assistant"]
    audit = customer.get("/api/audit").json()
    assert any(x["action"] == "document_indexed" for x in audit)
    assert all(x["trace_id"] and isinstance(x["tools"], list) for x in audit)


def test_recommendations_and_zero_rate_emi(customer):
    r = customer.get("/api/recommendations")
    assert r.status_code == 200
    assert len(r.json()["loans"]) == 3 and len(r.json()["insurance"]) == 2
    emi = customer.post(
        "/api/recommendations/calculate",
        json={"principal": "12000", "annual_rate": "0", "tenure_months": 12},
    )
    assert emi.status_code == 200
    assert emi.json()["emi"] == "1000.00"
    assert emi.json()["total_interest"] == "0.00"


def test_registration_zero_balance_and_scoped_access(client):
    r = client.post(
        "/api/auth/register",
        json={
            "name": "Other Customer",
            "email": "other@example.test",
            "password": "SafePassword!2026",
        },
    )
    assert r.status_code == 201, r.text
    client.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    assert balance(client) == 0
    assert client.get("/api/beneficiaries").json() == []
    assert client.get("/api/analyst/customers").status_code == 403
    docs = client.get("/api/documents").json()
    assert all(d["kind"] == "policy" for d in docs)


def test_logout_revocation_and_expiry(customer, db_factory):
    cookie = customer.cookies.get("aegis_session")
    assert customer.post("/api/auth/logout").status_code == 200
    customer.cookies.set("aegis_session", cookie, domain="testserver.local", path="/")
    assert customer.get("/api/auth/me").status_code == 401
    login = customer.post(
        "/api/auth/login",
        json={"email": "customer@aegis.demo", "password": "AegisDemo!2026"},
    )
    assert login.status_code == 200
    token = customer.cookies.get("aegis_session")
    with db_factory() as db:
        session = db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest())
        session.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert customer.get("/api/auth/me").status_code == 401


def test_origin_and_failed_login_throttle(client):
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "customer@aegis.demo", "password": "AegisDemo!2026"},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    for _ in range(8):
        assert (
            client.post(
                "/api/auth/login",
                json={"email": "customer@aegis.demo", "password": "wrong"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "customer@aegis.demo", "password": "AegisDemo!2026"},
        ).status_code
        == 429
    )


def test_append_only_database_evidence(customer, db_factory):
    with db_factory() as db:
        with pytest.raises(DatabaseError):
            db.execute(text("UPDATE audit_logs SET summary='tampered'"))
            db.commit()
        db.rollback()
        with pytest.raises(DatabaseError):
            db.execute(text("DELETE FROM ledger_entries"))
            db.commit()


def test_concurrent_replay_has_one_atomic_debit(customer, db_factory):
    before = balance(customer)
    data = payload(customer, "555.55")
    cookie = customer.cookies.get("aegis_session")
    csrf = customer.headers["X-CSRF-Token"]

    def transfer_once(_):
        with TestClient(app) as worker:
            worker.cookies.set(
                "aegis_session", cookie, domain="testserver.local", path="/"
            )
            return worker.post(
                "/api/transfers", json=data, headers={"X-CSRF-Token": csrf}
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(transfer_once, range(4)))
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    assert len({r.json()["id"] for r in responses}) == 1
    assert balance(customer) == before - Decimal("555.55")
    with db_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Transfer)
                .where(Transfer.idempotency_key == data["idempotency_key"])
            )
            == 1
        )
        assert sum(a.balance_paise for a in db.scalars(select(Account))) == 0


def test_approval_overdraft_rechecks_and_preserves_pending_case(customer, analyst):
    first = customer.post(
        "/api/transfers", json=payload(customer, "125000", "first-held-key")
    ).json()
    second = customer.post(
        "/api/transfers", json=payload(customer, "125000", "second-held-key")
    ).json()
    assert first["status"] == second["status"] == "held"
    assert (
        analyst.post(
            f"/api/analyst/cases/{first['case_id']}/resolve",
            json={"decision": "approve", "reason": "First transfer verified securely"},
        ).status_code
        == 200
    )
    remaining = balance(customer)
    assert (
        analyst.post(
            f"/api/analyst/cases/{second['case_id']}/resolve",
            json={"decision": "approve", "reason": "Second transfer verified securely"},
        ).status_code
        == 409
    )
    assert balance(customer) == remaining
    assert (
        analyst.get(f"/api/analyst/cases/{second['case_id']}").json()["case"]["status"]
        == "open"
    )


def test_audit_masks_identifiers_and_secret_assignments(customer, analyst):
    account_id = customer.get("/api/overview").json()["account"]["id"]
    reason = "Satyam Sahu email customer@example.com identity123456789012 password=DoNotLogThis"
    assert (
        analyst.post(
            f"/api/analyst/accounts/{account_id}/status",
            json={"status": "frozen", "reason": reason},
        ).status_code
        == 200
    )
    summaries = " ".join(x["summary"] for x in analyst.get("/api/analyst/audit").json())
    assert "customer@example.com" not in summaries
    assert "DoNotLogThis" not in summaries
    assert "Satyam Sahu" not in summaries


def test_health_contract(customer):
    response = customer.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok" and response.json()["demo_enabled"] is True
