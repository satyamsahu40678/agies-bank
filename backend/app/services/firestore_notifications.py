"""Optional Firestore projection for non-authoritative agent alerts."""

from __future__ import annotations

from datetime import timezone
import hashlib
import hmac
import logging
import os
from typing import Any

import httpx
from sqlalchemy import select

from ..config import SECRET
from ..models import AgentRun, FinancialInsight

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return os.getenv("FIRESTORE_AGENT_NOTIFICATIONS", "false").strip().lower() == "true"


def _firestore_base() -> str:
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    database = os.getenv("FIRESTORE_DATABASE", "(default)").strip() or "(default)"
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is required for Firestore notifications.")
    return f"projects/{project}/databases/{database}/documents"


def _access_token() -> str:
    emulator = os.getenv("FIRESTORE_EMULATOR_HOST", "").strip()
    if emulator:
        return ""
    try:
        response = httpx.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
            timeout=httpx.Timeout(3.0, connect=1.0),
        )
        response.raise_for_status()
        token = response.json().get("access_token")
    except (httpx.HTTPError, ValueError, TypeError):
        raise RuntimeError("Cloud Run service identity could not obtain a Firestore access token.") from None
    if not isinstance(token, str) or not token:
        raise RuntimeError("Cloud Run service identity returned no Firestore access token.")
    return token


def _request(path: str, payload: dict[str, Any]) -> Any:
    resource = _firestore_base()
    emulator = os.getenv("FIRESTORE_EMULATOR_HOST", "").strip()
    if emulator:
        base = "http://" + emulator.rstrip("/") + "/v1/" + resource
    else:
        base = "https://firestore.googleapis.com/v1/" + resource
    headers = {"content-type": "application/json"}
    token = _access_token()
    if token:
        headers["authorization"] = f"Bearer {token}"
    try:
        response = httpx.post(
            f"{base}{path}" if path.startswith(":") else f"{base}/{path.lstrip('/')}",
            headers=headers,
            json=payload,
            timeout=httpx.Timeout(10.0, connect=3.0),
        )
        if response.status_code not in {200, 201}:
            raise RuntimeError("Firestore returned an unsuccessful response.")
        return response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        raise RuntimeError("Firestore notification storage is unavailable.") from None


def _to_firestore(value: Any) -> dict[str, Any]:
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_to_firestore(item) for item in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {key: _to_firestore(item) for key, item in value.items()}}}
    return {"stringValue": str(value)}


def _from_firestore(value: dict[str, Any]) -> Any:
    for key, item in value.items():
        if key == "mapValue":
            return {name: _from_firestore(field) for name, field in item.get("fields", {}).items()}
        if key == "arrayValue":
            return [_from_firestore(child) for child in item.get("values", [])]
        if key == "integerValue":
            return int(item)
        if key == "doubleValue":
            return float(item)
        if key == "nullValue":
            return None
        if key in {"stringValue", "booleanValue"}:
            return item
    return None


def _customer_key(user_id: str) -> str:
    return hmac.new(SECRET.encode(), user_id.encode(), hashlib.sha256).hexdigest()


def _iso(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _notification(item: FinancialInsight) -> dict[str, Any]:
    return {
        "id": item.id,
        "kind": item.kind,
        "severity": item.severity,
        "title": item.title,
        "message": item.message,
        "action_label": item.action_label,
        "action_path": item.action_path,
        "status": item.status,
        "metrics": item.metrics,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def _database_items(db, user) -> list[dict[str, Any]]:
    return [
        _notification(item)
        for item in db.scalars(
            select(FinancialInsight)
                .where(
                    FinancialInsight.user_id == user.id,
                    FinancialInsight.status.in_(["active", "dismissed"]),
                )
            .order_by(FinancialInsight.updated_at.desc())
            .limit(50)
        )
    ]


def list_notifications(db, user) -> dict[str, Any]:
    """Return the owning customer's alert projection; SQL remains authoritative."""
    fallback = _database_items(db, user)
    if not enabled():
        return {"source": "database", "items": fallback}
    try:
        parent = f"{_firestore_base()}/agent_notifications/{_customer_key(user.id)}"
        result = _request(
            ":runQuery",
            {
                "parent": parent,
                "structuredQuery": {
                    "from": [{"collectionId": "items"}],
                    "where": {
                        "fieldFilter": {
                            "field": {"fieldPath": "status"},
                            "op": "IN",
                            "value": {"arrayValue": {"values": [_to_firestore("active"), _to_firestore("dismissed")] }},
                        }
                    },
                    "limit": 50,
                },
            },
        )
        items = [
            {key: _from_firestore(value) for key, value in row["document"].get("fields", {}).items()}
            for row in result
            if isinstance(row, dict) and isinstance(row.get("document"), dict)
        ]
        items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return {"source": "firestore", "items": items}
    except Exception as error:
        logger.warning("Firestore notification read failed (%s); using SQL projection.", type(error).__name__)
        return {"source": "database", "items": fallback}


def publish_run(factory, run_id: str) -> None:
    """Project committed alerts after SQL commit; delivery failure never rolls back banking work."""
    if not enabled():
        return
    with factory() as db:
        run = db.get(AgentRun, run_id)
        if not run or run.status != "completed":
            return
        items = db.scalars(
            select(FinancialInsight)
            .where(FinancialInsight.user_id == run.user_id)
            .order_by(FinancialInsight.updated_at.desc())
            .limit(50)
        ).all()
        customer_key = _customer_key(run.user_id)
        base = "https://firestore.googleapis.com/v1/" + _firestore_base()
        emulator = os.getenv("FIRESTORE_EMULATOR_HOST", "").strip()
        if emulator:
            base = "http://" + emulator.rstrip("/") + "/v1/" + _firestore_base()
        writes = []
        for item in items:
            writes.append(
                {
                    "update": {
                        "name": f"{base}/agent_notifications/{customer_key}/items/{item.id}",
                        "fields": {key: _to_firestore(value) for key, value in _notification(item).items()},
                    }
                }
            )
        if items:
            _request(":commit", {"writes": writes})
