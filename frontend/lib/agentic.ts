export type Insight = {
  id: string;
  kind: string;
  severity: "info" | "warning" | "critical";
  title: string;
  message: string;
  action_label: string;
  action_path: string;
  status: string;
  metrics: Record<string, string | number | boolean>;
  created_at: string;
  updated_at: string;
};

export type AgentRun = {
  id: string;
  kind: string;
  trigger: string;
  status: string;
  attempts: number;
  max_attempts: number;
  tools: string[];
  decisions: string[];
  trace_id: string;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type FinancialInsights = {
  items: Insight[];
  summary: {
    period: string;
    income: string;
    expenses: string;
    net_cashflow: string;
    savings_rate: number;
    balance: string;
    monthly_emi_capacity: string;
    active_goals: number;
    planning_only: boolean;
  };
  latest_run: AgentRun | null;
};

export type SavingsGoal = {
  id: string;
  name: string;
  target_amount: string;
  saved_amount: string;
  target_date: string | null;
  status: "active" | "paused" | "completed";
  progress_percent: number;
  monthly_contribution: string;
  created_at: string;
  updated_at: string;
  planning_only: true;
};
