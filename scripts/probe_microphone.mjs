import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { resolve } from 'node:path';
const browser = await chromium.launch({ headless: true, channel: 'chromium', args: ['--use-fake-device-for-media-stream', '--use-file-for-fake-audio-capture=' + resolve('dataset/asr_checks/1272-128104-0000.wav')] });
try {
  const context = await browser.newContext({ permissions: ['microphone'] });
  const page = await context.newPage(); await page.goto('http://127.0.0.1:5173/analyze');
  console.log(await page.evaluate(async () => {
    let phase = 'getUserMedia'; let stream; let context;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
      phase = 'AudioContext'; context = new AudioContext(); await context.resume();
      phase = 'addModule'; const url = URL.createObjectURL(new Blob([`class Capture extends AudioWorkletProcessor { process(inputs) { return true; } } registerProcessor('test-capture', Capture);`], { type: 'application/javascript' }));
      await context.audioWorklet.addModule(url); URL.revokeObjectURL(url);
      phase = 'AudioWorkletNode'; const node = new AudioWorkletNode(context, 'test-capture');
      context.createMediaStreamSource(stream).connect(node); node.connect(context.destination);
      return { status: 'passed', sampleRate: context.sampleRate, settings: stream.getAudioTracks()[0].getSettings() };
    } catch (e) { return { phase, name: e.name, message: e.message }; }
    finally { stream?.getTracks().forEach(t => t.stop()); await context?.close(); }
  }));
} finally { await browser.close(); }
