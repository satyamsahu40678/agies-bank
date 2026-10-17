"use client";

import { useMemo, useState } from "react";
import { dateTime, useResource } from "@/lib/api";
import { customerAgentName, customerActivitySummary } from "@/lib/customer-labels";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Notice,
  PageHeader,
} from "@/components/ui";
import {
  ArrowUpRight,
  Bot,
  Filter,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";

type Tool = string | { name: string; summary?: string; result?: string };
type AuditEvent = {
  id: string;
  agent: string;
  action: string;
  summary: string;
  risk_score?: number | null;
  tools: Tool[];
  created_at: string;
  trace_id: string;
};
const label = (value: string) =>
  value
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());

export default function ActivityPage() {
  const { data, loading, error, refresh } = useResource<AuditEvent[]>("/audit");
  const [agent, setAgent] = useState("all");
  const [search, setSearch] = useState("");
  const customerEvents = useMemo(() => (data || []).filter(event => !["assistant_tool_completed", "provider_connection_checked", "assistant_provider_fallback"].includes(event.action)), [data]);
  const agents = useMemo(
    () => Array.from(new Set(customerEvents.map((event) => customerAgentName(event.agent)))).sort(),
    [customerEvents],
  );
  const filtered = useMemo(
    () =>
      customerEvents.filter(
        (event) =>
          (agent === "all" || customerAgentName(event.agent) === agent) &&
          `${event.action} ${event.summary} ${customerAgentName(event.agent)}`
            .toLowerCase()
            .includes(search.trim().toLowerCase()),
      ),
    [customerEvents, agent, search],
  );
  const recentUpdates = customerEvents.filter(event => new Date(event.created_at).getTime() >= Date.now() - 7 * 24 * 60 * 60 * 1000).length;


  return (
    <>
      <PageHeader
        eyebrow="YOUR ACTIVITY"
        title="Every action, accounted for."
        description="See account updates, helpful reviews and the reasons behind important decisions."
        action={
          <Button variant="secondary" onClick={refresh} disabled={loading}>
            <RefreshCw size={15} />
            Refresh timeline
          </Button>
        }
      />
      <div className="grid three">
        <Card>
          <div className="row-between">
            <span className="stat-label">RECORDED DECISIONS</span>
            <ShieldCheck size={19} color="#07886a" />
          </div>
          <div className="metric-value">{customerEvents.length}</div>
          <p className="muted" style={{ fontSize: 12 }}>
            In your recent activity history
          </p>
        </Card>
        <Card>
          <div className="row-between">
            <span className="stat-label">ACTIVE AGENTS</span>
            <Bot size={19} color="#07886a" />
          </div>
          <div className="metric-value">{agents.length}</div>
          <p className="muted" style={{ fontSize: 12 }}>
            Specialists coordinating your account
          </p>
        </Card>
        <Card>
          <div className="row-between">
            <span className="stat-label">LAST 7 DAYS</span>
            <ArrowUpRight size={19} color="#07886a" />
          </div>
          <div className="metric-value">{recentUpdates}</div>
          <p className="muted" style={{ fontSize: 12 }}>
            Recent updates to your account
          </p>
        </Card>
      </div>
      <div style={{ height: 24 }} />
      <Notice>
        Decision summaries describe observable actions and rule outcomes.
        Your account updates and review summaries appear here.
      </Notice>
      <div style={{ height: 24 }} />
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : (
        <>
          <Card>
            <div className="activity-filters">
              <div className="row" style={{ gap: 9 }}>
                <Filter size={17} color="#07886a" />
                <h2 className="section-title" style={{ margin: 0 }}>
                  Decision timeline
                </h2>
              </div>
              <Field label="Agent">
                <select
                  aria-label="Agent"
                  className="select"
                  value={agent}
                  onChange={(event) => setAgent(event.target.value)}
                >
                  <option value="all">All agents</option>
                  {agents.map((name) => (
                    <option key={name} value={name}>
                      {label(name)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Search activity">
                <div style={{ position: "relative" }}>
                  <Search
                    size={16}
                    style={{
                      position: "absolute",
                      left: 12,
                      top: 13,
                      color: "#82908a",
                    }}
                  />
                  <input
                    aria-label="Search activity"
                    className="input"
                    style={{ paddingLeft: 38 }}
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Action, summary, or trace ID"
                  />
                </div>
              </Field>
            </div>
            <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
              {filtered.length} {filtered.length === 1 ? "event" : "events"}
              {agent !== "all" ? ` from ${label(agent)}` : " across all agents"}
            </p>
          </Card>
          <div style={{ height: 22 }} />
          {!filtered.length ? (
            <Card>
              <EmptyState
                title={
                  data?.length
                    ? "No matching activity"
                    : "Your activity will appear here"
                }
                description={
                  data?.length
                    ? "Try a different agent or search term."
                    : "Ask your assistant, upload a document, or run a security simulation to see your agents in action."
                }
              >
                {(search || agent !== "all") && (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setSearch("");
                      setAgent("all");
                    }}
                  >
                    Clear filters
                  </Button>
                )}
              </EmptyState>
            </Card>
          ) : (
            <div className="audit-timeline">
              {filtered.map((event, index) => (
                <div key={event.id} className="audit-row">
                  <div className="audit-marker">
                    <div className="audit-dot">
                      <Bot size={16} />
                    </div>
                    {index < filtered.length - 1 && (
                      <div className="audit-line" />
                    )}
                  </div>
                  <Card>
                    <div
                      className="row-between"
                      style={{ gap: 12, flexWrap: "wrap" }}
                    >
                      <div
                        className="row"
                        style={{ gap: 10, flexWrap: "wrap" }}
                      >
                        <span
                          className="chip"
                          style={{ background: "#edf8f4", color: "#047b60" }}
                        >
                          {customerAgentName(event.agent)}
                        </span>
                        <span className="muted" style={{ fontSize: 11 }}>
                          {dateTime(event.created_at)}
                        </span>
                      </div>
                      {event.risk_score != null && (
                        <span
                          className="chip"
                          style={{
                            color:
                              event.risk_score >= 70
                                ? "#bc5140"
                                : event.risk_score >= 35
                                  ? "#9c742e"
                                  : "#047b60",
                          }}
                        >
                          Risk {event.risk_score} / 100
                        </span>
                      )}
                    </div>
                    <h3 style={{ fontSize: 16, margin: "18px 0 8px" }}>
                      {label(event.action)}
                    </h3>
                    <p style={{ fontSize: 14, lineHeight: 1.8, margin: 0 }}>
                      {customerActivitySummary(event.summary)}
                    </p>
                  </Card>
                </div>
              ))}
            </div>
          )}
        </>
      )}
      <style jsx>{`
        .activity-filters {
          display: grid;
          grid-template-columns: 1fr 190px 280px;
          align-items: center;
          gap: 24px;
        }
        .audit-row {
          display: grid;
          grid-template-columns: 40px minmax(0, 1fr);
          gap: 14px;
          margin-bottom: 16px;
        }
        .audit-marker {
          display: flex;
          align-items: center;
          flex-direction: column;
          padding-top: 23px;
        }
        .audit-dot {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 34px;
          height: 34px;
          background: #e8f4ee;
          color: #07886a;
          border: 1px solid #d4e7dc;
          border-radius: 50%;
        }
        .audit-line {
          width: 1px;
          background: #dbe4df;
          flex: 1;
          margin-top: 8px;
          margin-bottom: -25px;
        }
        @media (max-width: 1050px) {
          .activity-filters {
            grid-template-columns: 1fr 1fr;
          }
          .activity-filters > div:first-child {
            grid-column: 1/-1;
          }
        }
        @media (max-width: 640px) {
          .activity-filters {
            grid-template-columns: 1fr;
          }
          .audit-row {
            grid-template-columns: 24px minmax(0, 1fr);
            gap: 10px;
          }
          .audit-dot {
            width: 24px;
            height: 24px;
          }
        }
      `}</style>
    </>
  );
}
