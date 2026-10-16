#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
jar="${FIRESTORE_EMULATOR_JAR:-${TMPDIR:-/tmp}/aegis-firestore-emulator-1.19.8.jar}"
if [[ ! -f "$jar" ]]; then
  curl -fsSL https://storage.googleapis.com/firebase-preview-drop/emulator/cloud-firestore-emulator-v1.19.8.jar -o "$jar"
fi
printf '%s  %s\n' 9d43599ed6151199e8d604dc87fac51218e49e5f3a48519b1ae560bbe5e3382d "$jar" | sha256sum --check --status
mkdir -p logs
java -jar "$jar" --host=127.0.0.1 --port=8085 > logs/firestore-emulator.log 2>&1 &
firestore_pid=$!
trap 'kill "$firestore_pid" 2>/dev/null || true' EXIT
backend/.venv/bin/python - <<'PY'
import time, urllib.request
for _ in range(100):
    try:
        urllib.request.urlopen('http://127.0.0.1:8085', timeout=1)
        break
    except Exception: time.sleep(.1)
else: raise SystemExit('Firestore emulator failed to start; check logs/firestore-emulator.log')
PY
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 AEGIS_TEST_FIRESTORE=true AEGIS_STORAGE_BACKEND=memory
if [[ $# == 0 ]]; then set -- backend/tests; fi
backend/.venv/bin/python -m pytest "$@" -q
