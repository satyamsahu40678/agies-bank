"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, useResource, money, dateTime } from "@/lib/api";
import {
  PageHeader,
  Card,
  StatusBadge,
  EmptyState,
  LoadingState,
  ErrorState,
  Button,
  Field,
  Modal,
  Notice,
} from "@/components/ui";

type Signal = { name: string; score?: number; detail: string } | string;
type Investigation = {
  id: string;
  kind: string;
  status: string;
  priority: string;
  customer_name: string;
  customer_id: string;
  risk_score: number;
  amount: string | null;
  summary: string;
  signals: Signal[];
  created_at: string;
  transfer_id?: string | null;
  kyc_id?: string | null;
  resolution_reason?: string | null;
  resolved_at?: string | null;
};
type Audit = {
  id: string;
  agent: string;
  action: string;
  summary: string;
  risk_score?: number | null;
  tools: (string | { name?: string; summary?: string })[];
  created_at: string;
  trace_id?: string;
};
type LoginEvent = {
  id: string;
  kind: string;
  city: string;
  country: string;
  device: string;
  is_new_device: boolean;
  vpn: boolean;
  risk_score: number;
  ip_masked: string;
  signals: Signal[];
  created_at: string;
};
type Detail = {
  case: Investigation;
  customer: { id: string; name: string; email: string };
  account: {
    id: string;
    number: string;
    balance: string;
    status: string;
    kyc_status: string;
  };
  events: LoginEvent[];
  audit: Audit[];
};
function label(value: string) {
  return value.replace(/_/g, " ");
}

export default function CaseDetail() {
  const params = useParams<{ id: string }>();
  const { data, loading, error, refresh } = useResource<Detail>(
    `/analyst/cases/${encodeURIComponent(params.id)}`,
  );
  const [decision, setDecision] = useState<"approve" | "reject" | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [success, setSuccess] = useState("");

  function openDecision(next: "approve" | "reject") {
    setDecision(next);
    setReason("");
    setSubmitError("");
  }
  async function resolve(event: FormEvent) {
    event.preventDefault();
    if (!decision || !data || saving) return;
    if (reason.trim().length < 10) {
      setSubmitError(
        "Enter at least 10 characters so the decision has a clear rationale.",
      );
      return;
    }
    setSaving(true);
    setSubmitError("");
    try {
      await api<Investigation>(
        `/analyst/cases/${encodeURIComponent(data.case.id)}/resolve`,
        { method: "POST", body: { decision, reason: reason.trim() } },
      );
      setSuccess(
        `Case ${decision === "approve" ? "approved" : "rejected"}. Your rationale has been recorded in the audit trail.`,
      );
      setDecision(null);
      await refresh();
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "The decision could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!data) return null;
  const item = data.case;
  const isTransfer =
    Boolean(item.transfer_id) || item.kind.toLowerCase().includes("transfer");
  const isIdentity =
    Boolean(item.kyc_id) || item.kind.toLowerCase().includes("kyc");
  const pending = ["open", "pending"].includes(item.status);

  return (
    <div className="stack">
      <Link className="analyst-text-link" href="/analyst/cases">
        ← Back to case queue
      </Link>
      <PageHeader
        eyebrow="CASE INVESTIGATION"
        title={`${isTransfer ? "Transfer" : isIdentity ? "Identity" : "Login activity"} under review.`}
        description={`Opened ${dateTime(item.created_at)} · Case ${item.id}`}
        action={<StatusBadge status={item.status} />}
      />
      {success && <Notice tone="success">{success}</Notice>}
      <Card>
        <div className="row-between">
          <div>
            <div className="analyst-detail-top">
              <div className="analyst-avatar">
                {data.customer.name
                  .split(" ")
                  .map((part) => part[0])
                  .slice(0, 2)
                  .join("")}
              </div>
              <h2 className="section-title">{data.customer.name}</h2>
              <span className="chip" style={{ textTransform: "capitalize" }}>
                {item.priority} priority
              </span>
            </div>
            <p className="muted" style={{ maxWidth: 700, lineHeight: 1.65 }}>
              {item.summary}
            </p>
          </div>
          <div
            className="analyst-case-score"
            aria-label={`Risk score ${item.risk_score} out of 100`}
          >
            <strong>{item.risk_score}</strong>
            <span>
              / 100
              <br />
              risk score
            </span>
          </div>
        </div>
        {isTransfer && <div className="divider" />}
        {isTransfer && (
          <div className="row-between">
            <span className="muted">Transfer amount</span>
            <strong style={{ fontSize: "1.4rem" }}>{money(item.amount)}</strong>
          </div>
        )}
      </Card>

      <div className="grid two">
        <Card>
          <h2 className="section-title">Risk evidence</h2>
          <p className="muted">Signals recorded when the case was created.</p>
          {item.signals?.length ? (
            <div className="analyst-signal-list">
              {item.signals.map((signal, index) => (
                <div className="analyst-signal" key={index}>
                  {typeof signal === "string" ? (
                    <p style={{ margin: 0 }}>{signal}</p>
                  ) : (
                    <>
                      <div className="row-between">
                        <strong>{label(signal.name)}</strong>
                        {signal.score != null && (
                          <span className="chip">+{signal.score} risk</span>
                        )}
                      </div>
                      <p>{signal.detail}</p>
                    </>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="analyst-evidence-empty">
              No individual risk signals were attached to this case. Review the
              case summary and activity history before deciding.
            </div>
          )}
        </Card>
        <div className="stack">
          <Card>
            <h2 className="section-title">Customer & account</h2>
            <div className="analyst-identity">
              <div>
                <span>Customer</span>
                <strong>{data.customer.name}</strong>
              </div>
              <div>
                <span>Email</span>
                <strong>{data.customer.email}</strong>
              </div>
              <div>
                <span>Account</span>
                <strong>{data.account.number}</strong>
              </div>
              <div>
                <span>Available balance</span>
                <strong>{money(data.account.balance)}</strong>
              </div>
              <div>
                <span>Account status</span>
                <StatusBadge status={data.account.status} />
              </div>
              <div>
                <span>Identity status</span>
                <StatusBadge status={data.account.kyc_status} />
              </div>
            </div>
            <div className="divider" />
            <Link className="analyst-text-link" href="/analyst/customers">
              Manage customer accounts ↗
            </Link>
          </Card>
          <Card>
            <h2 className="section-title">Your decision</h2>
            {pending ? (
              <>
                <p className="muted">
                  {isTransfer
                    ? "Approval settles this held transfer after the server rechecks account status and available funds. Rejection prevents settlement."
                    : isIdentity
                      ? "Approve identity verification after reviewing the evidence, or reject the submission with a clear reason."
                      : "Assess the login evidence and record your review decision. Use Customer accounts to change account status when a restriction is needed."}
                </p>
                <Notice tone="info">
                  Every decision requires a rationale and becomes part of the
                  permanent audit trail.
                </Notice>
                <div
                  className="analyst-decision-actions"
                  style={{ marginTop: "1.2rem" }}
                >
                  <Button onClick={() => openDecision("approve")}>
                    Approve case
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => openDecision("reject")}
                  >
                    Reject case
                  </Button>
                </div>
              </>
            ) : (
              <>
                <Notice
                  tone={
                    item.status === "approved"
                      ? "success"
                      : item.status === "rejected"
                        ? "danger"
                        : "info"
                  }
                >
                  This case is {label(item.status)} and is no longer awaiting a
                  decision.
                </Notice>
                {item.resolution_reason && (
                  <p className="muted">
                    Recorded rationale: {item.resolution_reason}
                  </p>
                )}
                {item.resolved_at && (
                  <p className="muted">Resolved {dateTime(item.resolved_at)}</p>
                )}
              </>
            )}
          </Card>
        </div>
      </div>

      <Card>
        <div className="row-between">
          <h2 className="section-title">Recent login evidence</h2>
          <span className="chip">{data.events.length} events</span>
        </div>
        {data.events.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Time</th>
                  <th scope="col">Location</th>
                  <th scope="col">Device</th>
                  <th scope="col">Signals</th>
                  <th scope="col">Risk</th>
                </tr>
              </thead>
              <tbody>
                {data.events.map((event) => (
                  <tr key={event.id}>
                    <td>
                      <span className="analyst-table-subtitle muted">
                        {dateTime(event.created_at)}
                      </span>
                    </td>
                    <td>
                      <span className="analyst-table-title">
                        {[event.city, event.country]
                          .filter(Boolean)
                          .join(", ") || "Unknown location"}
                      </span>
                      <span className="analyst-mono muted">
                        {event.ip_masked || "IP unavailable"}
                      </span>
                    </td>
                    <td>{event.device || "Unknown device"}</td>
                    <td>
                      <div className="row" style={{ flexWrap: "wrap" }}>
                        {event.is_new_device && (
                          <span className="chip">New device</span>
                        )}
                        {event.vpn && <span className="chip">VPN</span>}
                        {!event.is_new_device && !event.vpn && (
                          <span className="muted">No device / VPN flags</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span
                        className={`analyst-risk-number ${event.risk_score >= 70 ? "high" : event.risk_score >= 40 ? "medium" : ""}`}
                      >
                        {event.risk_score}/100
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No login evidence available"
            description="This customer's events will appear when recorded."
          />
        )}
      </Card>

      <Card>
        <h2 className="section-title">Decision & agent timeline</h2>
        <p className="muted">
          Recorded summaries and executed tools associated with this customer.
        </p>
        {data.audit.length ? (
          data.audit.map((entry) => (
            <article className="analyst-audit-entry" key={entry.id}>
              <div className="row-between">
                <strong style={{ textTransform: "capitalize" }}>
                  {label(entry.action)}
                </strong>
                <time className="muted" style={{ fontSize: ".75rem" }}>
                  {dateTime(entry.created_at)}
                </time>
              </div>
              <p>{entry.summary}</p>
              <div className="analyst-audit-meta">
                <span className="chip">{label(entry.agent)}</span>
                {entry.risk_score != null && (
                  <span>Risk {entry.risk_score}/100</span>
                )}
                {entry.tools?.map((tool, index) => (
                  <span className="chip" key={index}>
                    {typeof tool === "string"
                      ? label(tool)
                      : label(tool.name || "Recorded tool")}
                  </span>
                ))}
              </div>
              {entry.trace_id && (
                <details style={{ marginTop: ".65rem" }}>
                  <summary
                    className="muted"
                    style={{ fontSize: ".75rem", cursor: "pointer" }}
                  >
                    Trace reference
                  </summary>
                  <p className="analyst-mono">{entry.trace_id}</p>
                </details>
              )}
            </article>
          ))
        ) : (
          <EmptyState
            title="No audit entries yet"
            description="Actions appear here as they are recorded."
          />
        )}
      </Card>

      {decision && (
        <Modal
          title={
            decision === "approve" ? "Approve this case?" : "Reject this case?"
          }
          onClose={() => {
            if (!saving) setDecision(null);
          }}
        >
          <form onSubmit={resolve} className="stack">
            <p className="muted">
              {isTransfer
                ? decision === "approve"
                  ? `Approve the ${money(item.amount)} transfer for ${data.customer.name}. The server will validate and settle the transfer atomically.`
                  : `Reject the ${money(item.amount)} transfer for ${data.customer.name}. Funds will remain in the customer's account.`
                : isIdentity
                  ? `${decision === "approve" ? "Approve" : "Reject"} identity verification for ${data.customer.name}.`
                  : `Record ${decision === "approve" ? "approval" : "rejection"} of this login review for ${data.customer.name}. This review decision does not change account status.`}
            </p>
            <Field
              label="Decision rationale"
              hint="Record the evidence behind your decision. At least 10 characters."
            >
              <textarea
                className="textarea"
                name="reason"
                placeholder="Explain the evidence reviewed and why this decision is appropriate…"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                minLength={10}
                maxLength={500}
                rows={4}
                required
                disabled={saving}
              />
            </Field>
            {submitError && <Notice tone="danger">{submitError}</Notice>}
            <div className="analyst-decision-actions">
              <Button
                type="submit"
                variant={decision === "approve" ? "primary" : "danger"}
                disabled={saving || reason.trim().length < 10}
              >
                {saving
                  ? "Saving decision…"
                  : decision === "approve"
                    ? "Confirm approval"
                    : "Confirm rejection"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={saving}
                onClick={() => setDecision(null)}
              >
                Cancel
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
