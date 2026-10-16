#!/usr/bin/env bash
set -euo pipefail
project="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
failed=0
enabled_services="$(gcloud services list --enabled --project "$project" --format='value(config.name)' 2>/dev/null || true)"
for api in run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com firebasehosting.googleapis.com firebaserules.googleapis.com; do
  if [[ $'\n'"${enabled_services}"$'\n' != *$'\n'"${api}"$'\n'* ]]; then
    printf 'BLOCKED: enable %s in project %s.\n' "$api" "$project" >&2
    failed=1
  fi
done
if [[ "$(gcloud secrets versions describe latest --secret=AGIES_SECRET --project="$project" --format='value(state)' 2>/dev/null || true)" != ENABLED ]]; then
  printf 'BLOCKED: AGIES_SECRET needs an enabled latest version and permission to describe its metadata.\n' >&2
  failed=1
fi
if ! gcloud firestore databases describe --database='(default)' --project="$project" >/dev/null 2>&1; then
  printf 'BLOCKED: create the (default) Firestore Native database.\n' >&2; failed=1
fi
for account in "${CLOUD_RUN_SERVICE_ACCOUNT:-agies-runtime@${project}.iam.gserviceaccount.com}" "${CLOUD_BUILD_SERVICE_ACCOUNT:-agies-build@${project}.iam.gserviceaccount.com}" "${CLOUD_SCHEDULER_SERVICE_ACCOUNT:-agies-scheduler@${project}.iam.gserviceaccount.com}"; do
  if ! gcloud iam service-accounts describe "$account" --project "$project" >/dev/null 2>&1; then
    printf 'BLOCKED: service account is missing or inaccessible: %s\n' "$account" >&2; failed=1
  fi
done
if [[ "$failed" == 1 ]]; then
  printf 'Run scripts/bootstrap-google.sh as a project owner; see docs/CLOUD_SETUP.md. No build or rollout was attempted.\n' >&2
  exit 2
fi
printf 'Deployment prerequisites verified; runtime secret access and build permissions are checked by the jobs.\n'
