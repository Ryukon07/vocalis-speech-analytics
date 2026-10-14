import { resolve } from 'node:path';
import { readFileSync, writeFileSync } from 'node:fs';
process.env.PLAYWRIGHT_BROWSERS_PATH ||= resolve(import.meta.dirname, '../model-artifacts/playwright');
const { chromium } = await import('../frontend/node_modules/playwright/index.mjs');
const { expect } = await import('../frontend/node_modules/@playwright/test/index.mjs');
const root = resolve(import.meta.dirname, '..');
const hosting = JSON.parse(readFileSync(resolve(root, 'docs/submission/report-hosting.json'), 'utf8'));
const browser = await chromium.launch({ headless: true, channel: 'chromium' });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
const page = await context.newPage();
const errors = [], prohibited = [];
page.on('pageerror', error => errors.push(error.message));
page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
await context.route('**/*', route => {
  const url = new URL(route.request().url());
  if (['127.0.0.1', 'localhost'].includes(url.hostname) || url.hostname.endsWith('.trycloudflare.com')) {
    prohibited.push(url.origin); return route.abort();
  }
  return route.continue();
});
try {
  const base = hosting.url.replace(/\/$/, '') + '/';
  await page.goto(base + '#/dashboard');
  await expect(page.getByText('10 completed with real models')).toBeVisible({ timeout: 45000 });
  await expect(page.getByText('REPORT VIEWER', { exact: true })).toBeVisible();
  const snapshot = await (await context.request.get(base + 'archive/snapshot.json')).json();
  expect(snapshot['/analyses']).toHaveLength(10);
  expect(snapshot['/recordings'].some(item => item.original_filename === 'speech-1791959497867.wav')).toBe(false);
  for (const job of snapshot['/analyses']) {
    expect(job.execution_mode).toBe('real');
    await page.goto(base + '#/analyses/' + job.id);
    await expect(page.getByRole('heading', { name: 'Dimension scores' })).toBeVisible({ timeout: 45000 });
    if (snapshot['/analyses/' + job.id + '/result'].clarity) {
      await expect(page.getByRole('heading', { name: 'Clarity evidence' })).toBeVisible();
    }
    await expect(page.getByRole('button', { name: 'Play audio' }).first()).toBeEnabled({ timeout: 45000 });
  }
  const identifier = snapshot['/analyses'].find(job => job.flaw_count > 0).id;
  await page.goto(base + '#/analyses/' + identifier);
  await expect(page.locator('.flaw-row').first()).toBeVisible({ timeout: 30000 });
  await page.locator('.flaw-row').first().click();
  await expect(page.getByText('EVIDENCE & INTERPRETATION')).toBeVisible();
  const play = page.getByRole('button', { name: 'Play audio' }).first();
  await expect(play).toBeEnabled({ timeout: 30000 });
  await play.click();
  await expect(page.getByRole('button', { name: 'Pause audio' }).first()).toBeVisible();
  await page.waitForTimeout(800);
  await page.getByRole('button', { name: 'Pause audio' }).first().click();
  await expect(page.getByRole('button', { name: 'Listen to feedback' })).toBeVisible();
  for (const name of ['JSON', 'CSV', 'PDF']) {
    const event = page.waitForEvent('download');
    await page.getByRole('link', { name, exact: true }).click();
    const download = await event;
    await download.saveAs(resolve(root, 'tmp/permanent-demo/verified-report.' + name.toLowerCase()));
    expect(await download.failure()).toBe(null);
  }
  await page.screenshot({ path: resolve(root, 'tmp/permanent-demo/hosted-report.png'), fullPage: true });
  await page.goto(base + '#/references');
  await expect(page.getByRole('button', { name: 'Add reference' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Edit reference' }).first()).toBeDisabled();
  await page.goto(base + '#/datasets');
  await expect(page.getByRole('button', { name: 'Edit group' }).first()).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Annotate' }).first()).toBeEnabled();
  await page.goto(base + '#/analyze');
  await expect(page.getByRole('heading', { name: 'Explore real speech analyses' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start recording' })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(base + '#/dashboard');
  await expect(page.getByText('10 completed with real models')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(2);
  expect(errors).toEqual([]); expect(prohibited).toEqual([]);
  const result = { url: base, passed: true, real_reports: 10, laptop_backend_blocked: true, backend_requests: prohibited, audio_playback: true, feedback_controls: true, pdf_csv_json_downloads: true, public_sources_only: true, mutations_disabled: true, honest_new_analysis_unavailable: true, mobile_layout: true, page_errors: errors };
  writeFileSync(resolve(root, 'docs/submission/report-hosting-verification.json'), JSON.stringify(result, null, 2) + '\n');
  console.log('Hosted report viewer passed with all laptop/backend connections blocked:', base);
} finally { await context.close(); await browser.close(); }
