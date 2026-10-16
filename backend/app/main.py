from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
import io
import os
import re
import hashlib
import secrets
from decimal import Decimal
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response,
    UploadFile,
    File,
    Form,
)
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, func, or_, update, text, case
from sqlalchemy.exc import IntegrityError
from PIL import Image, UnidentifiedImageError
from . import config
from .db import Base, engine, get_db, SessionLocal
from .models import *
from .auth import *
from .serializers import *
from .services.common import paise, money, audit
from .services.workflows import *
from .seed import seed_demo


@asynccontextmanager
async def lifespan(app):
    config.validate_configuration()
    if config.PRODUCTION:
        with engine.connect() as conn:
            try:
                current = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                from alembic.config import Config as AlembicConfig
                from alembic.script import ScriptDirectory

                expected = ScriptDirectory.from_config(
                    AlembicConfig(str(config.ROOT / "alembic.ini"))
                ).get_current_head()
                if current != expected:
                    raise RuntimeError(
                        "Database migration required; run python -m app.manage migrate"
                    )
            except Exception as exc:
                raise RuntimeError(
                    "Database is not migrated; run python -m app.manage migrate"
                ) from exc
    else:
        Base.metadata.create_all(engine)
        from .immutability import install_guards

        with engine.begin() as connection:
            install_guards(connection)
    with SessionLocal() as db:
        if config.PRODUCTION and db.scalar(
            select(User.id)
            .where(User.email.in_(["customer@aegis.demo", "analyst@aegis.demo"]))
            .limit(1)
        ):
            raise RuntimeError(
                "Production database contains synthetic demo identities. Provision a clean production database; existing records have been preserved."
            )
        if config.DEMO_ENABLED:
            seed_demo(db)
        elif not db.scalar(
            select(Account).where(Account.number == "INTERNAL_CLEARING")
        ):
            db.add(
                Account(
                    number="INTERNAL_CLEARING",
                    user_id=None,
                    balance_paise=0,
                    status="active",
                    kyc_status="approved",
                )
            )
            db.commit()
    from .services.proactive import start_worker

    worker = start_worker(factory=SessionLocal)
    app.state.proactive_worker = worker
    try:
        yield
    finally:
        worker.stop()


app = FastAPI(title="AegisBank API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    length = request.headers.get("content-length")
    if length and (
        not length.isdigit() or int(length) > 2 * config.MAX_UPLOAD + 64 * 1024
    ):
        return __import__(
            "starlette.responses", fromlist=["JSONResponse"]
        ).JSONResponse({"detail": "Request too large"}, 413)
    if request.method in {"POST", "PUT", "PATCH"}:
        limit = (
            2 * config.MAX_UPLOAD + 64 * 1024
            if request.headers.get("content-type", "").startswith("multipart/")
            else 64 * 1024
        )
        chunks = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                from starlette.responses import JSONResponse

                return JSONResponse({"detail": "Request too large"}, 413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    if config.PRODUCTION:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        v = v.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", v):
            raise ValueError("Enter a valid email address")
        return v


class Register(Login):
    name: str = Field(min_length=2, max_length=100)

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must contain at least two non-space characters")
        return v

    @field_validator("password")
    @classmethod
    def strong_password(cls, v):
        if len(v) < 12 or not all(
            re.search(pattern, v)
            for pattern in ["[a-z]", "[A-Z]", "[0-9]", r"[^A-Za-z0-9]"]
        ):
            raise ValueError(
                "Use at least 12 characters with upper/lowercase, a number and a symbol"
            )
        return v


class BeneficiaryInput(Input):
    name: str = Field(min_length=2, max_length=100)
    bank: str = Field(min_length=2, max_length=100)
    account_number: str = Field(min_length=6, max_length=40)

    @field_validator("name", "bank")
    @classmethod
    def nonempty_identity(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError(
                "Name and bank must contain at least two non-space characters"
            )
        return v


class TransferInput(Input):
    beneficiary_id: str = Field(min_length=1, max_length=32)
    amount: Decimal
    description: str = Field(default="", max_length=200)
    idempotency_key: str = Field(min_length=8, max_length=100)


class PasswordInput(Input):
    password: str = Field(min_length=1, max_length=128)


class AlertInput(Input):
    recognized: bool


class SimulatorInput(Input):
    scenario: str


class BudgetInput(Input):
    limit_amount: Decimal


class ChatInput(Input):
    message: str = Field(min_length=1, max_length=4000)


class QueryInput(Input):
    question: str = Field(min_length=1, max_length=2000)
    document_id: str | None = Field(default=None, max_length=32)


class EMIInput(Input):
    principal: Decimal
    annual_rate: Decimal = Field(ge=0, le=50)
    tenure_months: int = Field(ge=1, le=360)


class ResolutionInput(Input):
    decision: str
    reason: str = Field(min_length=5, max_length=500)


class StatusInput(Input):
    status: str
    reason: str = Field(min_length=5, max_length=500)


class GoalInput(Input):
    name: str = Field(min_length=2, max_length=100)
    target_amount: Decimal
    saved_amount: Decimal = Decimal("0")
    target_date: str | None = Field(default=None, max_length=10)


class GoalUpdateInput(Input):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    target_amount: Decimal | None = None
    saved_amount: Decimal | None = None
    target_date: str | None = Field(default=None, max_length=10)
    status: str | None = Field(default=None, max_length=20)


def queue_financial_review(db, user, trigger, *, stale_only=False, dedup_key=None):
    if user.role == "customer":
        from .services.proactive import enqueue_health_check

        return enqueue_health_check(
            db,
            user,
            trigger,
            dedup_key=dedup_key or (None if stale_only else uid()),
            stale_only=stale_only,
        )


@app.get("/api/health")
def health(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": "connected",
        "ai_mode": config.resolve_ai_mode(),
        "demo_enabled": config.DEMO_ENABLED,
        "kyc_mode": config.resolve_kyc_mode(),
        "proactive_agents": "enabled",
    }


@app.post("/api/auth/login")
def login(payload: Login, request: Request, response: Response, db=Depends(get_db)):
    origin_check(request)
    keys = throttle_login(db, request, payload.email)
    user = db.scalar(select(User).where(User.email == payload.email))
    success = verify_password(
        payload.password, user.password_hash if user else DUMMY_HASH
    )
    for key in keys:
        db.add(LoginAttempt(key=key, success=bool(user and success)))
    if not user or not success:
        db.commit()
        raise HTTPException(401, "Email or password is incorrect")
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    result = create_session(db, user, request, response)
    login_event(db, user, request)
    audit(
        db,
        user.id,
        "orchestrator",
        "session_started",
        "Authenticated session created",
        ["authenticate"],
    )
    queue_financial_review(db, user, "login", stale_only=True)
    db.commit()
    return result


@app.post("/api/auth/register", status_code=201)
def register(
    payload: Register, request: Request, response: Response, db=Depends(get_db)
):
    origin_check(request)
    if not config.DEMO_ENABLED and payload.email.endswith("@aegis.demo"):
        raise HTTPException(
            422, "The aegis.demo email domain is reserved for synthetic demo identities"
        )
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(409, "An account with that email already exists")
    user = User(
        name=payload.name.strip(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="customer",
    )
    db.add(user)
    db.flush()
    db.add(
        Account(
            user_id=user.id,
            number="AEGIS" + secrets.token_hex(6).upper(),
            balance_paise=0,
            status="active",
            kyc_status="not_started",
        )
    )
    result = create_session(db, user, request, response)
    audit(
        db,
        user.id,
        "orchestrator",
        "account_created",
        "Customer account opened with zero balance",
        ["register"],
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with that email already exists")
    return result


@app.get("/api/auth/me")
def me(request: Request, user=Depends(session_user)):
    return {
        "user": user_json(user),
        "csrf_token": request.state.auth_session.csrf_token,
    }


@app.post("/api/auth/logout")
def logout(
    request: Request, response: Response, user=Depends(session_user), db=Depends(get_db)
):
    db.delete(request.state.auth_session)
    audit(
        db,
        user.id,
        "orchestrator",
        "session_ended",
        "Authenticated session revoked",
        ["logout"],
    )
    db.commit()
    response.delete_cookie("aegis_session", path="/")
    return {"ok": True}


def spending_for(db, account):
    cutoff = utcnow() - timedelta(days=30)
    conditions = (
        LedgerEntry.account_id == account.id,
        LedgerEntry.created_at >= cutoff,
        LedgerEntry.status == "posted",
    )
    row = db.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (LedgerEntry.direction == "credit", LedgerEntry.amount_paise),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (LedgerEntry.direction == "debit", LedgerEntry.amount_paise),
                        else_=0,
                    )
                ),
                0,
            ),
        ).where(*conditions)
    ).one()
    income, expenses = int(row[0]), int(row[1])
    category = func.lower(func.trim(LedgerEntry.category))
    grouped = db.execute(
        select(category, func.sum(LedgerEntry.amount_paise))
        .where(*conditions, LedgerEntry.direction == "debit")
        .group_by(category)
    ).all()
    return {
        "income": money(income),
        "expenses": money(expenses),
        "savings_rate": round((income - expenses) / income * 100, 1) if income else 0,
        "categories": [
            {"category": category, "amount": money(int(amount))}
            for category, amount in sorted(grouped, key=lambda entry: -entry[1])
        ],
    }


def budgets_for(db, user):
    account = account_for(db, user.id)
    categories = {
        e["category"]: e["amount"] for e in spending_for(db, account)["categories"]
    }
    return [
        {
            "id": b.id,
            "category": b.category,
            "limit_amount": money(b.limit_paise),
            "spent": categories.get(b.category, "0.00"),
        }
        for b in db.scalars(
            select(Budget).where(Budget.user_id == user.id).order_by(Budget.category)
        ).all()
    ]


def transactions_for(db, user, limit=100):
    account = account_for(db, user.id)
    rows = [
        transaction_json(e)
        for e in db.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.account_id == account.id)
            .order_by(LedgerEntry.created_at.desc())
            .limit(limit)
        ).all()
    ]
    pending = db.scalars(
        select(Transfer)
        .where(Transfer.user_id == user.id, Transfer.status != "posted")
        .order_by(Transfer.created_at.desc())
        .limit(limit)
    ).all()
    rows.extend(
        {
            "id": t.id,
            "amount": money(t.amount_paise),
            "direction": "debit",
            "description": t.description
            or f"Transfer to {db.get(Beneficiary, t.beneficiary_id).name}",
            "category": "transfer",
            "status": t.status,
            "created_at": iso(t.created_at),
            "balance_after": money(account.balance_paise),
            "transfer_id": t.id,
        }
        for t in pending
    )
    return sorted(rows, key=lambda x: x["created_at"], reverse=True)[:limit]


@app.get("/api/overview")
def overview(user=Depends(customer), db=Depends(get_db)):
    account = account_for(db, user.id)
    return {
        "user": user_json(user),
        "account": account_json(account),
        "spending": spending_for(db, account),
        "transactions": transactions_for(db, user, 20),
        "alerts": [
            alert_json(a)
            for a in db.scalars(
                select(Alert)
                .where(Alert.user_id == user.id)
                .order_by(Alert.created_at.desc())
                .limit(20)
            )
        ],
        "budgets": budgets_for(db, user),
        "agent_activity": [
            audit_json(a)
            for a in db.scalars(
                select(AuditLog)
                .where(AuditLog.user_id == user.id)
                .order_by(AuditLog.created_at.desc())
                .limit(10)
            )
        ],
    }


@app.get("/api/transactions")
def transactions(user=Depends(customer), db=Depends(get_db)):
    return transactions_for(db, user)


@app.get("/api/beneficiaries")
def beneficiaries(user=Depends(customer), db=Depends(get_db)):
    return [
        beneficiary_json(b)
        for b in db.scalars(
            select(Beneficiary)
            .where(Beneficiary.user_id == user.id)
            .order_by(Beneficiary.name)
            .limit(100)
        )
    ]


@app.post("/api/beneficiaries", status_code=201)
def add_beneficiary(
    payload: BeneficiaryInput, user=Depends(customer), db=Depends(get_db)
):
    number = payload.account_number.replace(" ", "")
    if not number.isdigit() or not 6 <= len(number) <= 34:
        raise HTTPException(422, "Account number must contain 6 to 34 digits")
    b = Beneficiary(
        user_id=user.id,
        name=payload.name.strip(),
        bank=payload.bank.strip(),
        account_last4=number[-4:],
        account_number_hash=account_hash(number),
        is_new=True,
    )
    db.add(b)
    audit(
        db,
        user.id,
        "banking_agent",
        "beneficiary_created",
        "New beneficiary added; account number stored only as a keyed hash and last four digits",
        ["beneficiary_create"],
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This beneficiary account already exists")
    return beneficiary_json(b)


@app.post("/api/transfers")
def transfers(payload: TransferInput, user=Depends(customer), db=Depends(get_db)):
    try:
        transfer = create_transfer(
            db,
            user,
            payload.beneficiary_id,
            paise(payload.amount),
            payload.description.strip(),
            payload.idempotency_key,
        )
        queue_financial_review(db, user, "transfer_created", dedup_key=transfer.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        transfer = db.scalar(
            select(Transfer).where(
                Transfer.user_id == user.id,
                Transfer.idempotency_key == payload.idempotency_key,
            )
        )
        fingerprint = hashlib.sha256(
            f"{payload.beneficiary_id}:{paise(payload.amount)}:{payload.description.strip()}".encode()
        ).hexdigest()
        if not transfer or transfer.fingerprint != fingerprint:
            raise HTTPException(409, "Idempotency conflict")
    return transfer_json(db, transfer)


@app.post("/api/transfers/{transfer_id}/step-up")
def step_up(
    transfer_id: str,
    payload: PasswordInput,
    request: Request,
    user=Depends(customer),
    db=Depends(get_db),
):
    keys = throttle_login(db, request, user.email)
    valid = verify_password(payload.password, user.password_hash)
    for key in keys:
        db.add(LoginAttempt(key=key, success=valid))
    if not valid:
        db.commit()
        raise HTTPException(401, "Password confirmation failed")
    transfer = db.scalar(
        select(Transfer).where(Transfer.id == transfer_id, Transfer.user_id == user.id)
    )
    if not transfer:
        raise HTTPException(404, "Transfer not found")
    if transfer.status == "posted":
        return transfer_json(db, transfer)
    changed = db.execute(
        update(Transfer)
        .where(Transfer.id == transfer_id, Transfer.status == "pending_step_up")
        .values(status="posted")
    ).rowcount
    if not changed:
        raise HTTPException(409, "This transfer is not awaiting step-up")
    db.refresh(transfer)
    beneficiary = db.get(Beneficiary, transfer.beneficiary_id)
    score, signals = transfer_risk(db, user, beneficiary, transfer.amount_paise)
    transfer.risk_score = max(score, transfer.risk_score)
    transfer.signals = signals
    if transfer.risk_score >= 70:
        transfer.status = "held"
        transfer.decision = "analyst_review"
        case = FraudCase(
            user_id=user.id,
            kind="transfer",
            priority="high",
            risk_score=transfer.risk_score,
            amount_paise=transfer.amount_paise,
            summary="Transfer context escalated after step-up proposal; analyst review required",
            signals=signals,
            transfer_id=transfer.id,
        )
        db.add(case)
        db.flush()
        db.add(
            Alert(
                user_id=user.id,
                case_id=case.id,
                title="Transfer risk increased",
                message="New security context requires analyst review. No funds moved.",
                severity="high",
            )
        )
        audit(
            db,
            user.id,
            "fraud_agent",
            "step_up_escalated",
            "Risk was reevaluated and elevated to analyst review before settlement",
            ["risk_score", "policy_gate"],
            transfer.risk_score,
        )
        db.commit()
        return transfer_json(db, transfer)
    settle(db, transfer)
    transfer.decision = "step_up_verified"
    queue_financial_review(db, user, "transfer_settled", dedup_key=transfer.id)
    audit(
        db,
        user.id,
        "fraud_agent",
        "step_up_verified",
        "Demo password challenge passed; transfer policy and balances rechecked",
        ["password_challenge", "policy_gate"],
        transfer.risk_score,
    )
    db.commit()
    return transfer_json(db, transfer)


@app.get("/api/events")
def events(user=Depends(customer), db=Depends(get_db)):
    return [
        event_json(e)
        for e in db.scalars(
            select(SecurityEvent)
            .where(SecurityEvent.user_id == user.id)
            .order_by(SecurityEvent.created_at.desc())
            .limit(100)
        )
    ]


@app.post("/api/alerts/{alert_id}/respond")
def respond_alert(
    alert_id: str, payload: AlertInput, user=Depends(customer), db=Depends(get_db)
):
    alert = db.scalar(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id)
    )
    if not alert:
        raise HTTPException(404, "Alert not found")
    if alert.status == "responded":
        raise HTTPException(409, "Alert has already been answered")
    alert.recognized = payload.recognized
    alert.status = "responded"
    if not payload.recognized:
        account_for(db, user.id).status = "frozen"
        if alert.case_id:
            case = db.get(FraudCase, alert.case_id)
            case.summary = (case.summary + " · Customer reports activity unrecognized")[
                :500
            ]
    audit(
        db,
        user.id,
        "fraud_agent",
        "customer_alert_response",
        "Customer recognized activity"
        if payload.recognized
        else "Customer denied activity; account frozen pending analyst review",
        ["customer_confirmation", "account_freeze"],
    )
    db.commit()
    return alert_json(alert)


@app.post("/api/simulator/events")
def simulate(payload: SimulatorInput, user=Depends(customer), db=Depends(get_db)):
    if not config.DEMO_ENABLED:
        raise HTTPException(403, "Simulator is disabled outside demo environments")
    allowed = {
        "routine_login",
        "impossible_travel",
        "vpn_login",
        "large_transfer",
        "velocity_burst",
    }
    if payload.scenario not in allowed:
        raise HTTPException(422, "Unknown simulator scenario")
    event = case = transfer = None
    if payload.scenario in {"routine_login", "impossible_travel", "vpn_login"}:
        event, case = synthetic_event(db, user, payload.scenario)
    else:
        b = db.scalar(
            select(Beneficiary)
            .where(Beneficiary.user_id == user.id)
            .order_by(Beneficiary.is_new, Beneficiary.name)
        )
        if not b:
            raise HTTPException(409, "Add a beneficiary before simulating a transfer")
        if payload.scenario == "large_transfer":
            transfer = create_transfer(
                db, user, b.id, 12_500_000, "Synthetic high-value transfer", uid()
            )
        else:
            for _ in range(6):
                transfer = create_transfer(
                    db, user, b.id, 100_00, "Synthetic velocity burst", uid()
                )
        case = db.scalar(select(FraudCase).where(FraudCase.transfer_id == transfer.id))
    db.commit()
    return {
        "event": event_json(event) if event else None,
        "transfer": transfer_json(db, transfer) if transfer else None,
        "case": case_json(db, case) if case else None,
        "message": "Synthetic scenario processed through server policy, audit and risk controls.",
    }


@app.get("/api/budgets")
def get_budgets(user=Depends(customer), db=Depends(get_db)):
    return budgets_for(db, user)


@app.put("/api/budgets/{category}")
def put_budget(
    category: str, payload: BudgetInput, user=Depends(customer), db=Depends(get_db)
):
    if not re.fullmatch(r"[a-z][a-z_ ]{1,49}", category):
        raise HTTPException(
            422, "Category must be 2 to 50 lowercase letters, spaces or underscores"
        )
    b = db.scalar(
        select(Budget).where(Budget.user_id == user.id, Budget.category == category)
    )
    if not b:
        b = Budget(
            user_id=user.id,
            category=category,
            limit_paise=paise(payload.limit_amount, allow_zero=True),
        )
        db.add(b)
    else:
        b.limit_paise = paise(payload.limit_amount, allow_zero=True)
    audit(
        db,
        user.id,
        "banking_agent",
        "budget_updated",
        f"{category} monthly budget updated",
        ["budget_update"],
    )
    queue_financial_review(db, user, "budget_updated")
    db.commit()
    return next(x for x in budgets_for(db, user) if x["category"] == category)


@app.get("/api/chat")
def get_chat(user=Depends(customer), db=Depends(get_db)):
    messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "agent": m.agent,
            "created_at": iso(m.created_at),
        }
        for m in reversed(messages)
    ]


@app.post("/api/chat")
def post_chat(payload: ChatInput, user=Depends(customer), db=Depends(get_db)):
    from .services.intelligence import chat

    result = chat(db, user, payload.message)
    db.commit()
    return result


@app.get("/api/recommendations")
def get_recommendations(user=Depends(customer), db=Depends(get_db)):
    from .services.intelligence import recommendations

    result = recommendations(db, user)
    db.commit()
    return result


@app.post("/api/recommendations/calculate")
def calculate(payload: EMIInput, user=Depends(customer), db=Depends(get_db)):
    from .services.intelligence import calculate_emi

    paise(payload.principal)
    result = calculate_emi(db, user, payload.model_dump())
    db.commit()
    return result


KYC_DISCLAIMER = "Identity and sanctions decisions use synthetic rules. No live identity, biometric face matching, liveness or sanctions provider is connected."


def kyc_disclaimer():
    mode = config.resolve_kyc_mode()
    provider = "OpenAI" if mode == "openai" else "Claude"
    return KYC_DISCLAIMER + (
        f" {provider} checks limited image quality, person presence and printed-name consistency; this does not verify legal identity."
        if mode != "local"
        else " Local mode validates file formats and submitted fields only; it performs no image recognition."
    )


@app.get("/api/kyc")
def get_kyc(user=Depends(customer), db=Depends(get_db)):
    return {
        "status": account_for(db, user.id).kyc_status,
        "submissions": [
            kyc_json(x)
            for x in db.scalars(
                select(KYCSubmission)
                .where(KYCSubmission.user_id == user.id)
                .order_by(KYCSubmission.created_at.desc())
                .limit(50)
            )
        ],
        "disclaimer": kyc_disclaimer(),
    }


async def bounded_file(file):
    data = await file.read(config.MAX_UPLOAD + 1)
    await file.close()
    if not data:
        raise HTTPException(422, "Uploaded file is empty")
    if len(data) > config.MAX_UPLOAD:
        raise HTTPException(413, "Each file must be at most 5 MiB")
    name = Path(file.filename or "upload").name[:200]
    return name, data


def verify_image(name, data):
    if not data.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"RIFF")):
        raise HTTPException(422, "Images must be genuine PNG, JPEG or WebP files")
    try:
        Image.MAX_IMAGE_PIXELS = 20_000_000
        with Image.open(io.BytesIO(data)) as image:
            if (
                image.format not in {"PNG", "JPEG", "WEBP"}
                or image.width * image.height > 20_000_000
            ):
                raise ValueError("Unsupported image")
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "Image content is invalid or exceeds safe dimensions")


@app.post("/api/kyc", status_code=201)
async def submit_kyc(
    full_name: str = Form(..., min_length=2, max_length=100),
    date_of_birth: str = Form(...),
    id_number: str = Form(..., min_length=6, max_length=30),
    country: str = Form(..., min_length=2, max_length=50),
    document: UploadFile = File(...),
    selfie: UploadFile = File(...),
    user=Depends(customer),
    db=Depends(get_db),
):
    try:
        born = date.fromisoformat(date_of_birth)
        age = (date.today() - born).days // 365
        if not 0 <= age <= 120:
            raise ValueError()
    except ValueError:
        raise HTTPException(422, "Enter a valid birth date")
    if not re.fullmatch("[A-Za-z0-9 -]{6,30}", id_number):
        raise HTTPException(422, "Identity number format is invalid")
    doc_name, doc_data = await bounded_file(document)
    selfie_name, selfie_data = await bounded_file(selfie)
    await run_in_threadpool(verify_image, selfie_name, selfie_data)
    if doc_data.startswith(b"%PDF-"):
        from .services.intelligence import extract_document

        await run_in_threadpool(
            extract_document,
            doc_name if doc_name.lower().endswith(".pdf") else "identity.pdf",
            doc_data,
        )
    else:
        await run_in_threadpool(verify_image, doc_name, doc_data)
    normalized = re.sub(r"\W+", "", full_name).lower()
    own = re.sub(r"\W+", "", user.name).lower()
    from .services.intelligence import assess_kyc_evidence

    vision = await run_in_threadpool(
        assess_kyc_evidence, full_name, doc_name, doc_data, selfie_name, selfie_data
    )
    risk = vision["risk_score"]
    reasons = [
        "Document format and image validity checks passed. Sanctions and identity rules use synthetic adapters."
    ] + vision["reasons"]
    if normalized != own:
        risk += 30
        reasons.append("Submitted name differs from the account profile")
    if age < 18:
        risk += 90
        reasons.append("Applicant is below the supported adult age")
    if country.upper() not in {"IN", "INDIA"}:
        risk += 30
        reasons.append("Non-resident identity requires manual review")
    if "sanction" in full_name.lower() or id_number.upper().startswith("TESTBLOCK"):
        risk += 85
        reasons.append(
            "Synthetic sanctions test fixture matched; analyst review required"
        )
    status = "review" if risk >= 30 or vision["requires_review"] else "approved"
    risk = min(risk, 100)
    submission = KYCSubmission(
        user_id=user.id,
        full_name=full_name,
        date_of_birth=date_of_birth,
        id_last4=id_number[-4:],
        country=country.upper(),
        status=status,
        risk_score=risk,
        reasons=reasons,
        document_name=doc_name,
        document_hash=hashlib.sha256(doc_data).hexdigest(),
        selfie_hash=hashlib.sha256(selfie_data).hexdigest(),
    )
    db.add(submission)
    db.flush()
    account_for(db, user.id).kyc_status = status
    if status == "review":
        db.add(
            FraudCase(
                user_id=user.id,
                kind="kyc",
                priority="high" if risk >= 70 else "medium",
                risk_score=risk,
                summary="Identity requires analyst approval based on synthetic risk rules",
                signals=[
                    {"name": "identity_risk", "score": risk, "detail": r}
                    for r in reasons[1:]
                ],
                kyc_id=submission.id,
            )
        )
    audit(
        db,
        user.id,
        "identity_agent",
        "kyc_submitted",
        f"Identity evidence hashes retained; risk {risk}/100, decision {status}. Raw identity images are not retained.",
        ["document_format", "synthetic_sanctions", "identity_policy"],
        risk,
    )
    queue_financial_review(db, user, "kyc_updated")
    db.commit()
    return kyc_json(submission) | {
        "disclaimer": kyc_disclaimer(),
        "vision_mode": vision["mode"],
    }


@app.get("/api/documents")
def list_documents(user=Depends(customer), db=Depends(get_db)):
    return [
        document_json(db, d)
        for d in db.scalars(
            select(Document)
            .where(or_(Document.user_id == user.id, Document.user_id.is_(None)))
            .order_by(Document.created_at.desc())
            .limit(100)
        )
    ]


@app.post("/api/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=150),
    user=Depends(customer),
    db=Depends(get_db),
):
    from .services.intelligence import extract_document

    name, data = await bounded_file(file)
    chunks = await run_in_threadpool(extract_document, name, data)
    if (
        not chunks
        or sum(len(c["text"]) for c in chunks) > 2_000_000
        or len(chunks) > 2000
    ):
        raise HTTPException(
            422, "Document has no usable text or exceeds extraction limits"
        )
    doc = Document(
        user_id=user.id,
        title=(title or name).strip()[:150],
        kind="uploaded",
        filename=name,
    )
    db.add(doc)
    db.flush()
    for c in chunks:
        db.add(DocumentChunk(document_id=doc.id, text=c["text"], page=c["page"]))
    audit(
        db,
        user.id,
        "document_agent",
        "document_indexed",
        f"Private document indexed into {len(chunks)} scoped passages",
        ["text_extraction", "scoped_index"],
    )
    queue_financial_review(db, user, "document_uploaded")
    db.commit()
    return document_json(db, doc)


@app.post("/api/documents/query")
def query_document(payload: QueryInput, user=Depends(customer), db=Depends(get_db)):
    from .services.intelligence import query_documents

    result = query_documents(db, user, payload.question, payload.document_id)
    db.commit()
    return result


@app.get("/api/audit")
def customer_audit(user=Depends(customer), db=Depends(get_db)):
    return [
        audit_json(a)
        for a in db.scalars(
            select(AuditLog)
            .where(AuditLog.user_id == user.id)
            .order_by(AuditLog.created_at.desc())
            .limit(200)
        )
    ]


@app.get("/api/analyst/overview")
def analyst_overview(user=Depends(analyst), db=Depends(get_db)):
    cases = db.scalars(
        select(FraudCase).order_by(FraudCase.created_at.desc()).limit(100)
    ).all()
    return {
        "metrics": {
            "open_cases": db.scalar(
                select(func.count())
                .select_from(FraudCase)
                .where(FraudCase.status == "open")
            ),
            "held_amount": money(
                db.scalar(
                    select(func.coalesce(func.sum(Transfer.amount_paise), 0)).where(
                        Transfer.status == "held"
                    )
                )
            ),
            "kyc_pending": db.scalar(
                select(func.count())
                .select_from(KYCSubmission)
                .where(KYCSubmission.status == "review")
            ),
            "frozen_accounts": db.scalar(
                select(func.count())
                .select_from(Account)
                .where(Account.status == "frozen")
            ),
        },
        "cases": [case_json(db, c) for c in cases],
        "recent_audit": [
            audit_json(a)
            for a in db.scalars(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(30)
            )
        ],
    }


@app.get("/api/analyst/cases")
def analyst_cases(user=Depends(analyst), db=Depends(get_db)):
    return [
        case_json(db, c)
        for c in db.scalars(
            select(FraudCase).order_by(FraudCase.created_at.desc()).limit(100)
        )
    ]


@app.get("/api/analyst/cases/{case_id}")
def analyst_case(case_id: str, user=Depends(analyst), db=Depends(get_db)):
    case = db.get(FraudCase, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    customer_user = db.get(User, case.user_id)
    return {
        "case": case_json(db, case),
        "customer": {
            "id": customer_user.id,
            "name": customer_user.name,
            "email": customer_user.email,
        },
        "account": account_json(account_for(db, case.user_id)),
        "events": [
            event_json(e)
            for e in db.scalars(
                select(SecurityEvent)
                .where(SecurityEvent.user_id == case.user_id)
                .order_by(SecurityEvent.created_at.desc())
                .limit(30)
            )
        ],
        "audit": [
            audit_json(a)
            for a in db.scalars(
                select(AuditLog)
                .where(AuditLog.user_id == case.user_id)
                .order_by(AuditLog.created_at.desc())
                .limit(100)
            )
        ],
    }


@app.post("/api/analyst/cases/{case_id}/resolve")
def resolve_case(
    case_id: str, payload: ResolutionInput, user=Depends(analyst), db=Depends(get_db)
):
    if payload.decision not in {"approve", "reject"}:
        raise HTTPException(422, "Decision must be approve or reject")
    case = db.get(FraudCase, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    result = db.execute(
        update(FraudCase)
        .where(FraudCase.id == case.id, FraudCase.status == "open")
        .values(
            status="approved" if payload.decision == "approve" else "rejected",
            resolved_by=user.id,
            resolution_reason=payload.reason,
        )
    )
    if result.rowcount != 1:
        raise HTTPException(409, "Case has already been resolved")
    db.refresh(case)
    if case.transfer_id:
        transfer = db.get(Transfer, case.transfer_id)
        if transfer.status != "held":
            raise HTTPException(409, "Transfer is no longer held")
        if payload.decision == "approve":
            settle(db, transfer)
            transfer.decision = "analyst_approved"
        else:
            transfer.status = "rejected"
            transfer.decision = "analyst_rejected"
    elif case.kyc_id:
        kyc = db.get(KYCSubmission, case.kyc_id)
        if kyc.status != "review":
            raise HTTPException(409, "Identity submission is no longer pending review")
        newer = db.scalar(
            select(KYCSubmission.id).where(
                KYCSubmission.user_id == case.user_id,
                KYCSubmission.created_at > kyc.created_at,
            )
        )
        kyc.status = "approved" if payload.decision == "approve" else "rejected"
        if not newer:
            account_for(db, case.user_id).kyc_status = kyc.status
    audit(
        db,
        case.user_id,
        "fraud_agent" if case.kind != "kyc" else "identity_agent",
        "analyst_resolution",
        f"Analyst {user.id[:8]} {payload.decision}: {payload.reason}",
        ["case_resolution", "policy_gate"],
        case.risk_score,
    )
    db.commit()
    return case_json(db, case)


@app.get("/api/analyst/customers")
def analyst_customers(user=Depends(analyst), db=Depends(get_db)):
    rows = db.execute(
        select(User, Account)
        .join(Account, Account.user_id == User.id)
        .where(User.role == "customer")
        .order_by(User.created_at.desc())
        .limit(200)
    ).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "account_id": a.id,
            "account_status": a.status,
            "balance": money(a.balance_paise),
            "kyc_status": a.kyc_status,
        }
        for u, a in rows
    ]


@app.post("/api/analyst/accounts/{account_id}/status")
def account_status(
    account_id: str, payload: StatusInput, user=Depends(analyst), db=Depends(get_db)
):
    if payload.status not in {"active", "frozen"}:
        raise HTTPException(422, "Status must be active or frozen")
    account = db.get(Account, account_id)
    if not account or account.user_id is None:
        raise HTTPException(404, "Customer account not found")
    db.execute(
        update(Account).where(Account.id == account.id).values(status=payload.status)
    )
    db.refresh(account)
    audit(
        db,
        account.user_id,
        "fraud_agent",
        "account_status_changed",
        f"Analyst {user.id[:8]} set account {payload.status}: {payload.reason}",
        ["account_status"],
    )
    db.commit()
    return account_json(account)


@app.get("/api/analyst/audit")
def analyst_audit(user=Depends(analyst), db=Depends(get_db)):
    return [
        audit_json(a)
        for a in db.scalars(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(300)
        )
    ]


@app.get("/api/insights")
def financial_insights(user=Depends(customer), db=Depends(get_db)):
    from .services.proactive import list_insights

    queue_financial_review(db, user, "insights_viewed", stale_only=True)
    db.commit()
    return list_insights(db, user)


@app.get("/api/notifications/agents")
def agent_notifications(user=Depends(customer), db=Depends(get_db)):
    from .services.firestore_notifications import list_notifications

    return list_notifications(db, user)


@app.post("/api/insights/refresh", status_code=202)
def refresh_financial_insights(user=Depends(customer), db=Depends(get_db)):
    from .services.proactive import refresh_insights

    result = refresh_insights(db, user)
    db.commit()
    return result


@app.post("/api/insights/{insight_id}/dismiss")
def dismiss_financial_insight(
    insight_id: str, user=Depends(customer), db=Depends(get_db)
):
    from .services.proactive import dismiss_insight

    result = dismiss_insight(db, user, insight_id)
    db.commit()
    return result


@app.get("/api/agent-runs")
def agent_runs(user=Depends(customer), db=Depends(get_db)):
    from .services.proactive import list_runs

    return list_runs(db, user)


@app.post("/api/agent-runs/{run_id}/retry", status_code=202)
def retry_agent_run(run_id: str, user=Depends(customer), db=Depends(get_db)):
    from .services.proactive import retry_run

    result = retry_run(db, user, run_id)
    db.commit()
    return result


@app.get("/api/goals")
def savings_goals(user=Depends(customer), db=Depends(get_db)):
    from .services.proactive import list_goals

    return list_goals(db, user)


@app.post("/api/goals", status_code=201)
def add_savings_goal(payload: GoalInput, user=Depends(customer), db=Depends(get_db)):
    from .services.proactive import create_goal

    result = create_goal(db, user, payload.model_dump())
    db.commit()
    return result


@app.patch("/api/goals/{goal_id}")
def edit_savings_goal(
    goal_id: str, payload: GoalUpdateInput, user=Depends(customer), db=Depends(get_db)
):
    from .services.proactive import update_goal

    result = update_goal(db, user, goal_id, payload.model_dump(exclude_unset=True))
    db.commit()
    return result


@app.delete("/api/goals/{goal_id}")
def remove_savings_goal(goal_id: str, user=Depends(customer), db=Depends(get_db)):
    from .services.proactive import delete_goal

    result = delete_goal(db, user, goal_id)
    db.commit()
    return result


@app.get("/api/analyst/integrations")
def integrations(user=Depends(analyst)):
    from .services.providers import integration_status

    return integration_status()


@app.post("/api/analyst/integrations/claude/check")
def verify_claude_integration(user=Depends(analyst), db=Depends(get_db)):
    from .services.providers import check_claude

    result = check_claude()
    audit(
        db,
        user.id,
        "orchestrator",
        "provider_connection_checked",
        f"Claude connection check: {result['status']}; no financial action performed",
        ["provider_models_read"],
    )
    db.commit()
    return result


@app.post("/api/analyst/integrations/openai/check")
def verify_openai_integration(user=Depends(analyst), db=Depends(get_db)):
    from .services.providers import check_openai

    result = check_openai()
    audit(
        db,
        user.id,
        "orchestrator",
        "provider_connection_checked",
        f"OpenAI connection check: {result['status']}; no financial action performed",
        ["provider_models_read"],
    )
    db.commit()
    return result


@app.post("/api/analyst/integrations/gemini/check")
def verify_gemini_integration(user=Depends(analyst), db=Depends(get_db)):
    from .services.providers import check_gemini

    result = check_gemini()
    audit(
        db,
        user.id,
        "orchestrator",
        "provider_connection_checked",
        f"Gemini connection check: {result['status']}; no financial action performed",
        ["provider_models_read"],
    )
    db.commit()
    return result


@app.post("/api/analyst/integrations/openrouter/check")
def verify_openrouter_integration(user=Depends(analyst), db=Depends(get_db)):
    from .services.providers import check_openrouter

    result = check_openrouter()
    audit(
        db,
        user.id,
        "orchestrator",
        "provider_connection_checked",
        f"OpenRouter connection check: {result['status']}; no financial action performed",
        ["provider_models_read"],
    )
    db.commit()
    return result


@app.get("/api/analyst/documents")
def shared_policy_library(user=Depends(analyst), db=Depends(get_db)):
    return [
        document_json(db, doc)
        for doc in db.scalars(
            select(Document)
            .where(Document.user_id.is_(None))
            .order_by(Document.created_at.desc())
            .limit(100)
        )
    ]


@app.post("/api/analyst/documents", status_code=201)
async def publish_bank_policy(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=2, max_length=150),
    confirmed_public: bool = Form(False),
    user=Depends(analyst),
    db=Depends(get_db),
):
    if not confirmed_public:
        raise HTTPException(
            422, "Confirm that this policy can be read by all customers"
        )
    title = title.strip()
    if len(title) < 2:
        raise HTTPException(
            422, "Policy title must contain at least two non-space characters"
        )
    from .services.intelligence import extract_document

    filename, data = await bounded_file(file)
    chunks = await run_in_threadpool(extract_document, filename, data)
    if not chunks or len(chunks) > 2000:
        raise HTTPException(
            422, "Document has no usable text or exceeds extraction limits"
        )
    doc = Document(user_id=None, title=title, kind="policy", filename=filename)
    db.add(doc)
    db.flush()
    for chunk in chunks:
        db.add(
            DocumentChunk(document_id=doc.id, text=chunk["text"], page=chunk["page"])
        )
    audit(
        db,
        user.id,
        "document_agent",
        "shared_policy_published",
        f"Analyst published a customer-visible policy with {len(chunks)} source passages",
        ["text_extraction", "shared_policy_publish"],
    )
    db.commit()
    return document_json(db, doc)


@app.get("/api/documents/{document_id}/content")
def source_document_content(
    document_id: str, user=Depends(customer), db=Depends(get_db)
):
    doc = db.scalar(
        select(Document).where(
            Document.id == document_id,
            or_(Document.user_id == user.id, Document.user_id.is_(None)),
        )
    )
    if doc is None:
        raise HTTPException(404, "Document not found")
    chunks = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc.id)
        .order_by(DocumentChunk.page, DocumentChunk.id)
        .limit(2000)
    ).all()
    return {
        "document": document_json(db, doc),
        "pages": [{"page": chunk.page, "text": chunk.text} for chunk in chunks],
    }
