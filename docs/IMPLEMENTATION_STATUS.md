# Implemented, configured and remaining work

Scope comes from the uploaded deck and the attached conversation, including approval to use banking/identity mocks and support Gemini, Claude, OpenAI and OpenRouter.

## Implemented workflows

| Area | Delivered behavior |
| --- | --- |
| Customer and analyst access | Registration, hashed passwords, expiring server sessions, CSRF, role checks, logout revocation and tenant isolation |
| Bank core | Persistent integer-paise double-entry ledger; customer/clearing conservation; idempotent payments; no overdrafts; balance rechecks |
| Governed transfers | Customer confirmation; low-risk settlement, password re-authentication, high-risk holds and analyst decisions |
| Identity | Bounded ID/selfie uploads, evidence hashes, local validation and synthetic sanctions/risk rules; approve/review/reject with analyst controls |
| Financial assistant | Scoped tools, balances, spending, budgets, affordability, policy citations, server-authored transfer consent text and disclosed OpenRouter fallback |
| Document intelligence | PDF/text/Markdown/CSV extraction, scoped retrieval, exact source citations, indexed-source preview and optional model-assisted synthesis |
| Product recommendations | Explainable rule-based loan/term-life estimates and paise-precise EMI calculator; no credit/insurance issuance |
| Fraud | Amount/z-score/velocity/new-recipient signals, synthetic geo/device/VPN events, calculated impossible-travel speed, alerts, cases and freeze/unfreeze |
| Proactive agents | Durable event queue, atomically claimed leases, bounded retries, crash recovery, scoped tools, decision summaries and complete run status |
| Financial health | Posted-ledger cash flow, budget warnings, subscription observations, safe guidance and dismissible insights |
| Savings goals | Create/edit/pause/remove manual planning goals, progress and monthly contribution estimates; goal changes never move money |
| Analyst knowledge | Explicitly confirmed publication of bank policies shared with customers; role checks and audit evidence |
| Integrations | Gemini/Claude/OpenAI/OpenRouter selection, automatic activation from supplied keys, read-only model-access checks, Firestore alert projection and truthful adapter status |
| Scheduled workflows | Financial health, security watch, document readiness, savings coaching; customer schedules, durable outbox dispatch, run traces and analyst reconciliation |
| Operations | Native launcher, cross-platform local launcher, Docker/Firestore emulator, Cloud Run/Firebase deployment tooling, safe offline imports, read-only rollout schema gate, production guards and secure analyst provisioning |
| Delivery | Full CI and automatic deployment of the exact passing current main commit; keyless OIDC owner bootstrap, source labels, serialized releases and hosted smoke checks |

## What an AI key enables

A Gemini, Anthropic, OpenAI or OpenRouter key enables the implemented model-assisted chat/tool loop and grounded document answers. Gemini, Anthropic and OpenAI also support limited KYC image assessment. Selection and model names are configurable and local mode remains available. Financial policy, settlement, identity authority and permissions remain server-governed; model output cannot bypass them.

Model-assisted KYC assesses legibility, person presence and name consistency. It is not legal identity proof, liveness, biometric matching or an authoritative sanctions decision. Stored decisions and tool records are summaries, not hidden chain-of-thought.

OpenRouter was enabled through Secret Manager during the live rollout. Its catalog check, real `get_balance` tool-call response and grounded policy answers were exercised using `openrouter/free`. Free-route failures also motivated a disclosed local fallback for rate limits, transient outages, timeouts and discarded unusable model output; effective answer mode is returned separately from configured mode. Other provider protocols remain covered by mocked responses. The analyst connection check verifies catalog access; executed inference and deployment outcomes are recorded separately in VALIDATION.md.

## Explicitly mocked by the user's decision

Core-bank settlement, KYC/sanctions vendors, credit bureau and geolocation/device providers remain synthetic, self-contained adapters. The app works end to end in this mode, with no real money moved or real loan issued. An LLM key does not turn these into real financial providers.

To operate with real customers and money, provider-specific agreements/APIs, sandbox verification, webhook signatures/idempotency, customer consent, regulatory review, reconciliation and operational security are separate required work. Production MFA requires an enrolled second-factor provider or WebAuthn/TOTP implementation; the current password challenge is labelled a demo substitute.

## Other limits and next steps

- Firestore-primary runtime, emulator verification and the Google Cloud/Firebase rollout are implemented. The deployment branch is `main`. The hosted app uses clean synthetic records; historical rows cannot be copied without the original SQLite source.
- Local retrieval uses lexical ranking, not learned production embeddings/vector search.
- Image-only/scanned PDFs require OCR before document ingestion.
- Voice/multilingual banking and regulatory-reporting agents are deck next steps.
- Goal progress is entered by the customer as a planning record, not bank-reserved funds.
- Device/network history is synthetic rather than an attested real GeoIP or device feed.
- HTTPS and Secret Manager bindings are configured for the hosted demo. Backups, restore drills, operational alerts, access reviews and privacy/retention controls remain production operational work.
- Remote GitHub CI, native Firestore verification and live deployment evidence are recorded separately in VALIDATION.md. The hosted demo is available at https://agies-bank.web.app; the local launcher remains available for development.

See [validation](VALIDATION.md) for executed evidence, [end-to-end flows](END_TO_END.md)
for the technology map and journeys, [CI/CD](CICD.md) for automatic main delivery,
[operations](OPERATIONS.md) for maintenance, [API contract](API_CONTRACT.md) for
responses, and [roadmap](ROADMAP.md) for prioritized future ideas.
