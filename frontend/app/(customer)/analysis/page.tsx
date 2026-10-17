"use client";

import Link from "next/link";
import { Activity, CalendarClock, RefreshCw, Target, TrendingUp } from "lucide-react";
import { money, useResource } from "@/lib/api";
import { AskAiButton } from "@/components/ai-help";
import { Button, Card, ErrorState, LoadingState, Notice, PageHeader } from "@/components/ui";
import styles from "@/components/ai-workspace.module.css";

type Analysis = {
  cashflow: { income: string; expenses: string; net_cashflow: string; monthly_capacity: string; as_of: string; projections: { days: number; estimated_balance: string }[]; assumptions: string };
  recurring: { patterns: { merchant: string; category: string; cadence: string; occurrences: number; typical_amount: string; estimated_monthly_cost: string; next_expected: string; overdue_pattern: boolean }[]; estimated_monthly_total: string; assumptions: string };
  goals: { goals: { id: string; name: string; monthly_contribution: string; target_amount: string }[]; combined_monthly_contribution: string; monthly_capacity: string; monthly_shortfall: string; assumptions: string };
};

export default function AnalysisPage() {
  const resource = useResource<Analysis>("/analysis");
  if (resource.loading && !resource.data) return <LoadingState />;
  if (!resource.data) return <ErrorState message={resource.error || "Unable to load your analysis."} onRetry={resource.refresh} />;
  const { cashflow, recurring, goals } = resource.data;
  return <>
    <PageHeader eyebrow="YOUR MONEY, IN FOCUS" title="See what your money is telling you" description="Explore your cash flow, possible recurring expenses and savings plans. Ask your specialists to explain any finding." action={<Button variant="secondary" onClick={resource.refresh} disabled={resource.loading}><RefreshCw size={15} />Refresh analysis</Button>} />
    {resource.error && <Notice tone="danger">{resource.error}</Notice>}
    <div className={styles.metrics}>
      <Card><TrendingUp size={22} /><span>30-day net cash flow</span><strong>{money(cashflow.net_cashflow)}</strong><small>Posted income minus expenses</small></Card>
      <Card><CalendarClock size={22} /><span>Possible recurring expenses</span><strong>{money(recurring.estimated_monthly_total)}</strong><small>Estimated monthly pattern total</small></Card>
      <Card><Target size={22} /><span>Your combined goal plan</span><strong>{money(goals.combined_monthly_contribution)}</strong><small>Monthly contributions across active goals</small></Card>
    </div>
    <div className={styles.columns}>
      <Card className={styles.section}><div className={styles.heading}><div><Activity size={21} /><h2>Cash-flow outlook</h2></div><AskAiButton prompt="Explain my 30, 60 and 90 day cash-flow forecast and the assumptions behind it.">Explain forecast</AskAiButton></div>
        <p>Last 30 days: {money(cashflow.income)} in and {money(cashflow.expenses)} out.</p>
        <div className={styles.table}><table><thead><tr><th>Looking ahead</th><th>Estimated balance</th></tr></thead><tbody>{cashflow.projections.map(point => <tr key={point.days}><td>In {point.days} days</td><td>{money(point.estimated_balance)}</td></tr>)}</tbody></table></div>
        <p className="muted">{cashflow.assumptions}</p>
      </Card>
      <Card className={styles.section}><div className={styles.heading}><div><Target size={21} /><h2>One surplus, all your goals</h2></div><AskAiButton prompt="Review my savings goals together. Explain any shortfall and suggest a practical plan.">Review my plan</AskAiButton></div>
        <p>Recorded monthly capacity: <strong>{money(goals.monthly_capacity)}</strong></p>
        {Number(goals.monthly_shortfall) > 0 && <Notice tone="warning">Your combined plan exceeds recorded capacity by {money(goals.monthly_shortfall)} per month.</Notice>}
        {goals.goals.length ? goals.goals.map(goal => <div className={styles.item} key={goal.id}><strong>{goal.name}</strong><span>{money(goal.monthly_contribution)} / month</span></div>) : <p>No active goals yet. Your savings coach can help you draft one.</p>}
        <AskAiButton prompt="Help me create a savings goal. Ask me for the target amount and timeframe before drafting it.">Plan a goal with AI</AskAiButton>
        <p className="muted">{goals.assumptions}</p><Link href="/insights#goals" className="health-text-link">Manage your goals →</Link>
      </Card>
    </div>
    <Card className={styles.section}><div className={styles.heading}><div><CalendarClock size={21} /><h2>Possible recurring expenses</h2></div><AskAiButton prompt="Find my possible recurring expenses. Explain the evidence and what I should check before changing a payment.">Ask expense detective</AskAiButton></div>
      {recurring.patterns.length ? <div className={styles.table}><table><thead><tr><th>Recorded description</th><th>Pattern</th><th>Typical payment</th><th>Occurrences</th><th>Next pattern date</th></tr></thead><tbody>{recurring.patterns.map((pattern, index) => <tr key={index}><td><strong>{pattern.merchant}</strong><small>{pattern.category}</small></td><td>{pattern.cadence}</td><td>{money(pattern.typical_amount)}</td><td>{pattern.occurrences}</td><td>{pattern.next_expected}{pattern.overdue_pattern ? " (past estimate)" : ""}</td></tr>)}</tbody></table></div> : <Notice>No consistent weekly or monthly pattern with three payment dates was found. As more posted activity is recorded, patterns may become visible.</Notice>}
      <p className="muted">{recurring.assumptions}</p>
    </Card>
    <Card className={styles.banner}><div><h2>Keep the useful reviews coming.</h2><p>Schedule the Cash-flow analyst or Expense detective and review new findings in Financial health.</p></div><Link href="/automations" className="button button-secondary">Choose a review →</Link></Card>
  </>;
}
