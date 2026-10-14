"use client";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  Banknote,
  ChevronRight,
  CircleDollarSign,
  CreditCard,
  Pencil,
  Plus,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Wallet,
  ShoppingBag,
  Utensils,
  Home,
  Car,
  BriefcaseBusiness,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api, dateTime, money, useResource } from "@/lib/api";
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
  StatusBadge,
} from "@/components/ui";
type Transaction = {
  id: string;
  amount: string;
  direction: string;
  description: string;
  category: string;
  status: string;
  created_at: string;
  balance_after: string;
};
type Budget = {
  id: string;
  category: string;
  limit_amount: string;
  spent: string;
};
type Audit = {
  id: string;
  agent: string;
  action: string;
  summary: string;
  created_at: string;
  risk_score?: number;
};
type Overview = {
  account: {
    id: string;
    number: string;
    balance: string;
    currency: string;
    status: string;
    kyc_status: string;
  };
  spending: {
    income: string;
    expenses: string;
    savings_rate: number;
    categories: { category: string; amount: string }[];
  };
  transactions: Transaction[];
  alerts: { id: string; message?: string; summary?: string; status: string }[];
  budgets: Budget[];
  agent_activity: Audit[];
};
const palette = [
  "#4e7f63",
  "#82a484",
  "#b4c2a1",
  "#d9dabe",
  "#d4e8d7",
  "#a6b99e",
];
export default function Dashboard() {
  const { user } = useAuth();
  const { data, loading, error, refresh } = useResource<Overview>("/overview");
  const healthInsights = useResource<{
    items: { title: string; message: string }[];
    latest_run: { status: string } | null;
  }>("/insights");
  const [filter, setFilter] = useState("all");
  const [editing, setEditing] = useState<Budget | null>(null);
  const [limit, setLimit] = useState("");
  const [saving, setSaving] = useState(false);
  const [budgetError, setBudgetError] = useState("");
  const [budgetCategory, setBudgetCategory] = useState("shopping");
  if (loading && !data) return <LoadingState />;
  if (error && !data) return <ErrorState message={error} onRetry={refresh} />;
  if (!data) return null;
  const spending = data.spending;
  const total = spending.categories.reduce(
    (sum, item) => sum + Number(item.amount),
    0,
  );
  const transactions = data.transactions.filter(
    (item) =>
      filter === "all" ||
      item.direction === (filter === "income" ? "credit" : "debit"),
  );
  async function saveBudget() {
    if (!editing) return;
    setSaving(true);
    setBudgetError("");
    try {
      await api(
        `/budgets/${encodeURIComponent(editing.id === "new" ? budgetCategory : editing.category)}`,
        { method: "PUT", body: { limit_amount: limit } },
      );
      setEditing(null);
      await refresh();
    } catch (err) {
      setBudgetError(
        err instanceof Error ? err.message : "Unable to update the budget",
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="stack dashboard-stack">
      <PageHeader
        eyebrow="A LITTLE CLARITY FOR YOUR DAY"
        title={`Good to see you, ${user?.name.split(" ")[0] || "there"}.`}
        description="Your money, your goals, your peace of mind. All in one place."
        action={
          <Link href="/payments" className="button button-primary">
            <Plus size={15} />
            Make a payment
          </Link>
        }
      />
      {data.account.status === "frozen" && (
        <Notice tone="danger">
          Your account is frozen. Outgoing payments are paused while our analyst
          team reviews your account.
        </Notice>
      )}
      <div className="grid four dashboard-metrics">
        <Card className="balance-metric">
          <div className="row-between">
            <span className="stat-label">Available balance</span>
            <Wallet size={17} />
          </div>
          <div className="metric-value">{money(data.account.balance)}</div>
          <div className="balance-detail">
            <span>•••• {String(data.account.number).slice(-4)}</span>
            <StatusBadge status={data.account.status} />
          </div>
        </Card>
        <Card className="metric-card">
          <div className="row-between">
            <span className="stat-label">Money in</span>
            <span className="metric-icon">
              <ArrowDownLeft size={17} />
            </span>
          </div>
          <div className="metric-value">{money(spending.income)}</div>
          <p className="metric-change">
            <span className="visual-dot" style={{ background: "#95b79b" }} />
            Recorded income
          </p>
        </Card>
        <Card className="metric-card">
          <div className="row-between">
            <span className="stat-label">Money out</span>
            <span className="metric-icon">
              <ArrowUpRight size={17} />
            </span>
          </div>
          <div className="metric-value">{money(spending.expenses)}</div>
          <p className="metric-change">
            <span className="visual-dot" style={{ background: "#c9cfb7" }} />
            Posted expenses
          </p>
        </Card>
        <Card className="metric-card">
          <div className="row-between">
            <span className="stat-label">Savings rate</span>
            <span className="metric-icon">
              <TrendingUp size={17} />
            </span>
          </div>
          <div className="metric-value">
            {Number(spending.savings_rate).toFixed(1)}
            <span className="metric-percent">%</span>
          </div>
          <p className="metric-change">
            {Number(spending.savings_rate) >= 20
              ? "A thoughtful pace"
              : "Room to build your cushion"}
            <span>of income</span>
          </p>
        </Card>
      </div>
      <div className="dashboard-analytics">
        <Card className="cashflow-card">
          <div className="row-between">
            <div>
              <h2>Cash flow</h2>
              <p className="muted" style={{ marginTop: 5 }}>
                A clear picture of your recent money movement.
              </p>
            </div>
            <span className="chart-period">Recent activity</span>
          </div>
          <Cashflow transactions={data.transactions} />
          <div className="chart-legend">
            <span>
              <i style={{ background: "#658d6d" }} />
              Money in
            </span>
            <span>
              <i style={{ background: "#c3ceb4" }} />
              Money out
            </span>
            <span className="chart-caption">Posted transactions only</span>
          </div>
        </Card>
        <Card className="spending-card">
          <div className="row-between">
            <h2>Where it goes</h2>
            <span className="chart-period">Spending</span>
          </div>
          {total > 0 ? (
            <>
              <div className="spending-donut">
                <svg
                  viewBox="0 0 160 160"
                  role="img"
                  aria-label={`Spending by category: ${spending.categories.map((item) => `${item.category} ${money(item.amount)}`).join(", ")}`}
                >
                  <circle
                    cx="80"
                    cy="80"
                    r="57"
                    fill="none"
                    stroke="#f0f3eb"
                    strokeWidth="17"
                  />
                  {spending.categories.map((item, index) => {
                    const before =
                      (spending.categories
                        .slice(0, index)
                        .reduce((sum, it) => sum + Number(it.amount), 0) /
                        total) *
                      358;
                    return (
                      <circle
                        key={item.category}
                        cx="80"
                        cy="80"
                        r="57"
                        fill="none"
                        stroke={palette[index % palette.length]}
                        strokeWidth="17"
                        strokeDasharray={`${Math.max(0, (Number(item.amount) / total) * 358 - 2)} 358`}
                        strokeDashoffset={-before}
                        transform="rotate(-90 80 80)"
                      />
                    );
                  })}
                </svg>
                <div>
                  <span>TOTAL SPENT</span>
                  <strong>{money(total)}</strong>
                </div>
              </div>
              <div className="spending-legend">
                {spending.categories.slice(0, 4).map((item, index) => (
                  <div key={item.category}>
                    <span>
                      <i
                        style={{ background: palette[index % palette.length] }}
                      />
                      {item.category}
                    </span>
                    <strong>
                      {Math.round((Number(item.amount) / total) * 100)}%
                    </strong>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <EmptyState
              title="A fresh start"
              description="Your spending categories will appear as you make payments."
            />
          )}
        </Card>
      </div>
      <div className="assistant-banner">
        <span className="ai-orb">
          <Sparkles size={24} />
        </span>
        <div>
          <div className="row">
            <h3>A thoughtful second opinion, whenever you need it.</h3>
            <span className="assistant-label">AEGIS AI</span>
          </div>
          <p>
            Ask about your spending, plan a payment, or find the answer in a
            document.
          </p>
        </div>
        <Link href="/assistant" className="button button-secondary">
          Talk to your assistant
          <ArrowUpRight size={14} />
        </Link>
      </div>
      <div className="dashboard-bottom">
        <Card className="transactions-card">
          <div className="row-between">
            <div>
              <h2>Recent transactions</h2>
              <p className="muted" style={{ marginTop: 5 }}>
                The details behind your balance.
              </p>
            </div>
            <Link href="/payments" className="button button-ghost">
              Full history
              <ChevronRight size={13} />
            </Link>
          </div>
          <div
            className="transaction-tabs"
            role="group"
            aria-label="Filter transactions"
          >
            {["all", "income", "expenses"].map((value) => (
              <button
                key={value}
                className={filter === value ? "selected" : ""}
                onClick={() => setFilter(value)}
              >
                {value === "all"
                  ? "All transactions"
                  : value[0].toUpperCase() + value.slice(1)}
              </button>
            ))}
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <caption className="sr-only">Recent transactions</caption>
              <thead>
                <tr>
                  <th>Transaction</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th style={{ textAlign: "right" }}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {transactions.slice(0, 5).map((item) => (
                  <tr key={item.id}>
                    <td>
                      <div className="transaction-name">
                        <span
                          className={`transaction-icon ${item.direction === "credit" ? "credit" : ""}`}
                        >
                          {categoryIcon(item.category, item.direction)}
                        </span>
                        <div>
                          <strong>{item.description}</strong>
                          <small>{item.category}</small>
                        </div>
                      </div>
                    </td>
                    <td>{dateTime(item.created_at)}</td>
                    <td>
                      <StatusBadge status={item.status} />
                    </td>
                    <td
                      className={`amount ${item.direction === "credit" ? "positive" : "negative"}`}
                    >
                      {item.direction === "credit" ? "+" : "−"}
                      {money(item.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!transactions.length && (
              <EmptyState
                title="No matching transactions"
                description="Your activity will appear here after your first payment."
              />
            )}
          </div>
        </Card>
        <div className="stack">
          <Card className="budget-card">
            <div className="row-between">
              <h2>Keep your goals in view</h2>
              <button
                className="budget-edit"
                aria-label="Add budget"
                onClick={() => {
                  setEditing({
                    id: "new",
                    category: "new",
                    limit_amount: "",
                    spent: "0",
                  });
                  setLimit("");
                  setBudgetCategory("shopping");
                  setBudgetError("");
                }}
              >
                <Plus size={14} />
              </button>
            </div>
            <div className="budgets-list">
              {data.budgets.map((budget) => {
                const percent =
                  Number(budget.limit_amount) > 0
                    ? Math.min(
                        100,
                        (Number(budget.spent) / Number(budget.limit_amount)) *
                          100,
                      )
                    : 0;
                return (
                  <div key={budget.id}>
                    <div className="row-between">
                      <strong>{budget.category}</strong>
                      <button
                        className="budget-edit"
                        aria-label={`Edit ${budget.category} budget`}
                        onClick={() => {
                          setEditing(budget);
                          setLimit(budget.limit_amount);
                          setBudgetError("");
                        }}
                      >
                        <Pencil size={12} />
                      </button>
                    </div>
                    <div className="budget-bar">
                      <span
                        style={{
                          width: `${percent}%`,
                          background: percent >= 95 ? "#c99b68" : "#8eb48a",
                        }}
                      />
                    </div>
                    <div className="row-between">
                      <span>{money(budget.spent)} spent</span>
                      <span>of {money(budget.limit_amount)}</span>
                    </div>
                  </div>
                );
              })}
              {!data.budgets.length && (
                <p className="muted">
                  Add a monthly budget to give each category a thoughtful
                  target.
                </p>
              )}
            </div>
            <Link
              href="/assistant?q=Help%20me%20set%20a%20monthly%20budget"
              className="button button-ghost"
            >
              Plan with your assistant
              <ArrowRight size={12} />
            </Link>
          </Card>
          <Card className="identity-mini">
            <span className="identity-icon">
              <ShieldCheck size={21} />
            </span>
            <div>
              <h3>Your identity, protected.</h3>
              <p>Verification status</p>
              <StatusBadge status={data.account.kyc_status} />
            </div>
            <Link href="/kyc" aria-label="Open identity verification">
              <ChevronRight size={17} />
            </Link>
          </Card>
        </div>
      </div>
      <div className="health-banner">
        <Sparkles size={21} />
        <div>
          <strong>
            {healthInsights.data?.items[0]?.title ||
              "Your proactive financial review"}
          </strong>
          <p>
            {healthInsights.data?.items[0]?.message ||
              "Your agents review posted activity and savings plans without moving money."}
          </p>
        </div>
        <Link href="/insights" className="health-text-link">
          View financial health
          <ArrowRight size={13} />
        </Link>
      </div>
      <Card className="agent-activity-card">
        <div className="row-between">
          <div className="row">
            <span className="mini-ai-icon">
              <Sparkles size={16} />
            </span>
            <h2>A quiet team, working for you</h2>
          </div>
          <Link href="/activity" className="button button-ghost">
            View agent activity
            <ChevronRight size={13} />
          </Link>
        </div>
        <div className="agent-activity-grid">
          {data.agent_activity.slice(0, 3).map((item) => (
            <div key={item.id}>
              <span className="agent-activity-dot" />
              <div>
                <strong>{item.agent.replaceAll("_", " ")}</strong>
                <p>{item.summary}</p>
                <span>{dateTime(item.created_at)}</span>
              </div>
            </div>
          ))}
          {!data.agent_activity.length && (
            <p className="muted">
              Agent decisions appear here when you use the assistant, verify
              your identity, or make a payment.
            </p>
          )}
        </div>
      </Card>
      {editing && (
        <Modal
          title={
            editing.id === "new"
              ? "Create a monthly budget"
              : `Set your ${editing.category.toLowerCase()} budget`
          }
          onClose={() => setEditing(null)}
        >
          <form
            className="stack"
            onSubmit={(event) => {
              event.preventDefault();
              void saveBudget();
            }}
          >
            {editing.id === "new" && (
              <Field label="Budget category">
                <input
                  value={budgetCategory}
                  onChange={(event) =>
                    setBudgetCategory(event.target.value.toLowerCase())
                  }
                  pattern="[a-z][a-z_ ]{1,49}"
                  minLength={2}
                  maxLength={50}
                  placeholder="e.g. groceries"
                  required
                />
              </Field>
            )}
            <Field label="Monthly limit (INR)">
              <input
                type="number"
                min="0"
                max="100000000"
                step="0.01"
                required
                value={limit}
                onChange={(event) => setLimit(event.target.value)}
              />
            </Field>
            {budgetError && <Notice tone="danger">{budgetError}</Notice>}
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save budget"}
            </Button>
            <p className="muted">
              Your budget is a planning target. It does not block payments.
            </p>
          </form>
        </Modal>
      )}
    </div>
  );
}
function categoryIcon(category: string, direction: string) {
  if (direction === "credit") return <BriefcaseBusiness size={16} />;
  const name = category.toLowerCase();
  if (name.includes("food") || name.includes("dining"))
    return <Utensils size={16} />;
  if (name.includes("shop")) return <ShoppingBag size={16} />;
  if (name.includes("rent") || name.includes("home")) return <Home size={16} />;
  if (name.includes("transport")) return <Car size={16} />;
  return <CreditCard size={16} />;
}
function Cashflow({ transactions }: { transactions: Transaction[] }) {
  const days = new Map<
    string,
    { income: number; expense: number; label: string }
  >();
  transactions
    .filter((item) => item.status === "posted")
    .slice()
    .reverse()
    .forEach((item) => {
      const key = item.created_at.slice(0, 10);
      const day = days.get(key) || {
        income: 0,
        expense: 0,
        label: new Date(key).toLocaleDateString("en-IN", {
          day: "numeric",
          month: "short",
        }),
      };
      if (item.direction === "credit") day.income += Number(item.amount);
      else day.expense += Number(item.amount);
      days.set(key, day);
    });
  const items = Array.from(days.values()).slice(-7);
  const max = Math.max(
    ...items.flatMap((item) => [item.income, item.expense]),
    1000,
  );
  const step = 520 / (items.length || 1);
  if (!items.length)
    return (
      <div className="cashflow-empty">
        <EmptyState
          title="Your story starts here"
          description="Your incoming and outgoing payments will form this chart."
        />
      </div>
    );
  return (
    <svg
      className="cashflow-chart"
      viewBox="0 0 650 235"
      role="img"
      aria-label="Incoming and outgoing money by transaction date"
    >
      {[0, 1, 2, 3].map((index) => (
        <g key={index}>
          <text x="0" y={30 + index * 51} fill="#a3afa0" fontSize="9">
            {index === 3
              ? "₹0"
              : `₹${Math.round((max * (3 - index)) / 3 / 1000)}k`}
          </text>
          <line
            x1="62"
            x2="640"
            y1={26 + index * 51}
            y2={26 + index * 51}
            stroke="#edf1e8"
            strokeDasharray="3 4"
          />
        </g>
      ))}
      {items.map((item, index) => {
        const x = 72 + step * index + step * 0.15;
        const bar = Math.min(23, step * 0.25);
        return (
          <g key={item.label}>
            <rect
              x={x}
              y={179 - (item.income / max) * 153}
              height={(item.income / max) * 153}
              width={bar}
              rx="3"
              fill="#729779"
            >
              <title>
                {item.label} income {money(item.income)}
              </title>
            </rect>
            <rect
              x={x + bar + 4}
              y={179 - (item.expense / max) * 153}
              height={(item.expense / max) * 153}
              width={bar}
              rx="3"
              fill="#c7d0b8"
            >
              <title>
                {item.label} expenses {money(item.expense)}
              </title>
            </rect>
            <text
              x={x + bar}
              y="207"
              textAnchor="middle"
              fill="#9eac99"
              fontSize="9"
            >
              {item.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
