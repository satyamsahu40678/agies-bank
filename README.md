# AegisBank

A runnable, governed agentic banking application with customer and analyst workspaces, configurable **Claude or OpenAI**, proactive financial reviews, identity workflows, cited document answers, recommendations and fraud investigation.

Banking, identity/sanctions, bureau and geo/device providers use explicit synthetic adapters, as requested. No real money moves. AI keys enable the implemented model-assisted capabilities; they do not establish a real bank or legal identity-provider connection.

![AegisBank customer overview](docs/images/dashboard.png)

## Run on your computer

Install **Python 3.12+** and **Node.js 24 LTS** (includes npm). Then:

```bash
git clone --branch feat/aegisbank-complete https://github.com/satyamsahu40678/agies-bank.git
cd agies-bank
python scripts/run-local.py --setup --open
```

On macOS/Linux use `python3` if `python` is not installed. On Windows you can use `py -3`. The launcher installs hash-verified Python and npm-lock dependencies, starts the API/web app, and opens your computer's browser. It stops both services on Ctrl+C. Subsequent starts omit `--setup`.

The app uses web port 3000 and API port 8000. Logs are in `logs/`. The local launcher uses loopback only. This cloud workspace cannot directly control your personal computer; run the commands on the computer where you want to view the app.

For development with uv/make:

```bash
make setup
make dev
```

For Docker Desktop/PostgreSQL, copy `.env.example` to `.env`, generate distinct random `POSTGRES_PASSWORD` and `AEGIS_SECRET`, then run `docker compose up --build -d`. See [operations](docs/OPERATIONS.md) for proxy-aware builds and production requirements.

## Add Claude or OpenAI

Create or edit the **project-root `.env`**, which is ignored by Git. Enter keys there or in secure backend environment settings; do not put them in chat, browser forms or source code.

```dotenv
AEGIS_AI_PROVIDER=auto
AEGIS_KYC_VISION=auto
# Add either provider's key:
ANTHROPIC_API_KEY=
AEGIS_OPENAI_API_KEY=
```

Restart the backend after editing. With one supplied key, automatic mode selects that provider for chat/tools, document synthesis and limited KYC image assessment. With both keys, auto deterministically prefers Claude; set `AEGIS_AI_PROVIDER=openai` or `claude` to choose. Set `local` to run without model calls. `AEGIS_AI_MODE` remains a compatibility setting, and `AEGIS_KYC_VISION` can override the image-assessment provider independently.

Local `OPENAI_API_KEY` is accepted as an alias. In Codex cloud settings use `AEGIS_OPENAI_API_KEY`, because `OPENAI_API_KEY` is a reserved platform target name. Optional model overrides are `ANTHROPIC_MODEL` and `AEGIS_OPENAI_MODEL`; otherwise the app discovers an accessible supported model. Allow `api.anthropic.com` and/or `api.openai.com` when running behind restricted egress.

The analyst **Integrations** page shows implemented adapters, effective modes and credential presence without revealing values. Connection buttons check model access without sending customer data. Supplied keys still need valid account permissions, billing and network access. No live AI key was supplied during development; provider behavior is exercised with mocked protocol responses.

## Demo sign-ins

| Role | Email | Password |
| --- | --- | --- |
| Customer | `customer@aegis.demo` | `AegisDemo!2026` |
| Analyst | `analyst@aegis.demo` | `AegisAnalyst!2026` |

These credentials are intentionally public synthetic demo credentials. Production startup rejects a database containing them. Newly registered customers start with zero balance, and public registration cannot grant the analyst role.

## What is implemented

- **Customer overview and payments:** persisted balances, complete monthly totals, transaction history, beneficiaries, explicit payment review, atomic double-entry settlement, replay protection and no overdrafts.
- **Financial health:** proactive scoped tools review posted activity, cash flow, budget pressure, subscriptions, identity status, affordability and savings plans.
- **Savings goals:** manual planning progress, target dates, contribution estimates and pause/completion controls; goals never debit or reserve money.
- **Durable agents:** persistent queue, event deduplication, atomic leases, bounded retries/crash recovery, tool scopes, decision summaries and run visibility. Agents propose; financial mutations remain governed.
- **Assistant:** balance/spend/budget/affordability/policy tools, Claude/OpenAI loops, exact citations and consent-required payment proposals.
- **Identity:** bounded ID/selfie uploads, evidence hashes, synthetic screening, transparent risk reasons and analyst review; optional model vision assists evidence quality without asserting legal identity or liveness.
- **Document intelligence:** searchable PDF/text/Markdown/CSV upload, tenant isolation, grounded answers, exact source passages and preview.
- **Recommendations:** loan and term-life rule explanations, eligible/blocked states and precise EMI calculations. No real credit or insurance is issued.
- **Security:** statistical/amount/velocity/new-recipient signals, synthetic device/VPN/geo history, calculated impossible-travel checks, customer alerts, transfer holds and analyst cases.
- **Analyst operations:** approve/reject with reasons, atomic balance rechecks, freeze/unfreeze, audit evidence, integration checks and explicitly confirmed shared-policy publication.
- **Deployment safeguards:** expiring authenticated sessions, CSRF/origin checks, upload bounds, append-only ledger/audit guards, migrations, production configuration refusal, secure analyst provisioning and CI workflow.

## Demo journey

1. Sign in as the customer; open Financial health to see the background agent's review and run trace.
2. Create a savings goal and confirm that your balance does not change.
3. Ask the assistant about spending, loan eligibility or a policy; inspect executed tools/citations.
4. Upload a document or sample KYC evidence from [examples](examples/README.md).
5. Send a routine payment; a larger new-recipient payment asks for password re-authentication.
6. Simulate impossible travel and a large payment in Security; funds are held before settlement.
7. Sign in as the analyst, inspect the case and approve/reject it with a reason.
8. Open Integrations, check configured AI access, and publish an approved shared bank policy for customer Q&A.

## Test and inspect

Verified: **111 backend tests, 11 HTTP security checks and 14 browser journeys**. Browser journeys passed with SQLite and with the final Docker/PostgreSQL stack. View [Financial health](docs/images/financial-health.png) and [Integrations](docs/images/integrations.png) screenshots.


```bash
make check
backend/.venv/bin/python -m unittest discover -s tests/acceptance -v
# With a fresh disposable demo API/web instance running:
npm run test:e2e --prefix frontend
```

The cloud image supplies Chromium. Elsewhere install a Playwright browser with `cd frontend` then `npx playwright install chromium`.

Browser journeys change banking/security state and require a fresh synthetic database. Retained suspicious events correctly change later risk decisions; do not disable those safeguards to force a repeat test to pass. CI starts from an empty database. See [validation](docs/VALIDATION.md) for executed outcomes and limitations.

## What remains for live financial use

The self-contained mock workflow is implemented. Real payment/bank APIs, authoritative KYC/liveness/sanctions, real bureau reports, attested device/GeoIP and enrolled production MFA remain separate provider integrations. They require provider accounts, protocols, consent, reconciliation, operational monitoring and regulatory review. An LLM key cannot provide these services.

Local retrieval is lexical rather than learned vector embeddings. Scanned-PDF OCR, multilingual voice and regulatory reporting are future extensions. Savings-goal progress is manually tracked rather than reserved funds. HTTPS, backups/restore drills, privacy/retention controls and real provider validation must be configured for an actual production deployment.

Read [implementation status](docs/IMPLEMENTATION_STATUS.md) for the full delivered/remaining matrix, [operations](docs/OPERATIONS.md) for setup/deployment, [architecture](docs/ARCHITECTURE.md) for trust boundaries, and [API contract](docs/API_CONTRACT.md) for endpoints.

```text
backend/       API, persistence, providers, scoped tools, risk rules and tests
frontend/      Customer/analyst web application with self-hosted fonts
tests/         Independent HTTP security and browser acceptance
scripts/       Locked setup, local startup, validation and Docker build helpers
examples/      Synthetic identity and policy upload samples
docs/          Requirements, implementation status, contracts and evidence
```
