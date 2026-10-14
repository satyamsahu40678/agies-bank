#!/usr/bin/env bash
# Use the configured proxy and CA bundle without weakening TLS verification.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_config="$(mktemp /tmp/aegis-build.XXXXXX.json)"
trap 'rm -f "$build_config"' EXIT
python3 - "$build_config" <<'PY'
import json, os, socket, sys
from pathlib import Path
from urllib.parse import urlparse
hosts={}
for name in ('HTTP_PROXY','HTTPS_PROXY'):
    host=urlparse(os.environ.get(name,'')).hostname
    if host: hosts[host]=socket.gethostbyname(host)
config={'services':{name:{'build':{'args':{key:'${'+key+':-}' for key in ('HTTP_PROXY','HTTPS_PROXY','NO_PROXY')}}} for name in ('api','web')}}
if hosts:
    for service in config['services'].values(): service['build'].update(network='host',extra_hosts=hosts)
ca=os.environ.get('SSL_CERT_FILE')
if ca and Path(ca).is_file():
    config['secrets']={'build_ca':{'file':ca}}
    for service in config['services'].values(): service['build']['secrets']=['build_ca']
Path(sys.argv[1]).write_text(json.dumps(config))
PY
cd "$repo_dir"
docker compose -f compose.yaml -f "$build_config" build "$@"
