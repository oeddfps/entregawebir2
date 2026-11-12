import {spawn} from 'node:child_process';
import {existsSync} from 'node:fs';
import {resolve} from 'node:path';
import process from 'node:process';
import {fileURLToPath} from 'node:url';

const webRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const repositoryRoot = resolve(webRoot, '..', '..');
const nextCli = resolve(webRoot, 'node_modules', 'next', 'dist', 'bin', 'next');
const python = process.env.PYTHON || (process.platform === 'win32' ? 'py' : 'python3');
const environment = {
  ...process.env,
  BACKEND_URL: process.env.BACKEND_URL || 'http://127.0.0.1:8787',
};

const playwrightBrowsersPath = process.env.PLAYWRIGHT_BROWSERS_PATH
  || (process.platform === 'win32' && existsSync('E:\\playwright-browsers') ? 'E:\\playwright-browsers' : '');
if (playwrightBrowsersPath) {
  environment.PLAYWRIGHT_BROWSERS_PATH = playwrightBrowsersPath;
}

if (!existsSync(nextCli)) {
  console.error('Next.js no está instalado. Ejecuta npm ci antes de iniciar el desarrollo.');
  process.exit(1);
}

const backend = spawn(python, ['-m', 'uvicorn', 'src.server.main:app', '--host', '127.0.0.1', '--port', '8787'], {
  cwd: repositoryRoot,
  env: environment,
  stdio: 'inherit',
  windowsHide: false,
});
const engine = spawn(python, ['-m', 'src.persistent.worker'], {
  cwd: repositoryRoot,
  env: environment,
  stdio: 'inherit',
  windowsHide: false,
});
const frontend = spawn(process.execPath, [nextCli, 'dev'], {
  cwd: webRoot,
  env: environment,
  stdio: 'inherit',
  windowsHide: false,
});

let stopping = false;
function stop(code=0) {
  if (stopping) return;
  stopping = true;
  if (!backend.killed) backend.kill();
  if (!engine.killed) engine.kill();
  if (!frontend.killed) frontend.kill();
  process.exitCode = code;
}

backend.on('error', error => {
  console.error(`No se pudo iniciar la API: ${error.message}`);
  stop(1);
});
frontend.on('error', error => {
  console.error(`No se pudo iniciar Next.js: ${error.message}`);
  stop(1);
});
backend.on('exit', code => {
  if (!stopping && code !== 0) stop(code || 1);
});
engine.on('error', error => {
  console.error(`No se pudo iniciar el motor: ${error.message}`);
  stop(1);
});
engine.on('exit', code => {
  if (!stopping && code !== 0) stop(code || 1);
});
frontend.on('exit', code => {
  if (!stopping && code !== 0) stop(code || 1);
});
process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
