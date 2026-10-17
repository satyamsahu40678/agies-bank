# Technologies and end-to-end journeys

The public entry point is https://agies-bank.web.app. Choose **Customer demo**
or **Analyst demo**. Both accounts and all banking/identity events are synthetic.
New registration creates a customer with zero balance; use the seeded customer
to exercise funded payment journeys.

## Technology map

| Component | Implementation | Purpose |
| --- | --- | --- |
| Customer and analyst UI | Next.js 15.5, React 19, TypeScript, react-markdown/remark-gfm, Lucide icons, self-hosted fonts | Responsive pages, Markdown replies, source previews, dialogs and run traces |
| API | Python 3.12, FastAPI, Uvicorn, Pydantic | Validated requests and server-owned banking decisions |
| Authentication | Argon2, opaque expiring sessions, Secure HttpOnly `__session`, CSRF/Origin checks | Customer/analyst and tenant boundaries; Firebase Auth is not used |
| Data | Firestore Native and Python Google Cloud SDK | All authoritative state, atomic commits and conditional preconditions |
| Domain repository | Plain records, query expressions and unit of work | Integer-paise money, unique reservations, append-only ledger/audit |
| AI | Hosted Gemini `gemini-3.1-flash-lite`; optional OpenRouter, Claude or OpenAI; scoped tool registry | Grounded answers and review-only proposals |
| Documents | pypdf and bounded text/Markdown/CSV extraction | Private/shared retrieval with exact page/excerpt citations |
| Background work | Durable Firestore outbox, leases, fencing and schedules | Retryable, customer-scoped reviews without moving funds |
| Cloud delivery | Cloud Build, Artifact Registry, Cloud Run, Firebase Hosting, Scheduler, Secret Manager | HTTPS app, independent finite workers and secret bindings |
| CI/CD and checks | GitHub Actions/OIDC, pytest, native Firestore emulator, Playwright, dependency audits | Verify and release passing `main` commits |

SQLAlchemy/Alembic are isolated development dependencies for historical import.
They are absent from the production image and authoritative runtime.

## Sign-in and account overview

1. The browser sends credentials through Firebase Hosting and the Next.js API proxy.
2. FastAPI checks the password hash and records an opaque session in Firestore.
3. The browser receives a Secure HttpOnly `__session` cookie and a CSRF token.
4. Authenticated requests read the customer's account, posted ledger, budgets,
   alerts and review status. Private records are filtered by the server user ID.
5. Login can queue a financial review in the same transaction as its audit event.
   Logout revokes the stored session; the prior cookie cannot authenticate again.

## Payments and analyst decisions

Select a saved beneficiary and amount in Payments, or ask the assistant to
prepare a proposal. Preparing a proposal is a read-only operation. Review the
recipient and amount and explicitly confirm before `POST /transfers` is sent.

| Decision | Result |
| --- | --- |
| Low risk | Atomic debit/credit, paired posted ledger entries, transfer status, audit and follow-up job |
| Verification required | Pending challenge; the demo asks for password reauthentication and rechecks the transfer |
| High risk | Held transfer, customer alert and analyst case; no settlement until an approved, rechecked decision |
| Rejected, frozen or insufficient funds | No settlement; the response explains the condition |

The server calculates risk from stored evidence, not customer-supplied scores.
The same idempotency key cannot settle twice. Analyst approval checks the latest
account/transfer status and available balance. A failed atomic commit leaves all
financial state unchanged. The clearing account balances customer postings.

To exercise the hold flow, use Security's synthetic impossible-travel or large
payment scenarios, then sign in as the analyst. Inspect the case's signals,
customer events and audit history; resolve with a reason. Analyst Operations
reports ledger reconciliation and job/lease counts. Existing suspicious evidence
continues to influence subsequent demo payments.

## Assistant and documents

1. Ask for a balance, spending summary, eligibility explanation or policy.
2. The server redacts identifiers and exposes only authorized scoped tools.
3. Gemini uses native `generateContent` function calling. Opaque thought
   signatures are retained for tool continuations and excluded from client
   responses. Scoped tools supply account data. Document tools retrieve only
   the customer's uploads and shared analyst-published policies.
4. Model citations are checked against retrieved excerpts. Invalid references
   fail validation and the generated answer is discarded. Document text cannot
   grant tools. Gemini configuration, quota and validation errors remain visible.
5. OpenRouter rate limits/outages/timeouts and unusable native tool/output
   responses use the local scoped assistant with
   a visible notice and `ai_mode=local`. Local document answers quote accessible
   passages. The notice distinguishes these from model-generated synthesis.
6. A validated transfer proposal opens the payment review dialog. Money moves only through the confirmed,
   governed payment endpoint.
7. Saved history and new assistant replies render Markdown headings, emphasis,
   lists, tables, blockquotes, links and fenced code. Raw HTML is ignored,
   unsafe link protocols are filtered, and external links use `noopener
   noreferrer`. User messages remain literal text. Markdown formatting does
   not grant tools or submit proposals.

Customer screens show named specialists and plain-language account/review
updates. Internal tool lists, execution identifiers and provider-routing copy
are omitted from chat, insights, scheduled-review history, activity and document
answers. The sidebar scrolls vertically when its contents exceed the screen.
Backend audit evidence and analyst operational controls remain available.

Upload [sample-policy.txt](../examples/sample-policy.txt), ask why a loan can be
rejected, then open the returned source passage. A private upload remains hidden
from other customers. Analysts can explicitly publish a shared bank policy;
knowledge publication does not change lending or transfer authorization rules.

## Identity

Submit the synthetic ID/selfie examples and structured fields from
[examples](../examples/README.md). The local adapter checks evidence format and
applies demo screening rules, storing hashes and decision summaries. High-risk
submissions enter analyst review. OpenRouter is not a KYC image provider.
This flow is functional synthetic verification, not legal identity proof,
biometric liveness or an authoritative sanctions service.

## Planning and durable automations

Create a budget or savings goal; these planning records do not reserve/debit
funds. Open Automations and enable a review with an interval of 1–168 hours.

| Workflow | Reads and guidance |
| --- | --- |
| Financial health | Posted income/spending, budget pressure, subscriptions and financial summary |
| Security watch | Account status, stored suspicious events, alerts and held-transfer guidance |
| Document readiness | Indexed document coverage, identity readiness and missing-document guidance |
| Savings coaching | Goal progress, dates and contribution planning |
| Cash-flow analyst | 30/60/90-day estimates and combined goal feasibility |
| Expense detective | Possible weekly/monthly expense patterns from posted debits |

Cloud Scheduler invokes the finite worker every five minutes. Due-time
advancement and job creation are atomic. A worker claims a lease/fencing token,
runs scoped tools, then commits outputs and completion together. Expired leases
recover, attempts are bounded and per-customer exclusion prevents overlap.
Manual Run/Refresh wakes queued work without waiting for the next scheduled tick.
Pause stops future dispatches; an already queued job can finish. Inspect the
customer review summaries and analyst Operations for completion and reconciliation.

## Contextual AI, goal drafts and banking guides

Sign in as a customer and choose **Ask AI** on a workspace page. Select a suggested
question to execute it immediately, or enter your own. The model reads current
scoped data and explains calculated results in Markdown. Opening the panel makes
no inference request. Conversation text is saved in the full assistant history.

For a goal, ask **Create a goal for Emergency fund of INR 60000 in 12 months**.
Inspect the monthly estimate and shortfall, choose **Review goal draft**, edit
the fields, then **Save this goal**. The separate CSRF-protected save request uses
a stable draft key for retries. Until that save, no goal exists. Account balances
and the ledger remain unchanged throughout this planning flow.

Open **Money analysis** to compare estimates, recurring-payment patterns and all
active goals against the same monthly capacity. Each section has an AI explanation
button. Open **Banking guides** for six searchable educational summaries, select
**Read guide**, follow the official source, or choose **Explain with AI** for a
cited answer. The guides are real-source education; the bank records remain
synthetic. Details and limits are in [AI workspace](AI_WORKSPACE.md).

## From code change to the hosted application

Push to `main` → full Application checks → verified exact current commit →
keyless Google identity → API/web images → read-only schema gate → Cloud Run
services/jobs → Firebase Hosting/rules/indexes → public smoke checks.
The deployed database and sessions persist across compatible app rollouts.
See [CI/CD](CICD.md) for the one-time owner trust setup and executed status,
[validation](VALIDATION.md) for evidence, and [roadmap](ROADMAP.md) for future work.
