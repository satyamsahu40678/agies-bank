#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
region="${CLOUD_RUN_REGION:-us-central1}"
service_account="${CLOUD_RUN_SERVICE_ACCOUNT:-}"
cloud_sql_instance="${CLOUD_SQL_INSTANCE:-}"
revision="${DEPLOY_REVISION:-$(git -C "$repo_dir" rev-parse --short HEAD)}"

if [[ -z "$project" || -z "$service_account" || -z "$cloud_sql_instance" ]]; then
  printf 'Set GOOGLE_CLOUD_PROJECT, CLOUD_RUN_SERVICE_ACCOUNT and CLOUD_SQL_INSTANCE first.\n' >&2
  exit 2
fi

registry="${region}-docker.pkg.dev/${project}/aegis"
api_image="${registry}/aegis-api:${revision}"
web_image="${registry}/aegis-web:${revision}"

cd "$repo_dir"
gcloud config set project "$project" >/dev/null
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  sqladmin.googleapis.com firestore.googleapis.com secretmanager.googleapis.com \
  --project "$project"

if ! gcloud artifacts repositories describe aegis --location "$region" >/dev/null 2>&1; then
  gcloud artifacts repositories create aegis \
    --repository-format=docker --location="$region" --project="$project"
fi

gcloud builds submit --project "$project" \
  --config cloudbuild.api.yaml \
  --substitutions="_IMAGE=${api_image}" .

common_job_args=(
  --image "$api_image"
  --region "$region"
  --project "$project"
  --service-account "$service_account"
  --set-secrets DATABASE_URL=DATABASE_URL:latest,AGIES_SECRET=AGIES_SECRET:latest
  --set-env-vars "AEGIS_ENV=production,AEGIS_DEMO_ENABLED=false,AEGIS_ALLOWED_ORIGINS=https://${project}.web.app,GOOGLE_CLOUD_PROJECT=${project}"
  --add-cloudsql-instances "$cloud_sql_instance"
)
gcloud run jobs deploy aegis-migrate "${common_job_args[@]}" \
  --command python --args=-m,app.manage,migrate
gcloud run jobs execute aegis-migrate --region "$region" --project "$project" --wait

if ! gcloud firestore databases describe --database='(default)' --project "$project" >/dev/null 2>&1; then
  gcloud firestore databases create \
    --database='(default)' --location="$region" --type=firestore-native \
    --project="$project"
fi

api_secrets=(DATABASE_URL=DATABASE_URL:latest AGIES_SECRET=AGIES_SECRET:latest)
for optional_secret in GEMINI_API_KEY ANTHROPIC_API_KEY AEGIS_OPENAI_API_KEY OPENROUTER_API_KEY; do
  if gcloud secrets describe "$optional_secret" --project "$project" >/dev/null 2>&1; then
    api_secrets+=("${optional_secret}=${optional_secret}:latest")
  fi
done

firebase_origin="https://${project}.web.app,https://${project}.firebaseapp.com"
gcloud run deploy aegis-api \
  --image "$api_image" \
  --region "$region" \
  --project "$project" \
  --service-account "$service_account" \
  --allow-unauthenticated \
  --add-cloudsql-instances "$cloud_sql_instance" \
  --set-env-vars "^@^AEGIS_ENV=production@AEGIS_DEMO_ENABLED=false@AEGIS_AI_PROVIDER=auto@AEGIS_KYC_VISION=auto@AEGIS_ALLOWED_ORIGINS=${firebase_origin}@GOOGLE_CLOUD_PROJECT=${project}@FIRESTORE_DATABASE=(default)@FIRESTORE_AGENT_NOTIFICATIONS=true" \
  --set-secrets "$(IFS=,; printf '%s' "${api_secrets[*]}")"

api_url="$(gcloud run services describe aegis-api --region "$region" --project "$project" --format='value(status.url)')"
gcloud builds submit --project "$project" \
  --config cloudbuild.web.yaml \
  --substitutions="_API_INTERNAL_URL=${api_url},_IMAGE=${web_image}" .
gcloud run deploy aegis-web \
  --image "$web_image" \
  --region "$region" \
  --project "$project" \
  --service-account "$service_account" \
  --allow-unauthenticated \
  --set-env-vars "API_INTERNAL_URL=${api_url}"

firebase deploy --only hosting,firestore:rules --project "$project"
printf 'Deployment complete. Firebase Hosting: https://%s.web.app\n' "$project"