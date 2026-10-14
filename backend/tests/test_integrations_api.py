from fastapi.testclient import TestClient
from app.main import app


def test_shared_policy_publication_requires_analyst_and_explicit_sharing(
    customer, analyst
):
    content = b"Public demo policy: travel cover begins after the stated waiting period. The evidence marker is CEDAR-831."
    files = {"file": ("public-policy.txt", content, "text/plain")}
    assert customer.get("/api/analyst/integrations").status_code == 403
    assert (
        customer.post(
            "/api/analyst/documents",
            data={"title": "Public policy", "confirmed_public": "true"},
            files=files,
        ).status_code
        == 403
    )
    assert (
        analyst.post(
            "/api/analyst/documents", data={"title": "Public policy"}, files=files
        ).status_code
        == 422
    )
    published = analyst.post(
        "/api/analyst/documents",
        data={"title": "Public travel policy", "confirmed_public": "true"},
        files=files,
    )
    assert published.status_code == 201, published.text
    doc_id = published.json()["id"]
    assert doc_id in [d["id"] for d in customer.get("/api/documents").json()]
    assert doc_id in [d["id"] for d in analyst.get("/api/analyst/documents").json()]
    sources = customer.get(f"/api/documents/{doc_id}/content")
    assert sources.status_code == 200
    assert any("CEDAR-831" in page["text"] for page in sources.json()["pages"])
    result = customer.post(
        "/api/documents/query",
        json={"question": "What is the evidence marker?", "document_id": doc_id},
    )
    assert result.status_code == 200
    assert any(c["document_id"] == doc_id for c in result.json()["citations"])


def test_private_source_passages_are_isolated(customer):
    result = customer.post(
        "/api/documents",
        files={
            "file": (
                "private.txt",
                b"Only this customer can read PALM-942.",
                "text/plain",
            )
        },
    )
    assert result.status_code == 201
    doc_id = result.json()["id"]
    assert customer.get(f"/api/documents/{doc_id}/content").status_code == 200
    with TestClient(app) as other:
        registration = other.post(
            "/api/auth/register",
            json={
                "name": "Other Source Reader",
                "email": "source-reader@example.test",
                "password": "ReaderPassword!2026",
            },
        )
        assert registration.status_code == 201
        assert other.get(f"/api/documents/{doc_id}/content").status_code == 404


def test_provider_metadata_and_checks_never_expose_credentials(analyst, monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "AEGIS_OPENAI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    metadata = analyst.get("/api/analyst/integrations")
    assert metadata.status_code == 200
    payload = metadata.json()
    assert payload["ai_mode"] == "local"
    assert any("Claude" in item["name"] for item in payload["providers"])
    assert any("OpenAI" in item["name"] for item in payload["providers"])
    assert any(
        item["mode"] == "mock_adapter" and not item["integrated"]
        for item in payload["providers"]
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "FAKE-PRIVATE-CREDENTIAL-FOR-REDACTION")
    assert (
        "FAKE-PRIVATE-CREDENTIAL-FOR-REDACTION"
        not in analyst.get("/api/analyst/integrations").text
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    for provider in ("claude", "openai"):
        result = analyst.post(f"/api/analyst/integrations/{provider}/check")
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "unconfigured"
        assert result.json()["configured"] is False


def test_budget_api_combines_category_variants(customer, db_factory):
    from sqlalchemy import select
    from app.models import Account, LedgerEntry, User

    with db_factory() as db:
        user = db.scalar(select(User).where(User.email == "customer@aegis.demo"))
        account = db.scalar(select(Account).where(Account.user_id == user.id))
        clearing = db.scalar(select(Account).where(Account.user_id.is_(None)))
        for category, amount in [("Education", 1200), (" education ", 800)]:
            account.balance_paise -= amount
            clearing.balance_paise += amount
            db.add_all(
                [
                    LedgerEntry(
                        account_id=account.id,
                        amount_paise=amount,
                        direction="debit",
                        description="Category aggregation fixture",
                        category=category,
                        balance_after_paise=account.balance_paise,
                    ),
                    LedgerEntry(
                        account_id=clearing.id,
                        amount_paise=amount,
                        direction="credit",
                        description="Category aggregation fixture",
                        category=category,
                        balance_after_paise=clearing.balance_paise,
                    ),
                ]
            )
        db.commit()
    result = customer.put("/api/budgets/education", json={"limit_amount": "100.00"})
    assert result.status_code == 200, result.text
    budget = next(
        b for b in customer.get("/api/budgets").json() if b["category"] == "education"
    )
    assert budget["spent"] == "20.00"
    categories = customer.get("/api/overview").json()["spending"]["categories"]
    assert (
        next(c for c in categories if c["category"] == "education")["amount"] == "20.00"
    )


def test_openai_kyc_disclosure_identifies_actual_evidence_destination(
    customer, monkeypatch
):
    monkeypatch.setenv("AEGIS_KYC_VISION", "openai")
    monkeypatch.setenv("AEGIS_OPENAI_API_KEY", "FAKE-TEST-ONLY-KEY")
    payload = customer.get("/api/kyc").json()
    assert "OpenAI" in payload["disclaimer"]
    assert "Local mode" not in payload["disclaimer"]
    assert "does not verify legal identity" in payload["disclaimer"]
