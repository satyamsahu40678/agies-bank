"""Provider configuration, safe diagnostics and bounded model discovery.

Status describes implemented adapters honestly. A credential configures its
Claude/OpenAI adapter; real banking providers require their own integration.
No secret or remote response text is exposed in diagnostics.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
import re
import threading
import time
from typing import Any

import httpx
from fastapi import HTTPException

from .. import config


ANTHROPIC_BASE = "https://api.anthropic.com/v1"
OPENAI_BASE = "https://api.openai.com/v1"
MODEL_CACHE_SECONDS = 60 * 60
_model_cache: dict[str, tuple[float, str]] = {}
_openai_model_cache: dict[str, tuple[float, str]] = {}
_model_lock = threading.RLock()


def anthropic_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            503,
            "Claude requires ANTHROPIC_API_KEY. Configure it securely or select local mode.",
        )
    return key


def anthropic_headers(key: str) -> dict[str, str]:
    return {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }


def _cache_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _valid_model(value: Any) -> bool:
    return isinstance(value, str) and bool(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", value)
    )


def _configured_model() -> str | None:
    model = os.getenv("ANTHROPIC_MODEL", "").strip()
    if model and not _valid_model(model):
        raise HTTPException(503, "ANTHROPIC_MODEL must contain a valid model ID.")
    return model or None


def _response_data(response: Any, provider: str = "Anthropic") -> dict[str, Any]:
    if response.status_code != 200:
        messages = {
            401: f"{provider} authentication failed. Check the configured API key.",
            403: f"{provider} denied model access. Check the API key permissions and account access.",
            404: f"The configured {provider} model was not found or is unavailable to this account.",
            429: f"{provider} rate limits prevented this check. Retry after the account limit clears.",
        }
        raise HTTPException(
            503,
            messages.get(
                response.status_code,
                f"{provider} is unavailable. Check connectivity and account availability.",
            ),
        )
    try:
        data = response.json()
    except (ValueError, TypeError):
        raise HTTPException(
            503, f"{provider} returned invalid model metadata."
        ) from None
    if not isinstance(data, dict):
        raise HTTPException(503, f"{provider} returned invalid model metadata.")
    return data


def resolve_claude_model(key: str | None = None, *, refresh: bool = False) -> str:
    """Use an explicit model or discover the newest accessible Sonnet model.

    Discovery uses the official read-only API, verifies TLS, handles bounded
    pagination, and caches only a hashed credential identity plus model ID.
    Discovery failures are explicit; no hard-coded model or local fallback is
    substituted for an unavailable configured provider.
    """
    configured = _configured_model()
    if configured:
        return configured
    key = key or anthropic_key()
    identity = _cache_key(key)
    with _model_lock:
        cached = _model_cache.get(identity)
        if cached and cached[0] > time.monotonic() and not refresh:
            return cached[1]
        _model_cache.pop(identity, None)
        models = []
        after_id = None
        try:
            with httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0)) as client:
                for _ in range(10):
                    params = {"limit": 100}
                    if after_id:
                        params["after_id"] = after_id
                    body = _response_data(
                        client.get(
                            f"{ANTHROPIC_BASE}/models",
                            headers=anthropic_headers(key),
                            params=params,
                        )
                    )
                    entries = body.get("data")
                    if not isinstance(entries, list):
                        raise HTTPException(
                            503, "Anthropic returned invalid model metadata."
                        )
                    for item in entries:
                        if not isinstance(item, dict) or not _valid_model(
                            item.get("id")
                        ):
                            raise HTTPException(
                                503, "Anthropic returned invalid model metadata."
                            )
                        if "sonnet" in item["id"].lower():
                            models.append(item)
                    if not body.get("has_more", False):
                        break
                    next_id = body.get("last_id")
                    if not _valid_model(next_id) or next_id == after_id:
                        raise HTTPException(
                            503, "Anthropic returned invalid model pagination."
                        )
                    after_id = next_id
                else:
                    raise HTTPException(
                        503,
                        "Anthropic model discovery exceeded its bounded page limit. Set ANTHROPIC_MODEL explicitly.",
                    )
        except (httpx.HTTPError, ValueError, TypeError):
            raise HTTPException(
                503,
                "Anthropic model discovery could not be reached. Check network access and provider configuration.",
            ) from None
        if not models:
            raise HTTPException(
                503,
                "No accessible Claude Sonnet model was found. Set an accessible ANTHROPIC_MODEL explicitly.",
            )
        # ISO-8601 timestamps sort chronologically when supplied in UTC by the API.
        model = max(
            models, key=lambda item: (str(item.get("created_at", "")), item["id"])
        )["id"]
        now = time.monotonic()
        for expired in [
            entry for entry, value in _model_cache.items() if value[0] <= now
        ]:
            _model_cache.pop(expired, None)
        if len(_model_cache) >= 32:
            _model_cache.pop(next(iter(_model_cache)))
        _model_cache[identity] = (now + MODEL_CACHE_SECONDS, model)
        return model


def _observed_model(key: str) -> str | None:
    configured = os.getenv("ANTHROPIC_MODEL", "").strip()
    if configured:
        return configured if _valid_model(configured) else None
    with _model_lock:
        cached = _model_cache.get(_cache_key(key))
        return cached[1] if cached and cached[0] > time.monotonic() else None


def openai_key() -> str:
    key = (
        os.getenv("AEGIS_OPENAI_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )
    if not key:
        raise HTTPException(
            503,
            "OpenAI requires AEGIS_OPENAI_API_KEY (or the local OPENAI_API_KEY alias). Configure it securely or select local mode.",
        )
    return key


def openai_headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "content-type": "application/json"}


def _configured_openai_model() -> str | None:
    model = (
        os.getenv("AEGIS_OPENAI_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
    )
    if model and not _valid_model(model):
        raise HTTPException(503, "AEGIS_OPENAI_MODEL must contain a valid model ID.")
    return model or None


def _responses_model(value: str) -> bool:
    # These general-purpose families support Responses, tools and vision.
    # Exclude chat-only, audio, image, coding-specialized and legacy variants.
    return bool(
        re.fullmatch(
            r"gpt-(?:5(?:\.\d+)?|4\.1)(?:-(?:mini|nano))?(?:-\d{4}-\d{2}-\d{2})?", value
        )
    )


def _model_preference(item: dict[str, Any]) -> tuple[Any, ...]:
    identifier = item["id"]
    version = re.match(r"gpt-(\d+)(?:\.(\d+))?", identifier)
    family = tuple(int(part or 0) for part in version.groups())
    capacity = 0 if "-nano" in identifier else (1 if "-mini" in identifier else 2)
    return family, capacity, item.get("created", 0), identifier


def resolve_openai_model(key: str | None = None, *, refresh: bool = False) -> str:
    configured = _configured_openai_model()
    if configured:
        return configured
    key = key or openai_key()
    identity = _cache_key(key)
    with _model_lock:
        cached = _openai_model_cache.get(identity)
        if cached and cached[0] > time.monotonic() and not refresh:
            return cached[1]
        _openai_model_cache.pop(identity, None)
        try:
            with httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0)) as client:
                body = _response_data(
                    client.get(f"{OPENAI_BASE}/models", headers=openai_headers(key)),
                    "OpenAI",
                )
            entries = body.get("data")
            if not isinstance(entries, list):
                raise HTTPException(503, "OpenAI returned invalid model metadata.")
            models = []
            for item in entries:
                if not isinstance(item, dict) or not _valid_model(item.get("id")):
                    raise HTTPException(503, "OpenAI returned invalid model metadata.")
                if _responses_model(item["id"]):
                    if type(item.get("created", 0)) is not int:
                        raise HTTPException(
                            503, "OpenAI returned invalid model metadata."
                        )
                    models.append(item)
        except (httpx.HTTPError, ValueError, TypeError):
            raise HTTPException(
                503,
                "OpenAI model discovery could not be reached. Check network access and provider configuration.",
            ) from None
        if not models:
            raise HTTPException(
                503,
                "No accessible general-purpose GPT-5 or GPT-4.1 model was found. Set a Responses-capable AEGIS_OPENAI_MODEL explicitly.",
            )
        model = max(models, key=_model_preference)["id"]
        now = time.monotonic()
        for expired in [
            entry for entry, value in _openai_model_cache.items() if value[0] <= now
        ]:
            _openai_model_cache.pop(expired, None)
        if len(_openai_model_cache) >= 32:
            _openai_model_cache.pop(next(iter(_openai_model_cache)))
        _openai_model_cache[identity] = (now + MODEL_CACHE_SECONDS, model)
        return model


def _observed_openai_model(key: str) -> str | None:
    configured = (
        os.getenv("AEGIS_OPENAI_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
    )
    if configured:
        return configured if _valid_model(configured) else None
    with _model_lock:
        cached = _openai_model_cache.get(_cache_key(key))
        return cached[1] if cached and cached[0] > time.monotonic() else None


def integration_status() -> dict[str, Any]:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    ai_mode, kyc_mode = config.resolve_ai_mode(), config.resolve_kyc_mode()
    model = _observed_model(key) if key else None

    def claude(
        identifier: str, name: str, mode: str, capabilities: list[str], limitation: str
    ) -> dict[str, Any]:
        return {
            "id": identifier,
            "name": name,
            "status": "local"
            if mode == "local"
            else ("configured" if key else "unconfigured"),
            "integrated": True,
            "mode": mode,
            "credential_configured": bool(key),
            "model": model,
            "model_selection": "configured"
            if os.getenv("ANTHROPIC_MODEL", "").strip()
            else "automatic",
            "endpoints": [f"{ANTHROPIC_BASE}/models", f"{ANTHROPIC_BASE}/messages"],
            "capabilities": capabilities,
            "limitations": limitation,
            "requirements": [
                "ANTHROPIC_API_KEY",
                "Network access to api.anthropic.com",
                "Restart the backend after changing .env; auto mode enables configured credentials",
                "An account with accessible models and sufficient inference credits",
            ],
        }

    providers = [
        claude(
            "claude",
            "Claude assistant and document answers",
            "claude" if ai_mode == "claude" else "local",
            [
                "Scoped banking tool orchestration",
                "Grounded answers from retrieved, redacted document excerpts",
                "Transfer proposals requiring customer confirmation",
            ],
            "Configured means a key is present, not that live inference has been validated. AI cannot settle money, override policy or approve identity.",
        ),
        claude(
            "claude_vision",
            "Claude evidence quality assistance",
            "claude" if kyc_mode == "claude" else "local",
            [
                "Document readability",
                "Apparent portrait/person presence",
                "Printed-name consistency",
            ],
            "Limited vision assistance does not authenticate documents, match faces, perform biometric liveness or verify legal identity.",
        ),
    ]
    openai_credential = (
        os.getenv("AEGIS_OPENAI_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )
    for identifier, name, selected in [
        ("openai", "OpenAI assistant and document answers", ai_mode),
        ("openai_vision", "OpenAI evidence quality assistance", kyc_mode),
    ]:
        mode = "openai" if selected == "openai" else "local"
        providers.append(
            {
                "id": identifier,
                "name": name,
                "status": "local"
                if mode == "local"
                else ("configured" if openai_credential else "unconfigured"),
                "integrated": True,
                "mode": mode,
                "credential_configured": bool(openai_credential),
                "model": _observed_openai_model(openai_credential)
                if openai_credential
                else None,
                "model_selection": "configured"
                if (
                    os.getenv("AEGIS_OPENAI_MODEL", "").strip()
                    or os.getenv("OPENAI_MODEL", "").strip()
                )
                else "automatic",
                "endpoints": [f"{OPENAI_BASE}/models", f"{OPENAI_BASE}/responses"],
                "capabilities": [
                    "Scoped banking tool orchestration",
                    "Grounded answers from retrieved, redacted document excerpts",
                    "Transfer proposals requiring customer confirmation",
                ]
                if identifier == "openai"
                else [
                    "Document readability",
                    "Apparent portrait/person presence",
                    "Printed-name consistency",
                ],
                "limitations": "Configured means a key is present, not that live inference has been validated. AI cannot settle money, override policy or approve identity."
                if identifier == "openai"
                else "Limited vision assistance does not authenticate documents, match faces, perform biometric liveness or verify legal identity.",
                "requirements": [
                    "AEGIS_OPENAI_API_KEY (local OPENAI_API_KEY alias is also supported)",
                    "Network access to api.openai.com",
                    "Restart the backend after changing .env; auto mode selects Claude first when both keys exist",
                    "An account with accessible Responses-capable models and sufficient inference credits",
                ],
            }
        )
    adapters = [
        (
            "core_banking",
            "Bank settlement",
            ["Synthetic ledger settlement and governed transfer approvals"],
            "Transfers affect the local ledger. No real bank account is debited or credited.",
            [
                "Choose a core-bank/payment provider and provision a sandbox account",
                "Implement its signed payment, reconciliation and webhook protocol",
                "Configure separate credentials, settlement accounts and jurisdiction-specific approvals",
            ],
        ),
        (
            "identity",
            "Identity and biometric verification",
            ["Synthetic identity adapter and analyst review"],
            "Synthetic checks cannot establish legal identity, document authenticity or biometric liveness.",
            [
                "Choose an identity/liveness provider and provision a sandbox account",
                "Implement verification sessions, signed webhooks and consent/retention rules",
                "Configure separate provider credentials and approved identity workflows",
            ],
        ),
        (
            "sanctions",
            "Sanctions screening",
            ["Synthetic demonstration watchlist"],
            "No live sanctions or politically exposed person feed is connected.",
            [
                "Select a licensed screening provider",
                "Implement authenticated screening, case resolution and feed/version evidence",
            ],
        ),
        (
            "credit_bureau",
            "Credit bureau",
            ["Explicit synthetic score for illustrative eligibility"],
            "The displayed synthetic bureau score is not a real credit report or loan approval.",
            [
                "Obtain a bureau agreement and consent workflow",
                "Integrate supported authenticated reports and approved credit-decision policy",
            ],
        ),
        (
            "geoip",
            "Location and device intelligence",
            ["Synthetic IP/location risk adapter"],
            "Demo geolocation and device signals do not attest a real device or location.",
            [
                "Choose a GeoIP/device-attestation provider",
                "Integrate trusted ingress signals, signed attestations and privacy controls",
            ],
        ),
        (
            "mfa",
            "Production multi-factor authentication",
            ["Password re-authentication for demonstration step-up"],
            "Password step-up is implemented; a second factor such as WebAuthn or TOTP is not integrated.",
            [
                "Choose WebAuthn/TOTP or an identity provider",
                "Implement enrolled factors, recovery, revocation and transaction-bound step-up",
            ],
        ),
    ]
    for identifier, name, capabilities, limitation, requirements in adapters:
        providers.append(
            {
                "id": identifier,
                "name": name,
                "status": "not_integrated",
                "integrated": False,
                "mode": "mock_adapter",
                "credential_configured": False,
                "model": None,
                "endpoints": [],
                "capabilities": capabilities,
                "limitations": limitation,
                "requirements": requirements,
            }
        )
    return {
        "ai_mode": ai_mode,
        "kyc_mode": kyc_mode,
        "providers": providers,
        "disclaimer": "Local workflows are runnable. Claude and OpenAI are key-ready; real banking, identity and other external adapters require provider-specific implementations and separate accounts. Model-access checks do not validate paid inference or real financial operations.",
    }


def check_claude() -> dict[str, Any]:
    """Non-destructive credential/model access check; never sends customer data."""
    checked_at = datetime.now(timezone.utc).isoformat()
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    result = {
        "status": "unconfigured",
        "configured": bool(key),
        "model": None,
        "checked_at": checked_at,
        "scope": "model_access",
        "message": "ANTHROPIC_API_KEY is not configured. Add it securely and restart the backend.",
    }
    if not key:
        return result
    try:
        configured = _configured_model()
        if configured:
            with httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0)) as client:
                body = _response_data(
                    client.get(
                        f"{ANTHROPIC_BASE}/models/{configured}",
                        headers=anthropic_headers(key),
                    )
                )
            if body.get("id") != configured:
                raise HTTPException(503, "Anthropic returned invalid model metadata.")
            model = configured
        else:
            model = resolve_claude_model(key, refresh=True)
        return {
            **result,
            "status": "ok",
            "model": model,
            "message": "Credentials can access this model. No customer data or paid inference was sent; live assistant and vision requests require account credits and separate validation.",
        }
    except HTTPException as error:
        return {
            **result,
            "status": "error",
            "error_code": "provider_configuration",
            "message": str(error.detail),
        }
    except (httpx.HTTPError, ValueError, TypeError):
        return {
            **result,
            "status": "error",
            "error_code": "provider_connectivity",
            "message": "Anthropic could not be reached. Check allowed network destinations and configured credentials.",
        }


def check_openai() -> dict[str, Any]:
    checked_at = datetime.now(timezone.utc).isoformat()
    key = (
        os.getenv("AEGIS_OPENAI_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )
    result = {
        "status": "unconfigured",
        "configured": bool(key),
        "model": None,
        "checked_at": checked_at,
        "scope": "model_access",
        "message": "AEGIS_OPENAI_API_KEY is not configured. Add it securely and restart the backend.",
    }
    if not key:
        return result
    try:
        configured = _configured_openai_model()
        if configured:
            with httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0)) as client:
                body = _response_data(
                    client.get(
                        f"{OPENAI_BASE}/models/{configured}",
                        headers=openai_headers(key),
                    ),
                    "OpenAI",
                )
            if body.get("id") != configured:
                raise HTTPException(503, "OpenAI returned invalid model metadata.")
            model = configured
        else:
            model = resolve_openai_model(key, refresh=True)
        return {
            **result,
            "status": "ok",
            "model": model,
            "message": "Credentials can access this model. No customer data or paid inference was sent; live assistant and vision requests require account credits and separate validation.",
        }
    except HTTPException as error:
        return {
            **result,
            "status": "error",
            "error_code": "provider_configuration",
            "message": str(error.detail),
        }
    except (httpx.HTTPError, ValueError, TypeError):
        return {
            **result,
            "status": "error",
            "error_code": "provider_connectivity",
            "message": "OpenAI could not be reached. Check allowed network destinations and configured credentials.",
        }
