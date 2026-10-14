"use client";

import { useMemo, useState } from "react";
import { useResource, dateTime } from "@/lib/api";
import {
  PageHeader,
  Card,
  EmptyState,
  LoadingState,
  ErrorState,
  Button,
  Notice,
} from "@/components/ui";

type Tool = string | { name?: string; summary?: string };
type Audit = {
  id: string;
  agent: string;
  action: string;
  summary: string;
  risk_score?: number | null;
  tools: Tool[];
  created_at: string;
  trace_id?: string;
};
function label(value: string) {
  return value.replace(/_/g, " ");
}
function csvCell(value: string | number | undefined | null) {
  const text = String(value ?? "");
  const safe = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
  return `"${safe.replaceAll('"', '""')}"`;
}

export default function GlobalAudit() {
  const { data, loading, error, refresh } =
    useResource<Audit[]>("/analyst/audit");
  const [search, setSearch] = useState("");
  const [agent, setAgent] = useState("all");
  const [risk, setRisk] = useState("all");
  const [exportNotice, setExportNotice] = useState("");
  const entries = useMemo(
    () =>
      (data || []).filter(
        (entry) =>
          (agent === "all" || entry.agent === agent) &&
          (risk !== "high" ||
            (entry.risk_score != null && entry.risk_score >= 70)) &&
          `${entry.action} ${entry.summary} ${entry.agent} ${entry.trace_id || ""}`
            .toLowerCase()
            .includes(search.toLowerCase()),
      ),
    [data, search, agent, risk],
  );
  const agents = [...new Set((data || []).map((entry) => entry.agent))];

  function exportCsv() {
    if (!entries.length) return;
    const rows = [
      [
        "Timestamp",
        "Agent",
        "Action",
        "Summary",
        "Risk score",
        "Tools",
        "Trace reference",
      ],
      ...entries.map((entry) => [
        entry.created_at,
        entry.agent,
        entry.action,
        entry.summary,
        entry.risk_score,
        entry.tools
          ?.map((tool) =>
            typeof tool === "string" ? tool : tool.name || "Recorded tool",
          )
          .join("; ") || "",
        entry.trace_id || "",
      ]),
    ];
    const content = rows
      .map((row) => row.map((value) => csvCell(value)).join(","))
      .join("\r\n");
    const blob = new Blob(["\uFEFF", content], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "aegisbank-audit-export.csv";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setExportNotice(
      `Exported ${entries.length} filtered audit ${entries.length === 1 ? "entry" : "entries"}.`,
    );
  }

  return (
    <div className="stack">
      <PageHeader
        eyebrow="GOVERNANCE & TRACEABILITY"
        title="Every action leaves a record."
        description="Explore recorded agent tools, customer actions, and analyst decisions across the available history."
        action={
          <div className="row">
            <Button variant="secondary" onClick={refresh}>
              Refresh
            </Button>
            <Button onClick={exportCsv} disabled={!entries.length}>
              Export CSV
            </Button>
          </div>
        }
      />
      {exportNotice && <Notice tone="success">{exportNotice}</Notice>}
      <div className="grid three">
        <Card>
          <span className="stat-label">Recorded actions</span>
          <div className="metric-value">{data?.length || 0}</div>
          <p className="muted">Available audit history</p>
        </Card>
        <Card>
          <span className="stat-label">Active agent types</span>
          <div className="metric-value">{agents.length}</div>
          <p className="muted">Distinct recorded actors</p>
        </Card>
        <Card>
          <span className="stat-label">High-risk actions</span>
          <div className="metric-value">
            {
              (data || []).filter((entry) => (entry.risk_score || 0) >= 70)
                .length
            }
          </div>
          <p className="muted">Reported score of 70 or higher</p>
        </Card>
      </div>
      <Card>
        <div className="analyst-toolbar">
          <div>
            <label htmlFor="audit-search">Search audit records</label>
            <input
              className="input"
              id="audit-search"
              placeholder="Action, agent, summary, or trace reference…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="audit-agent">Agent / actor</label>
            <select
              className="select"
              id="audit-agent"
              value={agent}
              onChange={(event) => setAgent(event.target.value)}
            >
              <option value="all">All agents & actors</option>
              {agents.map((value) => (
                <option key={value} value={value}>
                  {label(value)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="audit-risk">Risk level</label>
            <select
              className="select"
              id="audit-risk"
              value={risk}
              onChange={(event) => setRisk(event.target.value)}
            >
              <option value="all">All risk levels</option>
              <option value="high">High risk · 70+</option>
            </select>
          </div>
        </div>
      </Card>
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : (
        <Card>
          <div className="row-between">
            <h2 className="section-title">Audit timeline</h2>
            <span className="muted">
              {entries.length} {entries.length === 1 ? "record" : "records"}
            </span>
          </div>
          {entries.length ? (
            entries.map((entry) => (
              <article className="analyst-audit-entry" key={entry.id}>
                <div className="row-between">
                  <div className="row" style={{ flexWrap: "wrap" }}>
                    <span
                      className="chip"
                      style={{ textTransform: "capitalize" }}
                    >
                      {label(entry.agent)}
                    </span>
                    <strong
                      style={{
                        textTransform: "capitalize",
                        fontSize: ".92rem",
                      }}
                    >
                      {label(entry.action)}
                    </strong>
                  </div>
                  <time className="muted" style={{ fontSize: ".75rem" }}>
                    {dateTime(entry.created_at)}
                  </time>
                </div>
                <p>{entry.summary}</p>
                <div className="analyst-audit-meta">
                  {entry.risk_score != null && (
                    <span
                      className={`analyst-risk-number ${entry.risk_score >= 70 ? "high" : entry.risk_score >= 40 ? "medium" : ""}`}
                    >
                      Risk {entry.risk_score}/100
                    </span>
                  )}
                  {entry.trace_id && (
                    <span className="analyst-mono">Trace {entry.trace_id}</span>
                  )}
                </div>
                {entry.tools?.length > 0 && (
                  <details style={{ marginTop: ".75rem" }}>
                    <summary
                      className="muted"
                      style={{ cursor: "pointer", fontSize: ".78rem" }}
                    >
                      Executed tools ({entry.tools.length})
                    </summary>
                    <div
                      className="stack"
                      style={{ marginTop: ".75rem", gap: ".5rem" }}
                    >
                      {entry.tools.map((tool, index) => (
                        <div className="analyst-signal" key={index}>
                          <strong style={{ fontSize: ".82rem" }}>
                            {label(
                              typeof tool === "string"
                                ? tool
                                : tool.name || "Recorded tool",
                            )}
                          </strong>
                          {typeof tool !== "string" && tool.summary && (
                            <p>{tool.summary}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </article>
            ))
          ) : (
            <EmptyState
              title={
                search || agent !== "all" || risk !== "all"
                  ? "No matching audit records"
                  : "No audit records yet"
              }
              description={
                search || agent !== "all" || risk !== "all"
                  ? "Change your filters to explore the available history."
                  : "Customer actions and governed agent decisions will appear here."
              }
            />
          )}
        </Card>
      )}
      <Notice tone="info">
        This view contains recorded decision summaries and tools. Sensitive
        identifiers are masked by the server, and secret values are excluded.
      </Notice>
    </div>
  );
}
