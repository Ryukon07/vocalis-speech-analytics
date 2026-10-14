import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const API = 'http://127.0.0.1:8000/api/v1';
const accuracy = JSON.parse(readFileSync(resolve('../docs/benchmarks/transcription-accuracy.json'), 'utf8'));
const sample = accuracy.samples[0];
const audio = resolve('../dataset/asr_checks/1272-128104-0000.wav');
let reportId: string;
test.beforeAll(async ({ request }) => {
  const analyses = await (await request.get(API + '/analyses?limit=100')).json();
  for (const analysis of analyses.items.filter((a: any) => a.status === 'completed' && a.execution_mode === 'real')) {
    const result = await (await request.get(API + '/analyses/' + analysis.id + '/result')).json();
    if (result.clarity?.available && result.flaws.length && result.alignment.words.length > 12) { reportId = analysis.id; break; }
  }
  expect(reportId, 'Run scripts/verify_real_workflow.py first to provide a real report').toBeTruthy();
});
test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  (page as any).__runtimeErrors = errors;
});
test.afterEach(async ({ page }) => { expect((page as any).__runtimeErrors).toEqual([]); });

test('settings persist; rubric validation, creation, versioning and deletion', async ({ page, request }) => {
  const title = `Browser QA rubric ${Date.now()}`;
  let rubricId: string | undefined;
  try {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: 'Settings & rubrics' })).toBeVisible();
    await expect(page.getByText('Ready', { exact: true })).toBeVisible();
    await page.getByLabel('Display density').selectOption('compact');
    await page.reload();
    await expect(page.getByLabel('Display density')).toHaveValue('compact');
    expect(await page.locator('html').getAttribute('data-density')).toBe('compact');
    await expect(page.getByLabel('Default comparison mode').locator('option')).toHaveCount(1);
    await page.getByLabel('Default comparison mode').selectOption('recording');
    await page.goto('/analyze');
    expect(await page.evaluate(() => localStorage.getItem('vocalis-mode'))).toBe('recording');
    await page.goto('/settings');
    await page.getByLabel('Default comparison mode').selectOption('recording');
    await page.getByRole('button', { name: 'New rubric' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Rubric name').fill(title);
    await dialog.getByLabel('Pacing & cadence weight').fill('24');
    await expect(dialog.getByRole('button', { name: 'Save rubric' })).toBeDisabled();
    await dialog.getByLabel('Pacing & cadence weight').fill('25');
    await dialog.getByRole('button', { name: 'Save rubric' }).click();
    await expect(dialog).not.toBeVisible();
    const rubrics = await (await request.get(API + '/rubrics?limit=100')).json();
    const created = rubrics.items.find((r: any) => r.name === title);
    expect(created.version).toBe(1); rubricId = created.id;
    const row = page.locator('.rubric-row').filter({ hasText: title });
    await row.getByRole('button', { name: 'Edit rubric' }).click();
    await dialog.getByLabel('Rubric name').fill(title + ' revised');
    await dialog.getByRole('button', { name: 'Save rubric' }).click();
    await expect(dialog).not.toBeVisible();
    const edited = await (await request.get(API + '/rubrics/' + rubricId)).json();
    expect(edited.version).toBe(2);
    await row.getByRole('button', { name: 'Delete rubric' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Delete record' }).click();
    await expect(page.getByText(title + ' revised', { exact: true })).not.toBeVisible();
    rubricId = undefined;
  } finally {
    if (rubricId) await request.delete(API + '/rubrics/' + rubricId);
  }
});

test('annotation taxonomy and precise bounds survive create/edit/delete', async ({ page, request }) => {
  const note = `Browser QA annotation ${Date.now()}`;
  let annotationId: string | undefined;
  try {
    await page.goto('/datasets');
    await page.getByLabel('Recording to annotate').selectOption(sample.recording_id);
    await expect(page.getByRole('button', { name: 'Play audio' })).toBeEnabled();
    await page.getByLabel('Flaw type').selectOption('awkward_pause');
    await page.getByLabel('Start (seconds)').fill('1.2');
    await page.getByLabel('End (seconds)').fill('2.4');
    await page.getByLabel('Notes / annotator').fill(note);
    await page.getByRole('button', { name: 'Save annotation' }).click();
    const label = page.getByRole('button', { name: /awkward_pause ·/ });
    await expect(label).toBeVisible();
    const data = await (await request.get(API + '/datasets/annotations?recording_id=' + sample.recording_id)).json();
    const created = data.items.find((a: any) => a.notes === note);
    annotationId = created.id;
    expect(created.flaw_type).toBe('awkward_pause');
    expect(created.start_seconds).toBe(1.2); expect(created.end_seconds).toBe(2.4);
    await label.click();
    await expect(page.getByLabel('Flaw type')).toHaveValue('awkward_pause');
    await expect(page.getByLabel('Start (seconds)')).toHaveValue('1.2');
    await page.getByLabel('End (seconds)').fill('2.8');
    await page.getByRole('button', { name: 'Update annotation' }).click();
    await expect(label).toContainText('00:02.8');
    await page.getByRole('button', { name: 'Delete annotation' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Delete record' }).click();
    await expect(label).not.toBeVisible(); annotationId = undefined;
  } finally { if (annotationId) await request.delete(API + '/datasets/annotations/' + annotationId); }
});

test('real completed larger-model draft resumes into the editable wizard', async ({ page, request }) => {
  // A real public-audio API job; no ASR/network fixture is substituted.
  const job = await (await request.get(API + '/transcriptions/' + sample.runs[0].job_id)).json();
  expect(job.status).toBe('completed'); expect(job.model_name).toBe('medium');
  await page.addInitScript(({ recording, id }) => localStorage.setItem(`vocalis-transcription-${recording}`, id), { recording: job.recording_id, id: job.id });
  await page.goto('/analyze');
  await page.getByLabel('Or choose a saved recording').selectOption(job.recording_id);
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByLabel('Confirmed transcript')).toHaveValue(job.transcript);
  await expect(page.getByRole('status')).toContainText('Draft generated locally with medium');
  expect(await page.evaluate(id => localStorage.getItem(`vocalis-transcription-${id}`), job.recording_id)).toBeNull();
  await page.getByLabel('Confirmed transcript').fill('Reviewed words can be edited before any analysis is submitted.');
  await expect(page.getByLabel('Confirmed transcript')).toHaveValue('Reviewed words can be edited before any analysis is submitted.');
  await page.getByRole('button', { name: 'Back', exact: true }).click();
  await page.getByLabel('Or choose a saved recording').selectOption(accuracy.samples[1].recording_id);
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByLabel('Confirmed transcript')).toHaveValue('');
});

test('uploaded speech transcribes, validates, runs a real comparison and shows clarity', async ({ page, request }) => {
  test.setTimeout(300_000);
  let recordingId: string | undefined, referenceId: string | undefined, analysisId: string | undefined;
  try {
    await page.goto('/analyze');
    await page.getByRole('button', { name: 'Continue' }).click();
    await expect(page.getByRole('heading', { name: 'Add your speech recording' })).toBeVisible();
    const upload = page.waitForResponse(r => r.url() === API + '/recordings' && r.request().method() === 'POST');
    await page.getByLabel('Upload audio').setInputFiles(audio);
    recordingId = (await (await upload).json()).id;
    await page.getByRole('button', { name: 'Continue' }).click();
    await expect(page.getByLabel('Confirmed transcript')).toHaveValue('');
    await page.getByRole('button', { name: 'Generate transcript' }).click();
    await expect(page.getByLabel('Confirmed transcript')).not.toHaveValue('', { timeout: 180_000 });
    expect(await page.getByLabel('Confirmed transcript').inputValue()).toMatch(/Quilter/i);
    // Confirm the public gold transcript, as the wizard instructs, before alignment/scoring.
    await page.getByLabel('Confirmed transcript').fill(sample.expected);
    const created = await request.post(API + '/references', { data: { title: 'Browser QA public reference', recording_id: recordingId, transcript: sample.expected, speaker_id: '1272', source_url: 'https://www.openslr.org/12/', license: 'CC BY 4.0', eligible: true, profile: null } });
    expect(created.ok()).toBeTruthy(); referenceId = (await created.json()).id;
    await page.getByRole('button', { name: 'Continue' }).click();
    // A reference created during the wizard must become selectable when the step opens.
    await page.reload();
    await page.getByLabel('Or choose a saved recording').selectOption(recordingId!);
    await page.getByRole('button', { name: 'Continue' }).click();
    await page.getByLabel('Confirmed transcript').fill(sample.expected);
    await page.getByRole('button', { name: 'Continue' }).click();
    await page.getByLabel('Reference speech').selectOption(referenceId!);
    await page.getByRole('button', { name: 'Continue' }).click();
    const rubrics = await (await request.get(API + '/rubrics?limit=100')).json();
    const rubric = rubrics.items.find((r: any) => r.enabled_categories.length === 5);
    await page.getByLabel('Evaluation rubric').selectOption(rubric.id);
    await page.getByRole('button', { name: 'Continue' }).click();
    const submission = page.waitForResponse(r => r.url() === API + '/analyses' && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Analyze Speech', exact: true }).click();
    analysisId = (await (await submission).json()).id;
    await expect(page.getByRole('heading', { name: 'Clarity evidence' })).toBeVisible({ timeout: 180_000 });
    const result = await (await request.get(API + '/analyses/' + analysisId + '/result')).json();
    expect(result.execution_mode).toBe('real'); expect(result.clarity.available).toBe(true);
    expect(result.scores.dimensions.clarity).toBe(100);
  } finally {
    await page.goto('/');
    if (analysisId) await request.delete(API + '/analyses/' + analysisId);
    if (referenceId) await request.delete(API + '/references/' + referenceId);
    if (recordingId) await request.delete(API + '/recordings/' + recordingId);
  }
});

test('browser microphone worklet captures public speech, previews and saves PCM WAV', async ({ page, context, request }) => {
  let recordingId: string | undefined;
  try {
    await context.grantPermissions(['microphone']);
    await page.goto('/analyze');
    await page.getByRole('button', { name: 'Start recording' }).click();
    await expect(page.getByRole('button', { name: /Stop ·/ })).toBeVisible();
    await expect.poll(async () => await page.getByRole('button', { name: /Stop ·/ }).textContent()).toMatch(/Stop · [6-9]s/);
    await page.getByRole('button', { name: /Stop ·/ }).click();
    const preview = page.getByLabel('Preview microphone recording');
    await expect(preview).toBeVisible();
    const previewInfo = await preview.evaluate(async (element: HTMLAudioElement) => {
      const buffer = await (await fetch(element.src)).arrayBuffer(); const byteLength = buffer.byteLength;
      const ctx = new AudioContext(); const decoded = await ctx.decodeAudioData(buffer);
      const signal = decoded.getChannelData(0);
      const rms = Math.sqrt(signal.reduce((sum, x) => sum + x*x, 0) / signal.length);
      await ctx.close(); await element.play();
      return { duration: decoded.duration, rms, bytes: byteLength };
    });
    expect(previewInfo.duration).toBeGreaterThan(5); expect(previewInfo.rms).toBeGreaterThan(0.001);
    await expect.poll(() => preview.evaluate((a: HTMLAudioElement) => a.currentTime)).toBeGreaterThan(0.1);
    await preview.evaluate((a: HTMLAudioElement) => a.pause());
    const uploaded = page.waitForResponse(r => r.url() === API + '/recordings' && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Use this recording' }).click();
    const recording = await (await uploaded).json(); recordingId = recording.id;
    expect(recording.mime_type).toBe('audio/wav'); expect(recording.duration_seconds).toBeGreaterThan(5);
    const response = await request.get(API + '/recordings/' + recordingId + '/audio');
    const bytes = await response.body(); expect(bytes.subarray(0,4).toString()).toBe('RIFF');
    mkdirSync(resolve('../tmp/browser-checks'), { recursive: true });
    writeFileSync(resolve('../tmp/browser-checks/microphone-capture.json'), JSON.stringify({ protocol: 'Chromium file-backed simulated microphone through real AudioWorklet, preview and upload; physical microphone was separately human verified in Brave', ...previewInfo }, null, 2));
  } finally { await page.goto('/'); if (recordingId) await request.delete(API + '/recordings/' + recordingId); }
});

test('report playback, seeking, all charts, evidence, voice handling, exports and print', async ({ page, request }) => {
  await page.goto('/analyses/' + reportId);
  await expect(page.getByRole('heading', { name: 'Clarity evidence' })).toBeVisible();
  const play = page.getByRole('button', { name: 'Play audio' }).first();
  await expect(play).toBeEnabled(); await play.click();
  await expect(page.getByRole('button', { name: 'Pause audio' })).toBeVisible();
  await expect.poll(() => page.locator('.audio-controls .mono').first().textContent()).not.toMatch(/^00:00.0/);
  await page.getByRole('button', { name: 'Pause audio' }).click();
  await page.getByLabel('Speed').first().selectOption('1.5');
  await expect(page.getByLabel('Speed').first()).toHaveValue('1.5');
  const words = page.locator('button.word');
  await words.nth(12).click(); await expect(words.nth(12)).toHaveClass(/active/);
  await page.locator('button.flaw-row').first().click();
  await expect(page.getByText('EVIDENCE & INTERPRETATION')).toBeVisible();
  for (const tab of await page.locator('.plot-tabs button').all()) {
    await tab.click(); await expect(tab).toHaveClass(/active/);
    await expect(page.locator('.recharts-surface').first()).toBeVisible();
  }
  await page.getByText('Review independently recognized words').click();
  await expect(page.getByText('Reference:', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Listen to feedback' }).click();
  // Real OS voices are used if Chromium exposes them; headless environments may have none.
  const voices = await page.evaluate(() => speechSynthesis.getVoices().filter(v => v.localService && /^en(?:-|$)/i.test(v.lang)).length);
  if (voices) {
    await expect(page.getByRole('button', { name: 'Stop reading' })).toBeVisible();
    await page.getByRole('button', { name: 'Stop reading' }).click();
  } else await expect(page.getByText(/No local English speech voice is available/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Listen to feedback' })).toBeVisible();
  mkdirSync(resolve('../tmp/browser-checks/downloads'), { recursive: true });
  for (const format of ['JSON', 'CSV', 'PDF']) {
    const downloading = page.waitForEvent('download');
    await page.getByRole('link', { name: format, exact: true }).click();
    const download = await downloading;
    expect(await download.failure()).toBeNull();
    const path = resolve('../tmp/browser-checks/downloads', download.suggestedFilename());
    await download.saveAs(path); const data = readFileSync(path);
    if (format === 'JSON') expect(JSON.parse(data.toString()).analysis_id).toBe(reportId);
    if (format === 'CSV') expect(data.toString()).toContain('start_seconds');
    if (format === 'PDF') expect(data.subarray(0,5).toString()).toBe('%PDF-');
  }
  await page.evaluate(() => { (window as any).__printCalled = false; window.print = () => { (window as any).__printCalled = true; }; });
  await page.getByRole('button', { name: 'Print report' }).click();
  expect(await page.evaluate(() => (window as any).__printCalled)).toBe(true);
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('.no-print').first()).toBeHidden();
  await page.pdf({ path: resolve('../tmp/browser-checks/downloads/browser-print.pdf'), format: 'A4', printBackground: true });
  await page.emulateMedia({ media: 'screen' });
  await page.screenshot({ path: resolve('../tmp/browser-checks/report-desktop.png'), fullPage: true });
});

test('all website pages render on mobile, navigation and upload error remain usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const url of ['/', '/dashboard', '/analyze', '/references', '/datasets', '/history', '/settings', '/analyses/' + reportId]) {
    await page.goto(url); await expect(page.locator('h1')).toBeVisible();
    // Tables can scroll internally; the document should fit the viewport.
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    expect(overflow, url).toBeLessThanOrEqual(2);
  }
  await page.getByRole('button', { name: 'Toggle navigation' }).click();
  await expect(page.locator('.sidebar')).toHaveClass(/open/);
  await page.getByRole('link', { name: 'Settings & rubrics', exact: true }).click();
  await expect(page.locator('.sidebar')).not.toHaveClass(/open/);
  await page.screenshot({ path: resolve('../tmp/browser-checks/settings-mobile.png'), fullPage: true });
  await page.goto('/analyze');
  await page.getByLabel('Upload audio').setInputFiles({ name: 'invalid.txt', mimeType: 'text/plain', buffer: Buffer.from('not audio') });
  await expect(page.getByText(/WAV|MP3|FLAC/).filter({ hasText: /Choose|Only|supported/ })).toBeVisible();
  await page.goto('/missing-browser-check');
  await expect(page.getByText('This page is unavailable')).toBeVisible();
  await page.getByRole('link', { name: 'Return to workspace' }).click();
  await expect(page).toHaveURL(/dashboard/);
});
