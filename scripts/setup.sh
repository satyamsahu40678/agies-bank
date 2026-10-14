#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/aegis-uv-cache}"
export npm_config_cache="${npm_config_cache:-/tmp/aegis-npm-cache}"
cd "$repo_dir/backend"
if [[ ! -x .venv/bin/python ]]; then uv venv --python python3 .venv; fi
uv pip sync --python .venv/bin/python --require-hashes requirements.lock
cd "$repo_dir/frontend"
npm ci --no-audit --no-fund
printf 'Dependencies installed. Run make dev from %s.\n' "$repo_dir"
