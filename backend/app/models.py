"""Firestore domain records. No SQL engine or ORM is imported by the application."""

import uuid
from datetime import UTC, date, datetime, timezone
from typing import ClassVar

from .query import Field, Record


def uid():
    return uuid.uuid4().hex


def utcnow():
    return datetime.now(UTC)


class User(Record):
    __collection__ = "users"
    id: str = Field(default=uid, nullable=False, kind="str")
    name: str = Field(default=None, nullable=False, kind="str")
    email: str = Field(default=None, nullable=False, kind="str")
    role: str = Field(default="customer", nullable=False, kind="str")
    password_hash: str = Field(default=None, nullable=False, kind="str")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = [("email",)]
    __references__: ClassVar[dict[str, str]] = {}


class Account(Record):
    __collection__ = "accounts"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str | None = Field(default=None, nullable=True, kind="str | None")
    number: str = Field(default=None, nullable=False, kind="str")
    balance_paise: int = Field(default=0, nullable=False, kind="int")
    status: str = Field(default="active", nullable=False, kind="str")
    kyc_status: str = Field(default="not_started", nullable=False, kind="str")
    __unique__: ClassVar[list[tuple[str, ...]]] = [("user_id",), ("number",)]
    __references__: ClassVar[dict[str, str]] = {"user_id": "users.id"}


class AuthSession(Record):
    __collection__ = "auth_sessions"
    id: str = Field(default=None, nullable=False, kind="str")
    user_id: str = Field(default=None, nullable=False, kind="str")
    csrf_token: str = Field(default=None, nullable=False, kind="str")
    expires_at: datetime = Field(default=None, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = []
    __references__: ClassVar[dict[str, str]] = {"user_id": "users.id"}


class LoginAttempt(Record):
    __collection__ = "login_attempts"
    id: str = Field(default=uid, nullable=False, kind="str")
    key: str = Field(default=None, nullable=False, kind="str")
    success: bool = Field(default=False, nullable=False, kind="bool")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = []
    __references__: ClassVar[dict[str, str]] = {}


class Beneficiary(Record):
    __collection__ = "beneficiaries"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str = Field(default=None, nullable=False, kind="str")
    name: str = Field(default=None, nullable=False, kind="str")
    bank: str = Field(default=None, nullable=False, kind="str")
    account_last4: str = Field(default=None, nullable=False, kind="str")
    account_number_hash: str = Field(default=None, nullable=False, kind="str")
    is_new: bool = Field(default=True, nullable=False, kind="bool")
    __unique__: ClassVar[list[tuple[str, ...]]] = [("user_id", "account_number_hash")]
    __references__: ClassVar[dict[str, str]] = {"user_id": "users.id"}


class Transfer(Record):
    __collection__ = "transfers"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str = Field(default=None, nullable=False, kind="str")
    beneficiary_id: str = Field(default=None, nullable=False, kind="str")
    amount_paise: int = Field(default=None, nullable=False, kind="int")
    description: str = Field(default=None, nullable=False, kind="str")
    idempotency_key: str = Field(default=None, nullable=False, kind="str")
    fingerprint: str = Field(default=None, nullable=False, kind="str")
    status: str = Field(default=None, nullable=False, kind="str")
    risk_score: int = Field(default=None, nullable=False, kind="int")
    signals: list = Field(default=list, nullable=False, kind="list")
    decision: str = Field(default=None, nullable=False, kind="str")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = [("user_id", "idempotency_key")]
    __references__: ClassVar[dict[str, str]] = {
        "user_id": "users.id",
        "beneficiary_id": "beneficiaries.id",
    }


class LedgerEntry(Record):
    __collection__ = "ledger_entries"
    id: str = Field(default=uid, nullable=False, kind="str")
    account_id: str = Field(default=None, nullable=False, kind="str")
    amount_paise: int = Field(default=None, nullable=False, kind="int")
    direction: str = Field(default=None, nullable=False, kind="str")
    description: str = Field(default=None, nullable=False, kind="str")
    category: str = Field(default=None, nullable=False, kind="str")
    status: str = Field(default="posted", nullable=False, kind="str")
    balance_after_paise: int = Field(default=None, nullable=False, kind="int")
    transfer_id: str | None = Field(default=None, nullable=True, kind="str | None")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = [("transfer_id", "account_id")]
    __references__: ClassVar[dict[str, str]] = {
        "account_id": "accounts.id",
        "transfer_id": "transfers.id",
    }


class Budget(Record):
    __collection__ = "budgets"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str = Field(default=None, nullable=False, kind="str")
    category: str = Field(default=None, nullable=False, kind="str")
    limit_paise: int = Field(default=None, nullable=False, kind="int")
    __unique__: ClassVar[list[tuple[str, ...]]] = [("user_id", "category")]
    __references__: ClassVar[dict[str, str]] = {"user_id": "users.id"}


class SecurityEvent(Record):
    __collection__ = "security_events"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str = Field(default=None, nullable=False, kind="str")
    kind: str = Field(default=None, nullable=False, kind="str")
    city: str = Field(default=None, nullable=False, kind="str")
    country: str = Field(default=None, nullable=False, kind="str")
    latitude: float = Field(default=0.0, nullable=False, kind="float")
    longitude: float = Field(default=0.0, nullable=False, kind="float")
    ip_masked: str = Field(default=None, nullable=False, kind="str")
    device: str = Field(default=None, nullable=False, kind="str")
    is_new_device: bool = Field(default=None, nullable=False, kind="bool")
    vpn: bool = Field(default=None, nullable=False, kind="bool")
    risk_score: int = Field(default=None, nullable=False, kind="int")
    signals: list = Field(default=list, nullable=False, kind="list")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = []
    __references__: ClassVar[dict[str, str]] = {"user_id": "users.id"}


class KYCSubmission(Record):
    __collection__ = "kyc_submissions"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str = Field(default=None, nullable=False, kind="str")
    full_name: str = Field(default=None, nullable=False, kind="str")
    date_of_birth: str = Field(default=None, nullable=False, kind="str")
    id_last4: str = Field(default=None, nullable=False, kind="str")
    country: str = Field(default=None, nullable=False, kind="str")
    status: str = Field(default=None, nullable=False, kind="str")
    risk_score: int = Field(default=None, nullable=False, kind="int")
    reasons: list = Field(default=list, nullable=False, kind="list")
    document_name: str = Field(default=None, nullable=False, kind="str")
    document_hash: str = Field(default=None, nullable=False, kind="str")
    selfie_hash: str = Field(default=None, nullable=False, kind="str")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = []
    __references__: ClassVar[dict[str, str]] = {"user_id": "users.id"}


class FraudCase(Record):
    __collection__ = "fraud_cases"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str = Field(default=None, nullable=False, kind="str")
    kind: str = Field(default=None, nullable=False, kind="str")
    status: str = Field(default="open", nullable=False, kind="str")
    priority: str = Field(default=None, nullable=False, kind="str")
    risk_score: int = Field(default=None, nullable=False, kind="int")
    amount_paise: int = Field(default=0, nullable=False, kind="int")
    summary: str = Field(default=None, nullable=False, kind="str")
    signals: list = Field(default=list, nullable=False, kind="list")
    transfer_id: str | None = Field(default=None, nullable=True, kind="str | None")
    kyc_id: str | None = Field(default=None, nullable=True, kind="str | None")
    resolved_by: str | None = Field(default=None, nullable=True, kind="str | None")
    resolution_reason: str | None = Field(
        default=None, nullable=True, kind="str | None"
    )
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = [("transfer_id",), ("kyc_id",)]
    __references__: ClassVar[dict[str, str]] = {
        "user_id": "users.id",
        "transfer_id": "transfers.id",
        "kyc_id": "kyc_submissions.id",
        "resolved_by": "users.id",
    }


class Alert(Record):
    __collection__ = "alerts"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str = Field(default=None, nullable=False, kind="str")
    case_id: str | None = Field(default=None, nullable=True, kind="str | None")
    title: str = Field(default=None, nullable=False, kind="str")
    message: str = Field(default=None, nullable=False, kind="str")
    severity: str = Field(default=None, nullable=False, kind="str")
    status: str = Field(default="unread", nullable=False, kind="str")
    recognized: bool | None = Field(default=None, nullable=True, kind="bool | None")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = []
    __references__: ClassVar[dict[str, str]] = {
        "user_id": "users.id",
        "case_id": "fraud_cases.id",
    }


class Document(Record):
    __collection__ = "documents"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str | None = Field(default=None, nullable=True, kind="str | None")
    title: str = Field(default=None, nullable=False, kind="str")
    kind: str = Field(default=None, nullable=False, kind="str")
    filename: str = Field(default=None, nullable=False, kind="str")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = []
    __references__: ClassVar[dict[str, str]] = {"user_id": "users.id"}


class DocumentChunk(Record):
    __collection__ = "document_chunks"
    id: str = Field(default=uid, nullable=False, kind="str")
    document_id: str = Field(default=None, nullable=False, kind="str")
    text: str = Field(default=None, nullable=False, kind="str")
    page: int = Field(default=None, nullable=False, kind="int")
    __unique__: ClassVar[list[tuple[str, ...]]] = []
    __references__: ClassVar[dict[str, str]] = {"document_id": "documents.id"}


class ChatMessage(Record):
    __collection__ = "chat_messages"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str = Field(default=None, nullable=False, kind="str")
    role: str = Field(default=None, nullable=False, kind="str")
    content: str = Field(default=None, nullable=False, kind="str")
    agent: str = Field(default=None, nullable=False, kind="str")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = []
    __references__: ClassVar[dict[str, str]] = {"user_id": "users.id"}


class AuditLog(Record):
    __collection__ = "audit_logs"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str | None = Field(default=None, nullable=True, kind="str | None")
    agent: str = Field(default=None, nullable=False, kind="str")
    action: str = Field(default=None, nullable=False, kind="str")
    summary: str = Field(default=None, nullable=False, kind="str")
    risk_score: int | None = Field(default=None, nullable=True, kind="int | None")
    tools: list = Field(default=list, nullable=False, kind="list")
    trace_id: str = Field(default=uid, nullable=False, kind="str")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = []
    __references__: ClassVar[dict[str, str]] = {"user_id": "users.id"}


class SavingsGoal(Record):
    __collection__ = "savings_goals"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str = Field(default=None, nullable=False, kind="str")
    name: str = Field(default=None, nullable=False, kind="str")
    target_paise: int = Field(default=None, nullable=False, kind="int")
    saved_paise: int = Field(default=0, nullable=False, kind="int")
    target_date: date | None = Field(default=None, nullable=True, kind="date | None")
    status: str = Field(default="active", nullable=False, kind="str")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    updated_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = []
    __references__: ClassVar[dict[str, str]] = {"user_id": "users.id"}


class AgentRun(Record):
    __collection__ = "agent_runs"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str = Field(default=None, nullable=False, kind="str")
    kind: str = Field(default="financial_health", nullable=False, kind="str")
    trigger: str = Field(default=None, nullable=False, kind="str")
    dedup_key: str = Field(default=None, nullable=False, kind="str")
    status: str = Field(default="queued", nullable=False, kind="str")
    attempts: int = Field(default=0, nullable=False, kind="int")
    max_attempts: int = Field(default=3, nullable=False, kind="int")
    manual_retries: int = Field(default=0, nullable=False, kind="int")
    available_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    lease_expires_at: datetime | None = Field(
        default=None, nullable=True, kind="datetime | None"
    )
    lease_token: str | None = Field(default=None, nullable=True, kind="str | None")
    trace_id: str = Field(default=uid, nullable=False, kind="str")
    tools: list = Field(default=list, nullable=False, kind="list")
    decisions: list = Field(default=list, nullable=False, kind="list")
    output: dict = Field(default=dict, nullable=False, kind="dict")
    error: str | None = Field(default=None, nullable=True, kind="str | None")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    started_at: datetime | None = Field(
        default=None, nullable=True, kind="datetime | None"
    )
    completed_at: datetime | None = Field(
        default=None, nullable=True, kind="datetime | None"
    )
    __unique__: ClassVar[list[tuple[str, ...]]] = [("user_id", "dedup_key")]
    __references__: ClassVar[dict[str, str]] = {"user_id": "users.id"}


class FinancialInsight(Record):
    __collection__ = "financial_insights"
    id: str = Field(default=uid, nullable=False, kind="str")
    user_id: str = Field(default=None, nullable=False, kind="str")
    run_id: str = Field(default=None, nullable=False, kind="str")
    kind: str = Field(default=None, nullable=False, kind="str")
    key: str = Field(default=None, nullable=False, kind="str")
    fingerprint: str = Field(default=None, nullable=False, kind="str")
    severity: str = Field(default=None, nullable=False, kind="str")
    title: str = Field(default=None, nullable=False, kind="str")
    message: str = Field(default=None, nullable=False, kind="str")
    action_label: str = Field(default=None, nullable=False, kind="str")
    action_path: str = Field(default=None, nullable=False, kind="str")
    status: str = Field(default="active", nullable=False, kind="str")
    metrics: dict = Field(default=dict, nullable=False, kind="dict")
    created_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    updated_at: datetime = Field(default=utcnow, nullable=False, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = [("user_id", "kind", "key")]
    __references__: ClassVar[dict[str, str]] = {
        "user_id": "users.id",
        "run_id": "agent_runs.id",
    }


class Automation(Record):
    __collection__ = "automations"
    id: str = Field(default=uid)
    user_id: str = Field()
    kind: str = Field()
    name: str = Field()
    enabled: bool = Field(default=True, kind="bool")
    interval_hours: int = Field(default=24, kind="int")
    next_run_at: datetime = Field(default=utcnow, kind="datetime")
    last_run_id: str | None = Field(nullable=True)
    created_at: datetime = Field(default=utcnow, kind="datetime")
    updated_at: datetime = Field(default=utcnow, kind="datetime")
    __unique__: ClassVar[list[tuple[str, ...]]] = [("user_id", "kind")]
    __references__: ClassVar[dict[str, str]] = {"user_id": "users.id"}


__all__ = [
    name
    for name, value in list(globals().items())
    if isinstance(value, type) and issubclass(value, Record) and value is not Record
] + ["uid", "utcnow", "date", "datetime", "timezone"]
