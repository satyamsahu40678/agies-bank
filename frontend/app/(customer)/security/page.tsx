"use client";

import { useState } from "react";
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
import {
  Globe2,
  ShieldCheck,
  Smartphone,
  TriangleAlert,
  FlaskConical,
  RefreshCw,
} from "lucide-react";

type Signal = { name: string; score: number; detail: string };
type SecurityEvent = {
  id: string;
  kind: string;
  city: string;
  country: string;
  latitude: number;
  longitude: number;
  ip_masked: string;
  device: string;
  is_new_device: boolean;
  vpn: boolean;
  risk_score: number;
  signals: Signal[];
  created_at: string;
};
type Alert = {
  id: string;
  title: string;
  message: string;
  severity: string;
  status: string;
  recognized: boolean | null;
  created_at: string;
};
type Overview = { alerts: Alert[]; account: { status: string } };
type Health = { demo_enabled: boolean };
type SimulationResult = {
  message: string;
  event?: SecurityEvent;
  transfer?: { id: string; status: string; risk_score: number };
  case?: { id: string; status: string };
};

const scenarios = [
  {
    value: "routine_login",
    name: "Routine login",
    description:
      "A familiar device and location. Establish a trusted baseline.",
  },
  {
    value: "impossible_travel",
    name: "Impossible travel",
    description:
      "Distant login locations too close in time. Test geographic risk detection.",
  },
  {
    value: "vpn_login",
    name: "VPN login",
    description:
      "An anonymized network and an unfamiliar device. Test context signals.",
  },
  {
    value: "large_transfer",
    name: "Large transfer",
    description:
      "A transfer outside the usual spending pattern. Test holds and analyst review.",
  },
  {
    value: "velocity_burst",
    name: "Velocity burst",
    description:
      "Rapid transfers in a short window. Test transaction velocity protection.",
  },
];
const level = (score: number) =>
  score >= 70 ? "high" : score >= 35 ? "medium" : "low";
const position = (event: SecurityEvent) => ({
  x: ((event.longitude + 180) / 360) * 800,
  y: ((90 - event.latitude) / 180) * 350,
});

function EventMap({
  events,
  selectedId,
  onSelect,
}: {
  events: SecurityEvent[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const recent = events.slice(0, 12);
  return (
    <svg
      viewBox="0 0 800 350"
      role="img"
      aria-label="Approximate geographic locations of recent account login events"
      style={{
        width: "100%",
        display: "block",
        borderRadius: 14,
        background: "#f4f7f6",
      }}
    >
      <defs>
        <pattern
          id="security-map-grid"
          width="40"
          height="35"
          patternUnits="userSpaceOnUse"
        >
          <path
            d="M 40 0 L 0 0 0 35"
            fill="none"
            stroke="#e1e8e4"
            strokeWidth=".5"
          />
        </pattern>
      </defs>
      <rect width="800" height="350" fill="url(#security-map-grid)" />
      <g fill="#d9e3dc" stroke="#c8d6cc" strokeWidth="1">
        <path d="M67 66 92 47 135 42 156 53 198 52 219 76 205 95 177 102 164 130 138 141 127 164 110 164 96 136 79 128 61 100Z M143 162 171 170 199 189 219 217 212 243 194 270 187 296 174 308 159 278 154 246 145 217 136 187Z M238 42 264 35 278 44 272 68 254 78 239 65Z" />
        <path d="M343 83 365 63 389 68 400 82 432 85 443 110 421 126 394 118 378 132 352 119 334 101Z M370 132 404 124 433 149 451 179 435 206 418 244 400 250 383 221 366 196 354 164Z" />
        <path d="M425 65 470 43 515 45 545 60 588 54 635 69 697 70 729 91 712 113 678 120 659 142 627 134 599 152 577 146 566 176 546 190 530 165 510 150 487 129 461 121 438 100Z M582 191 614 196 634 219 617 233 594 217Z M645 239 680 224 715 236 734 262 712 280 670 274 646 256Z M742 282 750 291 745 308 735 311Z" />
      </g>
      {recent.length > 1 && (
        <polyline
          points={[...recent]
            .reverse()
            .map((event) => {
              const point = position(event);
              return `${point.x},${point.y}`;
            })
            .join(" ")}
          fill="none"
          stroke="#49a38a"
          strokeWidth="1.3"
          strokeDasharray="5 5"
          opacity=".55"
        />
      )}
      {recent.map((event) => {
        const point = position(event);
        const risky = event.risk_score >= 70;
        const color = risky
          ? "#df6249"
          : event.risk_score >= 35
            ? "#c8953d"
            : "#089a78";
        return (
          <g
            key={event.id}
            role="button"
            aria-label={`View ${event.city}, ${event.country} login, risk ${event.risk_score}`}
            tabIndex={0}
            onClick={() => onSelect(event.id)}
            onKeyDown={(key) => {
              if (key.key === "Enter" || key.key === " ") {
                key.preventDefault();
                onSelect(event.id);
              }
            }}
            style={{ cursor: "pointer" }}
          >
            <title>
              {event.city}, {event.country} · {dateTime(event.created_at)} ·
              Risk {event.risk_score}
            </title>
            <circle
              cx={point.x}
              cy={point.y}
              r={selectedId === event.id ? 18 : 11}
              fill={color}
              opacity=".12"
            />
            <circle
              cx={point.x}
              cy={point.y}
              r={selectedId === event.id ? 7 : 5}
              fill={color}
              stroke="white"
              strokeWidth="2"
            />
          </g>
        );
      })}
      <text x="16" y="330" fontSize="10" fill="#78867e">
        Approximate coordinates · synthetic demo activity
      </text>
    </svg>
  );
}

export default function SecurityPage() {
  const eventsResource = useResource<SecurityEvent[]>("/events");
  const overviewResource = useResource<Overview>("/overview");
  const health = useResource<Health>("/health");
  const [selectedId, setSelectedId] = useState("");
  const [scenario, setScenario] = useState("impossible_travel");
  const [simulating, setSimulating] = useState(false);
  const [simulation, setSimulation] = useState<SimulationResult | null>(null);
  const [simulationError, setSimulationError] = useState("");
  const [responding, setResponding] = useState("");
  const [alertMessage, setAlertMessage] = useState("");
  const [alertError, setAlertError] = useState("");
  const events = eventsResource.data || [];
  const selected = events.find((event) => event.id === selectedId) || events[0];
  const alerts = overviewResource.data?.alerts || [];
  const openAlerts = alerts.filter((alert) => alert.recognized == null);
  const highestRisk = events.length
    ? Math.max(...events.map((event) => event.risk_score))
    : 0;
  const devices = new Set(events.map((event) => event.device));

  async function refresh() {
    await Promise.all([
      eventsResource.refresh(),
      overviewResource.refresh(),
      health.refresh(),
    ]);
  }
  async function simulate() {
    setSimulating(true);
    setSimulationError("");
    setSimulation(null);
    try {
      const result = await api<SimulationResult>("/simulator/events", {
        method: "POST",
        body: { scenario },
      });
      setSimulation(result);
      if (result.event) setSelectedId(result.event.id);
      await refresh();
    } catch (cause) {
      setSimulationError(
        cause instanceof Error
          ? cause.message
          : "This simulation could not be run.",
      );
    } finally {
      setSimulating(false);
    }
  }
  async function respond(alert: Alert, recognized: boolean) {
    setResponding(alert.id);
    setAlertError("");
    setAlertMessage("");
    try {
      await api(`/alerts/${alert.id}/respond`, {
        method: "POST",
        body: { recognized },
      });
      await refresh();
      setAlertMessage(
        recognized
          ? "Your confirmation was recorded. Any held transfer still requires the analyst’s decision."
          : "Your report was recorded and your account has been frozen for protection. An analyst must review the activity before transfers can resume.",
      );
    } catch (cause) {
      setAlertError(
        cause instanceof Error
          ? cause.message
          : "Your response could not be recorded.",
      );
    } finally {
      setResponding("");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="SECURITY CENTER"
        title="Protection that stays a step ahead."
        description="Review devices, locations, and risk signals. Your security agents monitor account activity and bring important decisions to you."
        action={
          <Button
            variant="secondary"
            onClick={refresh}
            disabled={eventsResource.loading || overviewResource.loading}
          >
            <RefreshCw size={15} />
            Refresh activity
          </Button>
        }
      />
      {overviewResource.data?.account.status === "frozen" && (
        <div style={{ marginBottom: 20 }}>
          <Notice tone="warning">
            Your account is frozen for protection. Transfers are blocked until
            an analyst reviews the activity and restores account access.
          </Notice>
        </div>
      )}
      <div className="grid three">
        <Card>
          <div className="row-between">
            <span className="stat-label">UNANSWERED ALERTS</span>
            <TriangleAlert size={19} color="#bb8251" />
          </div>
          <div className="metric-value">{openAlerts.length}</div>
          <p className="muted" style={{ fontSize: 12 }}>
            Your response helps the security team
          </p>
        </Card>
        <Card>
          <div className="row-between">
            <span className="stat-label">RECENT DEVICES</span>
            <Smartphone size={19} color="#0a9474" />
          </div>
          <div className="metric-value">{devices.size}</div>
          <p className="muted" style={{ fontSize: 12 }}>
            Across your recorded login activity
          </p>
        </Card>
        <Card>
          <div className="row-between">
            <span className="stat-label">HIGHEST RECENT RISK</span>
            <ShieldCheck size={19} color="#0a9474" />
          </div>
          <div className="metric-value">
            {highestRisk}
            <span style={{ fontSize: 16, color: "#87918c" }}> / 100</span>
          </div>
          <p className="muted" style={{ fontSize: 12 }}>
            Transparent rules with visible signals
          </p>
        </Card>
      </div>
      <div style={{ height: 24 }} />
      {alertMessage && <Notice tone="success">{alertMessage}</Notice>}
      {alertError && <Notice tone="danger">{alertError}</Notice>}
      {overviewResource.error && (
        <ErrorState
          message={overviewResource.error}
          onRetry={overviewResource.refresh}
        />
      )}
      {alerts.length > 0 && (
        <Card>
          <div className="row-between">
            <h2 className="section-title">Security alerts</h2>
            <span className="chip">
              {openAlerts.length} awaiting your response
            </span>
          </div>
          {openAlerts.length > 0 && (
            <p className="muted" style={{ marginBottom: 18, lineHeight: 1.7 }}>
              Reporting activity as unrecognized freezes your account for
              protection until an analyst reviews it. Recognizing an alert does
              not release a held transfer.
            </p>
          )}
          <div className="stack">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                style={{
                  padding: 18,
                  borderRadius: 12,
                  border: `1px solid ${alert.recognized == null ? "#efddbf" : "var(--border, #e3e8eb)"}`,
                  background:
                    alert.recognized == null ? "#fffbf4" : "transparent",
                }}
              >
                <div
                  className="row-between"
                  style={{ flexWrap: "wrap", gap: 8 }}
                >
                  <strong>{alert.title}</strong>
                  <StatusBadge status={alert.severity} />
                </div>
                <p style={{ fontSize: 13, lineHeight: 1.8 }}>{alert.message}</p>
                <div
                  className="row-between"
                  style={{ flexWrap: "wrap", gap: 12 }}
                >
                  <span className="muted" style={{ fontSize: 11 }}>
                    {dateTime(alert.created_at)}
                  </span>
                  {alert.recognized == null ? (
                    <div className="row" style={{ flexWrap: "wrap" }}>
                      <Button
                        variant="secondary"
                        disabled={Boolean(responding)}
                        onClick={() => respond(alert, true)}
                      >
                        I recognize this
                      </Button>
                      <Button
                        variant="danger"
                        disabled={Boolean(responding)}
                        onClick={() => respond(alert, false)}
                      >
                        This wasn’t me
                      </Button>
                    </div>
                  ) : (
                    <span className="chip">
                      {alert.recognized
                        ? "You recognized this activity"
                        : "Reported as unrecognized"}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
      <div style={{ height: 24 }} />
      <div className="grid two security-layout" style={{ alignItems: "start" }}>
        <Card>
          <div className="row-between">
            <h2 className="section-title">Login geography</h2>
            <Globe2 size={19} color="#0a9474" />
          </div>
          <p className="muted" style={{ fontSize: 13, marginBottom: 20 }}>
            A view of your recent account access. Select a location to see its
            signals.
          </p>
          {eventsResource.loading ? (
            <LoadingState />
          ) : eventsResource.error ? (
            <ErrorState
              message={eventsResource.error}
              onRetry={eventsResource.refresh}
            />
          ) : !events.length ? (
            <EmptyState
              title="No login events yet"
              description="New login activity will appear here."
            />
          ) : (
            <>
              <EventMap
                events={events}
                selectedId={selected?.id || ""}
                onSelect={setSelectedId}
              />
              <div
                className="row"
                style={{
                  flexWrap: "wrap",
                  marginTop: 14,
                  fontSize: 11,
                  gap: 18,
                }}
              >
                <span style={{ color: "#07886a" }}>● Low risk</span>
                <span style={{ color: "#ac7a2d" }}>● Elevated risk</span>
                <span style={{ color: "#cd5745" }}>● High risk</span>
              </div>
              {selected && (
                <div
                  style={{
                    background: "#f7f9f8",
                    border: "1px solid var(--border, #e3e8eb)",
                    borderRadius: 12,
                    padding: 18,
                    marginTop: 22,
                  }}
                >
                  <div className="row-between">
                    <div>
                      <strong>
                        {selected.city}, {selected.country}
                      </strong>
                      <p
                        className="muted"
                        style={{ fontSize: 12, marginBottom: 0 }}
                      >
                        {dateTime(selected.created_at)}
                      </p>
                    </div>
                    <StatusBadge status={level(selected.risk_score)} />
                  </div>
                  <div
                    className="grid two"
                    style={{ margin: "20px 0", fontSize: 12 }}
                  >
                    <div>
                      <span className="muted">Device</span>
                      <p style={{ margin: "6px 0 0" }}>{selected.device}</p>
                    </div>
                    <div>
                      <span className="muted">Masked IP</span>
                      <p style={{ margin: "6px 0 0", fontFamily: "monospace" }}>
                        {selected.ip_masked}
                      </p>
                    </div>
                  </div>
                  <div
                    className="row"
                    style={{ flexWrap: "wrap", marginBottom: 15 }}
                  >
                    <span className="chip">Risk {selected.risk_score}/100</span>
                    {selected.is_new_device && (
                      <span className="chip">New device</span>
                    )}
                    {selected.vpn && <span className="chip">VPN / proxy</span>}
                  </div>
                  {selected.signals.length > 0 && (
                    <div className="stack">
                      {selected.signals.map((signal, index) => (
                        <div key={index} style={{ fontSize: 12 }}>
                          <div className="row-between">
                            <strong>{signal.name.replace(/_/g, " ")}</strong>
                            <span className="muted">+{signal.score}</span>
                          </div>
                          <p
                            className="muted"
                            style={{ margin: "5px 0 0", lineHeight: 1.6 }}
                          >
                            {signal.detail}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </Card>
        <Card>
          <div className="row-between">
            <h2 className="section-title">Fraud lab</h2>
            <FlaskConical size={19} color="#0a9474" />
          </div>
          {health.loading ? (
            <p className="muted">Checking simulator availability…</p>
          ) : health.error ? (
            <div className="stack">
              <Notice tone="warning">
                Simulator availability could not be checked.
              </Notice>
              <div>
                <Button variant="secondary" onClick={health.refresh}>
                  Check availability
                </Button>
              </div>
            </div>
          ) : health.data?.demo_enabled !== true ? (
            <Notice>
              Security simulation is unavailable in this environment. Live
              activity and alerts remain available in your security center.
            </Notice>
          ) : (
            <>
              <span
                className="chip"
                style={{
                  background: "#f8eee0",
                  color: "#99682c",
                  marginBottom: 10,
                }}
              >
                DEMO SIMULATOR
              </span>
              <p
                className="muted"
                style={{ fontSize: 13, lineHeight: 1.8, marginBottom: 20 }}
              >
                Generate synthetic activity and follow the full response: risk
                signals, alerts, transfer decisions, and analyst cases.
              </p>
              <Field label="Simulation scenario">
                <select
                  aria-label="Simulation scenario"
                  className="select"
                  value={scenario}
                  onChange={(event) => {
                    setScenario(event.target.value);
                    setSimulation(null);
                    setSimulationError("");
                  }}
                  disabled={simulating}
                >
                  {scenarios.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </Field>
              <p
                className="muted"
                style={{
                  fontSize: 13,
                  lineHeight: 1.7,
                  marginTop: 12,
                  marginBottom: 18,
                  minHeight: 46,
                }}
              >
                {scenarios.find((item) => item.value === scenario)?.description}
              </p>
              <Notice tone="warning">
                Demo only. Transfer scenarios can post or hold synthetic funds
                in your demo account. Simulation is disabled in production.
              </Notice>
              <div style={{ marginTop: 18 }}>
                <Button disabled={simulating} onClick={simulate}>
                  <FlaskConical size={16} />
                  {simulating ? "Running simulation…" : "Run simulation"}
                </Button>
              </div>
              {simulationError && (
                <div style={{ marginTop: 18 }}>
                  <Notice tone="danger">{simulationError}</Notice>
                </div>
              )}
              {simulation && (
                <div style={{ marginTop: 18 }}>
                  <Notice tone="success">{simulation.message}</Notice>
                  {simulation.transfer && (
                    <div style={{ marginTop: 16 }}>
                      <div className="row-between">
                        <strong style={{ fontSize: 13 }}>
                          Transfer decision
                        </strong>
                        <StatusBadge status={simulation.transfer.status} />
                      </div>
                      <p className="muted" style={{ fontSize: 12 }}>
                        Risk score: {simulation.transfer.risk_score} / 100
                      </p>
                    </div>
                  )}
                  {simulation.case && (
                    <p
                      className="muted"
                      style={{ fontSize: 12, lineHeight: 1.7 }}
                    >
                      An analyst case has been created. The security team can
                      review and resolve it in the analyst console.
                    </p>
                  )}
                </div>
              )}
            </>
          )}
          <div className="divider" />
          <h3 style={{ fontSize: 13 }}>A decision you can explain</h3>
          <p className="muted" style={{ fontSize: 12, lineHeight: 1.8 }}>
            Signals cover amount, transaction velocity, new beneficiaries,
            geographic anomalies, devices, and network context. High-risk
            transfers are held for a human decision.
          </p>
        </Card>
      </div>
      <div style={{ height: 24 }} />
      <Card>
        <div className="row-between">
          <h2 className="section-title">Recent access history</h2>
          <span className="chip">{events.length} events</span>
        </div>
        {!events.length ? (
          <EmptyState
            title="No activity recorded"
            description="Your device and location history will appear after account access."
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Location</th>
                  <th>Device</th>
                  <th>Network</th>
                  <th>Risk</th>
                  <th>Time</th>
                  <th>
                    <span className="sr-only">Details</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td>
                      <strong>{event.city}</strong>
                      <div
                        className="muted"
                        style={{ fontSize: 11, marginTop: 4 }}
                      >
                        {event.country}
                      </div>
                    </td>
                    <td>
                      {event.device}
                      {event.is_new_device && (
                        <div
                          className="muted"
                          style={{ fontSize: 11, marginTop: 4 }}
                        >
                          New device
                        </div>
                      )}
                    </td>
                    <td>
                      <span style={{ fontFamily: "monospace", fontSize: 12 }}>
                        {event.ip_masked}
                      </span>
                      {event.vpn && (
                        <div
                          className="muted"
                          style={{ fontSize: 11, marginTop: 4 }}
                        >
                          VPN / proxy
                        </div>
                      )}
                    </td>
                    <td>
                      <StatusBadge status={level(event.risk_score)} />
                      <div
                        className="muted"
                        style={{ fontSize: 11, marginTop: 5 }}
                      >
                        {event.risk_score}/100
                      </div>
                    </td>
                    <td style={{ whiteSpace: "nowrap", fontSize: 12 }}>
                      {dateTime(event.created_at)}
                    </td>
                    <td>
                      <Button
                        variant="ghost"
                        aria-label={`View ${event.city} event details`}
                        onClick={() => {
                          setSelectedId(event.id);
                          window.scrollTo({ top: 250, behavior: "smooth" });
                        }}
                      >
                        View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <style jsx>{`
        .security-layout {
          grid-template-columns: minmax(0, 1.45fr) minmax(300px, 1fr);
        }
        @media (max-width: 1050px) {
          .security-layout {
            grid-template-columns: minmax(0, 1fr);
          }
        }
      `}</style>
    </>
  );
}
