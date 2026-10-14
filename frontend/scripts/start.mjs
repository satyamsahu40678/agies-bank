import { access, cp, mkdir, rm } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// Next's standalone output deliberately excludes public/static files. Prepare
// only generated deployment directories before starting the supported server.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const standalone = path.join(root, '.next', 'standalone');
const server = path.join(standalone, 'server.js');
try {
  await access(server);
} catch {
  console.error('A production build is required. Run npm run build, then npm start.');
  process.exit(1);
}
const staticTarget = path.join(standalone, '.next', 'static');
await mkdir(path.dirname(staticTarget), { recursive: true });
await rm(staticTarget, { recursive: true, force: true });
await cp(path.join(root, '.next', 'static'), staticTarget, { recursive: true });
const publicSource = path.join(root, 'public');
try {
  await access(publicSource);
  const publicTarget = path.join(standalone, 'public');
  await rm(publicTarget, { recursive: true, force: true });
  await cp(publicSource, publicTarget, { recursive: true });
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}
const child = spawn(process.execPath, [server], {
  cwd: standalone,
  stdio: 'inherit',
  env: { ...process.env, HOSTNAME: process.env.AEGIS_WEB_HOST || '0.0.0.0', PORT: process.env.PORT || '3000' }
});
for (const signal of ['SIGTERM', 'SIGINT']) {
  process.on(signal, () => child.kill(signal));
}
child.on('error', error => { console.error(error.message); process.exitCode = 1; });
child.on('exit', (code, signal) => { process.exitCode = code ?? (signal === 'SIGTERM' || signal === 'SIGINT' ? 0 : 1); });
