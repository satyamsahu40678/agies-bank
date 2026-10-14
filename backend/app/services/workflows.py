from datetime import timedelta
import hashlib
import hmac
import ipaddress
import math
from fastapi import HTTPException
from sqlalchemy import select, update
from ..models import *
from ..config import DEMO_ENABLED, SECRET
from .common import money, audit


def account_for(db, user_id):
    account = db.scalar(select(Account).where(Account.user_id == user_id))
    if not account:
        raise HTTPException(404, "Account not found")
    return account


def account_hash(number):
    return hmac.new(SECRET.encode(), number.encode(), hashlib.sha256).hexdigest()


def add_signal(signals, name, score, detail):
    if score:
        signals.append({"name": name, "score": score, "detail": detail})


def mask_ip(ip):
    try:
        parsed = ipaddress.ip_address(ip)
        return (
            ".".join(ip.split(".")[:2]) + ".*.*"
            if parsed.version == 4
            else ":".join(ip.split(":")[:2]) + ":*"
        )
    except ValueError:
        return "unknown"


def login_event(db, user, request):
    device = (request.headers.get("user-agent") or "Unknown browser")[:100]
    previous = db.scalar(
        select(SecurityEvent)
        .where(SecurityEvent.user_id == user.id)
        .order_by(SecurityEvent.created_at.desc())
    )
    known = db.scalar(
        select(SecurityEvent.id).where(
            SecurityEvent.user_id == user.id, SecurityEvent.device == device
        )
    )
    signals = []
    add_signal(
        signals,
        "new_device",
        15 if previous and not known else 0,
        "A previously unseen browser signed in",
    )
    event = SecurityEvent(
        user_id=user.id,
        kind="login",
        city="Mumbai (demo)" if DEMO_ENABLED else "Unknown",
        country="IN" if DEMO_ENABLED else "Unknown",
        latitude=19.076 if DEMO_ENABLED else 0,
        longitude=72.878 if DEMO_ENABLED else 0,
        ip_masked=mask_ip(request.client.host if request.client else ""),
        device=device,
        is_new_device=not bool(known),
        vpn=False,
        risk_score=sum(x["score"] for x in signals),
        signals=signals,
    )
    db.add(event)
    audit(
        db,
        user.id,
        "fraud_agent",
        "login_monitor",
        "Login recorded with masked network and device context",
        ["login_monitor"],
        event.risk_score,
    )
    return event


def transfer_risk(db, user, beneficiary, amount):
    signals = []
    add_signal(
        signals,
        "amount",
        50
        if amount >= 10_000_000
        else 35
        if amount >= 2_500_000
        else 10
        if amount >= 1_000_000
        else 0,
        f"Transfer amount INR {money(amount)} assessed against demo thresholds",
    )
    entries = db.scalars(
        select(LedgerEntry)
        .where(
            LedgerEntry.account_id == account_for(db, user.id).id,
            LedgerEntry.direction == "debit",
            LedgerEntry.category != "transfer",
        )
        .limit(100)
    ).all()
    if entries:
        mean = sum(e.amount_paise for e in entries) / len(entries)
        deviation = math.sqrt(
            sum((e.amount_paise - mean) ** 2 for e in entries) / len(entries)
        )
        if amount > mean + 3 * max(deviation, 500_000):
            add_signal(
                signals,
                "statistical_anomaly",
                20,
                "Amount exceeds baseline spending by more than three estimated standard deviations",
            )
    add_signal(
        signals,
        "new_beneficiary",
        15 if beneficiary.is_new else 0,
        "First transfer to this beneficiary",
    )
    velocity = db.scalars(
        select(Transfer).where(
            Transfer.user_id == user.id,
            Transfer.created_at > utcnow() - timedelta(minutes=10),
            Transfer.status != "rejected",
        )
    ).all()
    add_signal(
        signals,
        "velocity",
        70 if len(velocity) >= 5 else 35 if len(velocity) >= 3 else 0,
        "Three or more transfers attempted within ten minutes",
    )
    event = db.scalar(
        select(SecurityEvent)
        .where(
            SecurityEvent.user_id == user.id,
            SecurityEvent.created_at > utcnow() - timedelta(minutes=30),
        )
        .order_by(SecurityEvent.risk_score.desc(), SecurityEvent.created_at.desc())
    )
    if event:
        for s in event.signals:
            add_signal(signals, s["name"], s["score"], s["detail"])
        add_signal(
            signals,
            "foreign_country",
            15 if event.country not in {"IN", "Unknown"} else 0,
            "Latest server-recorded login was outside the home country",
        )
    open_login = db.scalar(
        select(FraudCase)
        .where(
            FraudCase.user_id == user.id,
            FraudCase.kind == "login",
            FraudCase.status == "open",
        )
        .order_by(FraudCase.risk_score.desc())
    )
    if open_login and sum(s["score"] for s in signals) < open_login.risk_score:
        add_signal(
            signals,
            "unresolved_security_case",
            open_login.risk_score - sum(s["score"] for s in signals),
            "Unresolved high-risk login case requires analyst review",
        )
    score = min(100, sum(s["score"] for s in signals))
    return score, signals


def settle(db, transfer):
    account = account_for(db, transfer.user_id)
    if account.kyc_status != "approved":
        raise HTTPException(
            409, "Complete approved identity verification before transferring money"
        )
    result = db.execute(
        update(Account)
        .where(
            Account.id == account.id,
            Account.status == "active",
            Account.balance_paise >= transfer.amount_paise,
        )
        .values(balance_paise=Account.balance_paise - transfer.amount_paise)
        .returning(Account.balance_paise)
    )
    balance = result.scalar_one_or_none()
    if balance is None:
        raise HTTPException(409, "Account frozen or insufficient available balance")
    clearing = db.scalar(select(Account).where(Account.number == "INTERNAL_CLEARING"))
    if not clearing:
        raise HTTPException(503, "Settlement account unavailable")
    clearing_balance = db.execute(
        update(Account)
        .where(Account.id == clearing.id)
        .values(balance_paise=Account.balance_paise + transfer.amount_paise)
        .returning(Account.balance_paise)
    ).scalar_one()
    beneficiary = db.get(Beneficiary, transfer.beneficiary_id)
    beneficiary.is_new = False
    transfer.status = "posted"
    db.add_all(
        [
            LedgerEntry(
                account_id=account.id,
                amount_paise=transfer.amount_paise,
                direction="debit",
                description=transfer.description or f"Transfer to {beneficiary.name}",
                category="transfer",
                balance_after_paise=balance,
                transfer_id=transfer.id,
            ),
            LedgerEntry(
                account_id=clearing.id,
                amount_paise=transfer.amount_paise,
                direction="credit",
                description="External settlement",
                category="settlement",
                balance_after_paise=clearing_balance,
                transfer_id=transfer.id,
            ),
        ]
    )
    audit(
        db,
        transfer.user_id,
        "banking_agent",
        "transfer_settled",
        f"INR {money(transfer.amount_paise)} settled atomically",
        ["risk_score", "ledger_transfer"],
        transfer.risk_score,
    )


def create_transfer(db, user, beneficiary_id, amount, description, key):
    fingerprint = hashlib.sha256(
        f"{beneficiary_id}:{amount}:{description}".encode()
    ).hexdigest()
    existing = db.scalar(
        select(Transfer).where(
            Transfer.user_id == user.id, Transfer.idempotency_key == key
        )
    )
    if existing:
        if existing.fingerprint != fingerprint:
            raise HTTPException(
                409, "Idempotency key was already used for a different transfer"
            )
        return existing
    account = account_for(db, user.id)
    if account.status != "active":
        raise HTTPException(409, "Account is frozen")
    if account.kyc_status != "approved":
        raise HTTPException(
            409, "Complete approved identity verification before transferring money"
        )
    if amount > account.balance_paise:
        raise HTTPException(409, "Insufficient available balance")
    beneficiary = db.scalar(
        select(Beneficiary).where(
            Beneficiary.id == beneficiary_id, Beneficiary.user_id == user.id
        )
    )
    if not beneficiary:
        raise HTTPException(404, "Beneficiary not found")
    score, signals = transfer_risk(db, user, beneficiary, amount)
    status = "held" if score >= 70 else "pending_step_up" if score >= 35 else "posted"
    transfer = Transfer(
        user_id=user.id,
        beneficiary_id=beneficiary.id,
        amount_paise=amount,
        description=description,
        idempotency_key=key,
        fingerprint=fingerprint,
        status=status,
        risk_score=score,
        signals=signals,
        decision="analyst_review"
        if status == "held"
        else "step_up_required"
        if status == "pending_step_up"
        else "allow",
    )
    db.add(transfer)
    db.flush()
    if status == "posted":
        settle(db, transfer)
    elif status == "held":
        case = FraudCase(
            user_id=user.id,
            kind="transfer",
            priority="high",
            risk_score=score,
            amount_paise=amount,
            summary=f"High-risk INR {money(amount)} transfer held for review",
            signals=signals,
            transfer_id=transfer.id,
        )
        db.add(case)
        db.flush()
        db.add(
            Alert(
                user_id=user.id,
                case_id=case.id,
                title="Transfer held for your protection",
                message=f"Please confirm whether you recognize this INR {money(amount)} transfer. An analyst must authorize settlement.",
                severity="high",
            )
        )
    audit(
        db,
        user.id,
        "fraud_agent",
        "transfer_risk_assessed",
        f"Transfer risk {score}/100; decision {transfer.decision}",
        ["risk_score", "policy_gate"],
        score,
    )
    return transfer


def synthetic_event(db, user, scenario):
    if not DEMO_ENABLED:
        raise HTTPException(403, "Simulator is disabled outside demo environments")
    signals = []
    city, country, lat, lon = "Mumbai", "IN", 19.076, 72.878
    new = False
    vpn = False
    device = "Trusted demo browser"
    if scenario == "impossible_travel":
        city, country, lat, lon = "London", "GB", 51.507, -0.128
        new = True
        device = "Unrecognized synthetic browser"
        previous = db.scalar(
            select(SecurityEvent)
            .where(SecurityEvent.user_id == user.id)
            .order_by(SecurityEvent.created_at.desc())
        )
        if previous:
            dlat = math.radians(lat - previous.latitude)
            dlon = math.radians(lon - previous.longitude)
            arc = (
                math.sin(dlat / 2) ** 2
                + math.cos(math.radians(previous.latitude))
                * math.cos(math.radians(lat))
                * math.sin(dlon / 2) ** 2
            )
            distance = 6371 * 2 * math.asin(min(1, math.sqrt(arc)))
            created = (
                previous.created_at.replace(tzinfo=timezone.utc)
                if previous.created_at.tzinfo is None
                else previous.created_at
            )
            elapsed = max((utcnow() - created).total_seconds() / 3600, 1 / 3600)
            speed = distance / elapsed
            add_signal(
                signals,
                "impossible_travel",
                60 if distance > 500 and speed > 900 else 0,
                f"Synthetic haversine displacement {distance:.0f} km in {elapsed * 60:.2f} minutes implies {speed:.0f} km/h",
            )
        add_signal(
            signals, "new_device", 15, "Synthetic device has never been observed"
        )
    elif scenario == "vpn_login":
        vpn = True
        new = True
        device = "Synthetic VPN browser"
        add_signal(signals, "vpn", 25, "Synthetic anonymizing VPN endpoint")
        add_signal(
            signals, "new_device", 15, "Synthetic device has never been observed"
        )
    event = SecurityEvent(
        user_id=user.id,
        kind="simulated_login",
        city=city,
        country=country,
        latitude=lat,
        longitude=lon,
        ip_masked="203.0.*.*",
        device=device,
        is_new_device=new,
        vpn=vpn,
        risk_score=min(100, sum(s["score"] for s in signals)),
        signals=signals,
    )
    db.add(event)
    db.flush()
    case = None
    if event.risk_score >= 70:
        case = FraudCase(
            user_id=user.id,
            kind="login",
            priority="high",
            risk_score=event.risk_score,
            summary="Impossible travel detected in synthetic login event",
            signals=signals,
        )
        db.add(case)
        db.flush()
        db.add(
            Alert(
                user_id=user.id,
                case_id=case.id,
                title="Unusual sign-in detected",
                message="A synthetic login from an unexpected location was detected. Confirm whether you recognize it.",
                severity="high",
            )
        )
    audit(
        db,
        user.id,
        "fraud_agent",
        "event_simulated",
        f"{scenario}: risk {event.risk_score}/100. Synthetic event, no external network intelligence.",
        ["login_monitor", "anomaly_rules"],
        event.risk_score,
    )
    return event, case
