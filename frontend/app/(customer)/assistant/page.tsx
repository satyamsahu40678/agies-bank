"use client";
import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  CreditCard,
  Fingerprint,
  Send,
  ShieldCheck,
  Sparkles,
  Wallet,
  X,
} from "lucide-react";
import { api, dateTime, money, useResource } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ChatMarkdown } from "@/components/chat-markdown";
import { customerAgentName } from "@/lib/customer-labels";
import {
  Button,
  Card,
  Field,
  LoadingState,
  Modal,
  Notice,
  PageHeader,
  StatusBadge,
} from "@/components/ui";
type Citation = {
  document_id: string;
  title: string;
  excerpt: string;
  page: number;
};
type Proposal = {
  beneficiary_id: string;
  amount: string | number;
  description: string;
};
type Response = {
  reply: string;
  agent: string;
  tools: { name: string; summary: string }[];
  citations: Citation[];
  proposal?: Proposal;
  trace_id: string;
};
type Message = {
  id: string;
  role: string;
  content: string;
  agent?: string;
  created_at: string;
  result?: Response;
};
type Transfer = {
  id: string;
  status: string;
  risk_score: number;
  signals: { name: string; score: number; detail: string }[];
  decision: string;
  message: string;
  amount: string;
  beneficiary_name: string;
};
const prompts = [
  {
    icon: Wallet,
    title: "Know where you stand",
    text: "What is my available balance?",
  },
  {
    icon: Sparkles,
    title: "Understand your spending",
    text: "Analyze my spending and suggest how I can save.",
  },
  {
    icon: CreditCard,
    title: "Plan your next step",
    text: "Which loans and insurance plans am I eligible for?",
  },
  {
    icon: BookOpen,
    title: "Find a clear answer",
    text: "What does the loan policy say about prepayment?",
  },
];
export default function Assistant() {
  const { user } = useAuth();
  const history = useResource<Message[]>("/chat");
  const health = useResource<{ ai_mode: string; demo_enabled: boolean }>(
    "/health",
  );
  const beneficiaries =
    useResource<{ id: string; name: string; bank: string }[]>("/beneficiaries");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [proposedBy, setProposedBy] = useState("");
  const [idempotency, setIdempotency] = useState("");
  const [transfer, setTransfer] = useState<Transfer | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [paymentError, setPaymentError] = useState("");
  const [password, setPassword] = useState("");
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (history.data) setMessages(history.data);
  }, [history.data]);
  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("q");
    if (initial) setInput(initial);
  }, []);
  useEffect(() => {
    endRef.current?.scrollIntoView({
      behavior: messages.length > 2 ? "smooth" : "auto",
      block: "end",
    });
  }, [messages, sending]);
  async function send(value?: string) {
    const message = (value ?? input).trim();
    if (!message || sending) return;
    setInput("");
    setError("");
    setSending(true);
    const id = crypto.randomUUID();
    setMessages((previous) => [
      ...previous,
      {
        id,
        role: "user",
        content: message,
        created_at: new Date().toISOString(),
      },
    ]);
    try {
      const result = await api<Response>("/chat", {
        method: "POST",
        body: { message },
      });
      setMessages((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: result.reply,
          agent: result.agent,
          created_at: new Date().toISOString(),
          result,
        },
      ]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Your message could not be sent.",
      );
      setInput(message);
      setMessages((previous) => previous.filter((item) => item.id !== id));
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }
  function propose(value: Proposal, id: string) {
    setProposal(value);
    setProposedBy(id);
    setIdempotency(crypto.randomUUID());
    setTransfer(null);
    setPaymentError("");
    setPassword("");
  }
  async function confirm() {
    if (!proposal) return;
    setSubmitting(true);
    setPaymentError("");
    try {
      const result = await api<Transfer>("/transfers", {
        method: "POST",
        body: { ...proposal, idempotency_key: idempotency },
      });
      setTransfer(result);
      setCompleted((previous) => new Set(previous).add(proposedBy));
      if (!["pending_step_up", "step_up_required"].includes(result.status)) {
        setProposal(null);
      }
    } catch (err) {
      setPaymentError(
        err instanceof Error ? err.message : "Payment could not be submitted.",
      );
    } finally {
      setSubmitting(false);
    }
  }
  async function verify() {
    if (!transfer) return;
    setSubmitting(true);
    setPaymentError("");
    try {
      const result = await api<Transfer>(`/transfers/${transfer.id}/step-up`, {
        method: "POST",
        body: { password },
      });
      setTransfer(result);
      setProposal(null);
      setPassword("");
    } catch (err) {
      setPaymentError(
        err instanceof Error
          ? err.message
          : "Verification could not be completed.",
      );
    } finally {
      setSubmitting(false);
    }
  }
  const lastResponse = [...messages]
    .reverse()
    .find((item) => item.result)?.result;
  const recipient = beneficiaries.data?.find(
    (item) => item.id === proposal?.beneficiary_id,
  );
  return (
    <div className="assistant-page">
      <PageHeader
        eyebrow="YOUR PERSONAL BANKING COPILOT"
        title="A thoughtful second opinion."
        description="Ask freely. Understand the answer. Decide what happens next."
        action={
          <div className="assistant-mode">
            <span className="pulse-dot" />
            {health.data ? "Ready to help" : "Connecting…"}
          </div>
        }
      />
      <div className="assistant-layout">
        <Card className="chat-panel">
          <div className="chat-topbar">
            <span className="ai-orb">
              <Sparkles size={18} />
            </span>
            <div>
              <strong>Aegis assistant</strong>
              <span>Five specialists. One clear answer.</span>
            </div>
            <span className="chat-protected">
              <ShieldCheck size={13} />
              You stay in control
            </span>
          </div>
          <div
            className="chat-messages"
            aria-live="polite"
            aria-relevant="additions text"
          >
            {history.loading && !messages.length ? (
              <LoadingState />
            ) : !messages.length ? (
              <div className="chat-welcome">
                <div className="chat-welcome-icon">
                  <Sparkles size={30} />
                </div>
                <p className="eyebrow">LESS GUESSWORK. MORE CONFIDENCE.</p>
                <h2>What’s on your mind, {user?.name.split(" ")[0]}?</h2>
                <p>
                  Let’s turn your questions into a clearer next step.
                  <br />
                  Your account information stays within your workspace.
                </p>
                <div className="prompt-grid">
                  {prompts.map((prompt) => (
                    <button
                      key={prompt.title}
                      onClick={() => void send(prompt.text)}
                      disabled={sending}
                    >
                      <prompt.icon size={18} />
                      <div>
                        <strong>{prompt.title}</strong>
                        <span>{prompt.text}</span>
                      </div>
                      <ArrowUpRight size={13} />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`chat-message ${message.role === "user" ? "user-message" : "assistant-message"}`}
                >
                  {message.role !== "user" && (
                    <span className="message-avatar">
                      <Sparkles size={14} />
                    </span>
                  )}
                  <div className="message-body">
                    {message.role !== "user" && (
                      <span className="message-agent">
                        {customerAgentName(message.agent)}
                      </span>
                    )}
                    <div className="message-content">
                      {message.role === "user" ? message.content : (
                        <ChatMarkdown>{message.content}</ChatMarkdown>
                      )}
                    </div>
                    {message.result?.citations?.length ? (
                      <div className="chat-citations">
                        {message.result.citations.map((citation, index) => (
                          <details key={`${citation.document_id}-${index}`}>
                            <summary>
                              <BookOpen size={12} />
                              {citation.title}
                              <span>p. {citation.page}</span>
                              <ChevronDown size={12} />
                            </summary>
                            <blockquote>{citation.excerpt}</blockquote>
                            <Link href="/documents">
                              Open document workspace
                              <ArrowUpRight size={11} />
                            </Link>
                          </details>
                        ))}
                      </div>
                    ) : null}
                    {message.result?.proposal && (
                      <div className="chat-proposal">
                        <div className="row-between">
                          <strong>Payment prepared</strong>
                          <span className="chip">Your approval required</span>
                        </div>
                        <p>
                          {money(message.result.proposal.amount)} ·{" "}
                          {message.result.proposal.description}
                        </p>
                        <p className="muted">
                          No money has moved. Review the recipient and amount
                          before you submit.
                        </p>
                        <Button
                          disabled={completed.has(message.id)}
                          onClick={() =>
                            propose(message.result!.proposal!, message.id)
                          }
                        >
                          {completed.has(message.id) ? (
                            <>
                              <Check size={14} />
                              Submitted for processing
                            </>
                          ) : (
                            <>
                              Review proposed payment
                              <ArrowRight size={14} />
                            </>
                          )}
                        </Button>
                      </div>
                    )}
                    <span className="message-time">
                      {dateTime(message.created_at)}
                    </span>
                  </div>
                </div>
              ))
            )}
            {sending && (
              <div className="chat-message assistant-message">
                <span className="message-avatar">
                  <Sparkles size={14} />
                </span>
                <div className="assistant-thinking">
                  <span />
                  <span />
                  <span />
                  <p>Connecting the right specialists…</p>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>
          {history.error && !messages.length && (
            <Notice tone="danger">
              {history.error}
              <Button variant="ghost" onClick={history.refresh}>
                Retry history
              </Button>
            </Notice>
          )}
          {error && <Notice tone="danger">{error}</Notice>}
          {transfer && !proposal && (
            <div
              className={`chat-transfer-result notice notice-${transfer.status === "posted" ? "success" : transfer.status === "rejected" ? "danger" : "warning"}`}
              role="status"
            >
              <div className="row-between">
                <strong>{transfer.message}</strong>
                <StatusBadge status={transfer.status} />
              </div>
              <p>
                {money(transfer.amount)} · Risk score {transfer.risk_score}/100
              </p>
              <Link href="/payments">
                View your payment activity
                <ArrowRight size={12} />
              </Link>
            </div>
          )}
          <form
            className="chat-composer"
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              void send();
            }}
          >
            <label className="sr-only" htmlFor="assistant-message">
              Message your assistant
            </label>
            <textarea
              ref={inputRef}
              id="assistant-message"
              placeholder="Ask about your money, documents, or next move…"
              value={input}
              maxLength={4000}
              onChange={(event) => setInput(event.target.value)}
              rows={1}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send();
                }
              }}
            />
            <button
              type="submit"
              className="chat-send"
              disabled={sending || !input.trim()}
              aria-label="Send message"
            >
              <ArrowUpRight size={19} />
            </button>
          </form>
          <div className="chat-composer-note">
            <ShieldCheck size={11} />
            <span>
              Payments always require your confirmation.
            </span>
          </div>
        </Card>
        <aside className="assistant-context">
          <Card>
            <div className="row">
              <span className="mini-ai-icon">
                <Bot size={17} />
              </span>
              <h3>Your banking team</h3>
            </div>
            <div className="specialist-list">
              {[
                {
                  name: "Identity guide",
                  text: "Help with your verification steps",
                  icon: Fingerprint,
                },
                {
                  name: "Security guardian",
                  text: "Understand alerts and unusual activity",
                  icon: ShieldCheck,
                },
                {
                  name: "Banking assistant",
                  text: "Balances, budgets and payment planning",
                  icon: Wallet,
                },
                {
                  name: "Document guide",
                  text: "Clear answers from your documents",
                  icon: BookOpen,
                },
                {
                  name: "Money coach",
                  text: "Explore options that fit your budget",
                  icon: CreditCard,
                },
              ].map((item) => (
                <div key={item.name}>
                  <span>
                    <item.icon size={16} />
                  </span>
                  <div>
                    <strong>{item.name}</strong>
                    <p>{item.text}</p>
                  </div>
                  <i />
                </div>
              ))}
            </div>
            <div className="context-note">
              <Sparkles size={13} />
              <p>
                Your banking team helps you turn a question into a clear next step.
              </p>
            </div>
          </Card>
          <Card>
            <h3>You stay in control.</h3>
            <div className="assistant-assurances">
              <div>
                <Check size={14} />
                <p>No payment without your approval.</p>
              </div>
              <div>
                <Check size={14} />
                <p>See important updates in your activity history.</p>
              </div>
              <div>
                <Check size={14} />
                <p>Unusual activity gets an extra review.</p>
              </div>
            </div>
            <Link href="/activity" className="button button-ghost">
              View your activity
              <ChevronRight size={13} />
            </Link>
          </Card>
          {lastResponse && (
            <Card className="last-execution">
              <p className="eyebrow">YOUR ASSISTANT</p>
              <strong>{customerAgentName(lastResponse.agent)}</strong>
              <p>Here to help with your latest question.</p>
            </Card>
          )}
        </aside>
      </div>
      {proposal && (
        <Modal
          title={transfer ? "Verify your payment" : "Review proposed payment"}
          onClose={() => !submitting && setProposal(null)}
        >
          <div className="stack">
            <Notice tone="info">
              Your assistant prepared this payment. You are authorizing the bank
              to evaluate and process it under the account’s risk policy.
            </Notice>
            <div className="surface-inset">
              <div className="row-between">
                <span className="muted">Recipient</span>
                <strong>
                  {recipient?.name ||
                    transfer?.beneficiary_name ||
                    "Saved recipient"}
                </strong>
              </div>
              <div className="divider" />
              <div className="row-between">
                <span className="muted">Amount</span>
                <strong
                  className="metric-value"
                  style={{ fontSize: 24, margin: 0 }}
                >
                  {money(proposal.amount)}
                </strong>
              </div>
              <p className="muted" style={{ marginTop: 12 }}>
                {proposal.description}
              </p>
            </div>
            {paymentError && <Notice tone="danger">{paymentError}</Notice>}
            {transfer ? (
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  void verify();
                }}
              >
                <Notice tone="warning">
                  Confirm this payment with your account password.
                </Notice>
                <Field label="Account password (demo verification)">
                  <input
                    required
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </Field>
                <Button disabled={submitting} type="submit">
                  {submitting ? "Verifying…" : "Verify proposed payment"}
                </Button>
                <Link href="/payments" className="muted">
                  You can also complete this verification in Payments.
                </Link>
              </form>
            ) : (
              <div className="row-between">
                <Button
                  variant="secondary"
                  disabled={submitting}
                  onClick={() => setProposal(null)}
                >
                  Cancel
                </Button>
                <Button disabled={submitting} onClick={confirm}>
                  {submitting ? "Submitting…" : "Confirm proposed payment"}
                  <ArrowRight size={14} />
                </Button>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
