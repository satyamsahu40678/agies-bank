const agentNames: Record<string, string> = {
  orchestrator: "Aegis assistant",
  banking_agent: "Banking assistant",
  fraud_agent: "Security guardian",
  security_agent: "Security guardian",
  kyc_agent: "Identity guide",
  identity_agent: "Identity guide",
  document_agent: "Document guide",
  recommendation_agent: "Money coach",
  recommendations_agent: "Money coach",
  financial_health_agent: "Money coach",
  savings_agent: "Savings coach",
};

export function customerAgentName(agent?: string): string {
  return agentNames[agent || ""] || "Aegis assistant";
}

export function customerReviewDecisions(decisions: string[]): string[] {
  return decisions
    .filter((decision) => !/\btools?\b|\btrace\b/i.test(decision))
    .map((decision) => decision.replace(/\bscoped\s+/gi, ""));
}

export function customerActivitySummary(summary: string): string {
  return /\btools?\b|\borchestrator\b|\btrace\b|\bscoped\b/i.test(summary)
    ? "Your banking specialist reviewed the information for this update."
    : summary;
}
