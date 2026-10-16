# Implemented, configured and remaining work

The linked conversation could not be retrieved. Scope comes from the uploaded deck plus the user's subsequent decisions, including explicit approval to use banking/identity mocks and support both Claude and OpenAI.

## Implemented workflows

| Area | Delivered behavior |
| --- | --- |
| Customer and analyst access | Registration, hashed passwords, expiring server sessions, CSRF, role checks, logout revocation and tenant isolation |
| Bank core | Persistent integer-paise double-entry ledger; customer/clearing conservation; idempotent payments; no overdrafts; balance rechecks |
| Governed transfers | Customer confirmation; low-risk settlement, password re-authentication, high-risk holds and analyst decisions |
| Identity | Bounded ID/selfie uploads, evidence hashes, local validation and synthetic sanctions/risk rules; approve/review/reject with analyst controls |
| Financial assistant | Scoped tools, balances, spending, budgets, affordability, policy citations and confirmation-required payment proposals |
| Document intelligence | PDF/text/Markdown/CSV extraction, scoped retrieval, exact source citations, indexed-source preview and optional model-assisted synthesis |
| Product recommendations | Explainable rule-based loan/term-life estimates and paise-precise EMI calculator; no credit/insurance issuance |
| Fraud | Amount/z-score/velocity/new-recipient signals, synthetic geo/device/VPN events, calculated impossible-travel speed, alerts, cases and freeze/unfreeze |
| Proactive agents | Durable event queue, atomically claimed leases, bounded retries, crash recovery, scoped tools, decision summaries and complete run status |
| Financial health | Posted-ledger cash flow, budget warnings, subscription observations, safe guidance and dismissible insights |
| Savings goals | Create/edit/pause/remove manual planning goals, progress and monthly contribution estimates; goal changes never move money |
| Analyst knowledge | Explicitly confirmed publication of bank policies shared with customers; role checks and audit evidence |
| Integrations | Gemini/Claude/OpenAI selection, automatic activation from supplied keys, read-only model-access checks, Firestore alert projection and truthful adapter status |
| Operations | Native launcher, cross-platform local launcher, Docker/PostgreSQL, Cloud Run/Firebase deployment tooling, migrations, production guards, secure analyst provisioning and CI workflow |

## What an AI key enables

A Gemini, Anthropic or OpenAI key enables the implemented model-assisted chat/tool loop, grounded document answers and limited KYC image assessment. Selection and model names are configurable and local mode remains available. Financial policy, settlement, identity authority and permissions remain server-governed; model output cannot bypass them.

Model-assisted KYC assesses legibility, person presence and name consistency. It is not legal identity proof, liveness, biometric matching or an authoritative sanctions decision. Stored decisions and tool records are summaries, not hidden chain-of-thought.

No live AI key was supplied during development. Provider protocol behavior is tested with mocked responses; paid inference, account permissions, billing and real model behavior require verification using your configured account. The analyst connection check verifies model access without sending customer data or claiming paid inference worked.

## Explicitly mocked by the user's decision

Core-bank settlement, KYC/sanctions vendors, credit bureau and geolocation/device providers remain synthetic, self-contained adapters. The app works end to end in this mode, with no real money moved or real loan issued. An LLM key does not turn these into real financial providers.

To operate with real customers and money, provider-specific agreements/APIs, sandbox verification, webhook signatures/idempotency, customer consent, regulatory review, reconciliation and operational security are separate required work. Production MFA requires an enrolled second-factor provider or WebAuthn/TOTP implementation; the current password challenge is labelled a demo substitute.

## Other limits and next steps

- Local retrieval uses lexical ranking, not learned production embeddings/vector search.
- Image-only/scanned PDFs require OCR before document ingestion.
- Voice/multilingual banking and regulatory-reporting agents are deck next steps.
- Goal progress is entered by the customer as a planning record, not bank-reserved funds.
- Device/network history is synthetic rather than an attested real GeoIP or device feed.
- Backups, restore drills, HTTPS, provider-specific secrets, monitoring, access reviews and privacy/retention controls must be configured for a real deployment.
- Remote GitHub CI and production hosting are distinct from local tests. Do not treat a saved cloud draft or started local process as a published public deployment.
- This cloud session cannot control your personal computer. The local launcher lets you run the app there; a permanent hosted URL requires an authorized hosting account.

See VALIDATION.md for executed evidence, OPERATIONS.md for deployment details and API_CONTRACT.md for API behavior.
