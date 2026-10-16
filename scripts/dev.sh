#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export npm_config_cache="${npm_config_cache:-/tmp/aegis-npm-cache}"
export API_INTERNAL_URL="${API_INTERNAL_URL:-http://127.0.0.1:${API_PORT:-8000}}"
export AEGIS_STORAGE_BACKEND="${AEGIS_STORAGE_BACKEND:-memory}"
mkdir -p "$repo_dir/logs"
python3 - "${API_PORT:-8000}" "${WEB_PORT:-3000}" <<'PY'
import socket, sys
for raw in sys.argv[1:]:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', int(raw)))
        except OSError:
            raise SystemExit(f'Port {raw} is already in use. Inspect the existing service before starting AegisBank.')
PY
api_pid=''
web_pid=''
cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$web_pid" ]]; then kill -- "-$web_pid" 2>/dev/null || true; fi
  if [[ -n "$api_pid" ]]; then kill -- "-$api_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM
cd "$repo_dir/backend"
setsid .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${API_PORT:-8000}" > "$repo_dir/logs/api.log" 2>&1 &
api_pid=$!
cd "$repo_dir/frontend"
setsid env -u ANTHROPIC_API_KEY -u AEGIS_OPENAI_API_KEY -u OPENAI_API_KEY -u OPENROUTER_API_KEY -u GEMINI_API_KEY -u GOOGLE_API_KEY -u AGIES_SECRET -u GOOGLE_APPLICATION_CREDENTIALS npm run dev -- --hostname 0.0.0.0 --port "${WEB_PORT:-3000}" > "$repo_dir/logs/web.log" 2>&1 &
web_pid=$!
python3 "$repo_dir/scripts/wait_ready.py" "http://127.0.0.1:${API_PORT:-8000}/api/health" "http://127.0.0.1:${WEB_PORT:-3000}/login"
kill -0 "$api_pid" "$web_pid"
printf 'AegisBank API and web app are running. Logs: %s/logs. Ctrl-C stops both services.\n' "$repo_dir"
wait -n "$api_pid" "$web_pid"
