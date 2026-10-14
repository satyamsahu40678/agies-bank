import re
from decimal import Decimal, InvalidOperation
from fastapi import HTTPException
from ..models import AuditLog, User, uid


def money(value: int) -> str:
    return f"{Decimal(value) / 100:.2f}"


def paise(value, *, allow_zero=False) -> int:
    try:
        amount = Decimal(str(value))
        if (
            not amount.is_finite()
            or amount.as_tuple().exponent < -2
            or amount > Decimal("100000000")
            or amount < 0
            or (amount == 0 and not allow_zero)
        ):
            raise ValueError()
        return int(amount * 100)
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(
            422,
            "Amount must be positive, at most INR 100,000,000, with no more than two decimal places",
        )


def redact(value):
    value = re.sub(r"[\x00-\x1f\x7f]", " ", str(value))
    value = re.sub(r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", "[email redacted]", value)
    value = re.sub(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "[identity redacted]", value)
    value = re.sub(
        r"(?<![0-9])(?:\d[ -]?){8,}(?![0-9])", "[identifier redacted]", value
    )
    value = re.sub(
        r"(?i)\b(password|api[_ -]?key|token|secret)\s*[:=]\s*[^\s,;]+",
        r"\1=[redacted]",
        value,
    )
    return value


def audit(
    db, user_id, agent, action, summary, tools=None, risk_score=None, trace_id=None
):
    trace = trace_id or uid()
    summary = redact(summary)
    if user_id:
        subject = db.get(User, user_id)
        if subject and len(subject.name) > 2:
            summary = re.sub(
                re.escape(subject.name), "[customer]", summary, flags=re.IGNORECASE
            )
    db.add(
        AuditLog(
            user_id=user_id,
            agent=agent,
            action=action,
            summary=redact(summary)[:500],
            tools=tools or [],
            risk_score=risk_score,
            trace_id=trace,
        )
    )
    return trace
