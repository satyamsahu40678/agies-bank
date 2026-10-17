export type GoalDraft = {
  id: string;
  name: string;
  target_amount: string;
  saved_amount: string;
  target_date: string;
  monthly_contribution: string;
  monthly_capacity: string;
  monthly_shortfall: string;
  message: string;
};

export type AiCitation = { document_id: string; title: string; excerpt: string; page: number; source_url?: string; publisher?: string; reviewed_at?: string };
export type AiReply = { reply: string; agent: string; citations: AiCitation[]; goal_drafts?: GoalDraft[]; proposal?: { amount: string; description: string } };

export const aiContexts: Record<string, { title: string; prompts: string[] }> = {
  dashboard: { title: "Your money, explained", prompts: ["Explain my balance, spending and budgets. What should I focus on?", "Forecast my cash flow for the next 30, 60 and 90 days."] },
  insights: { title: "Make a plan you can follow", prompts: ["Review my goals together and explain whether my monthly plan fits my cash flow.", "Help me create a savings goal. Ask me for the target amount and timeframe."] },
  analysis: { title: "Explore the numbers with me", prompts: ["Explain my cash-flow forecast and its assumptions.", "Find possible recurring expenses and explain what the patterns mean."] },
  payments: { title: "A clearer next payment", prompts: ["What is my balance and what should I check before a transfer?", "Explain NEFT, RTGS and UPI using the banking guides."] },
  documents: { title: "Understand your documents", prompts: ["Find the prepayment terms in my accessible loan policy documents.", "What does the banking guide say about deposit insurance?"] },
  knowledge: { title: "Banking questions, clear answers", prompts: ["Explain how DICGC deposit insurance works, with a source.", "What does the RBI Ombudsman banking guide say about complaints?"] },
  security: { title: "Stay a step ahead", prompts: ["Review my recent security signals and tell me what I can do next.", "Explain UPI PIN safety using the banking guide."] },
  kyc: { title: "Your identity, step by step", prompts: ["Check my identity verification status and explain my next step.", "Explain RBI re-KYC guidance without asking me to share documents in chat."] },
  recommendations: { title: "Understand your options", prompts: ["Review my affordability and explain the assumptions behind my recommendations.", "Calculate EMI for INR 200000 at 12% for 24 months."] },
  automations: { title: "Find your next helpful review", prompts: ["Review my cash flow, recurring expenses and goals. What should I keep an eye on?", "Explain the differences between a goal plan and an actual transfer."] },
  activity: { title: "Understand recent activity", prompts: ["Summarize my recent security decisions and their next steps.", "Review my posted spending and identify the largest categories."] },
};
