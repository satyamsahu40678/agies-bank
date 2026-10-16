"use client";

import { FormEvent, useRef, useState } from "react";
import {
  ArrowUpRight,
  BookOpen,
  BrainCircuit,
  Check,
  ChevronDown,
  FileText,
  KeyRound,
  Plug,
  RefreshCw,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { api, dateTime, useResource } from "@/lib/api";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Modal,
  Notice,
  PageHeader,
  Pending,
} from "@/components/ui";

type Provider = {
  id: string;
  name: string;
  status: "configured" | "local" | "unconfigured" | "not_integrated";
  integrated: boolean;
  mode: string;
  credential_configured: boolean;
  model: string | null;
  model_selection?: "configured" | "automatic";
  endpoints: string[];
  capabilities: string[];
  limitations: string;
  requirements: string[];
};
type Readiness = {
  ai_mode: "local" | "claude" | "openai" | "gemini" | "openrouter";
  kyc_mode: "local" | "claude" | "openai" | "gemini";
  providers: Provider[];
  firestore: {
    agent_notifications_enabled: boolean;
    project_configured: boolean;
    database: string;
  };
  disclaimer: string;
};
type ConnectionCheck = {
  status: "ok" | "unconfigured" | "error";
  configured: boolean;
  model: string | null;
  checked_at: string;
  message: string;
  error_code?: string;
  scope: "model_access";
};
type PolicyDocument = {
  id: string;
  title: string;
  kind: string;
  filename: string;
  chunk_count: number;
  created_at: string;
};
const providerLabels: Record<Provider["status"], string> = {
  configured: "Key configured",
  local: "Local mode",
  unconfigured: "Key required",
  not_integrated: "Demo adapter",
};

export default function IntegrationsPage() {
  const readiness = useResource<Readiness>("/analyst/integrations");
  const policies = useResource<PolicyDocument[]>("/analyst/documents");
  const [checking, setChecking] = useState(false);
  const [connection, setConnection] = useState<ConnectionCheck | null>(null);
  const [checkError, setCheckError] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishError, setPublishError] = useState("");
  const [publishNotice, setPublishNotice] = useState("");
  const [confirmedPublic, setConfirmedPublic] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function checkConnection(
    provider: "claude" | "openai" | "gemini" | "openrouter",
  ) {
    if (checking) return;
    setChecking(true);
    setCheckError("");
    setConnection(null);
    try {
      setConnection(
        await api<ConnectionCheck>(`/analyst/integrations/${provider}/check`, {
          method: "POST",
        }),
      );
      await readiness.refresh();
    } catch (failure) {
      setCheckError(
        failure instanceof Error
          ? failure.message
          : "Unable to check model access.",
      );
    } finally {
      setChecking(false);
    }
  }

  async function publishPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (publishing) return;
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setPublishError("Select a policy document.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setPublishError("Policy documents must be 5 MB or smaller.");
      return;
    }
    if (!/\.(pdf|txt|md|csv)$/i.test(file.name)) {
      setPublishError("Select a PDF, plain text, Markdown, or CSV file.");
      return;
    }
    if (!confirmedPublic) {
      setPublishError(
        "Confirm that this document may be shared with every customer.",
      );
      return;
    }
    const body = new FormData();
    body.append("file", file);
    body.append("confirmed_public", "true");
    const title = titleRef.current?.value.trim();
    body.append("title", title || file.name);
    setPublishing(true);
    setPublishError("");
    try {
      const document = await api<PolicyDocument>("/analyst/documents", {
        method: "POST",
        body,
      });
      setPublishOpen(false);
      setConfirmedPublic(false);
      await policies.refresh();
      setPublishNotice(
        `“${document.title}” is published in the shared bank policy library and available for cited customer answers.`,
      );
    } catch (failure) {
      setPublishError(
        failure instanceof Error
          ? failure.message
          : "Unable to publish this policy.",
      );
    } finally {
      setPublishing(false);
    }
  }

  const aiProviders =
    readiness.data?.providers.filter((provider) => provider.integrated) || [];
  const externalProviders =
    readiness.data?.providers.filter((provider) => !provider.integrated) || [];

  return (
    <div className="stack integrations-page">
      <PageHeader
        eyebrow="PROVIDER READINESS & KNOWLEDGE"
        title="Know what’s connected."
        description="A clear inventory of live AI configuration, local adapters, and the bank policy knowledge your agents can use."
        action={
          <Button
            variant="secondary"
            disabled={readiness.loading}
            onClick={readiness.refresh}
          >
            <RefreshCw size={15} />
            Refresh readiness
          </Button>
        }
      />
      {readiness.loading && !readiness.data ? (
        <LoadingState />
      ) : readiness.error && !readiness.data ? (
        <ErrorState message={readiness.error} onRetry={readiness.refresh} />
      ) : (
        readiness.data && (
          <>
            {readiness.error && (
              <Notice tone="warning">
                {readiness.error} Showing the last loaded provider
                configuration.
              </Notice>
            )}
            <div className="integration-hero">
              <span className="integration-hero-icon">
                <Plug size={25} />
              </span>
              <div>
                <p className="eyebrow">EXPLICIT CONNECTION BOUNDARIES</p>
                <h2>
                  {readiness.data.ai_mode !== "local"
                    ? `${readiness.data.ai_mode === "openai" ? "OpenAI" : readiness.data.ai_mode === "gemini" ? "Gemini" : readiness.data.ai_mode === "openrouter" ? "OpenRouter" : "Claude"} is selected. Banking stays governed.`
                    : "A complete local workflow. A clear path to live AI."}
                </h2>
                <p>{readiness.data.disclaimer}</p>
              </div>
            </div>
            <section className="stack" aria-labelledby="claude-title">
              <div className="row-between health-section-heading">
                <div>
                  <p className="eyebrow">AI PROVIDER</p>
                  <h2 id="claude-title">AI provider integrations</h2>
                </div>
                <Button
                  disabled={checking}
                  variant="secondary"
                  onClick={() => checkConnection("claude")}
                >
                  {checking ? (
                    <Pending label="Checking model access…" />
                  ) : (
                    <>
                      <KeyRound size={14} />
                      Check Claude connection
                    </>
                  )}
                </Button>
                <Button
                  disabled={checking}
                  variant="secondary"
                  onClick={() => checkConnection("openai")}
                >
                  Check OpenAI connection
                </Button>
                <Button
                  disabled={checking}
                  variant="secondary"
                  onClick={() => checkConnection("gemini")}
                >
                  Check Gemini connection
                </Button>
                <Button
                  disabled={checking}
                  variant="secondary"
                  onClick={() => checkConnection("openrouter")}
                >
                  Check OpenRouter connection
                </Button>
              </div>
              <div className="grid two">
                {aiProviders.map((provider) => (
                  <Card key={provider.id} className="integration-ai-card">
                    <div className="row-between">
                      <span className="integration-provider-icon">
                        <BrainCircuit size={20} />
                      </span>
                      <span
                        className={`integration-status integration-status-${provider.status}`}
                      >
                        <i />
                        {providerLabels[provider.status]}
                      </span>
                    </div>
                    <h3>{provider.name}</h3>
                    <dl className="integration-provider-facts">
                      <div>
                        <dt>Active mode</dt>
                        <dd>
                          {provider.mode === "claude"
                            ? "Claude"
                            : provider.mode === "openai"
                              ? "OpenAI"
                              : provider.mode === "gemini"
                                ? "Gemini"
                                : provider.mode === "openrouter"
                                  ? "OpenRouter"
                                  : "Local"}
                        </dd>
                      </div>
                      <div>
                        <dt>Credential</dt>
                        <dd>
                          {provider.credential_configured
                            ? "Present · value protected"
                            : "Not configured"}
                        </dd>
                      </div>
                      <div>
                        <dt>Model</dt>
                        <dd className="integration-model">
                          {provider.model ||
                            (provider.model_selection === "automatic"
                              ? "Auto-select accessible model"
                              : "Pending configuration")}
                        </dd>
                      </div>
                    </dl>
                    <ul className="integration-capabilities">
                      {provider.capabilities.map((capability) => (
                        <li key={capability}>
                          <Check size={13} />
                          <span>{capability}</span>
                        </li>
                      ))}
                    </ul>
                    <p className="integration-limitation">
                      {provider.limitations}
                    </p>
                    <details className="integration-requirements">
                      <summary>
                        Configuration requirements
                        <ChevronDown size={14} />
                      </summary>
                      <ul>
                        {provider.requirements.map((requirement) => (
                          <li key={requirement}>{requirement}</li>
                        ))}
                      </ul>
                      {provider.endpoints.length > 0 && (
                        <div className="integration-destinations">
                          <span>Provider destinations</span>
                          {provider.endpoints.map((endpoint) => (
                            <code key={endpoint}>{endpoint}</code>
                          ))}
                        </div>
                      )}
                    </details>
                  </Card>
                ))}
              </div>
              {checkError && <Notice tone="danger">{checkError}</Notice>}
              {connection && (
                <Notice
                  tone={
                    connection.status === "ok"
                      ? "success"
                      : connection.status === "error"
                        ? "danger"
                        : "warning"
                  }
                >
                  <strong>
                    {connection.status === "ok"
                      ? "Model access verified."
                      : connection.status === "unconfigured"
                        ? "An AI provider key is needed."
                        : "Connection needs attention."}
                  </strong>{" "}
                  {connection.message}
                  {connection.model && (
                    <span className="integration-check-meta">
                      Model: <code>{connection.model}</code>
                    </span>
                  )}
                  <span className="integration-check-meta">
                    Checked {dateTime(connection.checked_at)} · Scope: model
                    access
                  </span>
                </Notice>
              )}
              <Card className="integration-setup">
                <div>
                  <span className="integration-provider-icon">
                    <ShieldCheck size={20} />
                  </span>
                  <h3>Add a key securely, then restart the backend.</h3>
                  <p>
                    Set <code>ANTHROPIC_API_KEY</code>,{" "}
                    <code>AEGIS_OPENAI_API_KEY</code>, or{" "}
                    <code>GEMINI_API_KEY</code>, or{" "}
                    <code>OPENROUTER_API_KEY</code> in the project .env or secure
                    cloud settings. Use{" "}
                    <code>AEGIS_AI_PROVIDER=auto</code> and{" "}
                    <code>AEGIS_KYC_VISION=auto</code> to activate the
                    configured provider across AI capabilities. You can
                    optionally set <code>ANTHROPIC_MODEL</code> or{" "}
                    <code>AEGIS_OPENAI_MODEL</code> or <code>GEMINI_MODEL</code>{" "}
                    to a model available to your account, or set{" "}
                    <code>OPENROUTER_MODEL</code> (defaults to{" "}
                    <code>openrouter/free</code>).
                  </p>
                  <p>
                    The connection check reads model metadata and sends no
                    customer data or paid inference. Exercise the assistant and
                    evidence review separately to validate live responses. A
                    Claude or OpenAI key enables AI reasoning and limited image
                    assistance; real settlement, legal identity verification,
                    and biometric liveness require their own integrations.
                  </p>
                </div>
                <div className="integration-secure-note">
                  <KeyRound size={23} />
                  <strong>Credentials stay on the server</strong>
                  <span>
                    This page shows presence and readiness only. Add secrets in
                    your environment, never in customer documents or chat.
                  </span>
                </div>
              </Card>
            </section>
            <section className="stack" aria-labelledby="firestore-title">
              <div className="health-section-heading">
                <p className="eyebrow">GOOGLE CLOUD DATA SERVICES</p>
                <h2 id="firestore-title">Firebase and Firestore</h2>
              </div>
              <Card className="integration-setup">
                <div>
                  <span className="integration-provider-icon">
                    <BrainCircuit size={20} />
                  </span>
                  <h3>
                    {readiness.data.firestore.agent_notifications_enabled
                      ? "Agent alerts are projected to Firestore."
                      : "Firestore alert projection is not enabled."}
                  </h3>
                  <p>
                    Firebase Hosting can serve this Cloud Run application. When
                    enabled, Firestore carries derived financial-health alert
                    projections; PostgreSQL remains authoritative for
                    accounts, balances, transfers, audit records, and agent
                    runs. Cloud Run uses its service identity through the
                    metadata server, so no service-account key file belongs in
                    the application.
                  </p>
                  <p>
                    Project: {readiness.data.firestore.project_configured
                      ? "configured"
                      : "not configured"} · Database: {readiness.data.firestore.database}
                  </p>
                </div>
                <div className="integration-secure-note">
                  <ShieldCheck size={23} />
                  <strong>Server-side only</strong>
                  <span>
                    Firestore is a notification projection, not a ledger or
                    authorization source. Failed delivery falls back to SQL.
                  </span>
                </div>
              </Card>
            </section>
            <section className="stack" aria-labelledby="external-title">
              <div className="health-section-heading">
                <p className="eyebrow">EXTERNAL SERVICE BOUNDARIES</p>
                <h2 id="external-title">Banking and identity adapters</h2>
              </div>
              <p className="muted health-explanation">
                The runnable app uses synthetic services for these workflows.
                Each live provider needs its supported protocol, credentials,
                test account, and operational controls before it can be enabled.
              </p>
              <Card className="integration-matrix">
                <div className="table-wrap">
                  <table className="data-table">
                    <caption className="sr-only">
                      External provider integration readiness
                    </caption>
                    <thead>
                      <tr>
                        <th>Service</th>
                        <th>Current implementation</th>
                        <th>Readiness</th>
                        <th>Needed for live use</th>
                      </tr>
                    </thead>
                    <tbody>
                      {externalProviders.map((provider) => (
                        <tr key={provider.id}>
                          <td>
                            <strong>{provider.name}</strong>
                            <small>{provider.limitations}</small>
                          </td>
                          <td>
                            {provider.capabilities.map((capability) => (
                              <p key={capability}>{capability}</p>
                            ))}
                          </td>
                          <td>
                            <span className="integration-status integration-status-not_integrated">
                              <i />
                              Provider required
                            </span>
                          </td>
                          <td>
                            <details className="integration-table-requirements">
                              <summary>
                                View requirements
                                <ChevronDown size={12} />
                              </summary>
                              <ul>
                                {provider.requirements.map((requirement) => (
                                  <li key={requirement}>{requirement}</li>
                                ))}
                              </ul>
                            </details>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </section>
          </>
        )
      )}

      <section
        className="stack health-anchor"
        id="policies"
        aria-labelledby="policies-title"
      >
        <div className="row-between health-section-heading">
          <div>
            <p className="eyebrow">TRUSTED KNOWLEDGE FOR EVERY CUSTOMER</p>
            <h2 id="policies-title">Bank policy library</h2>
          </div>
          <Button
            onClick={() => {
              setPublishError("");
              setConfirmedPublic(false);
              setPublishOpen(true);
            }}
          >
            <Upload size={14} />
            Publish a policy
          </Button>
        </div>
        <div className="health-planning-note">
          <BookOpen size={17} />
          <p>
            Only publish approved, public bank material. These documents are
            shared with every customer for cited Q&A. Publishing knowledge does
            not change credit, payment, or risk rules.
          </p>
        </div>
        {publishNotice && <Notice tone="success">{publishNotice}</Notice>}
        {policies.loading && !policies.data ? (
          <LoadingState />
        ) : policies.error && !policies.data ? (
          <ErrorState message={policies.error} onRetry={policies.refresh} />
        ) : (
          <Card>
            {policies.error && <Notice tone="warning">{policies.error}</Notice>}
            {policies.data?.length ? (
              <div className="integration-policy-list">
                {policies.data.map((document) => (
                  <div key={document.id}>
                    <span className="integration-policy-icon">
                      <FileText size={19} />
                    </span>
                    <div>
                      <h3>{document.title}</h3>
                      <p>
                        {document.filename} · {document.chunk_count} indexed
                        passages
                      </p>
                      <small>Published {dateTime(document.created_at)}</small>
                    </div>
                    <span className="integration-policy-sharing">
                      <ShieldCheck size={13} />
                      Shared policy
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="A clear source for bank policy"
                description="Publish a trusted policy to make its text available for document-grounded customer answers."
              >
                <Button
                  variant="secondary"
                  onClick={() => {
                    setPublishError("");
                    setConfirmedPublic(false);
                    setPublishOpen(true);
                  }}
                >
                  <Upload size={14} />
                  Publish your first policy
                </Button>
              </EmptyState>
            )}
          </Card>
        )}
      </section>
      {publishOpen && (
        <Modal
          title="Publish a shared bank policy"
          onClose={() => {
            if (!publishing) setPublishOpen(false);
          }}
        >
          <form
            className="stack"
            onSubmit={publishPolicy}
            aria-label="Publish bank policy form"
          >
            <Notice tone="warning">
              This document will be available to every customer. Do not upload
              private customer data, secrets, internal-only policies, or
              material you are not authorized to share.
            </Notice>
            <Field
              label="Policy title"
              hint="Optional. The filename is used if left empty."
            >
              <input
                aria-label="Policy title"
                ref={titleRef}
                maxLength={150}
                disabled={publishing}
                placeholder="e.g. Personal loan prepayment policy"
              />
            </Field>
            <Field
              label="Policy file"
              hint="PDF, plain text, Markdown, or CSV · maximum 5 MB"
            >
              <input
                aria-label="Policy file"
                ref={fileRef}
                type="file"
                accept=".pdf,.txt,.md,.csv,application/pdf,text/plain,text/markdown,text/csv"
                required
                disabled={publishing}
              />
            </Field>
            <label className="integration-public-confirm">
              <input
                type="checkbox"
                checked={confirmedPublic}
                onChange={(event) => setConfirmedPublic(event.target.checked)}
                required
                disabled={publishing}
              />
              <span>
                I confirm this policy is approved for sharing with every
                AegisBank customer.
              </span>
            </label>
            <p className="muted">
              Text is indexed for cited answers. This action does not configure
              lender eligibility or payment rules. Scanned PDFs need searchable
              text before uploading.
            </p>
            {publishError && <Notice tone="danger">{publishError}</Notice>}
            <div className="row">
              <Button
                variant="secondary"
                type="button"
                disabled={publishing}
                onClick={() => setPublishOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={publishing || !confirmedPublic}>
                {publishing ? (
                  <Pending label="Publishing and indexing…" />
                ) : (
                  <>
                    <Upload size={14} />
                    Publish to all customers
                  </>
                )}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
