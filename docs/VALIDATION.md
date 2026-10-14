# Validation evidence

The implemented scope is in REQUIREMENTS.md. The uploaded deck was available; the linked conversation could not be retrieved. The user authorized implementation decisions based on the available material.

## Executed checks

| Check | Outcome | Evidence and scope |
| --- | --- | --- |
| Backend suite | 111 passed | `backend/.venv/bin/python -m pytest backend/tests -q`: auth, sessions, roles, ledger conservation, atomic settlement, risk/geo events, KYC, documents, agent tools, recommendations, analyst actions, immutable evidence and production guards; Claude/OpenAI protocol handling, model discovery, complete financial aggregation, integration disclosures, shared policy publication and proactive workflows |
| Independent HTTP security | 11 passed | `backend/.venv/bin/python -m unittest discover -s tests/acceptance -v`: starts a real API process on an isolated SQLite database, checks CSRF, tenant boundaries, upload limits, role injection, four concurrent identical payments, concurrent analyst approvals, logout replay and step-up risk escalation |
| Browser journeys | 14 passed | Real Chromium against built Next.js/FastAPI containers with PostgreSQL on a fresh disposable synthetic database. Customer payments; new beneficiary and step-up; document upload/citations; registration and KYC; repayment calculator; fraud hold and analyst rejection; assistant tools/citations/payment consent; budgets and analyst freeze/unfreeze/audit; mobile layout; goal create/edit/complete/delete without balance changes; completed run tools/trace/decisions and dismissal; public-sharing consent, customer policy citations and source preview; both provider checks; mobile Financial health/Integrations navigation |
| Production frontend | Passed | TypeScript validation and Next.js production builds completed, including standalone assets and self-hosted fonts |
| Production web launcher | Passed | Frontend startup helper served login, all referenced JS/CSS assets and API proxy requests; forwards shutdown signals |
| Docker API/web builds | Passed | Both images built with locked dependencies; cloud proxy routing and supplied CA secret preserved TLS/checksum verification |
| PostgreSQL | Passed | PostgreSQL17 migrations, authenticated requests, double-entry settlement and idempotency; current `0002_proactive` schema head; all three Compose services reported healthy on the disposable validation stack |
| Proactive workflows | 24 passed | `backend/.venv/bin/pytest backend/tests/test_proactive.py -q`: scoped goals and insights, HTTP auth/role/CSRF and tenant isolation, background completion, dismissal, event deduplication, concurrent claims, lease recovery, rollback, bounded retries and interruptible shutdown; complete cash-flow/budget totals verified with 10,000 additional ledger entries |
| PostgreSQL durable workers | Passed | Repeated migrations reach `0002_proactive`; Alembic metadata comparison has no differences. Four concurrent independent clients claim only one run for one customer. An expired lease recovers on attempt two; the old token is rejected. Concurrent workers complete jobs, three injected failures terminate within the retry bound, and an explicit retry succeeds. All 14 seeded ledger entries and all account balances remain unchanged |
| Schema/immutability | Passed | SQLite migration repeated successfully; PostgreSQL migration verified; backend regression suite exercises append-only ledger/audit guards |
| Python dependency audit | Passed | pip-audit checked the complete pinned lock: no known vulnerabilities reported |
| Frontend dependency audit | Passed | npm audit reported zero known vulnerabilities after patched Next/React and transitive dependency updates |
| Installation repeatability | Passed | `bash scripts/setup.sh` synced hash-pinned Python dependencies and ran npm ci successfully |
| Cross-platform local launcher | Passed on Linux | `python3 scripts/run-local.py --setup` installed locked dependencies, started alternate ports with explicit origins, served web-proxied login/overview/insights/logout, and stopped both service groups on SIGTERM. Invalid/equal ports and mismatched explicit origins produce actionable errors. Windows/macOS execution was not performed |
| Native cloud startup | Passed | `bash scripts/dev.sh` reached database/web readiness; authenticated clean demo overview had INR225,480.50, three source documents and three loan recommendations; logout worked |
| Startup collision | Passed | Launcher refused occupied ports and preserved the running app instead of reporting another server as its newly started process |
| Repository hygiene | Passed | git diff --check; credentials, databases, dependencies, build outputs, reports and logs ignored; no pre-existing application files overwritten |

Native development startup has been verified. Prior generated SQLite test state is preserved under ignored `backend/data/onboarding-test-backup`; disposable PostgreSQL test data is retained in its Docker volume. Runtime availability should be checked through health and an authenticated request; live processes are not assumed to survive cloud publication/restoration.

Browser journeys deliberately change banking and security state and require a fresh synthetic database. CI starts with an empty database. Retained suspicious events correctly change later risk decisions; a password challenge must not override them merely to make a repeat test pass.

## Diagnosed failures and limits

- Security review found a step-up escalation bypass. The API now reassesses current risk before settlement and creates a held analyst case when new high risk appears; independent HTTP and backend regression checks pass.
- Production startup now refuses public demo identities in an existing database without deleting records. Registration reserves the demo domain when demo is disabled. Clean production initialization is covered by tests.
- Package audits initially identified vulnerable Next.js/transitive versions; patched versions were installed and audits passed.
- Browser CDN downloads were blocked by network policy. The installed Debian Chromium was used successfully; no verification checks were disabled.
- Initial container builders lacked proxy DNS/CA routing. The build helper uses the configured proxy and ephemeral CA mount; final images built successfully with TLS and hash checks intact.
- PostgreSQL browser validation exposed a test timing assumption: the first payment assertion could read history before its POST finished. The test now waits for the settlement response, checks posted status and verifies the exact balance change.
- One Starlette TestClient/httpx deprecation warning remains in the test suite. It is not a failing test and does not affect the production API or provider HTTP client.
- Claude and OpenAI assistant/tool, cited-document and KYC-vision adapters are implemented. Provider protocol tests use mocks for denied tools, malformed responses, context minimization, citation bounds and model discovery. No live AI key was supplied, so model-access checks, paid inference, current provider-account compatibility and real identity verification are not claimed as verified.
- Core-bank settlement, KYC/sanctions, bureau, GeoIP/device intelligence and password step-up are explicit synthetic adapters. Real providers, identity/liveness, payments, production MFA and regulated deployment controls require integration and operational review.
- Local retrieval uses lexical evidence ranking and exact citations, not production vector embeddings. Scanned-PDF OCR, voice/multilingual assistance and regulatory reporting are deck next steps, not implemented live provider capabilities.
- A fresh production database contains no sample shared policies. Private customer uploads work, and authenticated analysts can publish shared bank policies through Integrations after explicit public-sharing confirmation. Published text is Q&A evidence; it cannot change payment or lending authorization rules.
- Goals are manual planning records rather than reserved funds. Agent jobs make read-only proposals; tests verify that neither goals nor proactive reviews change balances or ledger entries. Financial totals use complete SQL aggregates, while recurring detection is explicitly limited to 10,000 entries over 120 days and represents estimates.
- GitHub CI workflow is provided; remote CI results and public deployment must be established separately. Cloud configuration drafts were saved; publication and restoration in a new task remain user/platform actions and were not validated here.

## Final delivery evidence (2026-10-14)

The current backend suite passed 111 tests and the isolated real-HTTP suite passed 11 tests. Fourteen browser journeys passed against the production Next.js output with SQLite; all fourteen also passed against the final Docker web/API images on a separately migrated PostgreSQL database. Docker API/web images and the native production frontend built successfully. Current pip-audit and npm audit reported no known vulnerabilities in the pinned dependencies.

Test results validate the implemented simulated banking scope. No live Claude/OpenAI credentials, authoritative identity provider, real settlement service, public hosting account or remote CI outcome was verified. Cross-platform launcher logic is provided; only Linux execution was tested. Local processes do not constitute a publicly deployed app.
