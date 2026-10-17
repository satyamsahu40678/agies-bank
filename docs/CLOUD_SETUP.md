# Firestore, Cloud Run and Firebase Hosting

The application runtime is Firestore-only. Accounts, sessions, ledger entries,
transfers, beneficiaries, documents, audit evidence, goals, agent jobs and schedules
are Firestore documents. SQLAlchemy/Alembic are isolated legacy import tools and
are absent from the production dependency lock. No Cloud SQL instance or
`DATABASE_URL` is required to deploy the application.

The deployment branch is `main`. The intended public entry
point is Firebase Hosting, which forwards to the Next.js Cloud Run service.
Next.js proxies `/api` to the API Cloud Run service. The `__session` HttpOnly,
Secure cookie survives Firebase Hosting forwarding. Direct client access to
Firestore is denied; server code uses its runtime service identity.

## Live deployment

The synthetic demo is hosted at [agies-bank.web.app](https://agies-bank.web.app).
The deployment branch is `main`; its merge contains the complete tested
Firestore migration. Cloud Build built the API and web images, Cloud Run hosts
them, and Firebase Hosting forwards the public HTTPS requests to the web service.

Owner setup completed for project `agies-bank`: the required APIs and distinct
runtime/build/scheduler identities are configured. Current deployment defaults
select `gemini` and pin `GEMINI_MODEL=gemini-3.8-flash`. Keep enabled latest
versions of `AGIES_SECRET` and `GEMINI_API_KEY` in Secret Manager, readable by
the runtime identity. The API and both durable jobs receive the same provider,
model and secret bindings. Removed secrets are omitted on the next deployment.
Earlier OpenRouter inference and its rate-limit fallback were verified before
the provider switch; that historical evidence does not validate Gemini.
Protocol and citation validation remain enforced. Executed outcomes are in
VALIDATION.md.

The `(default)` Firestore Native database is in `nam5`. Schema version 2 was
initialized on the previously empty target, and demo startup created synthetic
records. The historical 99-row SQLite file mentioned in the earlier migration
report is not in Git or among the supplied files and has not been imported.
Do not import historical records over the seeded demo. Use an isolated target
and the offline cutover procedure below for that source.

The finite `aegis-worker` job is deployed in `us-central1`, and
`aegis-agent-tick` invokes it every five minutes with the scheduler identity.
See [validation](VALIDATION.md) for the executed hosted checks and their limits.

## One-time project setup

Run this in Google Cloud Shell as the project owner or an administrator who can
enable APIs, create service accounts and grant IAM roles. This is required by
Google Cloud's actual permission checks, not an application confirmation flow.
The setup script does not attach a billing account; enable Firebase Blaze/link
billing first if needed. Cloud Run requires a billing association even when
usage stays within free allowances.

```bash
export GOOGLE_CLOUD_PROJECT=agies-bank
export DEPLOYER_SERVICE_ACCOUNT=firebase-adminsdk-fbsvc@agies-bank.iam.gserviceaccount.com
bash scripts/bootstrap-google.sh
```

This enables the required services and creates three separate identities:

| Identity | Purpose and permissions |
| --- | --- |
| `agies-runtime` | API/jobs: Datastore User, Secret Manager Secret Accessor |
| `agies-build` | Build containers: Artifact Registry Writer, Logs Writer, Storage Object Viewer, Service Usage Consumer |
| `agies-scheduler` | Invoke the worker job; Run Invoker is granted on that job during deployment |
| Deployment account | Deploy Run services/jobs, submit builds, stage source, manage the artifact repository and scheduler, publish Firebase, inspect secret metadata, and act as the three identities |

The bootstrap script contains the exact IAM grants. It preserves existing
`AGIES_SECRET` values. If that resource already exists without a usable version,
add a strong random value as a new enabled version through Secret Manager.
Never put credentials in source code or paste replacement values into chat.

For OpenRouter, create an enabled Secret Manager secret named
`OPENROUTER_API_KEY`. The deployment binds existing enabled provider secrets;
without a provider key the app uses its functional local assistant. The default
OpenRouter model is `openrouter/free`. Availability and support for tools are
provider-dependent; OpenRouter is not used for KYC image review.

## Deploy a runnable synthetic demo

Use a clean Firestore target for the demo. Authenticate `gcloud` and the Firebase
CLI with an authorized account or ADC; keys stay outside the checkout.

```bash
export GOOGLE_CLOUD_PROJECT=agies-bank
export DEPLOY_MODE=demo
bash scripts/deploy-google.sh
```

The script checks prerequisites before any build or database write, builds the
API image, runs a read-only schema compatibility check, deploys the
API and web services with explicit container ports, deploys a finite worker job,
creates a five-minute Cloud Scheduler trigger, publishes Hosting/rules/index
configuration, and checks the hosted app. The demo smoke check verifies secure
cookies, authenticated APIs, role boundaries and logout through Firebase.
It prints a verified public URL only after those checks pass.

For the **first rollout to an empty, offline target**, set
`INITIALIZE_SCHEMA=true` explicitly. This initializes uniqueness reservations and
reconciles the source before schema version 2 is written. The option refuses an
existing API service. Ordinary updates and automatic CI/CD keep this option
false and never reinitialize live application data.

`DEPLOY_MODE=demo` enables intentionally public synthetic customer/analyst demo
accounts while keeping HTTPS cookies and a strong secret mandatory. Use
`DEPLOY_MODE=production` for a clean workspace without seed users or simulator;
startup refuses known demo identities in that mode. Financial providers remain
synthetic in both modes. Limits default to two instances per service and zero
minimum instances. Build, storage, Firestore, Scheduler and Cloud Run usage can
still incur charges. No cost-free deployment is promised.

## Import the existing SQLite database and cut over

Do this with both old and new writers stopped. Preserve an offline backup and
its WAL-consistent source. The importer opens SQLite read-only, uses source row
IDs as document IDs, skips identical documents and uses create preconditions to
refuse both existing conflicts and racing inserts. Interrupted collection batches
can be resumed; this is not one transaction across the entire database.

```bash
cd backend
# The developer lock contains the legacy importer dependencies.
.venv/bin/python -m app.firestore_migration --source /private/path/aegis.db
GOOGLE_CLOUD_PROJECT=agies-bank .venv/bin/python -m app.firestore_migration \
  --source /private/path/aegis.db --apply --project agies-bank
```

After import, the CLI validates required fields, references, uniqueness and
ledger reconciliation, reserves unique values, and writes schema version 2.
It never edits the SQLite source. Existing application documents are preserved.
Do not enable writers after a partial import or failed reconciliation. If the
source contains demo identities, select demo mode; production intentionally
rejects those identities. Keep the old database and backup until the migrated
application and records have been verified. Do not import into an already seeded
demo unless its records are intentionally the source of truth.

The equivalent schema/reconciliation commands are:

```bash
.venv/bin/python -m app.manage migrate
.venv/bin/python -m app.manage reconcile
```

Schema initialization/import is an offline maintenance operation with writers
stopped. Ordinary compatible application deployments read the schema marker and
can run without that offline initialization. The script does not silently stop
writers, repair balances or overwrite financial data. `app.manage verify-schema`
is the equivalent read-only compatibility command.

## Durable workers and CI

An API background task wakes manual review requests after their response.
Cloud Scheduler invokes the finite worker job with an OAuth service identity,
so due schedules and expired leases recover even when the API scales to zero.
Each schedule advancement and queued job are committed atomically. Jobs use
per-customer exclusion, fencing tokens and bounded retries; their outputs cannot
move money or approve identity. `AEGIS_WORKER_ENABLED=false` disables the local
polling thread in hosted services.

`.github/workflows/ci.yml` runs both the isolated backend suite and the complete
suite against the actual Firestore emulator, builds Next.js, and runs independent
HTTP and browser journeys. `.github/workflows/deploy.yml` automatically deploys
the exact current `main` commit after successful push CI, and supports verified
manual dispatch. The project owner runs `scripts/bootstrap-github-actions.sh`
once to establish keyless identity. Workflow defaults already contain this
project's nonsecret provider/account IDs; `GCP_WORKLOAD_IDENTITY_PROVIDER` and
`GCP_DEPLOY_SERVICE_ACCOUNT` variables are optional overrides. The federation
condition pins repository/owner numeric IDs, main and the deployment workflow.
No JSON key is committed. Pull requests and other branches do not deploy. See
[CI/CD](CICD.md) for setup, trigger behavior and recovery.

## Verify and remove the prototype

Use `/api/health`, the analyst Operations page, `app.manage reconcile`, Cloud Run
job execution logs and the hosted smoke script. Emulator success does not prove
live IAM, billing, inference or the public gateway. For cleanup, pause/delete
`aegis-agent-tick`, remove the worker/migration jobs and Run services, delete
unneeded image versions and disable Hosting. Preserve or export data before
removing the database; no cleanup script automatically deletes bank records.

Official behavior references: [Firebase cookies](https://firebase.google.com/docs/hosting/manage-cache#using_cookies),
[Firestore transactions](https://firebase.google.com/docs/firestore/manage-data/transactions),
[Hosting and Cloud Run](https://firebase.google.com/docs/hosting/cloud-run).
