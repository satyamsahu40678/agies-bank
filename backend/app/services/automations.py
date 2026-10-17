"""Customer-controlled schedules and deterministic, scoped agent workflows."""

import time
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException

from ..db import SessionLocal
from ..models import (
    Alert,
    Automation,
    Document,
    DocumentChunk,
    SecurityEvent,
    User,
    utcnow,
)
from ..query import ConcurrentWrite, select
from .common import audit

CATALOG = [
    {
        "kind": "cashflow_review",
        "name": "Cash-flow analyst",
        "description": "Estimate your cash-flow outlook and compare all goals against the same savings capacity.",
        "tools": ["get_cashflow_forecast", "get_goal_plan"],
    },
    {
        "kind": "expense_review",
        "name": "Expense detective",
        "description": "Look for possible weekly or monthly recurring expenses in posted transactions.",
        "tools": ["get_recurring_expenses"],
    },
    {
        "kind": "financial_health",
        "name": "Financial health review",
        "description": "Review cash flow, budgets, recurring expenses and affordability.",
        "tools": ["get_balance", "get_spending", "get_budgets", "get_recommendations"],
    },
    {
        "kind": "security_review",
        "name": "Security watch",
        "description": "Check recent risky sessions and unresolved alerts; suggest your next action.",
        "tools": ["security_events:read", "alerts:read"],
    },
    {
        "kind": "document_review",
        "name": "Document readiness",
        "description": "Check your document inventory and whether uploaded evidence has searchable text.",
        "tools": ["documents:read", "document_chunks:read"],
    },
    {
        "kind": "savings_coach",
        "name": "Savings coach",
        "description": "Track planning goals and review contributions against your posted cash flow.",
        "tools": ["goals:read", "ledger:read"],
    },
]
KINDS = {item["kind"] for item in CATALOG}


def automation_json(item):
    return {
        key: getattr(item, key)
        for key in [
            "id",
            "kind",
            "name",
            "enabled",
            "interval_hours",
            "next_run_at",
            "last_run_id",
            "created_at",
            "updated_at",
        ]
    }


def owned(db, user, automation_id):
    item = db.get(Automation, automation_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "Automation not found")
    return item


def save(db, user, kind, interval_hours=24, enabled=True):
    if kind not in KINDS:
        raise HTTPException(422, "Unknown workflow")
    item = db.scalar(
        select(Automation).where(Automation.user_id == user.id, Automation.kind == kind)
    )
    if item is None:
        item = Automation(
            user_id=user.id,
            kind=kind,
            name=next(x["name"] for x in CATALOG if x["kind"] == kind),
        )
        db.add(item)
    was_enabled = item.enabled
    item.interval_hours, item.enabled, item.updated_at = (
        interval_hours,
        enabled,
        utcnow(),
    )
    if enabled and not was_enabled:
        item.next_run_at = utcnow()
    audit(
        db,
        user.id,
        "orchestrator",
        "automation_updated",
        f"Customer {'enabled' if enabled else 'paused'} the {kind} workflow every {interval_hours} hours.",
        ["automations:write"],
    )
    return item


def queue(db, user, item, *, scheduled=False):
    from .proactive import enqueue_health_check

    key = (
        item.id
        + ":"
        + (item.next_run_at.isoformat() if scheduled else utcnow().isoformat())
    )
    run = enqueue_health_check(
        db,
        user,
        "scheduled_review" if scheduled else "automation_manual",
        key,
        kind=item.kind,
    )
    item.last_run_id, item.updated_at = run.id, utcnow()
    if scheduled:
        item.next_run_at = utcnow() + timedelta(hours=item.interval_hours)
    return run


def dispatch_due(factory=SessionLocal, *, max_schedules=100):
    """Each schedule advance and its outbox job commit in the same transaction."""
    with factory() as db:
        due_ids = db.scalars(
            select(Automation.id)
            .where(Automation.enabled == True, Automation.next_run_at <= utcnow())
            .order_by(Automation.next_run_at)
            .limit(max_schedules)
        ).all()
    queued = 0
    for automation_id in due_ids:
        for attempt in range(5):
            try:
                with factory() as db:
                    item = db.get(Automation, automation_id)
                    if not item or not item.enabled or item.next_run_at > utcnow():
                        break
                    user = db.get(User, item.user_id)
                    if not user or user.role != "customer":
                        break
                    queue(db, user, item, scheduled=True)
                    db.commit()
                    queued += 1
                    break
            except ConcurrentWrite:
                if attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))
    return queued


def build_plan(db, user, run):
    from .proactive import TOOLS, _health_plan, _insight

    if run.kind in {"cashflow_review", "expense_review"}:
        from .intelligence import REGISTRY, ToolContext
        from .common import paise

        context = ToolContext(db, user, run.trace_id, frozenset({"ledger:read", "goals:read"}))
        names = ["get_cashflow_forecast", "get_goal_plan"] if run.kind == "cashflow_review" else ["get_recurring_expenses"]
        values = {name: REGISTRY.invoke(name, context, {}) for name in names}
        for name in names:
            audit(db, user.id, REGISTRY.agent_for(name), "proactive_tool_completed", "Reviewed customer planning information without changing any financial record.", [name], trace_id=run.trace_id)
        if run.kind == "cashflow_review":
            flow, goals = values[names[0]], values[names[1]]
            shortfall = paise(goals["monthly_shortfall"], allow_zero=True)
            summary = {"monthly_capacity": flow["monthly_capacity"], "monthly_goal_shortfall": goals["monthly_shortfall"], "estimated_balance_30_days": flow["projections"][0]["estimated_balance"], "read_only": True}
            message = f"Repeating the last 30 days gives an estimated balance of INR {summary['estimated_balance_30_days']} in 30 days. Active goals need INR {goals['combined_monthly_contribution']} monthly; recorded monthly capacity is INR {flow['monthly_capacity']}. Shortfall: INR {goals['monthly_shortfall']}. Estimates exclude unrecorded future changes."
            title = "Your cash-flow outlook"
            severity = "warning" if shortfall or Decimal(flow["projections"][0]["estimated_balance"]) < 0 else "info"
        else:
            expenses = values[names[0]]
            summary = {"possible_patterns": len(expenses["patterns"]), "estimated_monthly_total": expenses["estimated_monthly_total"], "read_only": True}
            message = f"Found {summary['possible_patterns']} possible recurring expense patterns, estimated at INR {summary['estimated_monthly_total']} monthly. Patterns require at least three payment dates and are not confirmed bills or subscriptions. Review them before changing any payment."
            title, severity = "Your recurring expense review", "info"
        proposal = _insight(run.kind, "latest", severity, title, message, "Explore analysis", "/analysis", summary)
        return summary, [proposal], names

    if run.kind == "savings_coach":
        summary, proposals = _health_plan(db, user, run)
        return (
            summary,
            [
                dict(p, kind="savings_coach_" + p["kind"])
                for p in proposals
                if p["kind"] in {"goal", "cashflow", "savings"}
            ],
            list(TOOLS) + ["goals:read"],
        )
    if run.kind == "security_review":
        events = db.scalars(
            select(SecurityEvent).where(
                SecurityEvent.user_id == user.id,
                SecurityEvent.created_at >= utcnow() - timedelta(days=7),
            )
        ).all()
        alerts = db.scalars(select(Alert).where(Alert.user_id == user.id)).all()
        risky = [e for e in events if e.risk_score >= 50]
        unresolved = [a for a in alerts if a.status == "unread"]
        summary = {
            "events_reviewed": len(events),
            "risky_events": len(risky),
            "unread_alerts": len(unresolved),
            "period": "Last 7 days",
            "read_only": True,
        }
        proposal = _insight(
            "security_watch",
            "weekly",
            "warning" if risky or unresolved else "info",
            "Review your security signals"
            if risky or unresolved
            else "Security review complete",
            f"Reviewed {len(events)} recent events: {len(risky)} elevated-risk signals and {len(unresolved)} unread alerts. Open Security center to review evidence.",
            "Review security",
            "/security",
            summary,
        )
        return summary, [proposal], ["security_events:read", "alerts:read"]
    if run.kind == "document_review":
        docs = db.scalars(select(Document).where(Document.user_id == user.id)).all()
        empty = []
        for doc in docs:
            if not db.scalar(
                select(DocumentChunk.id)
                .where(DocumentChunk.document_id == doc.id)
                .limit(1)
            ):
                empty.append(doc.id)
        summary = {
            "documents_reviewed": len(docs),
            "missing_text": len(empty),
            "read_only": True,
        }
        proposal = _insight(
            "document_readiness",
            "inventory",
            "warning" if empty or not docs else "info",
            "Document readiness review",
            f"You have {len(docs)} private documents; {len(empty)} lack searchable text. Upload a text-based PDF or TXT statement to ground assistant answers in your own evidence.",
            "Review documents",
            "/documents",
            summary,
        )
        return summary, [proposal], ["documents:read", "document_chunks:read"]
    raise ValueError("Unsupported workflow kind")
