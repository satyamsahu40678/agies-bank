from sqlalchemy import select, func
from .models import *
from .services.common import money, redact
from .auth import user_json


def iso(value):
    return (
        value.replace(tzinfo=timezone.utc).isoformat()
        if value.tzinfo is None
        else value.isoformat()
    )


def account_json(x):
    return {
        "id": x.id,
        "number": x.number,
        "balance": money(x.balance_paise),
        "currency": "INR",
        "status": x.status,
        "kyc_status": x.kyc_status,
    }


def beneficiary_json(x):
    return {
        "id": x.id,
        "name": x.name,
        "bank": x.bank,
        "account_last4": x.account_last4,
        "is_new": x.is_new,
    }


def event_json(x):
    return {
        k: getattr(x, k)
        for k in [
            "id",
            "kind",
            "city",
            "country",
            "latitude",
            "longitude",
            "ip_masked",
            "device",
            "is_new_device",
            "vpn",
            "risk_score",
            "signals",
        ]
    } | {"created_at": iso(x.created_at)}


def alert_json(x):
    return {
        k: getattr(x, k)
        for k in [
            "id",
            "case_id",
            "title",
            "message",
            "severity",
            "status",
            "recognized",
        ]
    } | {"created_at": iso(x.created_at)}


def audit_json(x):
    return {
        k: getattr(x, k)
        for k in ["id", "agent", "action", "risk_score", "tools", "trace_id"]
    } | {"summary": redact(x.summary), "created_at": iso(x.created_at)}


def case_json(db, x):
    user = db.get(User, x.user_id)
    return {
        k: getattr(x, k)
        for k in [
            "id",
            "kind",
            "status",
            "priority",
            "risk_score",
            "summary",
            "signals",
            "transfer_id",
            "kyc_id",
            "resolution_reason",
        ]
    } | {
        "customer_id": x.user_id,
        "customer_name": user.name,
        "amount": money(x.amount_paise),
        "created_at": iso(x.created_at),
    }


def transfer_json(db, x):
    case = db.scalar(select(FraudCase).where(FraudCase.transfer_id == x.id))
    b = db.get(Beneficiary, x.beneficiary_id)
    messages = {
        "posted": "Transfer completed securely.",
        "pending_step_up": "Confirm your password to authorize this transfer. This demo challenge stands in for production MFA.",
        "held": "Transfer held for analyst review. No funds have moved.",
        "rejected": "Transfer rejected. No funds have moved.",
    }
    return {
        k: getattr(x, k) for k in ["id", "status", "risk_score", "signals", "decision"]
    } | {
        "case_id": case.id if case else None,
        "message": messages[x.status],
        "amount": money(x.amount_paise),
        "beneficiary_name": b.name,
    }


def kyc_json(x):
    return {
        k: getattr(x, k)
        for k in ["id", "status", "risk_score", "reasons", "document_name"]
    } | {"created_at": iso(x.created_at), "decision": x.status}


def document_json(db, x):
    return {k: getattr(x, k) for k in ["id", "title", "kind", "filename"]} | {
        "chunk_count": db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == x.id)
        ),
        "created_at": iso(x.created_at),
    }


def transaction_json(x):
    return {
        k: getattr(x, k)
        for k in ["id", "direction", "description", "category", "status"]
    } | {
        "amount": money(x.amount_paise),
        "created_at": iso(x.created_at),
        "balance_after": money(x.balance_after_paise),
        "transfer_id": x.transfer_id,
    }
