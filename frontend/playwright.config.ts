import { defineConfig } from '@playwright/test';
import { resolve } from 'node:path';
export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  fullyParallel: false,
  outputDir: '../tmp/browser-checks/artifacts',
  reporter: [['list'], ['json', { outputFile: '../tmp/browser-checks/results.json' }]],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    browserName: 'chromium',
    channel: 'chromium',
    headless: true,
    actionTimeout: 15_000,
    viewport: { width: 1440, height: 1000 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: { args: [
      '--use-fake-device-for-media-stream',
      '--use-file-for-fake-audio-capture=' + resolve('../dataset/asr_checks/1272-128104-0000.wav'),
    ] },
  },
});
