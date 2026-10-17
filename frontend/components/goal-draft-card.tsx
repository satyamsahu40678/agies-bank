"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Target } from "lucide-react";
import { api, money } from "@/lib/api";
import type { GoalDraft } from "@/lib/ai";
import { Button, Field, Modal, Notice } from "./ui";

export function GoalDraftCard({ draft, inlineReview = false }: { draft: GoalDraft; inlineReview?: boolean }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(draft.name);
  const [amount, setAmount] = useState(draft.target_amount);
  const [date, setDate] = useState(draft.target_date);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (busy || saved) return;
    setBusy(true); setError("");
    try {
      await api("/goals", { method: "POST", headers: { "Idempotency-Key": draft.id }, body: { name: name.trim(), target_amount: amount, target_date: date, saved_amount: "0.00" } });
      setSaved(true); setOpen(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save your goal."); }
    finally { setBusy(false); }
  }
  const form = <form onSubmit={save} className="stack">
    <Field label="Goal name"><input aria-label="AI goal name" required minLength={2} maxLength={100} value={name} onChange={e => setName(e.target.value)} disabled={busy} /></Field>
    <Field label="Target amount (INR)"><input aria-label="AI goal target amount" type="number" required min="0.01" max="100000000" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} disabled={busy} /></Field>
    <Field label="Target date"><input aria-label="AI goal target date" type="date" required value={date} onChange={e => setDate(e.target.value)} disabled={busy} /></Field>
    <p className="muted">The estimate above applies to the original draft. Your saved plan recalculates contributions from the final amount and date. Recorded savings start at zero.</p>
    {error && <Notice tone="danger">{error}</Notice>}
    <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save this goal"}</Button>
  </form>;
  return <div className="chat-proposal ai-goal-card">
    <div className="row-between"><strong><Target size={16} /> {draft.name}</strong><span className="chip">{saved ? "Saved" : "Draft"}</span></div>
    <p>{money(draft.target_amount)} by {draft.target_date} · about {money(draft.monthly_contribution)} / month</p>
    <p className="muted">Estimated capacity after existing goals: {money(draft.monthly_capacity)} / month.</p>
    {Number(draft.monthly_shortfall) > 0 && <Notice tone="warning">This plan exceeds recorded monthly capacity by {money(draft.monthly_shortfall)}. Consider a smaller target or a later date.</Notice>}
    <p className="muted">A planning record. Saving it does not move or reserve money.</p>
    {saved ? <Link href="/insights#goals" className="button button-secondary"><Check size={14} /> View saved goals</Link> : <Button onClick={() => setOpen(true)}>Review goal draft</Button>}
    {open && (inlineReview ? form : <Modal title="Review your goal" onClose={() => { if (!busy) setOpen(false); }}>{form}</Modal>)}
  </div>;
}
