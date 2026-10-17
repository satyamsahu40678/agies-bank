"""Provider activation, configuration safety and grounded AI behavior."""

import json
from types import SimpleNamespace

import httpx
from conftest import seed_records
import pytest
from fastapi import HTTPException
from app.query import func, select

from app import config
from app.models import Beneficiary, Document, DocumentChunk, LedgerEntry, Transfer
from app.services import intelligence as ai
from app.services import providers
from test_intelligence import intelligence_db


@pytest.fixture
def clean_provider_env(monkeypatch):
    for name in [
        "AEGIS_AI_MODE",
        "AEGIS_AI_PROVIDER",
        "AEGIS_KYC_VISION",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "AEGIS_OPENAI_API_KEY",
        "AEGIS_OPENAI_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_MODEL",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
    ]:
        monkeypatch.delenv(name, raising=False)
    providers._model_cache.clear()
    providers._openai_model_cache.clear()
    yield
    providers._model_cache.clear()
    providers._openai_model_cache.clear()


def test_dotenv_loads_only_supported_settings_and_injected_values_win(tmp_path):
    path = tmp_path / ".env"
    path.write_text("""# local settings
export ANTHROPIC_API_KEY="synthetic-local-key" # never displayed
ANTHROPIC_MODEL='claude-sonnet-test'
AEGIS_AI_MODE=auto # comment
AGIES_SECRET='literal-$HOME-$(ignored)'
DATABASE_URL=sqlite:///local.db
PATH=/hostile/bin
PYTHONPATH=/hostile
HTTPS_PROXY=http://untrusted
AEGIS_UNSUPPORTED=unexpected
""")
    environment = {"ANTHROPIC_API_KEY": "injected-key"}
    loaded = config.load_project_env(path, environment)
    assert environment["ANTHROPIC_API_KEY"] == "injected-key"
    assert environment["AEGIS_AI_MODE"] == "auto"
    assert environment["ANTHROPIC_MODEL"] == "claude-sonnet-test"
    assert environment["AGIES_SECRET"] == "literal-$HOME-$(ignored)"
    assert (
        not {"PATH", "PYTHONPATH", "HTTPS_PROXY", "AEGIS_UNSUPPORTED"}
        & environment.keys()
    )
    assert "ANTHROPIC_API_KEY" not in loaded
    assert loaded <= config.DOTENV_VARIABLES


def test_dotenv_invalid_quoting_does_not_expose_secret(tmp_path):
    path = tmp_path / ".env"
    secret = "synthetic-sensitive-value"
    path.write_text(f'ANTHROPIC_API_KEY="{secret}\n')
    with pytest.raises(RuntimeError) as error:
        config.load_project_env(path, {})
    assert "line 1" in str(error.value)
    assert secret not in str(error.value)


def test_auto_modes_activate_with_key_and_explicit_local_wins(
    clean_provider_env, monkeypatch
):
    assert config.resolve_ai_mode() == config.resolve_kyc_mode() == "local"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-test-key")
    assert config.resolve_ai_mode() == config.resolve_kyc_mode() == "claude"
    monkeypatch.setenv("AEGIS_AI_MODE", "local")
    assert config.resolve_ai_mode() == "local"
    assert config.resolve_kyc_mode() == "local"
    monkeypatch.setenv("AEGIS_KYC_VISION", "local")
    assert config.resolve_kyc_mode() == "local"
    monkeypatch.setenv("AEGIS_AI_MODE", "unsupported")
    with pytest.raises(RuntimeError, match="auto, local, claude, openai, gemini or openrouter"):
        config.resolve_ai_mode()


def test_openrouter_auto_selection_model_override_and_kyc_exclusion(
    clean_provider_env, monkeypatch
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-openrouter-key")
    assert config.resolve_ai_mode() == "openrouter"
    assert config.resolve_kyc_mode() == "local"
    assert providers.resolve_openrouter_model() == "openrouter/free"
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    assert providers.resolve_openrouter_model() == "openai/gpt-4o-mini"
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "local")
    assert config.resolve_ai_mode() == "local"
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("AEGIS_KYC_VISION", "openrouter")
    with pytest.raises(RuntimeError, match="does not support openrouter"):
        config.resolve_kyc_mode()
    monkeypatch.setenv("OPENROUTER_MODEL", "../invalid")
    with pytest.raises(HTTPException, match="OPENROUTER_MODEL"):
        providers.resolve_openrouter_model()


def test_openrouter_connection_check_uses_model_catalog_without_exposing_key(
    clean_provider_env, monkeypatch
):
    secret = "synthetic-openrouter-key"
    assert providers.check_openrouter()["status"] == "unconfigured"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/free")
    calls = []

    def handle(request):
        calls.append(request)
        assert request.method == "GET"
        assert request.url.path == "/api/v1/models"
        assert request.headers["Authorization"] == f"Bearer {secret}"
        return httpx.Response(200, json={"data": []})

    client_type = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(handle), **kwargs
        ),
    )
    result = providers.check_openrouter()
    assert result["status"] == "ok"
    assert result["model"] == "openrouter/free"
    assert len(calls) == 1
    assert secret not in str(result)


def test_gemini_key_auto_selection_model_discovery_and_check(clean_provider_env, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-gemini-key")
    assert config.resolve_ai_mode() == config.resolve_kyc_mode() == "gemini"
    requests = []

    def handle(request):
        requests.append(request)
        assert request.headers["x-goog-api-key"] == "synthetic-gemini-key"
        assert "key=" not in str(request.url)
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
                ]
            },
        )

    client_type = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    assert providers.resolve_gemini_model() == "gemini-2.5-flash"
    assert providers.resolve_gemini_model() == "gemini-2.5-flash"
    checked = providers.check_gemini()
    assert checked["status"] == "ok"
    assert checked["model"] == "gemini-2.5-flash"
    assert len(requests) == 2
    status = {item["id"]: item for item in providers.integration_status()["providers"]}
    assert status["gemini"]["status"] == "configured"
    assert status["gemini"]["mode"] == "gemini"
    assert "synthetic-gemini-key" not in str(status)


def test_gemini_model_override_and_unconfigured_check(clean_provider_env, monkeypatch):
    assert providers.check_gemini()["status"] == "unconfigured"
    monkeypatch.setenv("GEMINI_MODEL", "models/gemini-test")
    assert providers.resolve_gemini_model("synthetic-key") == "gemini-test"
    monkeypatch.setenv("GEMINI_MODEL", "../invalid")
    with pytest.raises(HTTPException, match="GEMINI_MODEL"):
        providers.resolve_gemini_model("synthetic-key")


def test_gemini_connection_check_verifies_explicit_model(clean_provider_env, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-explicit-test")
    requests = []

    def handle(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.path.endswith("/models/gemini-explicit-test")
        return httpx.Response(200, json={"name": "models/gemini-explicit-test"})

    client_type = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    assert providers.check_gemini()["status"] == "ok"
    assert len(requests) == 1


def test_gemini_chat_uses_scoped_tools_and_hides_customer_identifiers(
    intelligence_db, clean_provider_env, monkeypatch
):
    db, user, *_ = intelligence_db
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    payloads = []

    def handle(request):
        assert request.headers["x-goog-api-key"] == "synthetic-gemini-key"
        assert request.url.path == "/v1beta/models/gemini-test-model:generateContent"
        payload = json.loads(request.content)
        payloads.append(payload)
        if len(payloads) == 1:
            parts = [{"functionCall": {"name": "get_balance", "args": {}}}]
        else:
            assert payload["contents"][-1]["role"] == "user"
            parts = [
                {"text": "hidden internal thought", "thought": True},
                {"text": "Your available balance is INR 20000.00."},
            ]
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"role": "model", "parts": parts}}]},
        )

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = ai.chat(
        db,
        user,
        "Synthetic Customer at synthetic@example.test, ID 123456789012: show my balance",
    )
    assert result["ai_mode"] == "gemini"
    assert result["tools"][0]["name"] == "get_balance"
    assert "INR 20000.00" in result["reply"]
    assert "hidden internal thought" not in result["reply"]
    assert "synthetic@example.test" not in json.dumps(payloads)
    assert "123456789012" not in json.dumps(payloads)
    assert payloads[0]["tools"][0]["functionDeclarations"]


def test_openrouter_chat_uses_scoped_tools_and_redacts_customer_identifiers(
    intelligence_db, clean_provider_env, monkeypatch
):
    db, user, *_ = intelligence_db
    secret = "synthetic-openrouter-key"
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/free")
    payloads = []

    def handle(request):
        assert request.url.path == "/api/v1/chat/completions"
        assert request.headers["Authorization"] == f"Bearer {secret}"
        payload = json.loads(request.content)
        payloads.append(payload)
        if len(payloads) == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_balance",
                        "type": "function",
                        "function": {"name": "get_balance", "arguments": "{}"},
                    }
                ],
            }
        else:
            message = {
                "role": "assistant",
                "content": "Your available balance is INR 20000.00.",
            }
        return httpx.Response(200, json={"choices": [{"message": message}]})

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(handle), **kwargs
        ),
    )
    result = ai.chat(
        db,
        user,
        "Synthetic Customer at synthetic@example.test, ID 123456789012: show my balance",
    )
    assert result["ai_mode"] == "openrouter"
    assert result["tools"][0]["name"] == "get_balance"
    assert "INR 20000.00" in result["reply"]
    assert secret not in str(result)
    assert len(payloads) == 2
    assert payloads[0]["model"] == "openrouter/free"
    assert "get_balance" in str(payloads[0]["tools"])
    assert payloads[0]["tool_choice"] == {
        "type": "function", "function": {"name": "get_balance"}
    }
    assert payloads[0]["provider"]["require_parameters"] is True
    assert payloads[1]["tool_choice"] == "auto"
    sent = json.dumps(payloads)
    assert "synthetic@example.test" not in sent
    assert "123456789012" not in sent


def test_openrouter_transfer_proposal_has_authoritative_consent_text_without_model_synthesis(
    intelligence_db, clean_provider_env, monkeypatch
):
    db, user, _, account, *_ = intelligence_db
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-openrouter-key")
    beneficiary = db.scalar(select(Beneficiary).where(Beneficiary.user_id == user.id))
    balance_before = account.balance_paise
    ledgers_before = db.scalar(select(func.count()).select_from(LedgerEntry))
    payloads = []

    def handle(request):
        payload = json.loads(request.content)
        payloads.append(payload)
        assert len(payloads) == 1, "Validated proposals must not need another model response"
        assert payload["tool_choice"] == {
            "type": "function", "function": {"name": "propose_transfer"}
        }
        return httpx.Response(200, json={"choices": [{"message": {
            "role": "assistant",
            "content": "The transfer is complete according to an earlier policy [99].",
            "tool_calls": [{
                "id": "call_proposal",
                "type": "function",
                "function": {
                    "name": "propose_transfer",
                    "arguments": json.dumps({"beneficiary_name": "Demo Landlord", "amount": 100}),
                },
            }],
        }}]})

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = ai.chat(db, user, "Transfer INR 100 to Demo Landlord")
    assert result["proposal"]["beneficiary_id"] == beneficiary.id
    assert result["proposal"]["amount"] == "100.00"
    assert "Prepared a transfer proposal for INR 100.00" in result["reply"]
    assert "explicitly submit" in result["reply"]
    assert "no money has moved" in result["reply"]
    assert "[99]" not in result["reply"]
    assert "transfer is complete" not in result["reply"]
    assert account.balance_paise == balance_before
    assert db.scalar(select(func.count()).select_from(Transfer)) == 0
    assert db.scalar(select(func.count()).select_from(LedgerEntry)) == ledgers_before


def test_gemini_document_answers_require_and_return_exact_citations(
    intelligence_db, clean_provider_env, monkeypatch
):
    db, user, *_ = intelligence_db
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")

    def handle(request):
        payload = json.loads(request.content)
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert "OBSIDIAN" not in json.dumps(payload)
        return httpx.Response(
            200,
            json={
                "candidates": [{
                    "content": {"parts": [{"text": json.dumps({
                        "answer": "The source states the annual rate is 10.75% [1].",
                        "citation_numbers": [1],
                    })}]}
                }]
            },
        )

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = ai.query_documents(db, user, "What is the loan rate?")
    assert result["ai_mode"] == "gemini"
    assert "10.75%" in result["answer"]
    assert result["citations"]


def test_gemini_vision_is_limited_and_does_not_claim_identity_verification(
    clean_provider_env, monkeypatch
):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")

    def handle(request):
        payload = json.loads(request.content)
        parts = payload["contents"][0]["parts"]
        assert parts[1]["inlineData"]["mimeType"] == "image/png"
        assert parts[3]["inlineData"]["mimeType"] == "image/png"
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps({
                "document_readable": True,
                "document_portrait_present": True,
                "selfie_person_present": True,
                "printed_full_name": "Synthetic Customer",
                "confidence": 0.95,
            })}]}}]},
        )

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    png = b"\x89PNG\r\n\x1a\nsynthetic-image"
    result = ai.assess_kyc_evidence(
        "Synthetic Customer", "id.png", png, "selfie.png", png
    )
    assert result["mode"] == "gemini"
    assert result["performed"] is True
    assert "legal identity" in result["reasons"][0]


def test_model_discovery_paginates_selects_latest_and_cache_is_key_scoped(
    clean_provider_env, monkeypatch
):
    requests = []
    pages = [
        {
            "data": [
                {"id": "claude-haiku-test", "created_at": "2027-01-01T00:00:00Z"},
                {"id": "claude-sonnet-old", "created_at": "2025-01-01T00:00:00Z"},
            ],
            "has_more": True,
            "last_id": "claude-sonnet-old",
        },
        {
            "data": [{"id": "claude-sonnet-new", "created_at": "2026-01-01T00:00:00Z"}],
            "has_more": False,
        },
        {
            "data": [
                {"id": "claude-sonnet-other", "created_at": "2026-02-01T00:00:00Z"}
            ],
            "has_more": False,
        },
    ]

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=pages[len(requests) - 1])

    client_type = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    assert providers.resolve_claude_model("synthetic-key-one") == "claude-sonnet-new"
    assert requests[1].url.params["after_id"] == "claude-sonnet-old"
    assert providers.resolve_claude_model("synthetic-key-one") == "claude-sonnet-new"
    assert len(requests) == 2
    assert providers.resolve_claude_model("synthetic-key-two") == "claude-sonnet-other"
    assert len(requests) == 3
    assert "synthetic-key" not in str(providers._model_cache)


def test_explicit_model_avoids_discovery_and_probe_checks_model_access(
    clean_provider_env, monkeypatch
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-test")
    requests = []

    def handle(request):
        requests.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json={"id": "claude-sonnet-test"})

    client_type = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    assert providers.resolve_claude_model() == "claude-sonnet-test"
    assert requests == []
    result = providers.check_claude()
    assert result["status"] == "ok"
    assert result["scope"] == "model_access"
    assert requests[0].url.path == "/v1/models/claude-sonnet-test"
    assert "synthetic-test-key" not in str(result)
    assert "paid inference" in result["message"]


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_provider_failure_is_explicit_and_diagnostics_never_echo_remote_secrets(
    clean_provider_env, monkeypatch, status
):
    secret = "synthetic-provider-sensitive-key"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    client_type = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(status, json={"error": f"echoed {secret}"})
            ),
            **kwargs,
        ),
    )
    with pytest.raises(HTTPException) as error:
        providers.resolve_claude_model()
    assert error.value.status_code == 503
    assert secret not in str(error.value.detail)
    probe = providers.check_claude()
    assert probe["status"] == "error"
    assert secret not in str(probe)
    assert not providers._model_cache


def test_model_discovery_cache_expires_and_no_sonnet_does_not_fallback(
    clean_provider_env, monkeypatch
):
    clock = [100.0]
    calls = []
    monkeypatch.setattr(providers.time, "monotonic", lambda: clock[0])

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200, json={"data": [{"id": "claude-sonnet-test"}], "has_more": False}
        )

    client_type = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    providers.resolve_claude_model("synthetic-key")
    clock[0] += providers.MODEL_CACHE_SECONDS + 1
    providers.resolve_claude_model("synthetic-key")
    assert len(calls) == 2
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json={"data": [{"id": "claude-haiku-test"}]}
                )
            ),
            **kwargs,
        ),
    )
    with pytest.raises(HTTPException, match="accessible Claude Sonnet"):
        providers.resolve_claude_model("different-synthetic-key")


def test_status_honestly_distinguishes_implemented_claude_from_mock_adapters(
    clean_provider_env, monkeypatch
):
    result = providers.integration_status()
    assert result["ai_mode"] == result["kyc_mode"] == "local"
    assert providers.check_claude()["status"] == "unconfigured"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-sensitive-key")
    result = providers.integration_status()
    by_id = {provider["id"]: provider for provider in result["providers"]}
    assert by_id["claude"]["status"] == "configured"
    assert by_id["claude"]["credential_configured"] is True
    assert by_id["claude_vision"]["integrated"] is True
    assert "biometric" in by_id["claude_vision"]["limitations"]
    for identifier in [
        "core_banking",
        "identity",
        "sanctions",
        "credit_bureau",
        "geoip",
        "mfa",
    ]:
        assert by_id[identifier]["status"] == "not_integrated"
        assert by_id[identifier]["mode"] == "mock_adapter"
        assert by_id[identifier]["integrated"] is False
        assert by_id[identifier]["requirements"]
    assert "synthetic-sensitive-key" not in json.dumps(result)
    monkeypatch.setenv("AEGIS_AI_MODE", "local")
    explicit = providers.integration_status()["providers"][0]
    assert explicit["status"] == "local"
    assert explicit["credential_configured"] is True


def test_claude_document_answer_sends_scoped_redacted_excerpts_and_preserves_exact_citations(
    intelligence_db, monkeypatch
):
    db, user, _, _, public, private = intelligence_db
    monkeypatch.setenv("AEGIS_AI_MODE", "auto")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-test")
    chunk = db.scalar(
        select(DocumentChunk).where(DocumentChunk.document_id == public.id)
    )
    chunk.text += (
        " Contact Synthetic Customer at synthetic@example.test; ID 123456789012."
    )
    db.flush()
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "tool_use",
                        "name": "submit_document_answer",
                        "input": {
                            "answer": "The annual interest rate is 10.75% [1].",
                            "citation_numbers": [1],
                        },
                    }
                ]
            },
        )

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = ai.query_documents(
        db,
        user,
        "Synthetic Customer, synthetic@example.test: what is the personal loan interest rate?",
    )
    assert result["ai_mode"] == "claude"
    assert "10.75%" in result["answer"]
    assert result["citations"][0]["document_id"] == public.id
    assert result["citations"][0]["excerpt"] in chunk.text
    sent = json.dumps(requests)
    assert "OBSIDIAN" not in sent
    assert str(private.id) not in sent
    assert "synthetic@example.test" not in sent
    assert "123456789012" not in sent
    assert "Synthetic Customer" not in sent
    assert requests[0]["tool_choice"]["name"] == "submit_document_answer"


@pytest.mark.parametrize(
    "answer,numbers",
    [("Invented source [42].", [1]), ("No source.", [42]), ("Bad values.", [True])],
)
def test_claude_document_answers_reject_invented_citations(
    intelligence_db, monkeypatch, answer, numbers
):
    db, user, *_ = intelligence_db
    monkeypatch.setenv("AEGIS_AI_MODE", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-test")
    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json={
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "submit_document_answer",
                                "input": {
                                    "answer": answer,
                                    "citation_numbers": numbers,
                                },
                            }
                        ]
                    },
                )
            ),
            **kwargs,
        ),
    )
    with pytest.raises(HTTPException) as error:
        ai.query_documents(db, user, "personal loan interest rate")
    assert error.value.status_code == 503


def test_empty_retrieval_does_not_call_claude_or_invent_an_answer(
    intelligence_db, monkeypatch
):
    db, user, *_ = intelligence_db
    monkeypatch.setenv("AEGIS_AI_MODE", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: pytest.fail("No external call is needed for empty retrieval"),
    )
    result = ai.query_documents(db, user, "OBSIDIAN")
    assert result["citations"] == []
    assert "could not find" in result["answer"]


def test_key_only_auto_chat_discovers_model_then_uses_authorized_tool(
    intelligence_db, monkeypatch
):
    db, user, *_ = intelligence_db
    monkeypatch.setenv("AEGIS_AI_MODE", "auto")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-test-key")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    providers._model_cache.clear()
    calls = []

    def handle(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "claude-sonnet-accessible",
                            "created_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                },
            )
        if len(calls) == 2:
            content = [
                {"type": "tool_use", "id": "read-1", "name": "get_balance", "input": {}}
            ]
        else:
            content = [
                {"type": "text", "text": "Your current balance is INR 20000.00."}
            ]
        return httpx.Response(200, json={"content": content})

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = ai.chat(db, user, "Show my balance")
    assert result["ai_mode"] == "claude"
    assert result["tools"][0]["name"] == "get_balance"
    assert json.loads(calls[1].content)["model"] == "claude-sonnet-accessible"
    assert len(calls) == 3
    providers._model_cache.clear()


def test_auto_vision_with_key_discovers_model_without_claiming_biometrics(
    clean_provider_env, monkeypatch
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-test-key")
    calls = []

    def handle(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(
                200, json={"data": [{"id": "claude-sonnet-accessible"}]}
            )
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "tool_use",
                        "name": "submit_evidence_assessment",
                        "input": {
                            "document_readable": True,
                            "document_portrait_present": True,
                            "selfie_person_present": True,
                            "printed_full_name": "Synthetic Customer",
                            "confidence": 0.95,
                        },
                    }
                ]
            },
        )

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    png = b"\x89PNG\r\n\x1a\nsynthetic"
    result = ai.assess_kyc_evidence(
        "Synthetic Customer", "id.png", png, "selfie.png", png
    )
    assert result["mode"] == "claude"
    assert result["performed"] is True
    assert "biometric matching remain unverified" in result["reasons"][0]
    assert json.loads(calls[1].content)["model"] == "claude-sonnet-accessible"
    assert len(calls) == 2


def _openai_message(text: str, *, status: str = "completed") -> dict:
    return {
        "status": status,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
    }


def test_openai_key_alias_auto_priority_and_explicit_provider_selection(
    clean_provider_env, monkeypatch
):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-alias-key")
    assert config.resolve_ai_mode() == config.resolve_kyc_mode() == "openai"
    assert providers.openai_key() == "synthetic-alias-key"
    monkeypatch.setenv("AEGIS_OPENAI_API_KEY", "synthetic-primary-key")
    assert providers.openai_key() == "synthetic-primary-key"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-claude-key")
    assert config.resolve_ai_mode() == config.resolve_kyc_mode() == "claude"
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "openai")
    assert config.resolve_ai_mode() == config.resolve_kyc_mode() == "openai"
    monkeypatch.setenv("AEGIS_KYC_VISION", "claude")
    assert config.resolve_kyc_mode() == "claude"
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "local")
    assert config.resolve_ai_mode() == "local"
    monkeypatch.setenv("AEGIS_KYC_VISION", "auto")
    assert config.resolve_kyc_mode() == "local"


def test_openai_model_discovery_selects_capable_latest_family_and_caches_by_key(
    clean_provider_env, monkeypatch
):
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url.host == "api.openai.com"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gpt-4.1", "created": 100},
                    {"id": "gpt-5", "created": 200},
                    {"id": "gpt-5.2-mini", "created": 300},
                    {"id": "gpt-5.2", "created": 250},
                    {"id": "gpt-5.2-chat-latest", "created": 999},
                    {"id": "gpt-5.2-codex", "created": 999},
                    {"id": "gpt-image-1", "created": 999},
                    {"id": "whisper-1", "created": 999},
                ]
            },
        )

    client_type = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    assert providers.resolve_openai_model("synthetic-key-one") == "gpt-5.2"
    assert providers.resolve_openai_model("synthetic-key-one") == "gpt-5.2"
    assert len(calls) == 1
    assert providers.resolve_openai_model("synthetic-key-two") == "gpt-5.2"
    assert len(calls) == 2
    assert "synthetic-key" not in str(providers._openai_model_cache)


def test_openai_probe_checks_explicit_model_access_without_inference(
    clean_provider_env, monkeypatch
):
    monkeypatch.setenv("AEGIS_OPENAI_API_KEY", "synthetic-openai-key")
    monkeypatch.setenv("AEGIS_OPENAI_MODEL", "gpt-4.1")
    calls = []

    def handle(request):
        calls.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json={"id": "gpt-4.1"})

    client_type = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    assert providers.resolve_openai_model() == "gpt-4.1"
    assert calls == []
    result = providers.check_openai()
    assert result["status"] == "ok"
    assert result["scope"] == "model_access"
    assert calls[0].url.path == "/v1/models/gpt-4.1"
    assert "synthetic-openai-key" not in str(result)
    assert providers.integration_status()["ai_mode"] == "openai"
    by_id = {
        provider["id"]: provider
        for provider in providers.integration_status()["providers"]
    }
    assert by_id["openai"]["status"] == by_id["openai_vision"]["status"] == "configured"
    assert by_id["claude"]["status"] == "local"


def test_openai_diagnostic_failure_never_echoes_secret_or_falls_back(
    clean_provider_env, monkeypatch
):
    secret = "synthetic-sensitive-openai-key"
    monkeypatch.setenv("AEGIS_OPENAI_API_KEY", secret)
    client_type = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(401, json={"error": secret})
            ),
            **kwargs,
        ),
    )
    with pytest.raises(HTTPException) as error:
        providers.resolve_openai_model()
    assert error.value.status_code == 503
    assert secret not in str(error.value.detail)
    assert providers.check_openai()["status"] == "error"
    assert secret not in str(providers.check_openai())
    assert not providers._openai_model_cache


def test_key_only_openai_auto_tool_loop_uses_redacted_scoped_context(
    intelligence_db, monkeypatch
):
    db, user, *_ = intelligence_db
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "auto")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("AEGIS_OPENAI_API_KEY", "synthetic-openai-key")
    monkeypatch.delenv("AEGIS_OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    providers._openai_model_cache.clear()
    calls, payloads = [], []

    def handle(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(
                200, json={"data": [{"id": "gpt-5.2", "created": 100}]}
            )
        payload = json.loads(request.content)
        payloads.append(payload)
        assert request.url.path == "/v1/responses"
        assert payload["store"] is False
        assert payload["model"] == "gpt-5.2"
        if len(payloads) == 1:
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {
                            "type": "reasoning",
                            "id": "r-1",
                            "summary": [],
                            "encrypted_content": "opaque-continuation",
                        },
                        {
                            "type": "function_call",
                            "id": "fc-1",
                            "call_id": "read-1",
                            "name": "get_balance",
                            "arguments": "{}",
                        },
                    ],
                },
            )
        return httpx.Response(
            200, json=_openai_message("Your balance is INR 20000.00.")
        )

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = ai.chat(
        db,
        user,
        "Synthetic Customer: synthetic@example.test, ID 123456789012, show my balance.",
    )
    assert result["ai_mode"] == "openai"
    assert result["tools"][0]["name"] == "get_balance"
    assert len(calls) == 3
    sent = json.dumps(payloads)
    assert "synthetic@example.test" not in sent
    assert "123456789012" not in sent
    assert "Synthetic Customer" not in sent
    assert "DEMO-001" not in sent
    assert payloads[1]["input"][-1]["type"] == "function_call_output"
    assert payloads[1]["input"][-1]["call_id"] == "read-1"
    assert "opaque-continuation" not in str(result)
    providers._openai_model_cache.clear()


def test_openai_tool_loop_cannot_settle_money_and_rejects_spoofed_customer(
    intelligence_db, monkeypatch
):
    from app.models import Transfer
    from app.query import func

    db, user, _, account, *_ = intelligence_db
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "openai")
    monkeypatch.setenv("AEGIS_OPENAI_API_KEY", "synthetic-openai-key")
    monkeypatch.setenv("AEGIS_OPENAI_MODEL", "gpt-4.1")
    payloads = []

    def handle(request):
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            output = [
                {
                    "type": "function_call",
                    "id": "fc-1",
                    "call_id": "bad-1",
                    "name": "settle_transfer",
                    "arguments": '{"amount":1000}',
                },
                {
                    "type": "function_call",
                    "id": "fc-2",
                    "call_id": "bad-2",
                    "name": "get_balance",
                    "arguments": '{"user_id":"foreign"}',
                },
            ]
            return httpx.Response(200, json={"status": "completed", "output": output})
        return httpx.Response(
            200, json=_openai_message("Those capabilities are unavailable.")
        )

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = ai.chat(
        db, user, "Move money immediately and show another customer balance."
    )
    assert result["tools"] == []
    assert account.balance_paise == 2000000
    assert db.scalar(select(func.count()).select_from(Transfer)) == 0
    assert "error" in json.loads(payloads[1]["input"][-1]["output"])
    assert "error" in json.loads(payloads[1]["input"][-2]["output"])


def test_openai_documents_answer_only_scoped_sources_with_exact_citations(
    intelligence_db, monkeypatch
):
    db, user, _, _, public, private = intelligence_db
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "openai")
    monkeypatch.setenv("AEGIS_OPENAI_API_KEY", "synthetic-openai-key")
    monkeypatch.setenv("AEGIS_OPENAI_MODEL", "gpt-4.1")
    payloads = []

    def handle(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=_openai_message(
                json.dumps(
                    {
                        "answer": "The annual loan interest rate is 10.75% [1].",
                        "citation_numbers": [1],
                    }
                )
            ),
        )

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = ai.query_documents(
        db,
        user,
        "Synthetic Customer, synthetic@example.test: what is the personal loan interest rate?",
    )
    assert result["ai_mode"] == "openai"
    assert result["citations"][0]["document_id"] == public.id
    assert result["citations"][0]["excerpt"] in db.scalar(
        select(DocumentChunk.text).where(DocumentChunk.document_id == public.id)
    )
    sent = json.dumps(payloads)
    assert "OBSIDIAN" not in sent
    assert str(private.id) not in sent
    assert "synthetic@example.test" not in sent
    assert "Synthetic Customer" not in sent
    assert payloads[0]["text"]["format"]["strict"] is True


def test_openai_document_answer_rejects_invented_reference(
    intelligence_db, monkeypatch
):
    db, user, *_ = intelligence_db
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "openai")
    monkeypatch.setenv("AEGIS_OPENAI_API_KEY", "synthetic-openai-key")
    monkeypatch.setenv("AEGIS_OPENAI_MODEL", "gpt-4.1")
    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json=_openai_message(
                        json.dumps(
                            {"answer": "Invented fact [9].", "citation_numbers": [1]}
                        )
                    ),
                )
            ),
            **kwargs,
        ),
    )
    with pytest.raises(HTTPException) as error:
        ai.query_documents(db, user, "personal loan interest rate")
    assert error.value.status_code == 503


def test_openai_auto_vision_is_transient_and_limited_to_quality(
    clean_provider_env, monkeypatch
):
    monkeypatch.setenv("AEGIS_OPENAI_API_KEY", "synthetic-openai-key")
    monkeypatch.setenv("AEGIS_OPENAI_MODEL", "gpt-4.1")
    payloads = []

    def handle(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=_openai_message(
                json.dumps(
                    {
                        "document_readable": True,
                        "document_portrait_present": True,
                        "selfie_person_present": True,
                        "printed_full_name": "Other Person",
                        "confidence": 0.95,
                    }
                )
            ),
        )

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    png = b"\x89PNG\r\n\x1a\nsynthetic"
    result = ai.assess_kyc_evidence(
        "Synthetic Customer", "id.pdf", b"%PDF-synthetic", "selfie.png", png
    )
    assert result["mode"] == "openai"
    assert result["requires_review"] is True
    assert result["risk_score"] == 40
    assert "biometric matching remain unverified" in result["reasons"][0]
    assert "Other Person" not in str(result)
    assert "printed_full_name" not in result
    assert "Synthetic Customer" not in str(payloads)
    content = payloads[0]["input"][0]["content"]
    assert content[1]["type"] == "input_file"
    assert content[3]["type"] == "input_image"
    assert payloads[0]["store"] is False


def test_openai_missing_credentials_and_incomplete_response_fail_clearly(
    intelligence_db, monkeypatch
):
    db, user, *_ = intelligence_db
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "openai")
    monkeypatch.delenv("AEGIS_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(HTTPException) as error:
        ai.chat(db, user, "Show my balance")
    assert error.value.status_code == 503
    monkeypatch.setenv("AEGIS_OPENAI_API_KEY", "synthetic-openai-key")
    monkeypatch.setenv("AEGIS_OPENAI_MODEL", "gpt-4.1")
    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json=_openai_message("Partial answer.", status="incomplete")
                )
            ),
            **kwargs,
        ),
    )
    with pytest.raises(HTTPException) as error:
        ai.chat(db, user, "Show my balance")
    assert error.value.status_code == 503
    assert "did not complete" in error.value.detail


def test_recommendations_spending_and_budgets_use_full_posted_ledger_beyond_2000(
    intelligence_db,
):
    from datetime import datetime, timedelta, timezone
    from app.models import LedgerEntry

    db, user, _, account, *_ = intelligence_db
    now = datetime.now(timezone.utc)
    seed_records(db,
        [
            LedgerEntry(
                account_id=account.id,
                direction=direction,
                amount_paise=amount,
                description="Synthetic aggregate regression",
                category="Shopping",
                status="posted",
                balance_after_paise=account.balance_paise,
                created_at=now,
            )
            for direction, amount in [("credit", 100), ("debit", 1)]
            for _ in range(3000)
        ]
    )
    db.add(
        LedgerEntry(
            account_id=account.id,
            direction="credit",
            amount_paise=999999,
            description="Excluded pending",
            category="Shopping",
            status="pending",
            balance_after_paise=account.balance_paise,
            created_at=now,
        )
    )
    db.add(
        LedgerEntry(
            account_id=account.id,
            direction="credit",
            amount_paise=999999,
            description="Excluded old",
            category="Shopping",
            status="posted",
            balance_after_paise=account.balance_paise,
            created_at=now - timedelta(days=31),
        )
    )
    db.flush()
    context = ai.ToolContext(db, user, "aggregate-test", ai.CUSTOMER_SCOPES)
    spending = ai.REGISTRY.invoke("get_spending", context, {})
    assert spending["income"] == "83000.00"
    assert spending["expenses"] == "20030.00"
    budget = ai.REGISTRY.invoke("get_budgets", context, {})["budgets"][0]
    assert budget["spent"] == "20030.00"
    profile = ai.recommendations(db, user)["profile"]
    assert profile["monthly_income"] == "83000.00"
    assert profile["monthly_expenses"] == "20030.00"


def test_budget_spending_combines_case_variants_without_losing_amounts(intelligence_db):
    from app.models import LedgerEntry

    db, user, _, account, *_ = intelligence_db
    db.add(
        LedgerEntry(
            account_id=account.id,
            direction="debit",
            amount_paise=1000,
            description="Synthetic category variant",
            category="shopping",
            status="posted",
            balance_after_paise=account.balance_paise,
        )
    )
    db.flush()
    context = ai.ToolContext(db, user, "case-aggregate-test", ai.CUSTOMER_SCOPES)
    budget = ai.REGISTRY.invoke("get_budgets", context, {})["budgets"][0]
    assert budget["spent"] == "20010.00"


@pytest.mark.parametrize("fenced", [False, True])
def test_openrouter_document_answer_uses_strict_schema_and_scoped_sources(
    intelligence_db, clean_provider_env, monkeypatch, fenced
):
    db, user, *_ = intelligence_db
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-openrouter-key")

    def handle(request):
        payload = json.loads(request.content)
        specification = payload["response_format"]["json_schema"]
        assert payload["response_format"]["type"] == "json_schema"
        assert specification["strict"] is True
        assert specification["schema"]["additionalProperties"] is False
        assert specification["schema"]["properties"]["citation_numbers"]["items"][
            "enum"
        ] == [1]
        assert payload["provider"]["require_parameters"] is True
        assert payload["reasoning"] == {"effort": "low", "exclude": True}
        assert "OBSIDIAN" not in json.dumps(payload)
        text = json.dumps(
            {"answer": "The annual loan rate is 10.75% [1].", "citation_numbers": [1]}
        )
        if fenced:
            text = "```json\n" + text + "\n```"
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})

    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = ai.query_documents(db, user, "What is the loan rate?")
    assert result["ai_mode"] == "openrouter"
    assert "10.75%" in result["answer"]
    assert result["citations"][0]["page"] == 2


@pytest.mark.parametrize(
    "content",
    [
        json.dumps({"answer": "Invented source [99].", "citation_numbers": [99]}),
        "",
    ],
)
def test_openrouter_document_answer_rejects_unknown_sources_and_empty_output(
    intelligence_db, clean_provider_env, monkeypatch, content
):
    db, user, *_ = intelligence_db
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-openrouter-key")
    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "choices": [
                            {"message": {"content": content}, "finish_reason": "length"}
                        ]
                    },
                )
            ),
            **kwargs,
        ),
    )
    with pytest.raises(HTTPException) as error:
        ai.query_documents(db, user, "What is the loan rate?")
    assert error.value.status_code == 503


def test_openrouter_cannot_answer_account_facts_without_a_fresh_tool_result(
    intelligence_db, clean_provider_env, monkeypatch
):
    db, user, *_ = intelligence_db
    monkeypatch.setenv("AEGIS_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-openrouter-key")
    client_type = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "choices": [{"message": {"content": "Your balance is 999."}}]
                    },
                )
            ),
            **kwargs,
        ),
    )
    with pytest.raises(HTTPException) as error:
        ai.chat(db, user, "What is my available balance?")
    assert error.value.status_code == 503
    assert "required scoped banking tool" in str(error.value.detail)
