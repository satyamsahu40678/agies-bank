# AegisBank delivery scope

Source: the supplied AegisBank Hackathon Deck and the user's subsequent migration, cloud deployment, documentation and automatic-main-deployment instructions.

## Application workflows

1. Authenticated customer and analyst roles, server sessions, isolation between customers, explicit demo data and synthetic identities. Account overview, ledger, balances and spending analytics.
2. KYC upload of ID and selfie, structured identity submission, sanctions screening, evidence and risk scoring, approve/review/reject decisions. High-risk decisions require analyst approval. Clearly distinguish simulated verification from live vendor verification.
3. Assistant with scoped tools for balances, spending, budgets, affordability, document questions and transfer proposals. Financial mutations require explicit consent and governed execution; never let model output bypass policy.
4. Document upload, text/PDF extraction, retrieval and Q&A with precise source excerpts and citations. Include seeded loan policy, insurance policy and sample statement. Isolate private documents per customer. Unsupported formats fail clearly.
5. Loan and term-life recommendations with eligibility rules, EMI calculation, affordability and reasons. No automatic credit issuance.
6. Transfer risk: amount, statistical anomaly, velocity, new beneficiary, country, device, VPN, impossible travel. Low risk executes atomically; medium risk requires step-up; high risk is held for analyst review. Prevent duplicate settlement and overdraft; use decimal/minor-unit money.
7. Login event monitoring with geo/device history; fraud simulator using synthetic events. High-risk transfer produces hold, alert, case, customer response and analyst resolution. Analyst can approve/reject held transfers, review KYC and freeze/unfreeze accounts, with reasons.
8. Orchestrator and five specialist agents, shared scoped tool registry, decision summaries and append-only audit timeline for event-driven and interactive workflows. Optional Claude tool loop enabled by secure configuration; local deterministic mode runs the complete demo without an API key. No hidden chain-of-thought stored.

## Stack and operational decisions

- Next.js/React/TypeScript customer app, analyst console and event simulator.
- FastAPI/Python gateway with authoritative Firestore storage. Explicit memory mode supports disposable local demos; Docker Compose supplies a persistent local Firestore emulator. Mock core bank, KYC, sanctions and bureau are explicit demo adapters.
- Local lexical retrieval with source citations works offline; semantic embeddings/vector search are future extensions. Never label local scoring as a learned production model.
- Password hashing, expiring authenticated sessions, HTTP-only cookies, origin/CSRF protections, upload limits, scoped authorization and redacted audit/LLM payloads.
- Production startup fails on insecure secrets/demo configuration; documented deployment and backup instructions. Real regulated banking requires real provider integrations and operational/compliance review.

## Acceptance evidence

Backend integration tests cover authentication and authorization, tenant isolation, money conservation, transfer idempotency, step-up and analyst decisions, fraud event flow, KYC, document citations, budgets/recommendations, audit and account freeze. Frontend must type-check/build and pass browser tests for customer and analyst workflows. Startup and health requests must be exercised. Every documented endpoint and UI control must be functional.

## Subsequent user-approved additions

- External bank and identity services remain explicit mocks unless real provider accounts/protocols are supplied.
- Gemini, Claude, OpenAI and OpenRouter are selectable for chat/tool orchestration and grounded document answers. Gemini, Claude and OpenAI can also provide limited KYC evidence-quality assistance; OpenRouter is excluded from that flow. Supplying a supported key enables automatic mode; explicit local selection is respected.
- Durable proactive financial-health workflows, bounded retries and run visibility; savings-goal planning without moving funds.
- Analyst integration readiness and public-policy publication; customer indexed-source preview.
- Cross-platform local launcher and complete README/status, technology, end-to-end flow and roadmap documentation.
- Firestore-only hosted runtime, all further work on `main`, Firebase Hosting/Cloud Run deployment, enabled Secret Manager versions and durable scheduled workers.
- Pushes to `main` run the complete checks and automatically deploy the exact passing current commit using GitHub OIDC; other branches and pull requests do not deploy. Routine delivery never runs the offline importer or initializes live data.
- Free OpenRouter availability failures must keep scoped banking guidance usable through a disclosed local fallback; provider validation and financial consent stay enforced.
- Contextual Ask AI throughout the customer workspace, editable goal drafts with explicit retry-safe saving, cash-flow and recurring-expense analysis, combined savings capacity and two additional durable specialists.
- Six attributed educational banking summaries from primary Indian sources, searchable reading, exact-summary citations, official links and review dates. Keep real-source education distinct from synthetic bank products.
