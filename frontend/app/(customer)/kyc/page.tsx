"use client";

import { FormEvent, useState } from "react";
import { api, dateTime, useResource } from "@/lib/api";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Notice,
  PageHeader,
  StatusBadge,
} from "@/components/ui";

type Submission = {
  id: string;
  status: string;
  risk_score: number;
  reasons: string[];
  document_name: string;
  created_at: string;
};
type Kyc = { status: string; submissions: Submission[]; disclaimer: string };
type Health = {
  demo_enabled: boolean;
  kyc_mode: "local" | "claude" | "openai";
};

export default function KycPage() {
  const { data, loading, error, refresh } = useResource<Kyc>("/kyc");
  const health = useResource<Health>("/health");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [result, setResult] = useState<Submission | null>(null);
  const today = new Date().toISOString().slice(0, 10);
  const visionEnabled =
    health.data?.kyc_mode === "claude" || health.data?.kyc_mode === "openai";
  const visionProvider =
    health.data?.kyc_mode === "openai" ? "OpenAI" : "Claude";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!health.data || health.error) {
      setSubmitError(
        "Check the evidence assessment mode before submitting files.",
      );
      return;
    }
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const document = form.get("document") as File;
    const selfie = form.get("selfie") as File;
    if (!document?.size || !selfie?.size) {
      setSubmitError(
        "Upload both an identity document and a selfie to continue.",
      );
      return;
    }
    if (document.size > 5 * 1024 * 1024 || selfie.size > 5 * 1024 * 1024) {
      setSubmitError("Each file must be 5 MB or smaller.");
      return;
    }
    setSubmitting(true);
    setSubmitError("");
    setResult(null);
    try {
      const submission = await api<Submission>("/kyc", {
        method: "POST",
        body: form,
      });
      setResult(submission);
      await refresh();
      formElement.reset();
    } catch (cause) {
      setSubmitError(
        cause instanceof Error
          ? cause.message
          : "Verification could not be submitted. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="IDENTITY & TRUST"
        title="Your identity. Protected."
        description="Submit your details and evidence to complete the identity review for your account."
      />
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : (
        <>
          <Card>
            <div className="row-between" style={{ gap: 16, flexWrap: "wrap" }}>
              <div>
                <div className="stat-label">VERIFICATION STATUS</div>
                <h2 style={{ margin: "10px 0 0", fontSize: 24 }}>
                  {data?.status === "approved" || data?.status === "verified"
                    ? "Identity review complete"
                    : data?.status === "pending" ||
                        data?.status === "review" ||
                        data?.status === "pending_review"
                      ? "Your evidence is under review"
                      : "Complete your identity verification"}
                </h2>
              </div>
              <StatusBadge status={data?.status || "unverified"} />
            </div>
            <p className="muted" style={{ lineHeight: 1.8, marginTop: 16 }}>
              {data?.disclaimer ||
                "Demo verification uses simulated identity and sanctions checks. It does not verify real identities or replace a regulated KYC provider."}
            </p>
          </Card>
          <div style={{ height: 24 }} />
          <div className="grid two kyc-layout" style={{ alignItems: "start" }}>
            <Card>
              <h2 className="section-title">Submit verification</h2>
              <p
                className="muted"
                style={{ fontSize: 13, lineHeight: 1.7, marginBottom: 22 }}
              >
                Provide the name and date of birth shown on your identity
                document. Demo users should submit synthetic details and sample
                files.
              </p>
              <form className="stack" onSubmit={submit}>
                <div className="form-grid">
                  <Field label="Full legal name">
                    <input
                      aria-label="Full legal name"
                      name="full_name"
                      className="input"
                      placeholder="Name on your identity document"
                      autoComplete="name"
                      required
                      minLength={2}
                      maxLength={100}
                      disabled={submitting}
                    />
                  </Field>
                  <Field label="Date of birth">
                    <input
                      aria-label="Date of birth"
                      name="date_of_birth"
                      className="input"
                      type="date"
                      max={today}
                      required
                      disabled={submitting}
                    />
                  </Field>
                  <Field
                    label="Identity document number"
                    hint="Use a synthetic number in this demo. 6–30 letters, digits, spaces, or hyphens."
                  >
                    <input
                      aria-label="Identity document number"
                      name="id_number"
                      className="input"
                      placeholder="e.g. DEMO12345678"
                      required
                      minLength={6}
                      maxLength={30}
                      pattern="[A-Za-z0-9 \-]{6,30}"
                      disabled={submitting}
                    />
                  </Field>
                  <Field label="Country of residence">
                    <select
                      aria-label="Country of residence"
                      name="country"
                      className="select"
                      defaultValue="IN"
                      required
                      disabled={submitting}
                    >
                      <option value="IN">India</option>
                      <option value="US">United States</option>
                      <option value="GB">United Kingdom</option>
                      <option value="AE">United Arab Emirates</option>
                      <option value="SG">Singapore</option>
                      <option value="CA">Canada</option>
                      <option value="AU">Australia</option>
                      <option value="DE">Germany</option>
                    </select>
                  </Field>
                </div>
                <div className="divider" />
                <Field
                  label="Identity document"
                  hint="Upload a valid sample image or text-based PDF. PNG, JPEG, WebP, or PDF · maximum 5 MB"
                >
                  <input
                    aria-label="Identity document"
                    name="document"
                    className="input"
                    type="file"
                    accept="image/png,image/jpeg,image/webp,application/pdf,.png,.jpg,.jpeg,.webp,.pdf"
                    required
                    disabled={submitting}
                  />
                </Field>
                <Field
                  label="Selfie"
                  hint="Upload a valid sample portrait image. PNG, JPEG, or WebP · maximum 5 MB"
                >
                  <input
                    aria-label="Selfie"
                    name="selfie"
                    className="input"
                    type="file"
                    accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"
                    required
                    disabled={submitting}
                  />
                </Field>
                <Notice tone="warning">
                  {!health.data || health.error
                    ? "Checking how this environment handles evidence. Use synthetic sample documents in this demo."
                    : visionEnabled
                      ? `Files are sent to ${visionProvider} for limited evidence quality and submitted-name consistency assessment. Legal identity and biometric matching remain unverified. Use synthetic sample documents in this demo.`
                      : "This is a simulated KYC workflow. Local checks validate file content and submitted fields; no image recognition or biometric matching is performed. Use synthetic sample documents in this demo."}
                </Notice>
                {health.error && (
                  <div className="row" style={{ flexWrap: "wrap" }}>
                    <span className="muted">
                      Evidence assessment mode could not be checked.
                    </span>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={health.refresh}
                    >
                      Check evidence mode
                    </Button>
                  </div>
                )}
                {submitError && <Notice tone="danger">{submitError}</Notice>}
                {result && (
                  <Notice
                    tone={
                      result.status === "approved" ||
                      result.status === "verified"
                        ? "success"
                        : result.status === "rejected"
                          ? "danger"
                          : "info"
                    }
                  >
                    <strong>
                      Verification {result.status.replace(/_/g, " ")}.
                    </strong>{" "}
                    {result.reasons?.join(" ") ||
                      "Your submission has been recorded."}
                  </Notice>
                )}
                <div>
                  <Button
                    type="submit"
                    disabled={
                      submitting ||
                      health.loading ||
                      !health.data ||
                      Boolean(health.error)
                    }
                  >
                    {submitting
                      ? "Reviewing your evidence…"
                      : "Submit for verification"}
                    <span aria-hidden="true"> →</span>
                  </Button>
                </div>
              </form>
            </Card>
            <div className="stack">
              <Card>
                <h2 className="section-title">How review works</h2>
                <span className="chip">
                  {health.loading
                    ? "Checking evidence mode…"
                    : health.error
                      ? "Evidence mode unavailable"
                      : visionEnabled
                        ? `${visionProvider} evidence assessment`
                        : "Local demo assessment"}
                </span>
                {[
                  {
                    number: "01",
                    title: "Identity evidence",
                    text:
                      !health.data || health.error
                        ? "The evidence assessment mode is checked before submission. Your document and selfie must contain valid, supported file content."
                        : visionEnabled
                          ? `${visionProvider} reviews document legibility, portrait and person presence, and printed-name consistency. It does not identify people or match faces.`
                          : "Your document and selfie are checked for valid file content. Submitted fields are compared with your account profile. No image recognition is performed.",
                  },
                  {
                    number: "02",
                    title: "Risk & sanctions screening",
                    text: "The demo adapter applies transparent identity rules and simulated sanctions screening.",
                  },
                  {
                    number: "03",
                    title: "Governed decision",
                    text: "Low-risk submissions can be approved. Cases that need attention are routed to an analyst.",
                  },
                ].map((step) => (
                  <div
                    key={step.number}
                    style={{
                      display: "flex",
                      gap: 14,
                      padding: "15px 0",
                      borderBottom:
                        step.number === "03"
                          ? "none"
                          : "1px solid var(--border, #e3e8eb)",
                    }}
                  >
                    <span
                      className="chip"
                      style={{
                        alignSelf: "flex-start",
                        color: "#07886a",
                        background: "#edf8f4",
                      }}
                    >
                      {step.number}
                    </span>
                    <div>
                      <strong style={{ fontSize: 14 }}>{step.title}</strong>
                      <p
                        className="muted"
                        style={{
                          fontSize: 13,
                          lineHeight: 1.75,
                          margin: "7px 0 0",
                        }}
                      >
                        {step.text}
                      </p>
                    </div>
                  </div>
                ))}
              </Card>
              <Card>
                <h2 className="section-title">Submission history</h2>
                {!data?.submissions.length ? (
                  <EmptyState
                    title="No submissions yet"
                    description="Your verification decisions and review evidence will appear here."
                  />
                ) : (
                  <div className="stack">
                    {data.submissions.map((submission) => (
                      <div
                        key={submission.id}
                        style={{
                          border: "1px solid var(--border, #e3e8eb)",
                          borderRadius: 12,
                          padding: 16,
                        }}
                      >
                        <div className="row-between">
                          <strong style={{ fontSize: 13 }}>
                            Identity review
                          </strong>
                          <StatusBadge status={submission.status} />
                        </div>
                        <p
                          className="muted"
                          style={{
                            fontSize: 11,
                            marginTop: 9,
                            marginBottom: 12,
                          }}
                        >
                          {dateTime(submission.created_at)}
                        </p>
                        <p
                          style={{
                            fontSize: 13,
                            marginBottom: 8,
                            overflowWrap: "anywhere",
                          }}
                        >
                          {submission.document_name}
                        </p>
                        <div className="row-between" style={{ fontSize: 12 }}>
                          <span className="muted">Risk score</span>
                          <strong>{submission.risk_score} / 100</strong>
                        </div>
                        {submission.reasons?.length > 0 && (
                          <ul style={{ paddingLeft: 16, marginBottom: 0 }}>
                            {submission.reasons.map((reason, index) => (
                              <li
                                key={index}
                                className="muted"
                                style={{ fontSize: 12, lineHeight: 1.7 }}
                              >
                                {reason}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          </div>
        </>
      )}
      <style jsx>{`
        .kyc-layout {
          grid-template-columns: minmax(0, 1.4fr) minmax(260px, 1fr);
        }
        @media (max-width: 1050px) {
          .kyc-layout {
            grid-template-columns: minmax(0, 1fr);
          }
        }
      `}</style>
    </>
  );
}
