"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import {
  ArrowUpRight,
  Check,
  ChevronDown,
  CircleDollarSign,
  Clock3,
  HeartPulse,
  Pencil,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
  Trash2,
  Workflow,
} from "lucide-react";
import { api, dateTime, money, useResource } from "@/lib/api";
import { AgentRun, FinancialInsights, SavingsGoal } from "@/lib/agentic";
import { AskAiButton } from "@/components/ai-help";
import { customerReviewDecisions } from "@/lib/customer-labels";
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
  StatusBadge,
} from "@/components/ui";

type GoalDraft = {
  name: string;
  target_amount: string;
  saved_amount: string;
  target_date: string;
  status: SavingsGoal["status"];
};
type AgentNotifications = {
  source: "database" | "firestore";
  items: { id: string; severity: string; title: string; message: string }[];
};
const blankGoal: GoalDraft = {
  name: "",
  target_amount: "",
  saved_amount: "0",
  target_date: "",
  status: "active",
};
const label = (value: string) => value.replaceAll("_", " ");
function today() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}
function goalDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function InsightsPage() {
  const insights = useResource<FinancialInsights>("/insights");
  const goals = useResource<SavingsGoal[]>("/goals");
  const runs = useResource<AgentRun[]>("/agent-runs");
  const notifications = useResource<AgentNotifications>("/notifications/agents");
  const [refreshing, setRefreshing] = useState(false);
  const [actionError, setActionError] = useState("");
  const [actionNotice, setActionNotice] = useState("");
  const [dismissBusy, setDismissBusy] = useState("");
  const [retryBusy, setRetryBusy] = useState("");
  const [editing, setEditing] = useState<SavingsGoal | "new" | null>(null);
  const [draft, setDraft] = useState<GoalDraft>(blankGoal);
  const [goalBusy, setGoalBusy] = useState(false);
  const [goalError, setGoalError] = useState("");
  const [deleting, setDeleting] = useState<SavingsGoal | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const runsRefresh = runs.refresh;
  const insightsRefresh = insights.refresh;
  const hasPendingRun = runs.data?.some(
    (run) => run.status === "running" || run.status === "queued",
  );
  useEffect(() => {
    if (!hasPendingRun) return;
    const timer = window.setInterval(() => {
      void Promise.all([runsRefresh(), insightsRefresh()]);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [hasPendingRun, runsRefresh, insightsRefresh]);

  async function refreshAnalysis() {
    if (refreshing) return;
    setRefreshing(true);
    setActionError("");
    setActionNotice("");
    try {
      const result = await api<AgentRun>("/insights/refresh", {
        method: "POST",
      });
      await Promise.all([insights.refresh(), runs.refresh(), goals.refresh()]);
      if (result.status === "failed")
        setActionError(
          result.error ||
            "The analysis could not finish. Review the run below and retry.",
        );
      else
        setActionNotice(
          result.status === "completed"
            ? "Your financial insights are up to date with posted account activity."
            : "Analysis started. You can follow its progress in agent runs below.",
        );
    } catch (failure) {
      setActionError(
        failure instanceof Error
          ? failure.message
          : "Unable to refresh insights.",
      );
    } finally {
      setRefreshing(false);
    }
  }

  async function dismissInsight(id: string) {
    if (dismissBusy) return;
    setDismissBusy(id);
    setActionError("");
    try {
      await api(`/insights/${id}/dismiss`, { method: "POST" });
      await insights.refresh();
    } catch (failure) {
      setActionError(
        failure instanceof Error
          ? failure.message
          : "Unable to dismiss this insight.",
      );
    } finally {
      setDismissBusy("");
    }
  }

  async function retryRun(id: string) {
    if (retryBusy) return;
    setRetryBusy(id);
    setActionError("");
    setActionNotice("");
    try {
      const result = await api<AgentRun>(`/agent-runs/${id}/retry`, {
        method: "POST",
      });
      await Promise.all([runs.refresh(), insights.refresh()]);
      if (result.status === "failed")
        setActionError(result.error || "The run still needs attention.");
      else setActionNotice("Run retried. Its latest result is recorded below.");
    } catch (failure) {
      setActionError(
        failure instanceof Error
          ? failure.message
          : "Unable to retry this run.",
      );
    } finally {
      setRetryBusy("");
    }
  }

  function openGoal(goal: SavingsGoal | "new") {
    setGoalError("");
    setEditing(goal);
    setDraft(
      goal === "new"
        ? { ...blankGoal }
        : {
            name: goal.name,
            target_amount: goal.target_amount,
            saved_amount: goal.saved_amount,
            target_date: goal.target_date || "",
            status: goal.status,
          },
    );
  }

  async function saveGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || goalBusy) return;
    const target = Number(draft.target_amount),
      saved = Number(draft.saved_amount);
    if (
      !draft.name.trim() ||
      !Number.isFinite(target) ||
      target <= 0 ||
      target > 100000000 ||
      !Number.isFinite(saved) ||
      saved < 0 ||
      saved > target
    ) {
      setGoalError(
        "Enter a name, a positive target up to ₹10 crore, and a saved amount between zero and your target.",
      );
      return;
    }
    if (draft.status === "completed" && saved !== target) {
      setGoalError(
        "To mark this goal completed, the saved amount must equal the target.",
      );
      return;
    }
    setGoalBusy(true);
    setGoalError("");
    const payload = {
      name: draft.name.trim(),
      target_amount: draft.target_amount,
      saved_amount: draft.saved_amount,
      target_date: draft.target_date || null,
      ...(editing === "new" ? {} : { status: draft.status }),
    };
    try {
      await api(editing === "new" ? "/goals" : `/goals/${editing.id}`, {
        method: editing === "new" ? "POST" : "PATCH",
        body: payload,
      });
      setEditing(null);
      setActionNotice(
        "Goal saved as a planning record. Your account balance has not changed.",
      );
      await Promise.all([goals.refresh(), insights.refresh(), runs.refresh()]);
    } catch (failure) {
      setGoalError(
        failure instanceof Error
          ? failure.message
          : "Unable to save this goal.",
      );
    } finally {
      setGoalBusy(false);
    }
  }

  async function deleteGoal() {
    if (!deleting || deleteBusy) return;
    setDeleteBusy(true);
    setGoalError("");
    try {
      await api(`/goals/${deleting.id}`, { method: "DELETE" });
      setDeleting(null);
      setActionNotice("Goal removed. Your account balance has not changed.");
      await Promise.all([goals.refresh(), insights.refresh(), runs.refresh()]);
    } catch (failure) {
      setGoalError(
        failure instanceof Error
          ? failure.message
          : "Unable to remove this goal.",
      );
    } finally {
      setDeleteBusy(false);
    }
  }

  const summary = insights.data?.summary?.period ? insights.data.summary : null;
  const activeInsights =
    insights.data?.items.filter((item) => item.status !== "dismissed") || [];
  const savings = Math.max(
    0,
    Math.min(100, Number(summary?.savings_rate || 0)),
  );
  const agentAlerts = notifications.data?.items.filter(
    (item) => item.severity === "critical" || item.severity === "warning",
  ) || [];

  return (
    <div className="stack health-page">
      <PageHeader
        eyebrow="A CLEARER PATH FOR YOUR MONEY"
        title="Your financial health"
        description="A proactive view of your account activity, thoughtful savings plans, and the work your agents do for you."
        action={
          <Button
            variant="secondary"
            disabled={refreshing || !runs.data || !insights.data}
            onClick={refreshAnalysis}
          >
            {refreshing ? (
              <Pending label="Reviewing your activity…" />
            ) : (
              <>
                <RefreshCw size={15} />
                Refresh insights
              </>
            )}
          </Button>
        }
      />
      {notifications.error && !notifications.data && (
        <Notice tone="warning">Agent notifications are temporarily unavailable.</Notice>
      )}
      {agentAlerts.length > 0 && (
        <Notice tone={agentAlerts.some((item) => item.severity === "critical") ? "danger" : "warning"}>
          <strong>{agentAlerts[0].title}</strong> {agentAlerts[0].message}{" "}
          <span className="muted">
            {notifications.data?.source === "firestore" ? "Cloud alert" : "Account alert"}
          </span>
        </Notice>
      )}
      {actionError && <Notice tone="danger">{actionError}</Notice>}
      {actionNotice && <Notice tone="success">{actionNotice}</Notice>}
      {insights.loading && !insights.data ? (
        <LoadingState />
      ) : insights.error && !insights.data ? (
        <ErrorState message={insights.error} onRetry={insights.refresh} />
      ) : (
        summary && (
          <>
            {insights.error && (
              <Notice tone="warning">
                {insights.error} Showing the last loaded analysis.{" "}
                <button className="text-button" onClick={insights.refresh}>
                  Try again
                </button>
              </Notice>
            )}
            <div className="health-overview">
              <Card className="health-compass">
                <div className="row-between">
                  <span className="eyebrow">YOUR SAVINGS PACE</span>
                  <HeartPulse size={20} />
                </div>
                <div
                  className="health-ring"
                  role="img"
                  aria-label={`Savings rate ${Number(summary.savings_rate).toFixed(1)} percent of income`}
                  style={{
                    background: `conic-gradient(#82aa70 ${savings * 3.6}deg, #385447 ${savings * 3.6}deg)`,
                  }}
                >
                  <div>
                    <strong>
                      {Number(summary.savings_rate).toFixed(1)}
                      <small>%</small>
                    </strong>
                    <span>of recorded income</span>
                  </div>
                </div>
                <h2>
                  {Number(summary.savings_rate) >= 20
                    ? "A steady foundation."
                    : Number(summary.net_cashflow) < 0
                      ? "Time for a closer look."
                      : "Small steps, lasting progress."}
                </h2>
                <p>
                  Based on posted transactions · {summary.period.toLowerCase()}
                </p>
              </Card>
              <div className="health-summary-grid">
                <Card>
                  <span className="health-stat-icon">
                    <CircleDollarSign size={19} />
                  </span>
                  <span className="stat-label">Net cash flow</span>
                  <strong className="metric-value">
                    {money(summary.net_cashflow)}
                  </strong>
                  <p className="muted">
                    {money(summary.income)} in · {money(summary.expenses)} out
                  </p>
                </Card>
                <Card>
                  <span className="health-stat-icon">
                    <ShieldCheck size={19} />
                  </span>
                  <span className="stat-label">Available balance</span>
                  <strong className="metric-value">
                    {money(summary.balance)}
                  </strong>
                  <p className="muted">Your ledger balance at analysis time</p>
                </Card>
                <Card>
                  <span className="health-stat-icon">
                    <Target size={19} />
                  </span>
                  <span className="stat-label">Active savings goals</span>
                  <strong className="metric-value">
                    {summary.active_goals}
                  </strong>
                  <Link href="#goals" className="health-text-link">
                    Give your next chapter a plan <ArrowUpRight size={13} />
                  </Link>
                </Card>
                <Card>
                  <span className="health-stat-icon">
                    <Sparkles size={19} />
                  </span>
                  <span className="stat-label">Estimated EMI capacity</span>
                  <strong className="metric-value">
                    {money(summary.monthly_emi_capacity)}
                  </strong>
                  <p className="muted">
                    Illustrative estimate, subject to eligibility
                  </p>
                </Card>
              </div>
            </div>
            <section aria-labelledby="insights-title" className="stack">
              <div className="row-between health-section-heading">
                <div>
                  <p className="eyebrow">PAY ATTENTION TO WHAT MATTERS</p>
                  <h2 id="insights-title">A few thoughtful observations</h2>
                </div>
                <span className="chip">
                  {activeInsights.length} active{" "}
                  {activeInsights.length === 1 ? "insight" : "insights"}
                </span>
              </div>
              {activeInsights.length ? (
                <div className="grid two">
                  {activeInsights.map((item) => (
                    <Card
                      key={item.id}
                      className={`health-insight health-insight-${item.severity}`}
                    >
                      <div className="row-between">
                        <span className="health-insight-kind">
                          <Sparkles size={15} />
                          {label(item.kind)}
                        </span>
                        <StatusBadge
                          status={
                            item.severity === "critical"
                              ? "high"
                              : item.severity === "warning"
                                ? "medium"
                                : "low"
                          }
                        />
                      </div>
                      <h3>{item.title}</h3>
                      <p>{item.message}</p>
                      <div className="health-insight-actions">
                        <Link
                          href={item.action_path}
                          className="health-text-link"
                        >
                          {item.action_label}
                          <ArrowUpRight size={14} />
                        </Link>
                        <Button
                          variant="ghost"
                          disabled={Boolean(dismissBusy)}
                          aria-label={`Dismiss ${item.title}`}
                          onClick={() => dismissInsight(item.id)}
                        >
                          {dismissBusy === item.id ? "Dismissing…" : "Dismiss"}
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              ) : (
                <Card>
                  <EmptyState
                    title="You’re all caught up"
                    description="Refresh your analysis when your activity changes to check for new observations."
                  >
                    <Button
                      variant="secondary"
                      disabled={refreshing || !runs.data || !insights.data}
                      onClick={refreshAnalysis}
                    >
                      <RefreshCw size={14} />
                      Review my account
                    </Button>
                  </EmptyState>
                </Card>
              )}
              {insights.data?.latest_run?.completed_at && (
                <p className="health-source-note">
                  <Clock3 size={13} />
                  Last analysis{" "}
                  {dateTime(insights.data.latest_run.completed_at)} · Grounded
                  in your account activity
                </p>
              )}
            </section>
          </>
        )
      )}

      <section
        id="goals"
        aria-labelledby="goals-title"
        className="stack health-anchor"
      >
        <div className="row-between health-section-heading">
          <div>
            <p className="eyebrow">TURN INTENTIONS INTO A PLAN</p>
            <h2 id="goals-title">Your savings goals</h2>
          </div>
          <div className="row"><AskAiButton prompt="Help me create a savings goal. Ask me for its name, target amount in INR and timeframe before drafting it.">Plan with AI</AskAiButton><Button onClick={() => openGoal("new")}>
            <Plus size={15} />
            Create a goal
          </Button></div>
        </div>
        <div className="health-planning-note">
          <ShieldCheck size={17} />
          <p>
            Goals are personal planning records. Saved amounts are entered by
            you; they do not move, reserve, or verify money in your account.
          </p>
        </div>
        {goals.loading && !goals.data ? (
          <LoadingState />
        ) : goals.error && !goals.data ? (
          <ErrorState message={goals.error} onRetry={goals.refresh} />
        ) : (
          <>
            {goals.error && (
              <Notice tone="warning">
                {goals.error}{" "}
                <button className="text-button" onClick={goals.refresh}>
                  Reload goals
                </button>
              </Notice>
            )}
            {goals.data?.length ? (
              <div className="grid three">
                {goals.data.map((goal) => (
                  <Card key={goal.id} className="health-goal">
                    <div className="row-between">
                      <span className="health-goal-icon">
                        {goal.status === "completed" ? (
                          <Check size={19} />
                        ) : (
                          <Target size={19} />
                        )}
                      </span>
                      <StatusBadge status={goal.status} />
                    </div>
                    <h3>{goal.name}</h3>
                    <div className="health-goal-amount">
                      <strong>{money(goal.saved_amount)}</strong>
                      <span>of {money(goal.target_amount)}</span>
                    </div>
                    <div
                      className="health-goal-progress"
                      role="progressbar"
                      aria-label={`${goal.name} savings progress`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={goal.progress_percent}
                    >
                      <span
                        style={{
                          width: `${Math.max(0, Math.min(100, goal.progress_percent))}%`,
                        }}
                      />
                    </div>
                    <div className="row-between health-goal-meta">
                      <span>
                        {Number(goal.progress_percent).toFixed(1)}% of target
                      </span>
                      <span>
                        {goal.target_date
                          ? goalDate(goal.target_date)
                          : "No deadline"}
                      </span>
                    </div>
                    <div className="health-goal-plan">
                      <span>Suggested monthly contribution</span>
                      <strong>
                        {goal.status === "completed"
                          ? "Goal reached"
                          : `${money(goal.monthly_contribution)} / mo`}
                      </strong>
                    </div>
                    <div className="health-goal-actions">
                      <Button
                        variant="secondary"
                        onClick={() => openGoal(goal)}
                        aria-label={`Edit ${goal.name}`}
                      >
                        <Pencil size={13} />
                        Edit plan
                      </Button>
                      <button
                        className="icon-button"
                        aria-label={`Delete ${goal.name}`}
                        onClick={() => {
                          setGoalError("");
                          setDeleting(goal);
                        }}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              <Card>
                <EmptyState
                  title="Make room for what matters"
                  description="Plan an emergency cushion, a new home, or your next adventure. Your agent will help you see a monthly contribution."
                >
                  <Button onClick={() => openGoal("new")}>
                    <Plus size={14} />
                    Create your first goal
                  </Button>
                </EmptyState>
              </Card>
            )}
          </>
        )}
      </section>

      <section
        id="runs"
        aria-labelledby="runs-title"
        className="stack health-anchor"
      >
        <div className="row-between health-section-heading">
          <div>
            <p className="eyebrow">YOUR RECENT REVIEWS</p>
            <h2 id="runs-title">Account reviews</h2>
          </div>
          <Button
            variant="ghost"
            disabled={runs.loading}
            onClick={runs.refresh}
          >
            <RefreshCw size={14} />
            Refresh runs
          </Button>
        </div>
        <p className="muted health-explanation">
          See what each review found and follow its progress. Your suggestions
          appear in Insights. You review and confirm every payment separately.
        </p>
        {runs.loading && !runs.data ? (
          <LoadingState />
        ) : runs.error && !runs.data ? (
          <ErrorState message={runs.error} onRetry={runs.refresh} />
        ) : (
          <Card className="health-runs-card">
            {runs.error && <Notice tone="warning">{runs.error}</Notice>}
            {runs.data?.length ? (
              <div className="health-run-list">
                {runs.data.map((run) => (
                  <details className="health-run" key={run.id} data-run-id={run.id}>
                    <summary>
                      <span className="health-run-icon">
                        <Workflow size={18} />
                      </span>
                      <div className="health-run-copy">
                        <strong>{label(run.kind)}</strong>
                        <span>
                          {label(run.trigger)} · {dateTime(run.created_at)}
                        </span>
                      </div>
                      <StatusBadge status={run.status} />
                      <ChevronDown className="health-run-chevron" size={16} />
                    </summary>
                    <div className="health-run-detail">
                      <dl>
                        <div>
                          <dt>Started</dt>
                          <dd>
                            {run.started_at
                              ? dateTime(run.started_at)
                              : "Waiting"}
                          </dd>
                        </div>
                        <div>
                          <dt>Completed</dt>
                          <dd>
                            {run.completed_at
                              ? dateTime(run.completed_at)
                              : "Pending"}
                          </dd>
                        </div>
                      </dl>
                      <div className="health-run-evidence">
                        <div>
                          <h4>Review summary</h4>
                          {run.decisions.length ? (
                            <ul>
                              {customerReviewDecisions(run.decisions).map((decision, index) => (
                                <li key={index}>{decision}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="muted">Your review summary will appear here.</p>
                          )}
                        </div>
                      </div>
                      {run.error && <Notice tone="danger">This review could not finish. Please try again.</Notice>}
                      {run.status === "failed" &&
                        run.attempts < run.max_attempts && (
                          <Button
                            variant="secondary"
                            disabled={Boolean(retryBusy)}
                            onClick={() => retryRun(run.id)}
                          >
                            {retryBusy === run.id ? (
                              <Pending label="Retrying…" />
                            ) : (
                              <>
                                <RefreshCw size={14} />
                                Retry run
                              </>
                            )}
                          </Button>
                        )}
                    </div>
                  </details>
                ))}
              </div>
            ) : (
              <EmptyState
                title="Ready when you are"
                description="Refresh your insights to start a financial analysis. Every run will keep a transparent record."
              >
                <Button
                  variant="secondary"
                  disabled={refreshing}
                  onClick={refreshAnalysis}
                >
                  <Sparkles size={14} />
                  Start an analysis
                </Button>
              </EmptyState>
            )}
          </Card>
        )}
      </section>
      <p className="health-disclosure">
        Insights are guidance based on recorded activity. Goals, repayment
        estimates, and savings suggestions are illustrative planning tools, not
        financial advice or a credit approval.
      </p>

      {editing && (
        <Modal
          title={
            editing === "new"
              ? "Create a savings goal"
              : "Edit your savings plan"
          }
          onClose={() => {
            if (!goalBusy) setEditing(null);
          }}
        >
          <form
            className="stack"
            aria-label="Savings goal form"
            onSubmit={saveGoal}
          >
            <Field label="Goal name">
              <input
                aria-label="Goal name"
                value={draft.name}
                onChange={(event) =>
                  setDraft({ ...draft, name: event.target.value })
                }
                maxLength={100}
                required
                disabled={goalBusy}
                placeholder="e.g. Emergency cushion"
              />
            </Field>
            <div className="form-grid">
              <Field label="Target amount (INR)">
                <input
                  aria-label="Target amount (INR)"
                  value={draft.target_amount}
                  onChange={(event) =>
                    setDraft({ ...draft, target_amount: event.target.value })
                  }
                  type="number"
                  min="0.01"
                  max="100000000"
                  step="0.01"
                  required
                  disabled={goalBusy}
                />
              </Field>
              <Field label="Saved amount (INR)">
                <input
                  aria-label="Saved amount (INR)"
                  value={draft.saved_amount}
                  onChange={(event) =>
                    setDraft({ ...draft, saved_amount: event.target.value })
                  }
                  type="number"
                  min="0"
                  max={draft.target_amount || "100000000"}
                  step="0.01"
                  required
                  disabled={goalBusy}
                />
              </Field>
            </div>
            <Field
              label="Target date (optional)"
              hint="Without a date, your suggested contribution uses a six-month plan."
            >
              <input
                aria-label="Target date (optional)"
                type="date"
                min={
                  editing !== "new" && editing.target_date === draft.target_date
                    ? undefined
                    : today()
                }
                value={draft.target_date}
                onChange={(event) =>
                  setDraft({ ...draft, target_date: event.target.value })
                }
                disabled={goalBusy}
              />
            </Field>
            {editing !== "new" && (
              <Field label="Plan status">
                <select
                  aria-label="Plan status"
                  value={draft.status}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      status: event.target.value as SavingsGoal["status"],
                    })
                  }
                  disabled={goalBusy}
                >
                  <option value="active">Active</option>
                  <option value="paused">Paused</option>
                  <option value="completed">Completed</option>
                </select>
              </Field>
            )}
            <Notice>
              Saving this goal updates your personal plan. It does not transfer
              or reserve funds.
            </Notice>
            {goalError && <Notice tone="danger">{goalError}</Notice>}
            <Button type="submit" disabled={goalBusy}>
              {goalBusy ? <Pending label="Saving goal…" /> : "Save goal"}
            </Button>
          </form>
        </Modal>
      )}
      {deleting && (
        <Modal
          title="Remove this savings goal?"
          onClose={() => {
            if (!deleteBusy) setDeleting(null);
          }}
        >
          <div className="stack">
            <p className="muted">
              This removes the planning record for{" "}
              <strong>{deleting.name}</strong>. Your account balance is
              unaffected.
            </p>
            {goalError && <Notice tone="danger">{goalError}</Notice>}
            <div className="row">
              <Button
                variant="secondary"
                disabled={deleteBusy}
                onClick={() => setDeleting(null)}
              >
                Keep goal
              </Button>
              <Button
                variant="danger"
                disabled={deleteBusy}
                onClick={deleteGoal}
              >
                {deleteBusy ? <Pending label="Removing…" /> : "Remove goal"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
