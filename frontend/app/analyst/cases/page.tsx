"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useResource, money, dateTime } from "@/lib/api";
import {
  PageHeader,
  Card,
  StatusBadge,
  LoadingState,
  ErrorState,
  EmptyState,
  Button,
} from "@/components/ui";

type Case = {
  id: string;
  kind: string;
  status: string;
  priority: string;
  customer_name: string;
  customer_id: string;
  risk_score: number;
  amount: string | null;
  summary: string;
  created_at: string;
};
function label(value: string) {
  return value.replace(/_/g, " ");
}

export default function CaseQueue() {
  const { data, loading, error, refresh } =
    useResource<Case[]>("/analyst/cases");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [kind, setKind] = useState("all");
  const [sort, setSort] = useState("priority");
  const cases = useMemo(
    () =>
      (data || [])
        .filter(
          (item) =>
            (status === "all" || item.status === status) &&
            (kind === "all" || item.kind === kind) &&
            `${item.customer_name} ${item.summary} ${item.id}`
              .toLowerCase()
              .includes(search.toLowerCase()),
        )
        .sort((a, b) =>
          sort === "recent"
            ? Date.parse(b.created_at) - Date.parse(a.created_at)
            : b.risk_score - a.risk_score,
        ),
    [data, search, status, kind, sort],
  );
  const kinds = [...new Set((data || []).map((item) => item.kind))];
  const statuses = [...new Set((data || []).map((item) => item.status))];

  return (
    <div className="stack">
      <PageHeader
        eyebrow="INVESTIGATIONS"
        title="The review queue."
        description="Every flagged transaction and identity check, with the evidence you need to act."
        action={
          <Button variant="secondary" onClick={refresh}>
            Refresh queue
          </Button>
        }
      />
      <div className="grid three">
        <Card>
          <span className="stat-label">Awaiting review</span>
          <div className="metric-value">
            {
              (data || []).filter((item) =>
                ["open", "pending"].includes(item.status),
              ).length
            }
          </div>
          <p className="muted">Pending human decisions</p>
        </Card>
        <Card>
          <span className="stat-label">High-risk cases</span>
          <div className="metric-value">
            {
              (data || []).filter(
                (item) =>
                  ["open", "pending"].includes(item.status) &&
                  item.risk_score >= 70,
              ).length
            }
          </div>
          <p className="muted">Reported score of 70 or higher</p>
        </Card>
        <Card>
          <span className="stat-label">Total investigations</span>
          <div className="metric-value">{data?.length || 0}</div>
          <p className="muted">Across the available case history</p>
        </Card>
      </div>
      <Card>
        <div className="analyst-toolbar">
          <div>
            <label htmlFor="case-search">Search cases</label>
            <input
              id="case-search"
              className="input"
              placeholder="Customer, case ID, or evidence…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="case-status">Status</label>
            <select
              id="case-status"
              className="select"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="all">All statuses</option>
              {statuses.map((value) => (
                <option key={value} value={value}>
                  {label(value)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="case-kind">Case type</label>
            <select
              id="case-kind"
              className="select"
              value={kind}
              onChange={(event) => setKind(event.target.value)}
            >
              <option value="all">All case types</option>
              {kinds.map((value) => (
                <option key={value} value={value}>
                  {label(value)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="case-sort">Sort by</label>
            <select
              id="case-sort"
              className="select"
              value={sort}
              onChange={(event) => setSort(event.target.value)}
            >
              <option value="priority">Highest risk</option>
              <option value="recent">Most recent</option>
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
            <h2 className="section-title">Case register</h2>
            <span className="muted">
              {cases.length} {cases.length === 1 ? "result" : "results"}
            </span>
          </div>
          {cases.length ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Customer / case</th>
                    <th scope="col">Type</th>
                    <th scope="col">Exposure</th>
                    <th scope="col">Risk score</th>
                    <th scope="col">Status</th>
                    <th scope="col">Created</th>
                    <th scope="col">Review</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <span className="analyst-table-title">
                          {item.customer_name}
                        </span>
                        <span className="muted analyst-mono">
                          {item.id.slice(0, 12)}
                        </span>
                      </td>
                      <td>
                        <span style={{ textTransform: "capitalize" }}>
                          {label(item.kind)}
                        </span>
                        <br />
                        <span
                          className="muted analyst-table-subtitle"
                          style={{ textTransform: "capitalize" }}
                        >
                          {item.priority} priority
                        </span>
                      </td>
                      <td>
                        {item.kind === "transfer" ? money(item.amount) : "—"}
                      </td>
                      <td>
                        <span
                          className={`analyst-risk-number ${item.risk_score >= 70 ? "high" : item.risk_score >= 40 ? "medium" : ""}`}
                        >
                          {item.risk_score}
                          <small className="muted">/100</small>
                        </span>
                      </td>
                      <td>
                        <StatusBadge status={item.status} />
                      </td>
                      <td>
                        <span className="muted analyst-table-subtitle">
                          {dateTime(item.created_at)}
                        </span>
                      </td>
                      <td>
                        <Link
                          className="analyst-action-link"
                          href={`/analyst/cases/${item.id}`}
                          aria-label={`Review case for ${item.customer_name}`}
                        >
                          Open case ↗
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title={
                search || status !== "all" || kind !== "all"
                  ? "No matching cases"
                  : "The case queue is clear"
              }
              description={
                search || status !== "all" || kind !== "all"
                  ? "Adjust your search or filters to see more investigations."
                  : "Flagged transfers and identity reviews appear here when they need a human decision."
              }
            />
          )}
        </Card>
      )}
    </div>
  );
}
