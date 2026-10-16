# Saved cloud configuration

The cloud draft contains these tested fields:

- `install_script`: change directory to `/workspace/agies-bank` and run `bash scripts/setup.sh`, installing hash-verified Python and npm-lock dependencies.
- `start_skill`: use the existing isolated checkout, inspect occupied ports, start `bash scripts/dev.sh`, verify health and authenticated banking responses, preserve retained data and respect supplied configuration. The repository's current startup instructions cover local mode, optional Claude/OpenAI capabilities, durable financial-health jobs and operational limitations.

The machine supports the synthetic development workflow. A saved draft does not execute installation, activate runtime settings, publish a snapshot or prove restoration in a new task. Repository documentation edits do not themselves update platform draft fields. Review and save the current draft in environment settings, then publish the environment when ready.

No required secret or network change was needed for local mode. For optional Claude, supply `ANTHROPIC_API_KEY` securely and allow `api.anthropic.com`; for OpenAI, supply `AEGIS_OPENAI_API_KEY` and allow `api.openai.com`. The root `.env` is ignored by Git and read through a variable allowlist without shell execution. Existing injected variables take precedence. Use the `AEGIS_OPENAI_API_KEY` binding in Codex cloud settings; `OPENAI_API_KEY` is a local alias and can be a reserved platform target.

With `AEGIS_AI_PROVIDER=auto`, the first configured key is selected in this order: Claude, OpenAI, OpenRouter, then Gemini. Select `claude`, `openai`, `openrouter`, `gemini` or `local` explicitly when required. OpenRouter supports assistant tool use and document answers, defaults to `openrouter/free`, and is not used for KYC vision. `AEGIS_KYC_VISION` independently controls optional evidence-quality assistance for Claude, OpenAI or Gemini. Restart the backend after configuration changes. Provider credentials also need account permissions, accessible models, credits and working network access. Model-access checks in the analyst Integrations page do not send customer data or validate paid inference. Never enter credentials in chat or source control.

Only the implemented AI adapters are key-ready. Bank settlement, legal identity/liveness, sanctions, bureau, GeoIP/device attestation and production MFA still need provider-specific integrations. An AI key does not activate those services. Model vision can assess submitted evidence quality; it cannot prove document authenticity or legal identity.

Development startup creates local tables; production requires an explicit migration job to the current Alembic head, including `0002_proactive`. Agent runs and planning goals are database records and survive API restarts. The worker restarts with the API and can recover expired leases; it does not move funds or approve identity. Saved goal progress is manually recorded planning data, never earmarked money.

Running processes and Docker containers must restart after restoration. Each cloud task is isolated; use the existing checkout rather than creating a Git worktree.

## Google Cloud prototype deployment

Optional server-side model credentials can be stored as Secret Manager secrets named `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `AEGIS_OPENAI_API_KEY` and/or `OPENROUTER_API_KEY`; the deployment script passes existing secrets to the API service. Never commit these values or send them in chat.

The repository includes `scripts/deploy-google.sh` and `firebase.json`. Firebase Hosting serves the stable public HTTPS/CDN origin and rewrites to the Next.js service on Cloud Run. Cloud Run hosts the API and web containers. Cloud SQL PostgreSQL remains the financial source of truth; Firestore is an optional projection of derived customer agent alerts only. The API uses the Cloud Run metadata server identity for Firestore, and `firestore.rules` denies direct browser/client access.

Before running the script, provision a Cloud SQL PostgreSQL instance, a Firestore Native database, Secret Manager secrets `DATABASE_URL` and `AGIES_SECRET`, and a dedicated runtime service account. Grant the runtime account Cloud SQL Client, Secret Manager Secret Accessor and Datastore User. Add the Gemini key as a Secret Manager secret named `GEMINI_API_KEY` to activate Gemini in automatic mode. `DATABASE_URL` must use the Cloud SQL Unix socket, for example `postgresql+psycopg://USER:PASSWORD@/DATABASE?host=/cloudsql/PROJECT:REGION:INSTANCE`. Create the Firebase project/site and authenticate `firebase` CLI in Cloud Shell. Then set `GOOGLE_CLOUD_PROJECT`, `CLOUD_RUN_REGION`, `CLOUD_SQL_INSTANCE` and `CLOUD_RUN_SERVICE_ACCOUNT` and run `bash scripts/deploy-google.sh`.

The deployment script enables the required Google APIs, builds both images using `cloudbuild.api.yaml` and `cloudbuild.web.yaml`, runs the Alembic migration job, deploys the services, and applies Firebase Hosting and Firestore rules. It does not create Cloud SQL or Secret Manager values and has not been executed from this workspace. A reachable prototype URL is only produced after a successful authorized deployment. Rotate any service-account key that has been exposed; Cloud Shell ADC and Cloud Run service identities are the supported credential path, not a JSON file.

## Firestore migration status

The full Firestore-primary migration is not complete. The running API still uses SQLAlchemy and requires a relational database, so do not deploy it as Firestore-only or remove the SQLite source. The first migration phase provides a read-only dry run and a resumable SQLite-to-Firestore importer; imported documents keep their SQL table name as the collection, row ID as the document ID and foreign-key IDs as fields. Existing identical documents are skipped and conflicts are never overwritten. This importer does not switch the application runtime to Firestore.

From `backend/`, inspect the existing database without Google credentials:

```bash
python -m app.firestore_migration
```

Only after the Firestore schema and remaining backend workflows are fully migrated and emulator-tested should an operator run the import with ADC and the required Firestore IAM role:

```bash
GOOGLE_CLOUD_PROJECT=agies-bank python -m app.firestore_migration --apply
```

The SQLite file is opened read-only. Import is resumable but writes collections in batches, so an interrupted import may leave a partial Firestore copy; rerun it to continue, and keep the SQL-backed application authoritative until the full migration and verification are complete. Do not pass service-account key values in chat or commit them.
