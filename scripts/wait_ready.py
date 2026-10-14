"""Bounded readiness checks: verifies response content, not merely a listening port."""
import json
import sys
import time
import urllib.request

for url in sys.argv[1:]:
    deadline = time.monotonic() + 55
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                payload = response.read()
                assert response.status == 200
                if url.endswith('/api/health'):
                    health = json.loads(payload)
                    assert health.get('status') in ('ok', 'healthy'), health
                else:
                    assert b'<html' in payload.lower(), 'HTML page missing'
                print(f'Ready: {url}')
                break
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    else:
        raise SystemExit(f'Readiness failed for {url}: {last_error}')
