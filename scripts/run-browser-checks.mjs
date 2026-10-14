import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
process.env.PLAYWRIGHT_BROWSERS_PATH ||= resolve(root, 'model-artifacts/playwright');
const result = spawnSync(process.execPath, [resolve(root, 'frontend/node_modules/playwright/cli.js'), 'test', ...process.argv.slice(2)], { cwd: resolve(root, 'frontend'), env: process.env, stdio: 'inherit' });
if (result.error) throw result.error;
process.exit(result.status ?? 1);
