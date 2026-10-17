"""Analysis correctness, grounded sources and explicit goal-consent boundaries."""

from datetime import date, timedelta
import json
from types import SimpleNamespace
from urllib.parse import urlparse

import httpx
import pytest
from fastapi import HTTPException

from app.models import Account, LedgerEntry, SavingsGoal, User, utcnow
from app.query import func, select
from app.services import analysis, intelligence as ai, knowledge
from app.services.proactive import create_goal
from test_intelligence import intelligence_db


def entry(account_id, amount=100000, days=0, **kwargs):
    return LedgerEntry(account_id=account_id, amount_paise=amount, direction="debit", description="Demo streaming", category="Entertainment", status="posted", balance_after_paise=2000000, created_at=utcnow() - timedelta(days=days), **kwargs)


def test_cashflow_uses_complete_posted_tenant_window_and_labels_negative_estimates(intelligence_db):
    db, user, other, account, *_ = intelligence_db
    foreign = Account(user_id=other.id, number="OTHER-ANALYSIS", balance_paise=1000)
    db.add(foreign)
    for days, status in [(31, "posted"), (-1, "posted"), (1, "pending")]:
        row = entry(account.id, amount=99000000, days=days)
        row.status = status
        db.add(row)
    db.add(entry(foreign.id, amount=99000000))
    db.add_all([entry(account.id, amount=100001, days=1) for _ in range(105)])
    db.flush()
    result = analysis.cashflow(db, user)
    assert result["record_count"] == 107
    assert result["income"] == "80000.00"
    assert result["expenses"] == "125001.05"
    assert result["net_cashflow"] == "-45001.05"
    assert result["monthly_capacity"] == "0.00"
    assert result["projections"][0]["estimated_balance"] == "-25001.05"
    assert "overdraft" in result["assumptions"]
    assert account.balance_paise == 2000000


def test_recurring_requires_three_distinct_dates_and_consistent_amounts(intelligence_db):
    db, user, _, account, *_ = intelligence_db
    db.add_all([entry(account.id, amount=amount, days=days) for days, amount in [(65, 99000), (35, 100000), (5, 101000)]])
    for days in [65, 35, 5]:
        row = entry(account.id, amount=1000, days=days)
        row.description, row.category = "Rent transfer", "Transfer"
        db.add(row)
    for _ in range(5):
        row = entry(account.id, days=2)
        row.description = "Same day shopping"
        db.add(row)
    db.flush()
    result = analysis.recurring(db, user)
    assert len(result["patterns"]) == 1
    pattern = result["patterns"][0]
    assert pattern["merchant"] == "Demo streaming"
    assert pattern["cadence"] == "monthly"
    assert pattern["occurrences"] == 3
    assert pattern["typical_amount"] == result["estimated_monthly_total"] == "1000.00"
    assert "not confirmed" in result["assumptions"]


def test_goal_analysis_shares_one_surplus_across_goals(intelligence_db):
    db, user, *_ = intelligence_db
    for name in ["Emergency", "Education"]:
        create_goal(db, user, {"name": name, "target_amount": "80000.00", "target_date": (date.today() + timedelta(days=60)).isoformat()})
    result = analysis.goal_review(db, user)
    assert result["monthly_capacity"] == "60000.00"
    assert result["combined_monthly_contribution"] == "80000.00"
    assert result["monthly_shortfall"] == "20000.00"
    draft = analysis.draft_goal(db, user, {"name": "Holiday", "target_amount": 12000, "months": 12})
    assert draft["monthly_capacity"] == "0.00"
    assert draft["monthly_shortfall"] == "21000.00"


def test_chat_drafts_goal_without_creating_it_or_moving_money(intelligence_db):
    db, user, _, account, *_ = intelligence_db
    before = db.scalar(select(func.count()).select_from(LedgerEntry))
    result = ai.chat(db, user, "Create a goal for Emergency fund of INR 60000 in 12 months.")
    draft = result["goal_drafts"][0]
    assert draft["name"] == "Emergency Fund"
    assert draft["target_amount"] == "60000.00"
    assert draft["monthly_contribution"] == "5000.00"
    assert draft["requires_confirmation"] is True
    assert db.scalar(select(func.count()).select_from(SavingsGoal)) == 0
    assert before == db.scalar(select(func.count()).select_from(LedgerEntry))
    assert account.balance_paise == 2000000


def test_goal_confirmation_is_explicit_editable_and_retry_safe(customer, analyst):
    before = customer.get("/api/overview").json()["account"]["balance"]
    drafts = customer.post("/api/chat", json={"message": "Create a goal for Holiday of INR 12000 in 12 months."}).json()["goal_drafts"]
    assert customer.get("/api/goals").json() == []
    draft = drafts[0]
    payload = {"name": "Edited holiday plan", "target_amount": "18000.00", "saved_amount": "0.00", "target_date": draft["target_date"]}
    key = {"Idempotency-Key": draft["id"]}
    first = customer.post("/api/goals", json=payload, headers=key)
    second = customer.post("/api/goals", json=payload, headers=key)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(customer.get("/api/goals").json()) == 1
    assert customer.post("/api/goals", json={**payload, "target_amount": "19000"}, headers=key).status_code == 409
    assert analyst.post("/api/goals", json=payload, headers=key).status_code == 403
    assert customer.get("/api/overview").json()["account"]["balance"] == before
    customer.headers.pop("X-CSRF-Token")
    assert customer.post("/api/goals", json=payload, headers=key).status_code == 403


def test_analysis_and_knowledge_require_customer_and_never_expose_another_tenant(customer, analyst):
    result = customer.get("/api/analysis")
    assert result.status_code == 200
    assert result.json()["cashflow"]["income"] == "95000.00"
    guides = customer.get("/api/knowledge").json()
    assert len(guides) == 6
    for guide in guides:
        assert urlparse(guide["source_url"]).hostname in {"www.rbi.org.in", "rbikehtahai.rbi.org.in", "www.dicgc.org.in", "www.npci.org.in", "financialservices.gov.in"}
        assert guide["reviewed_at"] == "2026-10-17"
        assert customer.get("/api/knowledge/" + guide["id"]).json() == guide
        preview = customer.get("/api/documents/" + guide["id"] + "/content")
        assert preview.status_code == 200
        assert preview.json()["pages"][0]["text"] == guide["content"]
        assert preview.json()["document"]["source_url"] == guide["source_url"]
    for route in ["/api/analysis", "/api/knowledge", "/api/knowledge/guide-neft"]:
        assert analyst.get(route).status_code == 403
    assert customer.get("/api/knowledge/missing").status_code == 404
    other = customer.post("/api/auth/register", json={"name": "Analysis Tenant", "email": "analysis-other@example.test", "password": "DifferentPass!2026"})
    assert other.status_code == 201
    assert customer.get("/api/analysis").json()["cashflow"]["income"] == "0.00"


@pytest.mark.parametrize("name,args", [
    ("get_cashflow_forecast", {}), ("get_recurring_expenses", {}), ("get_goal_plan", {}),
    ("propose_savings_goal", {"name": "Future", "target_amount": 10000, "months": 12}),
    ("search_banking_guides", {"question": "What is NEFT?"}),
])
def test_new_capabilities_enforce_scope_and_role(intelligence_db, name, args):
    db, user, *_ = intelligence_db
    for context in [ai.ToolContext(db, user, "scope-check", frozenset()), ai.ToolContext(db, SimpleNamespace(id=user.id, role="analyst"), "role-check", ai.CUSTOMER_SCOPES)]:
        with pytest.raises(HTTPException) as error:
            ai.REGISTRY.invoke(name, context, args)
        assert error.value.status_code == 403


@pytest.mark.parametrize("values", [
    {"months": 0}, {"months": 601}, {"months": True}, {"target_amount": float("nan")},
    {"target_amount": -100}, {"target_amount": 1.005}, {"name": "\x00bad"},
])
def test_goal_draft_rejects_invalid_inputs(intelligence_db, values):
    db, user, *_ = intelligence_db
    context = ai.ToolContext(db, user, "validation", ai.CUSTOMER_SCOPES)
    with pytest.raises(HTTPException) as error:
        ai.REGISTRY.invoke("propose_savings_goal", context, {"name": "Holiday", "target_amount": 1000, "months": 12, **values})
    assert error.value.status_code == 422
    assert context.goal_drafts == []


def test_banking_guide_citations_have_exact_summary_and_primary_source(intelligence_db):
    db, user, *_ = intelligence_db
    context = ai.ToolContext(db, user, "knowledge", ai.CUSTOMER_SCOPES)
    result = ai.REGISTRY.invoke("search_banking_guides", context, {"question": "How does DICGC deposit insurance combine branches?"})
    assert result["citations"]
    for citation in result["citations"]:
        guide = knowledge.get_guide(citation["document_id"])
        assert citation["excerpt"] in guide["content"]
        assert citation["source_url"] == "https://www.dicgc.org.in/FAQs"
        assert citation["source_kind"] == "educational_summary"
    with pytest.raises(HTTPException) as error:
        ai._retrieve_documents(db, user, "insurance", "another-tenant-document")
    assert error.value.status_code == 404


def test_native_gemini_returns_server_validated_goal_card(intelligence_db, monkeypatch):
    db, user, _, account, *_ = intelligence_db
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    calls = []
    def handle(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert request.headers["x-goog-api-key"] == "synthetic-gemini-key"
        if len(calls) == 1:
            parts = [{"functionCall": {"name": "propose_savings_goal", "args": {"name": "Emergency fund", "target_amount": 60000, "months": 12}}, "thoughtSignature": "opaque-goal-continuation"}]
        else:
            assert payload["contents"][-1]["parts"][0]["functionResponse"]["response"]["result"]["goal_draft"]["monthly_contribution"] == "5000.00"
            parts = [{"text": "Your estimated contribution is INR 5000 per month. Review your draft."}]
        return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": parts}}]})
    client_type = httpx.Client
    monkeypatch.setattr(ai.httpx, "Client", lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs))
    result = ai.chat(db, user, "Plan INR 60000 in 12 months for an emergency goal.")
    assert result["ai_mode"] == "gemini"
    assert result["goal_drafts"][0]["requires_confirmation"]
    assert "No money is moved" in result["reply"]
    assert db.scalar(select(func.count()).select_from(SavingsGoal)) == 0
    assert account.balance_paise == 2000000
