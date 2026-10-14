"use client";

import Link from "next/link";
import { useResource, money, dateTime } from "@/lib/api";
import {
  Card,
  PageHeader,
  StatusBadge,
  LoadingState,
  ErrorState,
  EmptyState,
} from "@/components/ui";

type Case = {
  id: string;
  kind: string;
  status: string;
  priority: string;
  customer_name: string;
  risk_score: number;
  amount: string | null;
  summary: string;
  created_at: string;
};
type Audit = {
  id: string;
  agent: string;
  action: string;
  summary: string;
  risk_score?: number | null;
  created_at: string;
  trace_id?: string;
};
type Overview = {
  metrics: {
    open_cases: number;
    held_amount: string;
    kyc_pending: number;
    frozen_accounts: number;
  };
  cases: Case[];
  recent_audit: Audit[];
};

function label(value: string) {
  return value.replace(/_/g, " ");
}

export default function AnalystOverview() {
  const { data, loading, error, refresh } =
    useResource<Overview>("/analyst/overview");
  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!data) return null;
  const urgent = data.cases.filter(
    (item) =>
      ["open", "pending"].includes(item.status) && item.risk_score >= 70,
  ).length;
  const riskGroups = [
    {
      title: "High risk",
      count: data.cases.filter(
        (item) =>
          item.risk_score >= 70 && ["open", "pending"].includes(item.status),
      ).length,
      color: "#cb6454",
    },
    {
      title: "Elevated risk",
      count: data.cases.filter(
        (item) =>
          item.risk_score >= 40 &&
          item.risk_score < 70 &&
          ["open", "pending"].includes(item.status),
      ).length,
      color: "#c5923c",
    },
    {
      title: "Standard review",
      count: data.cases.filter(
        (item) =>
          item.risk_score < 40 && ["open", "pending"].includes(item.status),
      ).length,
      color: "#3c8b72",
    },
  ];
  const largestGroup = Math.max(1, ...riskGroups.map((group) => group.count));

  return (
    <div className="stack">
      <PageHeader
        eyebrow="RISK OPERATIONS"
        title="A clear view of every decision."
        description="Investigate the evidence, protect customers, and keep every action accountable."
        action={
          <Link href="/analyst/cases" className="button button-primary">
            Review case queue <span aria-hidden="true">↗</span>
          </Link>
        }
      />

      <div className="analyst-hero">
        <div>
          <span className="analyst-kicker">HUMAN OVERSIGHT · ALWAYS ON</span>
          <h2>
            {data.metrics.open_cases
              ? `${data.metrics.open_cases} ${data.metrics.open_cases === 1 ? "case needs" : "cases need"} a closer look.`
              : "Your review queue is clear."}
          </h2>
          <p>
            {urgent
              ? `${urgent} high-risk ${urgent === 1 ? "case requires" : "cases require"} your attention. Review the signals before making a decision.`
              : "Agent decisions and customer activity are recorded in a complete audit trail."}
          </p>
        </div>
        <div className="analyst-hero-orbit" aria-hidden="true">
          <span>◈</span>
          <span className="analyst-orbit-label">AEGIS / CONTROL</span>
        </div>
      </div>

      <div className="grid four">
        <Card>
          <span className="stat-label">Open investigations</span>
          <div className="metric-value">{data.metrics.open_cases}</div>
          <p className="muted">Awaiting an analyst decision</p>
        </Card>
        <Card>
          <span className="stat-label">Funds on hold</span>
          <div className="metric-value">{money(data.metrics.held_amount)}</div>
          <p className="muted">Transfers under review</p>
        </Card>
        <Card>
          <span className="stat-label">KYC reviews</span>
          <div className="metric-value">{data.metrics.kyc_pending}</div>
          <p className="muted">Identity verification queue</p>
        </Card>
        <Card>
          <span className="stat-label">Frozen accounts</span>
          <div className="metric-value">{data.metrics.frozen_accounts}</div>
          <p className="muted">Protected from outgoing transfers</p>
        </Card>
      </div>

      <div className="grid two">
        <Card>
          <div className="row-between">
            <h2 className="section-title">Priority queue</h2>
            <Link href="/analyst/cases" className="analyst-text-link">
              View all cases ↗
            </Link>
          </div>
          {data.cases.length ? (
            <div className="stack">
              {data.cases.slice(0, 5).map((item) => (
                <Link
                  className="analyst-case-preview"
                  href={`/analyst/cases/${item.id}`}
                  key={item.id}
                >
                  <div className="analyst-avatar">
                    {item.customer_name
                      .split(" ")
                      .map((part) => part[0])
                      .slice(0, 2)
                      .join("")}
                  </div>
                  <div className="analyst-preview-copy">
                    <strong>{item.customer_name}</strong>
                    <span className="muted">
                      {label(item.kind)} ·{" "}
                      {item.kind === "transfer"
                        ? money(item.amount)
                        : label(item.kind) + " review"}
                    </span>
                  </div>
                  <div className="analyst-preview-end">
                    <StatusBadge status={item.status} />
                    <small className="muted">Risk {item.risk_score}/100</small>
                  </div>
                  <span aria-hidden="true">↗</span>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No investigations to review"
              description="New cases will appear here when an agent requests human oversight."
            />
          )}
        </Card>

        <Card>
          <div className="row-between">
            <h2 className="section-title">Review exposure</h2>
            <span className="chip">Pending cases</span>
          </div>
          <p className="muted">
            Current case distribution by reported risk score.
          </p>
          <div
            className="analyst-risk-chart"
            role="img"
            aria-label={riskGroups
              .map((group) => `${group.title}: ${group.count} cases`)
              .join(", ")}
          >
            {riskGroups.map((group) => (
              <div key={group.title}>
                <div className="row-between">
                  <span>{group.title}</span>
                  <strong>{group.count}</strong>
                </div>
                <div className="analyst-bar-track">
                  <div
                    style={{
                      width: `${(group.count / largestGroup) * 100}%`,
                      backgroundColor: group.color,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="divider" />
          <p className="muted">
            A score is a signal, not a verdict. Final decisions require evidence
            and a recorded rationale.
          </p>
        </Card>
      </div>

      <Card>
        <div className="row-between">
          <div>
            <span className="stat-label">TRACEABLE BY DESIGN</span>
            <h2 className="section-title">Recent agent activity</h2>
          </div>
          <Link href="/analyst/audit" className="analyst-text-link">
            Open audit trail ↗
          </Link>
        </div>
        {data.recent_audit.length ? (
          <div className="analyst-timeline">
            {data.recent_audit.slice(0, 6).map((item) => (
              <div className="analyst-timeline-item" key={item.id}>
                <span className="analyst-timeline-dot" />
                <div>
                  <div className="row-between">
                    <strong>{label(item.action)}</strong>
                    <time className="muted">{dateTime(item.created_at)}</time>
                  </div>
                  <p>{item.summary}</p>
                  <span className="chip">{label(item.agent)}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No activity yet"
            description="Governed decisions appear here as customers use AegisBank."
          />
        )}
      </Card>
    </div>
  );
}
