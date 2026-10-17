#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
region="${CLOUD_RUN_REGION:-us-central1}"
runtime_account="${CLOUD_RUN_SERVICE_ACCOUNT:-agies-runtime@${project}.iam.gserviceaccount.com}"
build_account="${CLOUD_BUILD_SERVICE_ACCOUNT:-agies-build@${project}.iam.gserviceaccount.com}"
scheduler_account="${CLOUD_SCHEDULER_SERVICE_ACCOUNT:-agies-scheduler@${project}.iam.gserviceaccount.com}"
revision="${DEPLOY_REVISION:-$(git -C "$repo_dir" rev-parse --short HEAD)}"
deploy_mode="${DEPLOY_MODE:-demo}"
phase="${DEPLOY_PHASE:-all}"
initialize_schema="${INITIALIZE_SCHEMA:-false}"
ai_provider="${AEGIS_AI_PROVIDER:-gemini}"
gemini_model="${GEMINI_MODEL:-gemini-3.8-flash}"
case "$ai_provider" in
  auto|local|claude|openai|gemini|openrouter) ;;
  *) printf 'AEGIS_AI_PROVIDER must name a supported provider.\n' >&2; exit 2 ;;
esac
if [[ ! "$gemini_model" =~ ^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$ ]]; then
  printf 'GEMINI_MODEL must be a valid model ID.\n' >&2; exit 2
fi
openrouter_model="${OPENROUTER_MODEL:-openrouter/free}"
if [[ ! "$openrouter_model" =~ ^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$ ]]; then
  printf 'OPENROUTER_MODEL must be a valid model ID.\n' >&2; exit 2
fi
if [[ ! "$revision" =~ ^[a-f0-9]{7,40}$ ]]; then
  printf 'DEPLOY_REVISION must identify the source Git commit.\n' >&2; exit 2
fi
if [[ "$phase" != all && "$phase" != services && "$phase" != publish ]]; then
  printf 'DEPLOY_PHASE must be all, services or publish.\n' >&2; exit 2
fi
if [[ "$initialize_schema" != true && "$initialize_schema" != false ]]; then
  printf 'INITIALIZE_SCHEMA must be true or false.\n' >&2; exit 2
fi
if [[ "$region" != us-central1 ]]; then
  printf 'Update firebase.json rewrites before choosing a region other than us-central1.\n' >&2; exit 2
fi
if [[ "$deploy_mode" != demo && "$deploy_mode" != production ]]; then
  printf 'DEPLOY_MODE must be demo or production.\n' >&2; exit 2
fi
for executable in gcloud firebase python3 curl; do
  command -v "$executable" >/dev/null || { printf 'Missing executable: %s\n' "$executable" >&2; exit 2; }
done
cd "$repo_dir"
# Preflight happens before any build, rollout, or database write.
bash scripts/preflight-google.sh
publish_and_verify() {
  firebase deploy --only hosting,firestore:rules,firestore:indexes --project "$project" --message "main@${revision}" --non-interactive
  python3 scripts/wait_ready.py "https://${project}.web.app/api/health" "https://${project}.web.app/login"
  if [[ "$deploy_mode" == demo ]]; then
    python3 scripts/smoke-deployment.py "https://${project}.web.app"
  fi
  printf 'Deployment verified: https://%s.web.app\n' "$project"
}
if [[ "$phase" == publish ]]; then
  publish_and_verify
  exit 0
fi
if [[ "$initialize_schema" == true ]] && gcloud run services describe aegis-api --region "$region" --project "$project" >/dev/null 2>&1; then
  printf 'INITIALIZE_SCHEMA is only for a first offline rollout. For an existing service, stop writers and migrate separately, then deploy with INITIALIZE_SCHEMA=false.\n' >&2
  exit 2
fi
registry="${region}-docker.pkg.dev/${project}/aegis"
api_image="${registry}/aegis-api:${revision}"
web_image="${registry}/aegis-web:${revision}"
if ! gcloud artifacts repositories describe aegis --location "$region" --project "$project" >/dev/null 2>&1; then
  gcloud artifacts repositories create aegis --repository-format=docker --location="$region" --project="$project" --quiet
fi
api_secrets=(AGIES_SECRET=AGIES_SECRET:latest)
for secret in GEMINI_API_KEY ANTHROPIC_API_KEY AEGIS_OPENAI_API_KEY OPENROUTER_API_KEY; do
  if [[ "$(gcloud secrets versions describe latest --secret="$secret" --project="$project" --format='value(state)' 2>/dev/null || true)" == ENABLED ]]; then
    api_secrets+=("${secret}=${secret}:latest")
  fi
done
if [[ "$ai_provider" == gemini && ! " ${api_secrets[*]} " =~ " GEMINI_API_KEY=GEMINI_API_KEY:latest " ]]; then
  printf 'GEMINI_API_KEY needs an enabled latest Secret Manager version before a Gemini deployment.\n' >&2; exit 2
fi
secret_bindings="$(IFS=,; printf '%s' "${api_secrets[*]}")"
origins="https://${project}.web.app,https://${project}.firebaseapp.com"
demo_enabled=false
if [[ "$deploy_mode" == demo ]]; then demo_enabled=true; fi
api_environment="^@^AEGIS_ENV=${deploy_mode}@AEGIS_DEMO_ENABLED=${demo_enabled}@AEGIS_STORAGE_BACKEND=firestore@AEGIS_AI_PROVIDER=${ai_provider}@GEMINI_MODEL=${gemini_model}@OPENROUTER_MODEL=${openrouter_model}@AEGIS_KYC_VISION=auto@AEGIS_ALLOWED_ORIGINS=${origins}@GOOGLE_CLOUD_PROJECT=${project}@FIRESTORE_DATABASE=(default)@AEGIS_WORKER_ENABLED=false@FIRESTORE_AGENT_NOTIFICATIONS=false"
gcloud builds submit --polling-interval=5 --project "$project" --config cloudbuild.api.yaml --service-account "projects/${project}/serviceAccounts/${build_account}" --substitutions="_IMAGE=${api_image}" .
job_args=(--image "$api_image" --region "$region" --project "$project" --service-account "$runtime_account" --set-secrets "$secret_bindings" --set-env-vars "$api_environment" --labels "source-branch=main,source-commit=${revision}" --memory 1Gi --cpu 1 --tasks 1 --parallelism 1 --max-retries 1 --task-timeout 300s)
# No SQL instance, DATABASE_URL or Alembic is required by either job or service.
schema_action=verify-schema
if [[ "$initialize_schema" == true ]]; then schema_action=migrate; fi
gcloud run jobs deploy aegis-migrate "${job_args[@]}" --command python --args="-m,app.manage,${schema_action}" --quiet
gcloud run jobs execute aegis-migrate --region "$region" --project "$project" --wait
# Routine deployments only read the schema marker. Offline initialization and
# historical imports are explicit operator actions, never automatic CD writes.
gcloud run deploy aegis-api --image "$api_image" --region "$region" --project "$project" --service-account "$runtime_account" --allow-unauthenticated --port 8000 --set-env-vars "$api_environment" --set-secrets "$secret_bindings" --labels "source-branch=main,source-commit=${revision}" --min-instances 0 --max-instances 2 --concurrency 10 --memory 1Gi --cpu 1 --timeout 120 --quiet
api_url="$(gcloud run services describe aegis-api --region "$region" --project "$project" --format='value(status.url)')"
python3 scripts/wait_ready.py "${api_url}/api/health"
gcloud builds submit --polling-interval=5 --project "$project" --config cloudbuild.web.yaml --service-account "projects/${project}/serviceAccounts/${build_account}" --substitutions="_API_INTERNAL_URL=${api_url},_IMAGE=${web_image}" .
gcloud run deploy aegis-web --image "$web_image" --region "$region" --project "$project" --service-account "$runtime_account" --allow-unauthenticated --port 3000 --set-env-vars "API_INTERNAL_URL=${api_url}" --labels "source-branch=main,source-commit=${revision}" --min-instances 0 --max-instances 2 --concurrency 20 --memory 512Mi --cpu 1 --timeout 120 --quiet
web_url="$(gcloud run services describe aegis-web --region "$region" --project "$project" --format='value(status.url)')"
gcloud run services update aegis-api --project "$project" --region "$region" --update-env-vars "^@^AEGIS_ALLOWED_ORIGINS=${origins},${web_url}" --quiet
gcloud run jobs deploy aegis-worker "${job_args[@]}" --command python --args=-m,app.manage,worker,--max-jobs,50 --quiet
gcloud run jobs add-iam-policy-binding aegis-worker --region "$region" --project "$project" --member="serviceAccount:${scheduler_account}" --role=roles/run.invoker --quiet >/dev/null
scheduler_args=(--project "$project" --location "$region" --schedule '*/5 * * * *' --time-zone UTC --uri "https://run.googleapis.com/v2/projects/${project}/locations/${region}/jobs/aegis-worker:run" --http-method POST --oauth-service-account-email "$scheduler_account" --oauth-token-scope https://www.googleapis.com/auth/cloud-platform --attempt-deadline 180s --max-retry-attempts 2)
if gcloud scheduler jobs describe aegis-agent-tick --project "$project" --location "$region" >/dev/null 2>&1; then
  gcloud scheduler jobs update http aegis-agent-tick "${scheduler_args[@]}" --quiet
else
  gcloud scheduler jobs create http aegis-agent-tick "${scheduler_args[@]}" --quiet
fi
gcloud run jobs execute aegis-worker --region "$region" --project "$project" --wait
if [[ "$phase" == all ]]; then
  publish_and_verify
else
  printf 'Cloud services verified for main@%s; publish phase is next.\n' "$revision"
fi
