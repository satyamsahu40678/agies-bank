#!/usr/bin/env bash
# Run once as a project owner or an administrator with IAM/API provisioning access.
# This script never prints secrets and does not change a billing account.
set -euo pipefail
project="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
region="${CLOUD_RUN_REGION:-us-central1}"
deployer="${DEPLOYER_SERVICE_ACCOUNT:?Set DEPLOYER_SERVICE_ACCOUNT to the account that will deploy}"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com firebasehosting.googleapis.com firebaserules.googleapis.com cloudbilling.googleapis.com --project "$project"
if [[ "$(gcloud billing projects describe "$project" --format='value(billingEnabled)')" != True ]]; then
  printf 'Link a billing account / enable Firebase Blaze for %s, then rerun.\n' "$project" >&2; exit 2
fi
for name in agies-runtime agies-build agies-scheduler; do
  account="${name}@${project}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "$account" --project "$project" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$name" --display-name "$name" --project "$project"
  fi
  gcloud iam service-accounts add-iam-policy-binding "$account" --project "$project" --member="serviceAccount:${deployer}" --role=roles/iam.serviceAccountUser --quiet >/dev/null
done
for role in roles/datastore.user roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$project" --member="serviceAccount:agies-runtime@${project}.iam.gserviceaccount.com" --role="$role" --condition=None --quiet >/dev/null
done
for role in roles/artifactregistry.writer roles/logging.logWriter roles/storage.objectViewer roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$project" --member="serviceAccount:agies-build@${project}.iam.gserviceaccount.com" --role="$role" --condition=None --quiet >/dev/null
done
for role in roles/run.admin roles/cloudbuild.builds.editor roles/artifactregistry.admin roles/storage.admin roles/cloudscheduler.admin roles/firebase.admin roles/secretmanager.viewer roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$project" --member="serviceAccount:${deployer}" --role="$role" --condition=None --quiet >/dev/null
done
if ! gcloud firestore databases describe --database='(default)' --project "$project" >/dev/null 2>&1; then
  gcloud firestore databases create --database='(default)' --location=nam5 --type=firestore-native --project "$project"
fi
if ! gcloud secrets describe AGIES_SECRET --project "$project" >/dev/null 2>&1; then
  gcloud secrets create AGIES_SECRET --replication-policy=automatic --project "$project"
  python3 -c 'import secrets; print(secrets.token_hex(32), end="")' | gcloud secrets versions add AGIES_SECRET --data-file=- --project "$project" >/dev/null
fi
printf 'Cloud identities and services configured. Ensure AGIES_SECRET has an enabled version. Optional OPENROUTER_API_KEY belongs in Secret Manager.\n'
