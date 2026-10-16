"""Cross-platform local launcher. Run: python scripts/run-local.py --setup --open"""
from pathlib import Path
import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import runpy
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--setup', action='store_true', help='Install verified Python and locked npm dependencies first')
parser.add_argument('--open', action='store_true', help='Open the local app in this computer\'s browser')
parser.add_argument('--api-port', type=int, default=8000)
parser.add_argument('--web-port', type=int, default=3000)
args = parser.parse_args()
if not (1 <= args.api_port <= 65535 and 1 <= args.web_port <= 65535):
    parser.error('Ports must be between 1 and 65535.')
if args.api_port == args.web_port:
    parser.error('The API and web ports must be different.')
if sys.version_info < (3, 12):
    raise SystemExit('Python 3.12 or newer is required.')
npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
node = shutil.which('node')
if not npm or not node:
    raise SystemExit('Install Node.js 24 LTS (includes npm), then run this command again.')
major = int(subprocess.check_output([node, '--version'], text=True).strip().lstrip('v').split('.')[0])
if major < 22:
    raise SystemExit('Node.js 22 or newer is required; Node.js 24 LTS is recommended.')
python = ROOT / 'backend/.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
if args.setup:
    if not python.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(ROOT / 'backend/.venv')], check=True)
    subprocess.run([str(python), '-m', 'ensurepip', '--upgrade'], check=True)
    subprocess.run([str(python), '-m', 'pip', 'install', '--require-hashes', '-r', 'requirements-dev.lock'], cwd=ROOT/'backend', check=True)
    subprocess.run([npm, 'ci', '--no-audit', '--no-fund'], cwd=ROOT/'frontend', check=True)
if not python.exists() or not (ROOT/'frontend/node_modules').exists():
    raise SystemExit('Dependencies are missing. Run this launcher with --setup.')
# Reuse the backend's allowlisted .env reader so explicit origins are preserved.
# This module only uses the standard library; it does not start the API.
runpy.run_path(str(ROOT/'backend/app/config.py'))
os.environ.setdefault('AEGIS_STORAGE_BACKEND', 'memory')
local_origin = f'http://localhost:{args.web_port}'
allowed_origins = os.environ.get('AEGIS_ALLOWED_ORIGINS')
if allowed_origins and local_origin not in {origin.strip() for origin in allowed_origins.split(',')}:
    raise SystemExit(f'Add {local_origin} to AEGIS_ALLOWED_ORIGINS in your .env or backend environment before starting this web port.')
for port in (args.api_port, args.web_port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            raise SystemExit(f'Port {port} is already in use; stop your earlier app or choose another port.')
logs = ROOT/'logs'
logs.mkdir(exist_ok=True)
api_log = (logs/'api.log').open('w')
web_log = (logs/'web.log').open('w')
children = []
exit_code = 0
kwargs = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
def stop_signal(_signum, _frame):
    raise KeyboardInterrupt
for signal_name in ('SIGTERM', 'SIGHUP'):
    if hasattr(signal, signal_name):
        signal.signal(getattr(signal, signal_name), stop_signal)
try:
    env = dict(os.environ)
    env['API_INTERNAL_URL'] = f'http://127.0.0.1:{args.api_port}'
    env.setdefault('AEGIS_ALLOWED_ORIGINS', f'http://localhost:{args.web_port},http://127.0.0.1:{args.web_port}')
    web_env = {key:value for key,value in env.items() if key not in {'ANTHROPIC_API_KEY','AEGIS_OPENAI_API_KEY','OPENAI_API_KEY','OPENROUTER_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY','AGIES_SECRET','GOOGLE_APPLICATION_CREDENTIALS'}}
    children.append(subprocess.Popen([str(python), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(args.api_port)], cwd=ROOT/'backend', env=env, stdout=api_log, stderr=api_log, **kwargs))
    children.append(subprocess.Popen([node, str(ROOT/'frontend/node_modules/next/dist/bin/next'), 'dev', '--hostname', '127.0.0.1', '--port', str(args.web_port)], cwd=ROOT/'frontend', env=web_env, stdout=web_log, stderr=web_log, **kwargs))
    deadline = time.monotonic()+55
    for url in (f'http://127.0.0.1:{args.api_port}/api/health', f'http://127.0.0.1:{args.web_port}/login'):
        while True:
            if any(child.poll() is not None for child in children):
                raise RuntimeError('A service exited; check logs/api.log and logs/web.log.')
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if response.status == 200:
                        break
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Startup did not complete; check the logs directory.') from None
                time.sleep(.25)
    print(f'AegisBank is running on this computer at http://localhost:{args.web_port}', flush=True)
    print('Press Ctrl+C to stop both services. API keys stay in the backend environment.', flush=True)
    if args.open:
        webbrowser.open(f'http://localhost:{args.web_port}')
    while all(child.poll() is None for child in children):
        time.sleep(.5)
    raise RuntimeError('A service stopped unexpectedly; inspect logs/api.log and logs/web.log.')
except KeyboardInterrupt:
    pass
except Exception as error:
    print(str(error), file=sys.stderr)
    exit_code = 1
finally:
    for child in reversed(children):
        if os.name == 'nt':
            if child.poll() is None:
                subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                child.kill()
            else:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            child.wait(timeout=5)
    api_log.close()
    web_log.close()
raise SystemExit(exit_code)
