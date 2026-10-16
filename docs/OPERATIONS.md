# Running and deploying AegisBank

## Development

Run `make setup` once and after dependency changes, then `make dev`. The setup script uses a hash-pinned Python lock and npm lock; installation preserves TLS and artifact verification. Package caches use `/tmp` in the cloud sandbox. SQLite data defaults to `backend/data/aegis.db`. Do not delete that directory to troubleshoot a live instance; it contains accounts and audit history.

If a port is occupied, inspect its owner before starting another instance. Stop only services you started. Environment variables override backend behavior; their values are read at startup.

| Variable | Use |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL; SQLite by default, `postgresql+psycopg://...` for deployment |
| `AEGIS_ENV` | `development`, `test` or `production` |
| `AEGIS_DEMO_ENABLED` | Enables synthetic seeded credentials/data and event simulator; must be false in production |
| `AGIES_SECRET` | Strong instance secret; required in production |
| `AEGIS_ALLOWED_ORIGINS` | Comma-separated exact origins; explicit HTTPS origins in production |
| `AEGIS_AI_MODE` | Compatibility setting: `auto` (default), `local`, `claude`, `openai`, `gemini` or `openrouter` |
| `AEGIS_AI_PROVIDER` | Preferred provider: auto/local/claude/openai/gemini/openrouter; explicit local disables AI |
| `AEGIS_OPENAI_API_KEY` | Optional OpenAI key; secure backend-only binding |
| `AEGIS_OPENAI_MODEL` | Optional OpenAI model override; otherwise supported-model discovery |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Local aliases; use `AEGIS_OPENAI_API_KEY` for Codex cloud secret bindings |
| `ANTHROPIC_API_KEY` | Optional Claude credential, supplied securely; never checked into source |
| `ANTHROPIC_MODEL` | Supported Claude model ID |
| `GEMINI_API_KEY`, `GOOGLE_API_KEY` | Optional Gemini credential and local alias |
| `GEMINI_MODEL` | Optional Gemini model override; otherwise supported-model discovery |
| `OPENROUTER_API_KEY` | Optional OpenRouter key for chat/tool orchestration and document synthesis |
| `OPENROUTER_MODEL` | Optional OpenRouter model ID; defaults to `openrouter/free` |
| `AEGIS_KYC_VISION` | `auto`, `local`, `claude`, `openai` or `gemini`; optional image-quality assistance, not biometric identity proof |
| `API_INTERNAL_URL` | Next.js server proxy target; default backend on port 8000, set before Next build |

Configure AI keys through secure environment settings or the ignored root `.env`. Explicit injected environment variables take precedence over that file. `AEGIS_AI_PROVIDER` takes precedence over the compatibility `AEGIS_AI_MODE` setting; auto mode selects Claude, OpenAI, OpenRouter, then Gemini. OpenRouter supports assistant tools and grounded document answers, but is not used for identity evidence. Explicit `AEGIS_KYC_VISION` selects Claude, OpenAI or Gemini independently; its default auto mode follows those supported providers and otherwise stays local. Set vision to `local` when external processing of identity evidence should be disabled.

The Integrations page shows configured key presence and effective modes without revealing credentials. Its connection check reads provider model/catalog metadata without sending customer data or performing paid inference. Validate live assistant, source-grounded answers and optional vision separately after checking account permissions, credits and egress to the selected provider (`api.anthropic.com`, `api.openai.com`, `generativelanguage.googleapis.com` or `openrouter.ai`). OpenRouter route availability and free-model tool support may change. Public customer and analyst credentials apply only to demo mode. Password re-authentication is a demo substitute for enrolled MFA.

## Docker and PostgreSQL

Copy `.env.example` to `.env` and replace both random-secret placeholders with distinct output from:

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Never paste credentials into chat or commit `.env`. PostgreSQL passwords should be hex strings for this example so they need no URL escaping. Launch:

```bash
docker compose up --build -d
docker compose ps
docker compose logs --tail=80 api web
```

Only the web gateway is bound to host loopback; the database and API are internal services. The web image embeds its API proxy target at build time. Persistent PostgreSQL data is in the named `postgres_data` volume. `docker compose down` stops processes while preserving data; **do not use `down -v` on retained data**.

In a managed cloud with proxy-only egress, use `bash scripts/build-containers.sh` then `docker compose up -d`. It resolves the configured proxy hostname for the builder and mounts the supplied CA bundle as an ephemeral build secret. TLS checks and Python artifact hashes remain enabled. No proxy credential is printed or stored in the image. If Docker config paths are read-only, set `DOCKER_CONFIG=/tmp/aegis-docker-config` and `BUILDX_CONFIG=/tmp/aegis-buildx`.

## Production prerequisites

Set `AEGIS_ENV=production`, `AEGIS_DEMO_ENABLED=false`, a random `AGIES_SECRET`, a PostgreSQL URL and your explicit HTTPS origin in `AEGIS_ALLOWED_ORIGINS`. The API refuses insecure production defaults. Terminate TLS through a managed gateway or reverse proxy in front of the loopback web port. Preserve `Origin`, secure cookies and forwarding semantics. Do not expose raw database ports or trust arbitrary client IP headers.

The Compose file's defaults are a local demo, not a production deployment recipe with real banking providers. Provision an analyst securely using the backend admin CLI after migrations. Public self-registration creates only customers. Supply real integrations for identity, sanctions, bureau, payment settlement and MFA before any real financial operation. Review data retention, privacy requirements, key management, access revocation and operational controls for your jurisdiction.

Use one controlled schema-migration job before scaling API replicas; do not run parallel migrations across workers. The current head includes `0002_proactive` for agent runs, financial insights and savings goals. Production startup checks the database revision against the repository's current head and refuses an outdated schema. Record migration versions, perform migrations on a restored staging copy first, and back up before destructive migrations. Database-level audit access must be protected separately; append-only triggers do not prevent a privileged database owner from changing the guards.

Use a fresh production database: startup refuses a database containing public synthetic demo identities and preserves those records. Production registration reserves the demo email domain. Production does not seed sample policies; private customer uploads work, and analysts can publish shared policies in the Integrations screen after explicit public-sharing confirmation. Publish only approved information suitable for every customer. Shared policy text supplies Q&A evidence and does not change executable lending, payment or approval rules. Uploaded text is retained in the database, so include it in backup, retention and access reviews.

After setting production configuration, migrate and provision an analyst before API startup:

```bash
docker compose run --rm api python -m app.manage migrate
docker compose run --rm api python -m app.manage create-analyst --email analyst@your-domain.example --name 'Risk Analyst'
docker compose up -d
```

Analyst provisioning prompts for a strong password without echoing it. Automation can send a value from a secret manager on stdin with `--password-stdin`; do not put it in arguments or shell history.

## Backup, recovery and diagnostics

For PostgreSQL use a managed backup service or `pg_dump` from a secured admin session. Keep encrypted backups off the application host and test `pg_restore` to an isolated database. Do not echo passwords or full database URLs into CI logs. A backup is useful only after a restoration test.

For local SQLite, stop API processes before copying `backend/data` or use SQLite's online backup API. Preserve WAL consistency. Local demo data should never be used as a production starting balance.

Readiness requires `/api/health` to report a healthy database and an actual application request to work. Monitor API failures, settlement conflicts, held funds, open cases, model failures and request latency. Review decision summaries with their trace IDs; never collect raw passwords, session cookies, identity numbers, model secrets or hidden chain-of-thought. Live provider failures must fail visibly rather than fabricate a successful financial action.

Optional vision sends uploaded ID/selfie evidence to the selected AI provider; those files can contain personal information. Review customer consent, provider data handling, retention and network access before enabling it for real documents. Limited readability/name-consistency observations cannot authenticate documents, match faces, establish liveness or verify legal identity.

## Proactive agents and local AI configuration

The root `.env` is read by a supported-variable allowlist without shell execution; injected environment variables take precedence. Adding a Gemini, Anthropic or OpenAI key with auto mode selects that provider (Claude, OpenAI, then Gemini precedence). Restart the backend after changing keys/modes. API keys are never passed to browser code or returned by integration status. No paid live model request is claimed until tested with your supplied account.

A durable financial-health queue runs in the API lifecycle. Login and banking activity enqueue read-only tasks in their database transaction. Customer-scoped tools, event deduplication and atomically claimed leases govern execution; runs and outputs survive process restarts. PostgreSQL serializes work for one customer across API replicas. Expired leases recover, stale tokens cannot commit completion and failures roll back outputs. Automatic retries stop after three attempts; customers can request up to three explicit retry cycles from a failed run. An idle worker uses an interruptible wait rather than a busy loop.

For Google Cloud, deploy with `scripts/deploy-google.sh` after creating Cloud SQL, Firestore Native, Secret Manager secrets `DATABASE_URL` and `AGIES_SECRET`, and a dedicated Cloud Run service identity. Grant it Cloud SQL Client, Secret Manager Secret Accessor, and Datastore User. Store Gemini under `GEMINI_API_KEY` in Secret Manager to activate it automatically. Set `GOOGLE_CLOUD_PROJECT`, `FIRESTORE_DATABASE=(default)` and `FIRESTORE_AGENT_NOTIFICATIONS=true`; Firestore receives only derived insight notifications. The relational database remains authoritative. Firebase Hosting rewrites to the `aegis-web` Cloud Run service, and direct Firestore client access is denied by `firestore.rules`.

Inspect Financial health for queued/running/completed/failed runs, tool names, concise decisions and trace IDs. Long-lived queued jobs or expired running leases indicate worker/database trouble; check API lifecycle and database connectivity before retrying. Refresh coalesces pending work and creates a fresh run after prior work finishes. Financial totals and budget usage cover complete posted activity over 30 days. Recurring-charge forecasts examine at most 10,000 entries over 120 days and are estimates, not billing guarantees.

Savings goals record customer-entered targets, saved progress and deadlines. Monthly contribution suggestions use historical surplus across all active plans. They do not debit, reserve or hold funds, and do not prove the customer has segregated savings. The worker cannot settle transfers, alter budgets, approve identity, freeze accounts or release holds. PostgreSQL claims, crash recovery, bounded retries and unchanged financial balances were verified; SQLite remains the simple local path.

The Python launcher supports `--setup --open` and avoids external preview routing: it starts on your computer loopback, checks ports, preserves injected configuration and terminates its own service groups. Its Linux execution is tested; Windows/macOS require the stated Python/Node prerequisites and platform-specific execution verification.

For custom local ports, use `--api-port` and `--web-port`. If `.env` or the environment already defines `AEGIS_ALLOWED_ORIGINS`, include the selected `http://localhost:PORT` web origin there. The launcher preserves explicit origins and refuses a mismatch.
