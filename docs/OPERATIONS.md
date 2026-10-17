# Running and operating AegisBank

## Quick local demo

```bash
make setup
make dev
```

Python dependencies are hash-locked; npm uses its committed lock. `make dev` and
`python scripts/run-local.py --setup --open` explicitly default to ephemeral
in-memory storage. Restarting that mode resets the demo. Use Docker Compose's
persistent Firestore emulator, a manually started emulator, or a configured live
Firestore development project when data must survive restarts.

```bash
docker compose up --build -d
```

Compose starts a Firestore emulator plus API and Next.js. Only web port 3000 is
bound to host loopback; emulator and API ports remain internal. Emulator exports
are retained in `firestore_data`. `docker compose down` preserves the volume;
`down -v` removes it. The first emulator start downloads Java/Firebase tooling.
Docker requires a local Docker engine; native tests do not substitute for a
container build.

## Configuration

| Setting | Behavior |
| --- | --- |
| `AEGIS_STORAGE_BACKEND` | `firestore` (runtime default) or explicit `memory` for development/tests |
| `GOOGLE_CLOUD_PROJECT` | Required for Firestore |
| `FIRESTORE_DATABASE` | Defaults to `(default)` |
| `FIRESTORE_EMULATOR_HOST` | Local host:port only; forbidden in hosted mode |
| `AEGIS_ENV` | `development`, `test`, `demo`, `production` |
| `AEGIS_DEMO_ENABLED` | Synthetic identities and simulator; forbidden in production |
| `AGIES_SECRET` | Canonical application secret; at least 32 characters in hosted mode |
| `AEGIS_ALLOWED_ORIGINS` | Explicit allowed origins; HTTPS only in hosted mode |
| `AEGIS_AI_PROVIDER` | `auto`, `local`, `openrouter`, `gemini`, `openai`, `claude` |
| `GEMINI_API_KEY` | Backend-only Secret Manager binding; required for hosted Gemini |
| `GEMINI_MODEL` | Hosted default `gemini-3.1-flash-lite`; applies to chat, documents and assisted image review |
| `OPENROUTER_API_KEY` | Optional backend-only key; default model `openrouter/free` |
| `AEGIS_WORKER_ENABLED` | Enables development polling; false in hosted services |

The root `.env` is ignored by Git and loaded through an allowlist without shell
execution. Injected environment values win. A live local Firestore process can
use ADC or `GOOGLE_APPLICATION_CREDENTIALS` pointing outside the checkout.
Cloud Run uses its service identity and should never carry a JSON key file.
Provider keys must not reach the browser environment or source archives.

OpenRouter availability failures and unusable model output use disclosed local
scoped answers. Rejected model content is discarded; credential/configuration
errors remain operator-visible errors. `/chat` and `/documents/query`
report the effective `ai_mode` and optional `fallback_from`. Catalog connection
checks are separate from inference. See API_CONTRACT.md for the response shape.

## Schema, import and reconciliation

The runtime needs no relational engine. The production image deliberately
excludes SQLAlchemy, Alembic and PostgreSQL drivers. Legacy tools are installed
with `backend/requirements-dev.lock` and only run explicitly. Preserve any old
SQLite source and follow [cloud setup](CLOUD_SETUP.md) for read-only import and
offline cutover. Never run the importer while application writers are active.

With Firestore configured and writers stopped:

```bash
cd backend
.venv/bin/python -m app.manage migrate
.venv/bin/python -m app.manage reconcile
```

Initialization validates references, constraints and unique values, checks every
account against its posted ledger and requires global double-entry conservation.
It backfills unique reservations without overwriting bank documents, then writes
schema version 2. Hosted startup requires this marker. Reconciliation reports
mismatches; it never repairs a balance automatically.

An ordinary compatible release runs `python -m app.manage verify-schema`, a
read-only marker check. It does not rerun offline initialization. The deployment
script defaults to `INITIALIZE_SCHEMA=false`; the true option is for an initial
empty target and refuses an existing API service.

Create a non-demo analyst with `python -m app.manage create-analyst --email ...
--name ...`; the command prompts for a strong password and only stores its hash.
A public registration request cannot assign the analyst role or an opening
balance.

## Agent operations

Jobs, schedules, retry state, insights and decision summaries are durable
Firestore records. `python -m app.manage worker --max-jobs 50` dispatches due
schedules and drains a bounded queue. Cloud Scheduler executes this as a finite
Cloud Run job every five minutes. Manual review endpoints also wake a bounded
background task. A crash leaves a leased job recoverable; an expired fencing
token cannot commit its output. Automatic attempts stop after three by default;
customers may request up to three explicit retry cycles for a failed review.

The customer Automations page controls six review types, including Cash-flow
analyst and Expense detective. Their calculations do not call a model; customer
AI explanations use the configured provider quota. Pausing a schedule
prevents future dispatches; a job already queued continues. Removing a schedule
does not erase its prior run or audit history. The analyst Operations page shows
reconciliation, job counts and expired leases. Operational checks themselves do
not move funds.

Banking education summaries are release-versioned in `services/knowledge.py`.
Review the official links and update their review date with content changes; no
runtime scraper or Firestore seed job is needed. No new secret or schema migration
is required for the contextual AI expansion. See [AI workspace](AI_WORKSPACE.md).

## Validation

```bash
make check
make test-firestore
backend/.venv/bin/python -m unittest discover -s tests/acceptance -v
# With a fresh disposable API and web process running:
npm run test:e2e --prefix frontend
```

The Firestore test script starts a hash-verified official emulator and runs the
same complete suite against it. Fixture projects are isolated; it never contacts
a live Firestore database. Browser tests intentionally alter demo risk state and
require a fresh fixture. Keep known risk checks enabled rather than clearing
suspicious evidence to make a rerun pass. See [validation](VALIDATION.md) for the
checks actually executed in this revision.

## Hosted operations and recovery

Use `scripts/bootstrap-google.sh` for owner provisioning and
`scripts/deploy-google.sh` for the reviewed Firestore deployment. The latter
checks prerequisites before builds, binds Secret Manager values, schedules the
worker and verifies the public gateway. It does not create an authorized billing
association or grant its own missing IAM privileges. Use a maintenance window
with writers stopped for schema initialization or historical cutover. Routine
compatible releases preserve the current data and use the read-only schema gate.

Pushes to `main` are checked and automatically released by the workflow in
`.github/workflows/deploy.yml`. The owner must first establish the GitHub
federation trust using `scripts/bootstrap-github-actions.sh`. Long-lived cloud
keys and model tokens are not GitHub secrets. See [CI/CD](CICD.md) for the
owner command, verified commit selection, phase separation and rerun procedure.

Configure Firestore exports/PITR as appropriate, test restoration to an isolated
target, preserve a separately protected audit archive, and monitor Cloud Run
errors, worker failures, Scheduler invocations, Firestore contention and cost.
The repository does not claim that backups or monitoring have been provisioned.
Rotate credentials through the provider and Secret Manager; do not log their
values. Build contexts exclude credentials, `.env`, databases and conversation
attachments.
