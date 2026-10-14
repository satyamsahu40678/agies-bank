#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export AEGIS_ENV=test AEGIS_DEMO_ENABLED=true AEGIS_AI_PROVIDER=local AEGIS_AI_MODE=local AEGIS_KYC_VISION=local
cd "$repo_dir/backend"
.venv/bin/python -m pytest -q
cd "$repo_dir/frontend"
npm run build
printf 'API integration checks and frontend production build passed.\n'
