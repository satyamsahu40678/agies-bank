"""Read-only analysis. Integer paise and complete scoped posted-ledger windows."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
import math
import re
from statistics import median

from fastapi import HTTPException

from ..models import Account, LedgerEntry, SavingsGoal, utcnow
from ..query import select
from .common import money, paise, redact


def account(db, user):
    if user.role != "customer":
        raise HTTPException(403, "Customer access is required.")
    row = db.scalar(select(Account).where(Account.user_id == user.id))
    if row is None:
        raise HTTPException(404, "Customer account not found.")
    return row


def cashflow(db, user):
    row = account(db, user)
    now = utcnow()
    entries = db.scalars(select(LedgerEntry).where(
        LedgerEntry.account_id == row.id, LedgerEntry.status == "posted",
        LedgerEntry.created_at >= now - timedelta(days=30), LedgerEntry.created_at <= now,
    )).all()
    income = sum(e.amount_paise for e in entries if e.direction == "credit")
    expenses = sum(e.amount_paise for e in entries if e.direction == "debit")
    net = income - expenses
    return {
        "period": "Last 30 days", "as_of": now.isoformat(), "record_count": len(entries),
        "balance": money(row.balance_paise), "income": money(income), "expenses": money(expenses),
        "net_cashflow": money(net), "monthly_capacity": money(max(0, net)),
        "projections": [{"days": days, "estimated_balance": money(row.balance_paise + net * (days // 30))} for days in (30, 60, 90)],
        "estimated": True,
        "assumptions": "Illustration repeats the last 30 days of posted income and expenses, including transfers. Future bills, timing, interest and unrecorded activity are unknown. A negative estimate is a planning shortfall, not an available overdraft.",
    }


def recurring(db, user):
    row = account(db, user)
    now = utcnow()
    entries = db.scalars(select(LedgerEntry).where(
        LedgerEntry.account_id == row.id, LedgerEntry.status == "posted", LedgerEntry.direction == "debit",
        LedgerEntry.created_at >= now - timedelta(days=120), LedgerEntry.created_at <= now,
    )).all()
    groups = defaultdict(list)
    for entry in entries:
        if entry.category.casefold() == "transfer":
            continue
        label = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", entry.description.casefold())).strip()
        if label:
            groups[(label, entry.category)].append(entry)
    patterns = []
    for (label, category), rows in groups.items():
        rows.sort(key=lambda e: e.created_at)
        days = sorted({e.created_at.date() for e in rows})
        if len(days) < 3:
            continue
        gaps = [(b - a).days for a, b in zip(days, days[1:])]
        typical = median(gaps)
        cadence = "weekly" if 5 <= typical <= 9 else "monthly" if 25 <= typical <= 35 else None
        if not cadence or any(abs(gap - typical) > (3 if cadence == "weekly" else 7) for gap in gaps):
            continue
        amounts = [e.amount_paise for e in rows]
        ordered_amounts = sorted(amounts)
        middle = len(ordered_amounts) // 2
        amount = ordered_amounts[middle] if len(ordered_amounts) % 2 else (ordered_amounts[middle - 1] + ordered_amounts[middle]) // 2
        if amount <= 0 or max(amounts) - min(amounts) > max(100, amount // 5):
            continue
        next_date = days[-1] + timedelta(days=round(typical))
        patterns.append({
            "merchant": redact(rows[-1].description)[:100], "category": category, "cadence": cadence,
            "occurrences": len(rows), "typical_amount": money(amount),
            "estimated_monthly_cost": money((amount * 30 + 3) // 7 if cadence == "weekly" else amount),
            "last_seen": days[-1].isoformat(), "next_expected": next_date.isoformat(),
            "overdue_pattern": next_date < now.date(),
        })
    patterns.sort(key=lambda p: (-Decimal(p["estimated_monthly_cost"]), p["merchant"]))
    return {
        "period": "Last 120 days", "record_count": len(entries), "patterns": patterns,
        "estimated_monthly_total": money(sum(paise(p["estimated_monthly_cost"], allow_zero=True) for p in patterns)),
        "assumptions": "Possible recurring expenses require at least three distinct payment dates, similar amounts and weekly or monthly gaps. These are patterns, not confirmed subscriptions or scheduled bills. Nothing is cancelled or paid automatically.",
    }


def goal_review(db, user):
    flow = cashflow(db, user)
    goals = db.scalars(select(SavingsGoal).where(SavingsGoal.user_id == user.id, SavingsGoal.status == "active")).all()
    items = []
    total = 0
    for goal in goals:
        months = max(1, math.ceil((goal.target_date - date.today()).days / 30)) if goal.target_date else 6
        required = max(0, (goal.target_paise - goal.saved_paise + months - 1) // months)
        total += required
        items.append({"id": goal.id, "name": goal.name, "target_amount": money(goal.target_paise), "saved_amount": money(goal.saved_paise), "target_date": goal.target_date.isoformat() if goal.target_date else None, "months": months, "monthly_contribution": money(required)})
    capacity = paise(flow["monthly_capacity"], allow_zero=True)
    return {"goals": items, "combined_monthly_contribution": money(total), "monthly_capacity": flow["monthly_capacity"], "monthly_shortfall": money(max(0, total - capacity)), "planning_only": True, "assumptions": "Monthly contributions share the same last-30-day surplus. A goal without a date uses six months. Saved amounts are customer-entered plans, not reserved balances."}


def draft_goal(db, user, values):
    name = str(values.get("name", "")).strip()
    if not 2 <= len(name) <= 100 or re.search(r"[\x00-\x1f\x7f]", name):
        raise HTTPException(422, "Provide a goal name of 2 to 100 printable characters.")
    target = paise(values.get("target_amount"))
    months = values.get("months", 6)
    if type(months) is not int or not 1 <= months <= 600:
        raise HTTPException(422, "Choose a whole number of months between 1 and 600.")
    flow = cashflow(db, user)
    review = goal_review(db, user)
    contribution = (target + months - 1) // months
    existing = paise(review["combined_monthly_contribution"], allow_zero=True)
    capacity = paise(flow["monthly_capacity"], allow_zero=True)
    return {
        "name": name, "target_amount": money(target), "saved_amount": "0.00",
        "target_date": (date.today() + timedelta(days=months * 30)).isoformat(), "months": months,
        "monthly_contribution": money(contribution), "monthly_capacity": money(max(0, capacity - existing)),
        "monthly_shortfall": money(max(0, existing + contribution - capacity)),
        "planning_only": True, "requires_confirmation": True,
        "message": "Review and save this goal to add it to your plan. No money is moved or reserved. The estimate repeats recorded cash flow; income and expenses may change.",
    }


def overview(db, user):
    return {"cashflow": cashflow(db, user), "recurring": recurring(db, user), "goals": goal_review(db, user)}
