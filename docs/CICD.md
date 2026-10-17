# Automatic deployment from main

The live project's keyless trust connection and automatic release have been
verified end to end; no additional setup is needed for normal pushes to this
repository. The owner setup commands below document reproduction/recovery.

The deployment source is `main`. Pushes to `main` start **Application checks**.
After that workflow succeeds, **Deploy Firestore application** automatically
builds and deploys the exact passing commit. Pull requests and other branches
run checks without deployment. No `develop` branch promotion is configured.

## One-time owner trust setup

The workflow uses GitHub OpenID Connect and Google Workload Identity Federation
to impersonate the existing authorized deployment service account. Google
provides short-lived credentials; no service-account JSON or model key is stored
in GitHub. The workflow includes this project's nonsecret provider/account IDs;
repository/environment variables may override them when intentionally moving
the deployment.

Hosted releases default to `AEGIS_AI_PROVIDER=gemini` and
`GEMINI_MODEL=gemini-3.1-flash-lite`. These optional nonsecret Actions variables can
override the selection. `GEMINI_API_KEY` stays in Secret Manager; its latest
version must be enabled and readable by `agies-runtime`. The script checks the
selected Gemini secret before building and replaces the API/job secret bindings,
so a removed OpenRouter key is not retained in new revisions. Adding or rotating
a secret requires a new deployment for environment-injected values to reload.
`OPENROUTER_MODEL` remains available when deliberately selecting OpenRouter.

Run once in Google Cloud Shell as the project owner:

```bash
curl -fsSL https://raw.githubusercontent.com/satyamsahu40678/agies-bank/main/scripts/bootstrap-github-actions.sh -o /tmp/agies-github-setup.sh
bash /tmp/agies-github-setup.sh
```

Review [the script](../scripts/bootstrap-github-actions.sh) before running it.
It enables IAM/STS APIs, creates/updates pool `agies-github` and provider
`github-main`, and grants `roles/iam.workloadIdentityUser` on the deployment
account to repository ID `1417723532`. Its condition also requires owner ID
`94219315`, `refs/heads/main` and this repository's `deploy.yml` workflow path.
It creates no key, reads no secret value and does not grant general project
administration to all GitHub workflows. The initial owner project bootstrap has
already given the deployment account its application deployment permissions.

During implementation, the supplied deployment identity's IAM permission check
showed that it could not create federation resources or change service-account
IAM. After owner trust setup, automatic releases completed Cloud Build, schema
verification, Run updates, Firebase publication and hosted smoke checks. The
application release for `2373f97` passed in
[run 39005230735](https://github.com/satyamsahu40678/agies-bank/actions/runs/39005230735).
Executed results are recorded in [validation](VALIDATION.md).

## Release sequence

1. CI installs locked dependencies, runs the complete backend suite in memory and
   on the actual Firestore emulator, builds Next.js, runs independent HTTP
   security checks and dependency audits, and completes browser journeys.
2. The deployment workflow accepts successful **push** runs from this repository
   on `main`. It independently confirms successful CI for the exact source SHA.
3. If that SHA is no longer the current `main` head, the older release is skipped.
   Deployments are serialized; an active release is allowed to finish.
4. Keyless authentication supplies the cloud identity. Cloud Build produces
   API/web images tagged with the full source SHA; Run resources receive source
   branch/commit labels.
5. The schema job runs `verify-schema`, which reads the schema marker only.
   Incompatible schema stops delivery. CI/CD does not import SQLite, initialize
   existing data or change ledger balances.
6. Cloud Run updates API/web, the finite worker and Scheduler. Identity is
   refreshed before Firebase publication to avoid reusing an expired OIDC token.
7. Firebase Hosting/rules/indexes are published and same-origin smoke checks
   verify Firestore health, secure sessions, APIs, workflow catalog, roles and
   logout. GitHub's `google-cloud` deployment links to the public application.

The services and publication phases are `DEPLOY_PHASE=services` and
`DEPLOY_PHASE=publish`. The local script's default `all` runs both. Automatic
deployment always uses demo mode and `INITIALIZE_SCHEMA=false`. Manual
`workflow_dispatch` also requires successful CI for the exact current `main`
commit; production mode requires a clean database and explicit operator setup.

## Day-to-day use and recovery

```bash
git switch main
# Edit and commit your application changes.
git push origin main
```

Watch [Actions](https://github.com/satyamsahu40678/agies-bank/actions). A failed
application check prevents the deployment job. Fix and push again. If cloud
identity setup or a transient build/deploy step fails after CI passed, fix that
cause and use **Re-run failed jobs** on the deployment workflow. No additional
commit is required. A newer `main` head still prevents an older run from being
released; let its own checks/deployment run instead.

An incompatible schema needs a separate maintenance window with writers stopped,
offline migration and reconciliation, then another routine deployment. Never
enable `INITIALIZE_SCHEMA=true` for automatic releases. Use a first rollout to
an empty target or the [documented maintenance procedure](CLOUD_SETUP.md).

Failed CI leaves the current app running. A failed deployment can have updated
some services before the failure; this pipeline does not promise automatic
cross-service rollback. Inspect Run revisions and restore compatible previous
traffic/image versions if necessary. Keep the Firestore data intact. Staging,
canary releases and automated rollback are [future work](ROADMAP.md).

Reference protocols: [GitHub workflow_run](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run),
[GitHub OIDC claims](https://docs.github.com/en/actions/reference/security/oidc),
and [Google pipeline federation](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines).
