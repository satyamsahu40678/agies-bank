"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bot, CalendarClock, FileSearch, Play, ShieldCheck, Sparkles, Target } from "lucide-react";
import { api, dateTime, useResource } from "@/lib/api";
import type { AgentRun } from "@/lib/agentic";
import { Button, Card, ErrorState, LoadingState, Notice, PageHeader, StatusBadge } from "@/components/ui";
import styles from "./workflows.module.css";

type Schedule = { id: string; kind: string; enabled: boolean; interval_hours: number; next_run_at: string; last_run_id: string | null };
type Workflow = { kind: string; name: string; description: string; tools: string[] };
type Catalog = { catalog: Workflow[]; items: Schedule[] };
const icons: Record<string, typeof Bot> = { financial_health: Sparkles, security_review: ShieldCheck, document_review: FileSearch, savings_coach: Target };
const descriptions: Record<string, string> = {
  financial_health: "A regular look at your balances, spending, budgets and next steps.",
  security_review: "Review account access and unusual activity so you can act with confidence.",
  document_review: "Check your saved documents and find the information you need.",
  savings_coach: "Track your goals and find practical ways to save.",
  cashflow_review: "Look ahead at estimated balances and see whether your goals fit the same monthly savings capacity.",
  expense_review: "Spot possible recurring payments and decide what deserves a closer look.",
};
const reviewPages: Record<string, string> = { security_review: "/security", document_review: "/documents", savings_coach: "/insights", financial_health: "/insights", cashflow_review: "/analysis", expense_review: "/analysis" };
const reviewSummary = (status: string) => status === "completed" ? "Your banking specialist has completed this review." : status === "running" ? "Your review is in progress." : status === "failed" ? "This review could not finish. You can try again." : "Your review is saved and will begin shortly.";

export default function AutomationsPage() {
  const schedules = useResource<Catalog>("/automations");
  const runs = useResource<AgentRun[]>("/agent-runs");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [failure, setFailure] = useState("");
  const [intervals, setIntervals] = useState<Record<string, number>>({});
  const pending = runs.data?.some(run => ["queued", "running"].includes(run.status));
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => { void runs.refresh(); }, 4000);
    return () => clearInterval(timer);
  }, [pending, runs.refresh]);

  async function change(workflow: Workflow, enabled: boolean, runNow = false) {
    setBusy(workflow.kind); setFailure(""); setMessage("");
    const current = schedules.data?.items.find(item => item.kind === workflow.kind);
    try {
      const saved = await api<Schedule>("/automations", { method: "PUT", body: { kind: workflow.kind, enabled, interval_hours: intervals[workflow.kind] ?? current?.interval_hours ?? 24 } });
      if (runNow) {
        await api(`/automations/${saved.id}/run`, { method: "POST" });
        setMessage(`${workflow.name} is queued. You can leave this page; its progress is saved.`);
      } else setMessage(`${workflow.name} ${enabled ? "schedule saved" : "paused"}.`);
      await Promise.all([schedules.refresh(), runs.refresh()]);
    } catch (error) { setFailure(error instanceof Error ? error.message : "Unable to update workflow."); }
    finally { setBusy(""); }
  }

  if (schedules.loading && !schedules.data) return <LoadingState />;
  if (schedules.error) return <ErrorState message={schedules.error} onRetry={schedules.refresh} />;
  return <>
    <PageHeader eyebrow="YOUR AGENT WORKSPACE" title="Put your reviews on a schedule" description="Choose the reviews you want, set their cadence, and follow every run." />
    <div className={styles.banner}><div className={styles.bannerIcon}><CalendarClock size={26} /></div><div><h2>A little less to keep track of.</h2><p>Your agents review your saved banking information and suggest next steps. You stay in control of payments, account access, identity decisions, and every financial action.</p></div><Link href="/insights">View your insights →</Link></div>
    {message && <Notice tone="success">{message}</Notice>}
    {failure && <Notice tone="danger">{failure}</Notice>}
    <div className={styles.grid}>
      {schedules.data?.catalog.map(workflow => {
        const item = schedules.data?.items.find(item => item.kind === workflow.kind);
        const Icon = icons[workflow.kind] || Bot;
        return <Card key={workflow.kind} className={styles.workflow}>
          <div className={styles.top}><div className={styles.icon}><Icon size={23} /></div><StatusBadge status={item?.enabled ? "active" : "paused"} /></div>
          <h2>{workflow.name}</h2><p>{descriptions[workflow.kind] || "Review your information and plan your next step."}</p>
          <label className="field"><span>Review frequency</span><select aria-label={`${workflow.name} frequency`} value={intervals[workflow.kind] ?? item?.interval_hours ?? 24} onChange={e => setIntervals(previous => ({ ...previous, [workflow.kind]: Number(e.target.value) }))}><option value={6}>Every 6 hours</option><option value={12}>Every 12 hours</option><option value={24}>Daily</option><option value={168}>Weekly</option></select></label>
          <div className={styles.next}>{item?.enabled ? `Next review ${dateTime(item.next_run_at)}` : "Enable a schedule whenever you’re ready."}</div>
          <div className={styles.actions}><Button disabled={!!busy} onClick={() => change(workflow, true)}>{busy === workflow.kind ? "Saving…" : item?.enabled ? "Save schedule" : "Enable schedule"}</Button><Button variant="secondary" disabled={!!busy} onClick={() => change(workflow, true, true)}><Play size={14} /> Run now</Button>{item?.enabled && <Button variant="ghost" disabled={!!busy} onClick={() => change(workflow, false)}>Pause</Button>}</div>
        </Card>;
      })}
    </div>
    <div className={styles.runHeading}><div><p className="eyebrow">TRANSPARENT BY DESIGN</p><h2>Recent agent runs</h2></div><Button variant="secondary" onClick={runs.refresh}>Refresh history</Button></div>
    {runs.error && <Notice tone="danger">{runs.error}</Notice>}
    {!runs.data?.length && <Card><p>Your first run will appear here after you enable or start a review.</p></Card>}
    <div className={styles.history}>{runs.data?.slice(0, 12).map(run => <Card key={run.id} className={styles.run}><div className={styles.top}><div><h3>{schedules.data?.catalog.find(item => item.kind === run.kind)?.name || "Financial health review"}</h3><small>{dateTime(run.created_at)}</small></div><StatusBadge status={run.status} /></div><p>{reviewSummary(run.status)}</p>{run.status === "completed" && <Link className="button button-ghost" href={reviewPages[run.kind || "financial_health"] || "/insights"}>View updates →</Link>}</Card>)}</div>
  </>;
}
