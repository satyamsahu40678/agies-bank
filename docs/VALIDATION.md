# Verification evidence

Verification uses synthetic records, local provider fixtures and the live OpenRouter configuration. Hosted checks use the actual Firebase URL.
The authoritative-storage tests use the actual official Firestore emulator,
not a SQL database disguised as Firestore.

| Check | Executed outcome |
| --- | --- |
| Complete backend suite, explicit memory adapter | 166 passed |
| Complete backend suite, actual Firestore emulator | 166 passed |
| Independent real-HTTP security acceptance on Firestore emulator | 11 passed |
| Production Next.js build and TypeScript validation | Passed, including Automations and analyst Operations |
| Chromium browser journeys against production Next.js + Firestore emulator | 16 passed, including mobile navigation, schedules, ledger results, KYC, document citations and analyst controls |
| Hosted-worker behavior regression on production Next.js | Savings and financial-review journeys passed with the polling worker disabled; a queued review can be woken manually |
| Fresh installation of the production-only hash lock | Passed; complete app imports and configuration validates without SQLAlchemy installed |
| Runtime Python dependency audit | No known vulnerabilities reported |
| npm dependency audit | 0 vulnerabilities reported |
| New datastore/workflow source lint, Python/JSON syntax, shell syntax and whitespace | Passed |
| SQLite export → native Firestore domain → schema initialization → ledger reconciliation | Passed against the emulator, with the source hash unchanged |
| Live Google Cloud credential and project read | Authenticated to `agies-bank`; default Firestore database exists |
| Live public rollout and hosted smoke check | Passed at https://agies-bank.web.app: Firestore health, secure cookie forwarding, customer APIs, role isolation and logout |
| GitHub CI for Firestore/CD base `1e7f847` on `main` | Passed: [run 39003298928](https://github.com/satyamsahu40678/agies-bank/actions/runs/39003298928), including all 16 browser journeys |
| Cloud Scheduler → authenticated Cloud Run job → due workflow | Passed: document readiness review completed with scoped tools; test schedule paused afterward |
| Hosted browser coverage | Initial suite: 12 passed. Focused financial-review and shared-policy journeys passed after correction; final assistant continuation retest follows the current rollout |
| Cloud Build API and web Docker images | Both built and deployed successfully |
| Local Docker Compose execution | Not run: no local Docker engine available |
| Live model inference | Real balance and grounded policy responses passed. Runtime diagnostics reproduced the free router switching models mid-tool-loop and an upstream HTTP400; continuations now stay on the first selected free model |
| Main deployment workflow validation | Official hash-verified actionlint passed; first automatic release passed exact-source and keyless Google-authentication gates and started Cloud Build |
| Routine rollout schema gate | Compatible schema verified without writes; absent/older/future markers rejected in memory and native Firestore tests |

One existing Starlette/httpx deprecation warning remains. The isolated developer
venv initially carried stale dependency metadata; a fresh production-lock
installation passed its dependency compatibility check. That installation also
proved the live application does not need a relational package or engine.

## Correctness exercised

Payments conserve customer/clearing balances, write matching ledger entries,
reject invalid minor-unit amounts and overdrafts, deduplicate concurrent requests,
recheck balances during analyst approval, and preserve held state on failure.
Authentication covers hashing, expiry, revocation, CSRF, role checks and tenant
isolation. The canonical cookie is `__session`, matching Firebase Hosting's
forwarding behavior.

Firestore tests cover stale writes, query phantoms, unique reservations,
append-only ledger/audit enforcement, required references, signed integer fields,
goal date round trips, schema initialization, and complete financial totals beyond
history sampling caps. Legacy rows are read through the new domain repository
and reconcile after import; the SQLite bytes remain unchanged.

Native OpenRouter tool-call fixtures confirm that validated transfer proposals use server-authored consent text, ignore false model settlement claims and stale source references, and leave balances/ledger entries unchanged. Availability tests cover rate limits, outages, timeouts and the 40-second tool-loop budget; responses disclose scoped local fallback. Credential/configuration failures and invalid citations still reject. Continuation tests retain the selected free model, never request an unexpected paid ID, and prove opaque provider state is absent from persisted chat and client responses.

Worker tests cover atomic event outbox creation, competing claims and schedule
dispatchers, per-customer exclusion, crash/lease recovery, fencing old workers,
rollback of failed output, retry bounds and unchanged balances. Specialized
reviews cannot replace the financial-health summary. Paused schedules do not
dispatch and foreign schedule IDs are inaccessible.

The browser run found an initial-render race on Refresh insights: an enabled
server-rendered button could be clicked before its handler was hydrated. It is
now disabled until the initial insight and job resources load. Provider UI checks
were updated to the current four-provider interface. All sixteen final journeys
passed after these corrections.

## Repeat the checks

```bash
make setup
make check
make test-firestore
backend/.venv/bin/python -m unittest discover -s tests/acceptance -v
# Start a fresh disposable demo API/web stack before browser tests:
npm run test:e2e --prefix frontend
```

The emulator script starts an official hash-verified jar and isolates each test's
project. It never uses the attached live credential. HTTP/browser runs must start
with a fresh synthetic fixture because they intentionally create fraud evidence
and change demo state. Existing risk evidence must not be removed to force an
unsafe repeat payment to pass.

Live IAM, enabled secret bindings, Cloud Build image creation, Firebase cookie
forwarding and authenticated Scheduler invocation were verified during the
Google Cloud rollout. The target was empty before initialization, so this is a
fresh synthetic demo rather than an import of the unavailable historical SQLite
file. The public gateway and scoped balance inference passed. The initial hosted
browser run also exposed conditions that the local polling-worker fixture did
not reproduce. CI now disables that worker for browser tests, matching hosted
mode. The queued-review and shared-policy focused hosted checks passed. Final assistant and automatic release results will be recorded after the current main rollout.
