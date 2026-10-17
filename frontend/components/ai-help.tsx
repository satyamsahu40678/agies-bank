"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { aiContexts, type AiReply } from "@/lib/ai";
import { customerAgentName } from "@/lib/customer-labels";
import { ChatMarkdown } from "./chat-markdown";
import { GoalDraftCard } from "./goal-draft-card";
import { Button, Modal, Notice } from "./ui";

export function AskAiButton({ prompt, children }: { prompt: string; children?: React.ReactNode }) {
  return <Button variant="secondary" onClick={() => window.dispatchEvent(new CustomEvent("agies:ask-ai", { detail: prompt }))}><Sparkles size={15} />{children || "Ask AI"}</Button>;
}

export function AiHelp() {
  const path = usePathname();
  const context = aiContexts[path.split("/")[1]] || aiContexts.dashboard;
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reply, setReply] = useState<AiReply | null>(null);
  const inFlight = useRef(false);
  useEffect(() => { setOpen(false); }, [path]);
  useEffect(() => {
    const listener = (event: Event) => {
      const prompt = (event as CustomEvent<unknown>).detail;
      if (typeof prompt !== "string" || !prompt.trim() || prompt.length > 2000) return;
      setOpen(true); setInput(prompt); void ask(prompt);
    };
    window.addEventListener("agies:ask-ai", listener);
    return () => window.removeEventListener("agies:ask-ai", listener);
  }, []);
  async function ask(question: string) {
    if (!question.trim() || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(""); setReply(null);
    try { setReply(await api<AiReply>("/chat", { method: "POST", body: { message: question.trim() } })); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to reach your assistant. Please try again."); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <>
    <button className="ai-help-trigger" onClick={() => setOpen(true)} aria-label="Ask AI about this page"><Sparkles size={18} /><span>Ask AI</span></button>
    {open && <Modal title={context.title} onClose={() => setOpen(false)}>
      <div className="ai-help-panel">
        <p className="muted">Ask a question or choose a starting point. Your assistant uses your saved information and banking guides.</p>
        <div className="ai-help-actions">{context.prompts.map(prompt => <button key={prompt} disabled={busy} onClick={() => { setInput(prompt); void ask(prompt); }}><Sparkles size={15} />{prompt}</button>)}</div>
        <form onSubmit={event => { event.preventDefault(); void ask(input); }} className="ai-help-form">
          <label className="sr-only" htmlFor="page-ai-question">Your AI question</label>
          <textarea id="page-ai-question" placeholder="What would you like to understand or plan?" maxLength={2000} value={input} onChange={e => setInput(e.target.value)} disabled={busy} />
          <Button type="submit" disabled={busy || !input.trim()}><Send size={15} />{busy ? "Thinking…" : "Ask your assistant"}</Button>
        </form>
        {error && <Notice tone="danger">{error}</Notice>}
        {busy && <p role="status">Reviewing your information…</p>}
        {reply && <div className="ai-help-answer" aria-live="polite"><span className="eyebrow">{customerAgentName(reply.agent)}</span><ChatMarkdown>{reply.reply}</ChatMarkdown>
          {reply.goal_drafts?.map(draft => <GoalDraftCard key={draft.id} draft={draft} inlineReview />)}
          {reply.proposal && <Notice>Payment draft: {reply.proposal.amount} INR. <Link href="/payments">Open Payments to choose the recipient and review the amount.</Link></Notice>}
          {!!reply.citations?.length && <div className="ai-source-list">{reply.citations.map((source, index) => <details key={`${source.document_id}-${index}`}><summary>[{index + 1}] {source.title}</summary><blockquote>{source.excerpt}</blockquote>{source.source_url ? <a href={source.source_url} target="_blank" rel="noopener noreferrer">{source.publisher} · reviewed {source.reviewed_at} ↗</a> : <Link href="/documents">Open documents</Link>}</details>)}</div>}
        </div>}
        <Link className="health-text-link" href="/assistant">Open your full conversation →</Link>
      </div>
    </Modal>}
  </>;
}
