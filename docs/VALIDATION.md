# Verification evidence

This revision was verified with synthetic records and local provider mode.
The authoritative-storage tests use the actual official Firestore emulator,
not a SQL database disguised as Firestore.

| Check | Executed outcome |
| --- | --- |
| Complete backend suite, explicit memory adapter | 147 passed |
| Complete backend suite, actual Firestore emulator | 147 passed |
| Independent real-HTTP security acceptance on Firestore emulator | 11 passed |
| Production Next.js build and TypeScript validation | Passed, including Automations and analyst Operations |
| Chromium browser journeys against production Next.js + Firestore emulator | 16 passed, including mobile navigation, schedules, ledger results, KYC, document citations and analyst controls |
| Fresh installation of the production-only hash lock | Passed; complete app imports and configuration validates without SQLAlchemy installed |
| Runtime Python dependency audit | No known vulnerabilities reported |
| npm dependency audit | 0 vulnerabilities reported |
| New datastore/workflow source lint, Python/JSON syntax, shell syntax and whitespace | Passed |
| SQLite export → native Firestore domain → schema initialization → ledger reconciliation | Passed against the emulator, with the source hash unchanged |
| Live Google Cloud credential and project read | Authenticated to `agies-bank`; default Firestore database exists |
| Live public rollout and hosted smoke check | Pending external API/IAM/Secret Manager prerequisites; no verified public URL yet |
| Docker image builds / Compose execution | Not run here: no Docker engine available |
| Live model inference | Not run; provider protocols and scope boundaries are mocked |

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

Live IAM, billing, enabled secret versions, Cloud Build image creation, Firebase
cookie forwarding and Cloud Scheduler invocation still require a real rollout.
The deployment script includes those checks and a hosted demo smoke test. This
file records local/emulator evidence separately from that external work.
