#!/usr/bin/env bash
# Run once as a project owner. No service-account key or secret value is created.
set -euo pipefail
project="${GOOGLE_CLOUD_PROJECT:-agies-bank}"
deployer="${DEPLOYER_SERVICE_ACCOUNT:-firebase-adminsdk-fbsvc@${project}.iam.gserviceaccount.com}"
pool=agies-github
provider=github-main
repository_id=1417723532
owner_id=94219315
workflow='satyamsahu40678/agies-bank/.github/workflows/deploy.yml@refs/heads/main'
gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com --project "$project"
project_number="$(gcloud projects describe "$project" --format='value(projectNumber)')"
if ! gcloud iam workload-identity-pools describe "$pool" --location=global --project "$project" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$pool" --location=global --project "$project" --display-name='Agies GitHub main deployments'
fi
mapping='google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref,attribute.workflow_ref=assertion.workflow_ref'
condition="assertion.repository_id=='${repository_id}' && assertion.repository_owner_id=='${owner_id}' && assertion.ref=='refs/heads/main' && assertion.workflow_ref=='${workflow}'"
provider_args=(--location=global --project "$project" --workload-identity-pool "$pool" --issuer-uri=https://token.actions.githubusercontent.com --attribute-mapping "$mapping" --attribute-condition "$condition")
if gcloud iam workload-identity-pools providers describe "$provider" --location=global --project "$project" --workload-identity-pool "$pool" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers update-oidc "$provider" "${provider_args[@]}"
else
  gcloud iam workload-identity-pools providers create-oidc "$provider" "${provider_args[@]}"
fi
gcloud iam service-accounts add-iam-policy-binding "$deployer" --project "$project" --role=roles/iam.workloadIdentityUser --member="principalSet://iam.googleapis.com/projects/${project_number}/locations/global/workloadIdentityPools/${pool}/attribute.repository_id/${repository_id}" --quiet >/dev/null
printf 'Keyless main deployment identity configured.\nProvider: projects/%s/locations/global/workloadIdentityPools/%s/providers/%s\nService account: %s\n' "$project_number" "$pool" "$provider" "$deployer"
