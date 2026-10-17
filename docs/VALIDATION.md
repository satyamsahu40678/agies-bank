# Verification evidence

Verification uses synthetic records, local provider fixtures and live provider configuration. Hosted checks use the actual Firebase URL.
The authoritative-storage tests use the actual official Firestore emulator,
not a SQL database disguised as Firestore.

## Gemini provider switch — 2026-10-17

The API and durable worker/schema jobs were reconfigured to select Gemini and
pin `gemini-3.1-flash-lite`, using the enabled latest `GEMINI_API_KEY` secret version.
The deleted OpenRouter key binding was removed from those resources. Existing
Firestore records and sessions were preserved.

- Provider and integration tests: **68 passed**, including native Gemini 3.1 Flash-Lite
  function calling with an opaque thought signature preserved for continuation
  and excluded from the client response. Shell syntax and whitespace checks passed.
- Hosted `/login`, customer/analyst sign-in, authenticated sessions and logout:
  HTTP 200. The analyst Gemini check also returned HTTP 200, `status=ok` and
  `model=gemini-3.1-flash-lite`.
- Hosted balance chat: HTTP 200, effective `ai_mode=gemini`,
  scoped `get_balance` tool invoked, answer present and no local fallback.
- Hosted document query: HTTP 200, effective `ai_mode=gemini`, a nonempty
  grounded answer and three allowed source citations.
- Historical OpenRouter observations below describe the earlier release; they
  are not the current hosted provider selection.

| Check | Executed outcome |
| --- | --- |
| Complete backend suite, explicit memory adapter | 171 passed |
| Complete backend suite, actual Firestore emulator | 171 passed |
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
| GitHub CI for application commit `2373f97` on `main` | Passed: [run 39004983557](https://github.com/satyamsahu40678/agies-bank/actions/runs/39004983557), including all 16 browser journeys |
| Cloud Scheduler → authenticated Cloud Run job → due workflow | Passed: document readiness review completed with scoped tools; test schedule paused afterward |
| Hosted browser coverage | 15 distinct journeys covered across the initial and focused runs: the original 12 passed, followed by corrected financial-review, shared-policy and assistant-consent journeys |
| Cloud Build API and web Docker images | Both built and deployed successfully |
| Local Docker Compose execution | Not run: no local Docker engine available |
| Live assistant and model inference | Passed in 42.5 seconds: native OpenRouter balance and policy answers (3 citations); INR100 proposal used a disclosed local fallback; balance unchanged before consent; explicit confirmation returned a risk-controlled hold |
| Main automatic deployment | Passed end to end: [run 39005230735](https://github.com/satyamsahu40678/agies-bank/actions/runs/39005230735). Exact-source gate, keyless authentication, both images, schema check, services/jobs, Firebase publication and hosted smoke checks succeeded; official hash-verified actionlint also passed |
| Final hosted ledger and operations | 3 accounts reconcile; global balance total 0 paise; no mismatches/invalid entries; 27 completed jobs, 0 queued/running/failed jobs and 0 expired leases |
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

Native OpenRouter tool-call fixtures confirm that validated transfer proposals use server-authored consent text, ignore false model settlement claims and stale source references, and leave balances/ledger entries unchanged. Availability tests cover rate limits, outages, timeouts and the 40-second tool-loop budget; responses disclose scoped local fallback. Credential/configuration failures still reject. Invalid model citations, answers lacking required fresh tool results, malformed/empty completions, wrapped provider rejections and exhausted native tool loops are discarded before a labelled local answer uses fresh authorized tools. Continuation tests retain the selected free model, never request an unexpected paid ID, and prove opaque provider state is absent from persisted chat and client responses.

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
mode. The queued-review, shared-policy and final assistant focused checks passed. The final assistant run exercised genuine OpenRouter balance/policy inference and a clearly labelled local proposal fallback; confirmation respected the existing fraud evidence and held the transfer. That evidence was preserved.


## Final hosted release

Verified on 2026-10-17 at 05:20 UTC (10:50 IST):

- Application source: `2373f97917c7401f06ff51a3f21ff882ecb5009b` on `main`. API and web images both carry that source SHA and `source-branch=main`.
- Firebase release: `sites/agies-bank/releases/1792214312484000`, message `main@2373f97917c7401f06ff51a3f21ff882ecb5009b`, published 05:18:32 UTC. Hosting forwards to the ready web Run service.
- API revision `aegis-api-00010-8bg`; web revision `aegis-web-00006-rh7`; worker and schema-check jobs use the same application source.
- Scheduler is enabled and its last checked invocation succeeded. Latest `AGIES_SECRET` and `OPENROUTER_API_KEY` versions are enabled; no values are recorded here.
- Same-origin customer/analyst smoke checks passed after rollout. Reconciliation, role boundaries and session revocation passed; the public URL is https://agies-bank.web.app.

The release evidence update changes documentation only. Subsequent ordinary
main pushes use the same verified automatic CI/CD pipeline. The hosted data is
synthetic; the unavailable historical 99-row SQLite file has not been imported.
