# Contextual AI and banking knowledge

## What customers can do

**Ask AI** is available throughout the customer workspace. It opens a page-aware
panel with suggested questions and a free-text question box. Choosing a suggestion
executes the request; opening the panel alone makes no model request. Answers use
the same authenticated assistant and Markdown renderer as the full conversation.
Open **AI assistant** to see saved conversation text.

| Experience | How it works | Customer control |
| --- | --- | --- |
| Cash-flow analyst | Calculates 30/60/90-day estimates by repeating the complete last 30 days of posted income and expenses | Read-only estimates; no credit or overdraft is created |
| Expense detective | Looks through 120 days of posted debits for similar weekly/monthly patterns with at least three distinct payment dates | Possible patterns, not confirmed subscriptions; cannot cancel or pay |
| Savings coach | Compares combined contributions for all active goals against one shared cash-flow surplus | Draft, edit, then explicitly save each new goal |
| Banking guide | Retrieves attributed summaries of Indian banking publications | Inspect the excerpt, publisher, review date and official source |
| Contextual help | Provides questions suited to balances, payments, identity, documents, security, goals and recommendations | Every financial action keeps its existing confirmation and server checks |

Try: **Create a goal for Emergency fund of INR 60000 in 12 months.** The server
calculates a monthly contribution and any shortfall after existing goals. AI
returns a draft card; this does not create a goal. Review its name, amount and
date, then choose **Save this goal**. The saved amount starts at zero. The request
uses a per-draft idempotency key so an unchanged save can be retried safely. An
existing goal changed after saving causes a conflicting replay to fail. Deleting
a goal removes the planning record; request keys are not permanent tombstones.
Goal creation remains available through the normal form.

Draft cards are attached to the current answer. Saved conversation history keeps
the answer text, not interactive draft cards. Ask again for a fresh draft after
reloading. The contextual panel retains the most recent answer while navigating;
close it or open the full conversation as needed.

## Source library

The **Banking guides** page contains six original educational summaries, reviewed
on **2026-10-17**, with primary-source links. These are not copies of complete
regulations or official product contracts.

| Guide | Primary publication |
| --- | --- |
| Deposit insurance | [DICGC FAQ](https://www.dicgc.org.in/FAQs) |
| UPI and PIN safety | [NPCI UPI FAQ](https://www.npci.org.in/what-we-do/upi/faqs) |
| NEFT processing | [RBI NEFT availability direction](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11750) |
| RTGS essentials | [RBI RTGS FAQ](https://www.rbi.org.in/scripts/FS_FAQs.aspx?Id=65) |
| Re-KYC preparation | [RBI customer-awareness guidance](https://rbikehtahai.rbi.org.in/RBIREKYC.html) |
| Complaint escalation | [Government of India banking guidance](https://financialservices.gov.in/banking) |

Summaries ship with the API release in `services/knowledge.py`. There is no runtime
crawler, remote HTML execution, Firestore seed import or overwrite of uploaded
documents. Reviewing a source change requires updating the summary and review
date, running citation tests and publishing through the normal main pipeline.
External publications can change; customers should consult the current authority
and their bank. AegisBank's synthetic balances do not establish deposit insurance,
regulated banking, a real NEFT/RTGS/UPI connection or regulatory KYC compliance.

Banking-guide retrieval includes exact substrings of the shipped summary plus its
official source URL and review date. Existing private-document questions preserve
their tenant scope and policy focus; banking-topic requests or explicit guide IDs
can include educational sources. Model output cannot author the citation list.

## Implementation and operations

The five added capabilities are `get_cashflow_forecast`,
`get_recurring_expenses`, `get_goal_plan`, `propose_savings_goal` and
`search_banking_guides`. Server roles, scopes, bounded argument schemas and
numeric validation apply before execution. Account/ledger queries derive the
customer from the session. The model supplies no account or tenant selector.
Drafting has only `goals:propose` permission, not a goal-write capability.

New **Cash-flow analyst** and **Expense detective** schedules use the existing
durable outbox, tenant fences, lease expiry, deduplication and bounded retries.
Their calculations are deterministic and do not make background model calls.
Customers opt into schedules and can pause them. Completed findings appear in
Financial health; the current analysis is available in Money analysis. Existing
financial-health, security, document and savings reviews remain available.

Hosted explanations use **Gemini `gemini-3.1-flash-lite`** with the existing
Secret Manager binding. No new credential, cloud service, data migration or
deployment permission is needed. Contextual and full-chat requests consume the
configured provider quota only after a customer submits a question. Scheduled
reviews consume worker/Firestore resources without model inference.

Complete scoped windows are used for the new analysis; no sample is presented as
a complete financial total. These reads can become expensive for large ledgers.
Tenant aggregate projections and measured load tests remain scale work. Repeated
expense detection is a conservative rule, not a learned subscription classifier.
Forecasts omit future timing, unrecorded bills, interest and changing income.

## Verification

`backend/tests/test_ai_workspace.py` exercises complete-window arithmetic,
future/pending/foreign-record exclusion, shared savings capacity, goal drafts
without writes, explicit idempotent confirmation, invalid input, role/scope/CSRF
checks, primary-source citations and native Gemini function-call continuation.
The existing workflow suite runs every schedule kind without moving money.

`tests/e2e/ai-workspace.spec.ts` exercises contextual goal drafting, edited
confirmation, saved-goal visibility, balance conservation, mobile analysis and
source-linked banking answers. Full backend and browser results are recorded in
[validation](VALIDATION.md). Main pushes run CI before deploying the exact passing
current commit; see [CI/CD](CICD.md).
