"""Durable proactive guidance with customer scopes and explicit financial consent.

All tools are read-only. Goals record plans, never reserved money. A database
lease, event deduplication and bounded retries make jobs safe across restarts and
multiple workers. Stored traces contain decisions and tool names, not reasoning.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import logging
import math
import re
from threading import Event, Thread
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, case, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from ..db import SessionLocal
from ..models import (
    Account,
    AgentRun,
    Budget,
    FinancialInsight,
    LedgerEntry,
    SavingsGoal,
    User,
    uid,
    utcnow,
)
from .common import audit, money, paise, redact
from .intelligence import REGISTRY, ToolContext

logger = logging.getLogger(__name__)
FRESHNESS = timedelta(minutes=15)
LEASE = timedelta(minutes=2)
READ_SCOPES = frozenset(
    {
        "accounts:read",
        "ledger:read",
        "budgets:read",
        "risk:read",
        "kyc:read",
        "recommendations:read",
    }
)
TOOLS = (
    "get_balance",
    "get_spending",
    "get_budgets",
    "get_security_summary",
    "get_identity_status",
    "get_recommendations",
)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def _customer(user):
    if user.role != "customer":
        raise HTTPException(403, "Customer access is required.")


def _payload(payload: Any) -> dict:
    return (
        payload if isinstance(payload, dict) else payload.model_dump(exclude_unset=True)
    )


def _goal(db, user, goal_id):
    _customer(user)
    goal = db.scalar(
        select(SavingsGoal).where(
            SavingsGoal.id == goal_id, SavingsGoal.user_id == user.id
        )
    )
    if not goal:
        raise HTTPException(404, "Savings goal not found.")
    return goal


def goal_json(goal):
    remaining = goal.target_paise - goal.saved_paise
    months = (
        max(1, math.ceil((goal.target_date - date.today()).days / 30))
        if goal.target_date
        else 6
    )
    return {
        "id": goal.id,
        "name": goal.name,
        "target_amount": money(goal.target_paise),
        "saved_amount": money(goal.saved_paise),
        "target_date": goal.target_date.isoformat() if goal.target_date else None,
        "status": goal.status,
        "progress_percent": round(goal.saved_paise * 100 / goal.target_paise, 1),
        "monthly_contribution": money((remaining + months - 1) // months),
        "created_at": _utc(goal.created_at),
        "updated_at": _utc(goal.updated_at),
        "planning_only": True,
    }


def list_goals(db, user):
    _customer(user)
    return [
        goal_json(goal)
        for goal in db.scalars(
            select(SavingsGoal)
            .where(SavingsGoal.user_id == user.id)
            .order_by(SavingsGoal.created_at.desc())
            .limit(100)
        )
    ]


def _validated_goal(payload, current=None):
    values = _payload(payload)
    allowed = {"name", "target_amount", "saved_amount", "target_date", "status"}
    if not values or set(values) - allowed:
        raise HTTPException(422, "Provide valid savings goal fields.")
    name = values.get("name", current.name if current else "")
    if (
        not isinstance(name, str)
        or not 1 <= len(name.strip()) <= 100
        or re.search(r"[\x00-\x1f\x7f]", name)
    ):
        raise HTTPException(
            422, "Goal name must contain 1 to 100 printable characters."
        )
    target = (
        paise(values["target_amount"])
        if "target_amount" in values
        else current.target_paise
        if current
        else 0
    )
    saved = (
        paise(values["saved_amount"], allow_zero=True)
        if "saved_amount" in values
        else current.saved_paise
        if current
        else 0
    )
    if target <= 0 or saved > target:
        raise HTTPException(
            422, "Target must be positive and saved amount cannot exceed the target."
        )
    target_date = current.target_date if current else None
    if "target_date" in values:
        raw = values["target_date"]
        try:
            target_date = date.fromisoformat(raw) if isinstance(raw, str) else raw
            if target_date is not None and (
                type(target_date) is not date
                or target_date < date.today()
                or target_date > date.today() + timedelta(days=365 * 50)
            ):
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(
                422, "Target date must be today or later, within 50 years."
            )
    status = values.get("status", current.status if current else "active")
    if status not in {"active", "paused", "completed"}:
        raise HTTPException(422, "Goal status must be active, paused or completed.")
    if saved == target:
        status = "completed"
    elif current and current.status == "completed" and "status" not in values:
        status = "active"
    if status == "completed" and saved < target:
        raise HTTPException(
            422, "A completed goal must have its full target recorded as saved."
        )
    return {
        "name": name.strip(),
        "target_paise": target,
        "saved_paise": saved,
        "target_date": target_date,
        "status": status,
    }


def create_goal(db, user, payload):
    _customer(user)
    if (
        db.scalar(
            select(func.count())
            .select_from(SavingsGoal)
            .where(SavingsGoal.user_id == user.id)
        )
        >= 100
    ):
        raise HTTPException(409, "A maximum of 100 savings goals is supported.")
    goal = SavingsGoal(user_id=user.id, **_validated_goal(payload))
    db.add(goal)
    db.flush()
    audit(
        db,
        user.id,
        "banking_agent",
        "goal_created",
        "Customer recorded a savings plan; no money was moved or reserved.",
        ["goals:write"],
    )
    enqueue_health_check(db, user, "goal_changed", dedup_key=goal.id + ":" + uid())
    return goal_json(goal)


def update_goal(db, user, goal_id, payload):
    goal = _goal(db, user, goal_id)
    for key, value in _validated_goal(payload, goal).items():
        setattr(goal, key, value)
    goal.updated_at = utcnow()
    db.flush()
    audit(
        db,
        user.id,
        "banking_agent",
        "goal_updated",
        "Customer updated a savings plan; ledger balances were unchanged.",
        ["goals:write"],
    )
    enqueue_health_check(db, user, "goal_changed", dedup_key=goal.id + ":" + uid())
    return goal_json(goal)


def delete_goal(db, user, goal_id):
    goal = _goal(db, user, goal_id)
    db.delete(goal)
    db.flush()
    audit(
        db,
        user.id,
        "banking_agent",
        "goal_deleted",
        "Customer removed a savings planning record.",
        ["goals:write"],
    )
    enqueue_health_check(db, user, "goal_changed", dedup_key=goal_id + ":deleted")
    return {"deleted": True}


def run_json(run):
    return {
        "id": run.id,
        "kind": run.kind,
        "trigger": run.trigger,
        "status": run.status,
        "attempts": run.attempts,
        "max_attempts": run.max_attempts,
        "tools": run.tools,
        "decisions": run.decisions,
        "trace_id": run.trace_id,
        "error": run.error,
        "created_at": _utc(run.created_at),
        "started_at": _utc(run.started_at),
        "completed_at": _utc(run.completed_at),
    }


def insight_json(insight):
    return {
        "id": insight.id,
        "kind": insight.kind,
        "severity": insight.severity,
        "title": insight.title,
        "message": insight.message,
        "action_label": insight.action_label,
        "action_path": insight.action_path,
        "status": insight.status,
        "metrics": insight.metrics,
        "created_at": _utc(insight.created_at),
        "updated_at": _utc(insight.updated_at),
    }


def enqueue_health_check(db, user, trigger, dedup_key=None, *, stale_only=False):
    """Stage an event in the caller's transaction. Caller commits with its business event."""
    _customer(user)
    now = utcnow()
    if not isinstance(trigger, str) or not re.fullmatch(r"[a-z_]{1,40}", trigger):
        raise ValueError("Invalid workflow trigger")
    if stale_only:
        recent = db.scalar(
            select(AgentRun)
            .where(
                AgentRun.user_id == user.id,
                or_(
                    AgentRun.status.in_(["queued", "running"]),
                    and_(
                        AgentRun.status == "completed",
                        AgentRun.completed_at >= now - FRESHNESS,
                    ),
                ),
            )
            .order_by(AgentRun.created_at.desc())
            .limit(1)
        )
        if recent:
            return recent
    raw = str(dedup_key) if dedup_key is not None else str(int(now.timestamp()) // 60)
    key = hashlib.sha256((trigger + ":" + raw).encode()).hexdigest()
    existing = db.scalar(
        select(AgentRun).where(AgentRun.user_id == user.id, AgentRun.dedup_key == key)
    )
    if existing:
        return existing
    # Bound accidental event floods without silently changing financial state.
    pending = db.scalars(
        select(AgentRun)
        .where(AgentRun.user_id == user.id, AgentRun.status.in_(["queued", "running"]))
        .order_by(AgentRun.created_at)
        .limit(100)
    ).all()
    if len(pending) >= 100:
        return pending[-1]
    run = AgentRun(user_id=user.id, trigger=trigger, dedup_key=key, available_at=now)
    try:
        with db.begin_nested():
            db.add(run)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(AgentRun).where(
                AgentRun.user_id == user.id, AgentRun.dedup_key == key
            )
        )
        if existing:
            return existing
        raise
    audit(
        db,
        user.id,
        "orchestrator",
        "agent_run_queued",
        f"Queued a read-only financial-health review after {trigger}.",
        [],
        trace_id=run.trace_id,
    )
    return run


def refresh_insights(db, user):
    _customer(user)
    pending = db.scalar(
        select(AgentRun)
        .where(AgentRun.user_id == user.id, AgentRun.status.in_(["queued", "running"]))
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    if pending:
        return run_json(pending)
    latest = db.scalar(
        select(AgentRun.id)
        .where(AgentRun.user_id == user.id)
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    # A completed run must never suppress a requested refresh in the same minute.
    # Concurrent requests following the same run still share one durable event.
    return run_json(
        enqueue_health_check(
            db, user, "manual_refresh", dedup_key=f"after:{latest or 'initial'}"
        )
    )


def list_runs(db, user):
    _customer(user)
    return [
        run_json(run)
        for run in db.scalars(
            select(AgentRun)
            .where(AgentRun.user_id == user.id)
            .order_by(AgentRun.created_at.desc())
            .limit(50)
        )
    ]


def retry_run(db, user, run_id):
    _customer(user)
    run = db.scalar(
        select(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.user_id == user.id)
        .with_for_update()
    )
    if not run:
        raise HTTPException(404, "Agent run not found.")
    if run.status != "failed":
        raise HTTPException(409, "Only failed agent runs can be retried.")
    if run.manual_retries >= 3:
        raise HTTPException(
            409, "Retry limit reached. A new review may be requested instead."
        )
    run.manual_retries += 1
    run.status = "queued"
    run.attempts = 0
    run.error = None
    run.lease_token = None
    run.lease_expires_at = None
    run.completed_at = None
    run.available_at = utcnow()
    audit(
        db,
        user.id,
        "orchestrator",
        "agent_run_retried",
        "Customer requested a bounded retry of a failed read-only review.",
        [],
        trace_id=run.trace_id,
    )
    db.flush()
    return run_json(run)


def dismiss_insight(db, user, insight_id):
    _customer(user)
    insight = db.scalar(
        select(FinancialInsight).where(
            FinancialInsight.id == insight_id, FinancialInsight.user_id == user.id
        )
    )
    if not insight:
        raise HTTPException(404, "Insight not found.")
    insight.status = "dismissed"
    insight.updated_at = utcnow()
    audit(
        db,
        user.id,
        "orchestrator",
        "insight_dismissed",
        "Customer dismissed financial guidance; no financial state was changed.",
        ["insights:write"],
    )
    return insight_json(insight)


def list_insights(db, user):
    _customer(user)
    enqueue_health_check(db, user, "overview", stale_only=True)
    latest = db.scalar(
        select(AgentRun)
        .where(AgentRun.user_id == user.id)
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    completed = db.scalar(
        select(AgentRun)
        .where(AgentRun.user_id == user.id, AgentRun.status == "completed")
        .order_by(AgentRun.completed_at.desc())
        .limit(1)
    )
    items = db.scalars(
        select(FinancialInsight)
        .where(FinancialInsight.user_id == user.id, FinancialInsight.status == "active")
        .order_by(FinancialInsight.updated_at.desc())
        .limit(50)
    ).all()
    return {
        "items": [insight_json(insight) for insight in items],
        "summary": completed.output.get("summary", {}) if completed else {},
        "latest_run": run_json(latest) if latest else None,
    }


def _eligible(now):
    return and_(
        AgentRun.kind == "financial_health",
        AgentRun.attempts < AgentRun.max_attempts,
        or_(
            and_(AgentRun.status == "queued", AgentRun.available_at <= now),
            and_(AgentRun.status == "running", AgentRun.lease_expires_at <= now),
        ),
    )


def claim_next_run(db, now=None):
    """Atomically claim one due job. PostgreSQL skips locks; SQLite uses a compare-and-set UPDATE."""
    now = now or utcnow()
    # A crash on the last attempt must eventually reach a terminal state.
    db.execute(
        update(AgentRun)
        .where(
            AgentRun.status == "running",
            AgentRun.lease_expires_at <= now,
            AgentRun.attempts >= AgentRun.max_attempts,
        )
        .values(
            status="failed",
            error="Worker lease expired after the final attempt.",
            completed_at=now,
            lease_token=None,
            lease_expires_at=None,
        ),
        execution_options={"synchronize_session": False},
    )
    other = aliased(AgentRun)
    active_other = exists(
        select(other.id).where(
            other.user_id == AgentRun.user_id,
            other.id != AgentRun.id,
            other.status == "running",
            other.lease_expires_at > now,
        )
    )
    candidate = (
        select(AgentRun.id)
        .join(User, User.id == AgentRun.user_id)
        .where(_eligible(now), User.role == "customer", ~active_other)
        .order_by(AgentRun.available_at, AgentRun.created_at)
        .limit(1)
    )
    if db.get_bind().dialect.name == "postgresql":
        # Lock the customer too, so parallel workers cannot claim different runs for one tenant.
        candidate = candidate.with_for_update(skip_locked=True, of=(AgentRun, User))
    token = uid()
    claimed = db.execute(
        update(AgentRun)
        .where(AgentRun.id == candidate.scalar_subquery(), _eligible(now))
        .values(
            status="running",
            attempts=AgentRun.attempts + 1,
            lease_token=token,
            lease_expires_at=now + LEASE,
            started_at=now,
            completed_at=None,
            error=None,
        )
        .returning(AgentRun.id),
        execution_options={"synchronize_session": False},
    ).scalar_one_or_none()
    if not claimed:
        return None
    db.expire_all()
    return db.get(AgentRun, claimed)


def _insight(kind, key, severity, title, message, label, path, metrics):
    # Fingerprints exclude volatile evaluation timestamps, so dismissal survives identical reruns.
    fingerprint = hashlib.sha256(
        json.dumps(metrics, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "kind": kind,
        "key": key[:100],
        "severity": severity,
        "title": title[:150],
        "message": message[:750],
        "action_label": label[:60],
        "action_path": path,
        "metrics": metrics,
        "fingerprint": fingerprint,
    }


def _health_plan(db, user, run):
    context = ToolContext(db=db, user=user, trace_id=run.trace_id, scopes=READ_SCOPES)
    results = {}
    for tool in TOOLS:
        results[tool] = REGISTRY.invoke(tool, context, {})
        audit(
            db,
            user.id,
            REGISTRY.agent_for(tool),
            "proactive_tool_completed",
            "Read a tenant-scoped summary for proactive financial guidance.",
            [tool],
            trace_id=run.trace_id,
        )
    account = db.scalar(select(Account).where(Account.user_id == user.id))
    if not account:
        raise HTTPException(404, "Customer account not found.")
    now = utcnow()
    # The SQL cutoff and cap bound both memory and database work.
    entries = db.scalars(
        select(LedgerEntry)
        .where(
            LedgerEntry.account_id == account.id,
            LedgerEntry.status == "posted",
            LedgerEntry.created_at >= now - timedelta(days=120),
        )
        .order_by(LedgerEntry.created_at.desc())
        .limit(10000)
    ).all()
    monthly_scope = (
        LedgerEntry.account_id == account.id,
        LedgerEntry.status == "posted",
        LedgerEntry.created_at >= now - timedelta(days=30),
    )
    # Calculate financial totals over the complete SQL result, never a sampled history.
    income, expenses, debt = db.execute(
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
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                LedgerEntry.direction == "debit",
                                func.lower(LedgerEntry.category).in_(
                                    ["loan", "loans", "debt", "emi", "mortgage"]
                                ),
                            ),
                            LedgerEntry.amount_paise,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
        ).where(*monthly_scope)
    ).one()
    # PostgreSQL SUM(bigint) returns NUMERIC/Decimal; minor-unit contracts use integers.
    income, expenses, debt = int(income), int(expenses), int(debt)
    surplus = income - expenses
    capacity = max(0, min(income * 40 // 100 - debt, surplus * 35 // 100))
    goals = db.scalars(
        select(SavingsGoal)
        .where(SavingsGoal.user_id == user.id, SavingsGoal.status == "active")
        .limit(100)
    ).all()
    summary = {
        "period": "Last 30 days",
        "income": money(income),
        "expenses": money(expenses),
        "net_cashflow": money(surplus),
        "savings_rate": round(surplus * 100 / income, 1) if income else 0,
        "balance": money(account.balance_paise),
        "monthly_emi_capacity": money(capacity),
        "active_goals": len(goals),
        "planning_only": True,
        "source": "Complete posted ledger totals for 30 days. Recurring detection checks up to 10,000 entries over 120 days; proposals need your action.",
    }
    insights = []
    spend = defaultdict(
        int,
        (
            (category, int(amount))
            for category, amount in db.execute(
                select(
                    func.lower(LedgerEntry.category), func.sum(LedgerEntry.amount_paise)
                )
                .where(*monthly_scope, LedgerEntry.direction == "debit")
                .group_by(func.lower(LedgerEntry.category))
            ).all()
        ),
    )
    for budget in db.scalars(
        select(Budget).where(Budget.user_id == user.id).limit(100)
    ):
        amount = spend[budget.category.lower()]
        if (
            amount > budget.limit_paise
            or budget.limit_paise > 0
            and amount * 100 >= budget.limit_paise * 80
        ):
            over = amount > budget.limit_paise
            insights.append(
                _insight(
                    "budget",
                    budget.category.lower(),
                    "critical" if over else "warning",
                    f"{budget.category.title()} budget {'exceeded' if over else 'near its limit'}",
                    f"Posted spending of INR {money(amount)} {'exceeds' if over else 'is approaching'} your INR {money(budget.limit_paise)} plan over the last 30 days. Review upcoming purchases before changing your budget.",
                    "Review budget",
                    "/dashboard#budgets",
                    {
                        "category": budget.category,
                        "spent": money(amount),
                        "limit_amount": money(budget.limit_paise),
                    },
                )
            )
    if not income:
        insights.append(
            _insight(
                "cashflow",
                "monthly",
                "warning",
                "Income evidence is limited",
                f"No posted income appeared in the last 30 days, while expenses were INR {money(expenses)}. Forecasts and affordability are limited until income is recorded.",
                "Review transactions",
                "/payments",
                {"income": money(income), "expenses": money(expenses)},
            )
        )
    elif surplus < 0:
        insights.append(
            _insight(
                "cashflow",
                "monthly",
                "critical",
                "Spending exceeds recent income",
                f"Your last 30 days show INR {money(-surplus)} more spending than income. Review flexible expenses and maintain an emergency buffer.",
                "Review spending",
                "/dashboard#budgets",
                {
                    "income": money(income),
                    "expenses": money(expenses),
                    "net_cashflow": money(surplus),
                },
            )
        )
    else:
        insights.append(
            _insight(
                "cashflow",
                "monthly",
                "info",
                "A savings opportunity in your cash flow",
                f"Your posted income exceeds spending by INR {money(surplus)} over the last 30 days. A plan can help allocate this surplus; it is historical evidence, not guaranteed future income.",
                "Plan a goal",
                "/insights#goals",
                {
                    "income": money(income),
                    "expenses": money(expenses),
                    "net_cashflow": money(surplus),
                },
            )
        )
    if expenses and account.balance_paise < expenses:
        insights.append(
            _insight(
                "buffer",
                "emergency",
                "warning",
                "Your cash buffer is below one month of spending",
                f"Your current balance covers less than your recent INR {money(expenses)} monthly outflow. Consider an emergency savings plan before adding commitments.",
                "Plan a buffer",
                "/insights#goals",
                {
                    "balance": money(account.balance_paise),
                    "monthly_expenses": money(expenses),
                },
            )
        )
    groups = defaultdict(list)
    for entry in entries:
        if entry.direction == "debit":
            merchant = re.sub(
                r"\s+",
                " ",
                re.sub(
                    r"\b(?:\d{1,4}|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
                    "",
                    entry.description.lower(),
                ),
            ).strip(" ·-")
            if merchant:
                groups[(merchant, entry.category.lower())].append(entry)
    for (merchant, category), group in sorted(groups.items()):
        if len(group) < 2 or category not in {
            "subscriptions",
            "subscription",
            "utilities",
            "insurance",
        }:
            continue
        ordered = sorted(group, key=lambda entry: _utc(entry.created_at))
        intervals = [
            (_utc(b.created_at) - _utc(a.created_at)).days
            for a, b in zip(ordered, ordered[1:])
        ]
        amounts = [entry.amount_paise for entry in ordered]
        cadence = (
            "monthly"
            if all(20 <= gap <= 40 for gap in intervals)
            else "weekly"
            if all(6 <= gap <= 8 for gap in intervals)
            else None
        )
        if (
            not cadence
            or max(amounts) * 100 > min(amounts) * 120
            or _utc(ordered[-1].created_at) < now - timedelta(days=40)
        ):
            continue
        typical = sum(amounts) // len(amounts)
        next_date = (
            _utc(ordered[-1].created_at)
            + timedelta(days=30 if cadence == "monthly" else 7)
        ).date()
        if next_date < now.date():
            continue
        insights.append(
            _insight(
                "recurring",
                hashlib.sha256((merchant + ":" + category).encode()).hexdigest()[:32],
                "info",
                "A recurring charge may be coming up",
                f"{redact(ordered[-1].description)[:100]} has {len(group)} similar {cadence} charges of about INR {money(typical)}. The next charge may be around {next_date.isoformat()}; check the merchant agreement.",
                "Review transactions",
                "/payments",
                {
                    "merchant": redact(ordered[-1].description)[:100],
                    "amount": money(typical),
                    "cadence": cadence,
                    "occurrences": len(group),
                    "expected_date": next_date.isoformat(),
                    "estimated": True,
                },
            )
        )
        if len(insights) >= 40:
            break
    contributions = sum(
        paise(goal_json(goal)["monthly_contribution"], allow_zero=True)
        for goal in goals
    )
    for goal in goals[:10]:
        proposal = goal_json(goal)
        suggested = paise(proposal["monthly_contribution"], allow_zero=True)
        affordable = surplus > 0 and contributions <= surplus
        insights.append(
            _insight(
                "goal",
                goal.id,
                "info" if affordable else "warning",
                f"{goal.name[:110]}: {'planning on track' if affordable else 'review your savings pace'}",
                f"Recording INR {money(suggested)} per month would reach this planning target"
                + (
                    f" by {goal.target_date.isoformat()}"
                    if goal.target_date
                    else " over six months"
                )
                + ". "
                + (
                    "All active goal contributions fit within your recent cash-flow surplus."
                    if affordable
                    else "All active goal contributions exceed your recent surplus; adjust the date or target."
                )
                + " These records do not reserve or move funds.",
                "Review goal",
                "/insights#goals",
                {
                    "goal_id": goal.id,
                    "monthly_contribution": money(suggested),
                    "all_goals_monthly_contribution": money(contributions),
                    "affordable": affordable,
                    "target_amount": proposal["target_amount"],
                    "saved_amount": proposal["saved_amount"],
                },
            )
        )
    if income:
        insights.append(
            _insight(
                "affordability",
                "emi",
                "info",
                "Know your illustrative EMI capacity",
                f"Your current ledger supports an illustrative additional monthly EMI ceiling of INR {money(capacity)}, bounded by income, current debt payments and disposable cash flow. Approval, future income and underwriting still require verification.",
                "Explore recommendations",
                "/recommendations",
                {
                    "monthly_emi_capacity": money(capacity),
                    "current_debt_payments": money(debt),
                    "illustrative": True,
                },
            )
        )
    kyc_status = results["get_identity_status"].get("kyc_status")
    if kyc_status not in {"approved", "verified"}:
        insights.append(
            _insight(
                "identity",
                "verification",
                "warning",
                "Complete your identity review",
                "Your identity verification is not approved yet. Follow the Identity page to complete requirements; this workflow cannot verify identity or change your status.",
                "Review identity",
                "/kyc",
                {"kyc_status": kyc_status},
            )
        )
    return summary, insights[:50]


class LostLease(RuntimeError):
    pass


def _execute(db, run_id, lease_token):
    run = db.get(AgentRun, run_id)
    if (
        not run
        or run.status != "running"
        or run.lease_token != lease_token
        or _utc(run.lease_expires_at) <= utcnow()
    ):
        raise LostLease()
    user = db.get(User, run.user_id)
    _customer(user)
    summary, proposals = _health_plan(db, user, run)
    existing = {
        (insight.kind, insight.key): insight
        for insight in db.scalars(
            select(FinancialInsight).where(FinancialInsight.user_id == user.id)
        )
    }
    seen = set()
    now = utcnow()
    for proposal in proposals:
        key = (proposal["kind"], proposal["key"])
        seen.add(key)
        insight = existing.get(key)
        if not insight:
            db.add(FinancialInsight(user_id=user.id, run_id=run.id, **proposal))
        else:
            keep_dismissed = (
                insight.status == "dismissed"
                and insight.fingerprint == proposal["fingerprint"]
            )
            for field, value in proposal.items():
                setattr(insight, field, value)
            insight.run_id = run.id
            insight.updated_at = now
            insight.status = "dismissed" if keep_dismissed else "active"
    for key, insight in existing.items():
        if key not in seen and insight.status == "active":
            insight.status = "resolved"
            insight.updated_at = now
    decisions = [
        f"Reviewed {len(TOOLS)} customer-scoped read-only tools.",
        f"Produced {len(proposals)} financial guidance items from posted ledger records and customer plans.",
        "No money, identity status, account controls or budgets were changed.",
    ]
    # Fence completion and every staged output behind the current lease token.
    result = db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run_id,
            AgentRun.status == "running",
            AgentRun.lease_token == lease_token,
            AgentRun.lease_expires_at > utcnow(),
        )
        .values(
            status="completed",
            tools=list(TOOLS),
            decisions=decisions,
            output={"summary": summary, "insight_count": len(proposals)},
            completed_at=now,
            lease_token=None,
            lease_expires_at=None,
            error=None,
        ),
        execution_options={"synchronize_session": False},
    )
    if result.rowcount != 1:
        raise LostLease()
    audit(
        db,
        user.id,
        "orchestrator",
        "agent_run_completed",
        decisions[1],
        list(TOOLS),
        trace_id=run.trace_id,
    )


def process_next(factory=SessionLocal):
    """Claim/commit first, then execute atomically. Failure rolls back all proposed outputs."""
    with factory() as db:
        run = claim_next_run(db)
        db.commit()
        if not run:
            return False
        run_id, lease_token = run.id, run.lease_token
    try:
        with factory() as db:
            _execute(db, run_id, lease_token)
            db.commit()
    except LostLease:
        logger.info("Discarded a proactive workflow whose lease is no longer owned.")
    except Exception as exc:
        # Exception text may contain customer/provider data and is never saved or logged.
        logger.warning("Proactive workflow failed (%s).", type(exc).__name__)
        with factory() as db:
            run = db.get(AgentRun, run_id)
            if run and run.status == "running" and run.lease_token == lease_token:
                failed = run.attempts >= run.max_attempts
                now = utcnow()
                run.status = "failed" if failed else "queued"
                run.error = "Financial review failed. Retry after checking service availability."
                run.available_at = now + timedelta(seconds=min(60, 5 * 2**run.attempts))
                run.completed_at = now if failed else None
                run.lease_token = None
                run.lease_expires_at = None
                audit(
                    db,
                    run.user_id,
                    "orchestrator",
                    "agent_run_failed",
                    "Read-only financial review failed; outputs were rolled back and retries are bounded.",
                    [],
                    trace_id=run.trace_id,
                )
                db.commit()
    return True


class ProactiveWorker:
    def __init__(self, factory=SessionLocal, poll_seconds=2):
        self.factory = factory
        self.poll_seconds = max(0.1, float(poll_seconds))
        self.stopped = Event()
        self.thread = Thread(
            target=self._loop, name="aegis-financial-health-worker", daemon=True
        )

    def start(self):
        self.thread.start()
        return self

    def stop(self, timeout=10):
        self.stopped.set()
        self.thread.join(timeout=timeout)

    def _loop(self):
        while not self.stopped.is_set():
            try:
                worked = process_next(self.factory)
            except Exception as exc:
                logger.warning(
                    "Proactive worker polling failed (%s).", type(exc).__name__
                )
                worked = False
            # Use an interruptible wait, including between jobs, to avoid busy waiting.
            self.stopped.wait(0.1 if worked else self.poll_seconds)


def start_worker(factory=SessionLocal, poll_seconds=2):
    return ProactiveWorker(factory, poll_seconds).start()
