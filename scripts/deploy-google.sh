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
secret_bindings="$(IFS=,; printf '%s' "${api_secrets[*]}")"
origins="https://${project}.web.app,https://${project}.firebaseapp.com"
demo_enabled=false
if [[ "$deploy_mode" == demo ]]; then demo_enabled=true; fi
api_environment="^@^AEGIS_ENV=${deploy_mode}@AEGIS_DEMO_ENABLED=${demo_enabled}@AEGIS_STORAGE_BACKEND=firestore@AEGIS_AI_PROVIDER=auto@AEGIS_KYC_VISION=auto@AEGIS_ALLOWED_ORIGINS=${origins}@GOOGLE_CLOUD_PROJECT=${project}@FIRESTORE_DATABASE=(default)@AEGIS_WORKER_ENABLED=false@FIRESTORE_AGENT_NOTIFICATIONS=false"
gcloud builds submit --project "$project" --config cloudbuild.api.yaml --service-account "projects/${project}/serviceAccounts/${build_account}" --substitutions="_IMAGE=${api_image}" .
job_args=(--image "$api_image" --region "$region" --project "$project" --service-account "$runtime_account" --set-secrets "$secret_bindings" --set-env-vars "$api_environment" --memory 1Gi --cpu 1 --tasks 1 --parallelism 1 --max-retries 1 --task-timeout 300s)
# No SQL instance, DATABASE_URL or Alembic is required by either job or service.
gcloud run jobs deploy aegis-migrate "${job_args[@]}" --command python --args=-m,app.manage,migrate --quiet
gcloud run jobs execute aegis-migrate --region "$region" --project "$project" --wait
# This schema step validates all existing records and reserves unique values.
# Import historical SQLite separately, with writers stopped, BEFORE this rollout.
gcloud run deploy aegis-api --image "$api_image" --region "$region" --project "$project" --service-account "$runtime_account" --allow-unauthenticated --port 8000 --set-env-vars "$api_environment" --set-secrets "$secret_bindings" --min-instances 0 --max-instances 2 --concurrency 10 --memory 1Gi --cpu 1 --timeout 120 --quiet
api_url="$(gcloud run services describe aegis-api --region "$region" --project "$project" --format='value(status.url)')"
python3 scripts/wait_ready.py "${api_url}/api/health"
gcloud builds submit --project "$project" --config cloudbuild.web.yaml --service-account "projects/${project}/serviceAccounts/${build_account}" --substitutions="_API_INTERNAL_URL=${api_url},_IMAGE=${web_image}" .
gcloud run deploy aegis-web --image "$web_image" --region "$region" --project "$project" --service-account "$runtime_account" --allow-unauthenticated --port 3000 --set-env-vars "API_INTERNAL_URL=${api_url}" --min-instances 0 --max-instances 2 --concurrency 20 --memory 512Mi --cpu 1 --timeout 120 --quiet
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
firebase deploy --only hosting,firestore:rules,firestore:indexes --project "$project" --non-interactive
gcloud run jobs execute aegis-worker --region "$region" --project "$project" --wait
python3 scripts/wait_ready.py "https://${project}.web.app/api/health" "https://${project}.web.app/login"
if [[ "$deploy_mode" == demo ]]; then
  python3 scripts/smoke-deployment.py "https://${project}.web.app"
fi
printf 'Deployment verified: https://%s.web.app\n' "$project"
