# Verification

The completed local target is Vocalis 3.1.3 on Windows, Python 3.12, Node.js 24.15 and CPU-only PyTorch 2.8, using a 16 GB Intel i5-10200H laptop. The public repository is https://github.com/Ryukon07/vocalis-speech-analytics. The user handles final YouTube upload and Devpost/Unstop submission.

## Final regression and browser checks

65 backend tests and 24 frontend tests passed; TypeScript/Vite production build, pip dependency check and npm audit passed (zero reported vulnerabilities). The final backend regression includes a new check for session filtering before pagination, stable totals and restoration of unrestricted local queries. Vitest was upgraded to 5.0.4 to remove critical/moderate transitive advisories. An AnyIO deprecation warning remains informational.

All seven isolated Chromium browser checks passed against the real localhost services, without computer use:

1. Settings density/default persistence, capability-limited choices, rubric weight validation, creation, edit/versioning and deletion.
2. Annotation taxonomy, exact interval bounds, editing and deletion.
3. Real completed medium-model draft restoration into the editable wizard; switching recordings clears stale words.
4. Actual upload, API transcription, transcript confirmation, five-step submission, real CTC/acoustic inference and available clarity result.
5. File-backed simulated microphone through the actual AudioWorklet, signal/duration validation, audible-media timeline preview, PCM WAV upload and retrieval.
6. Report playback/pause, speed, word/flaw seeking, every acoustic chart, recognition/evidence disclosure, speech voice handling, completed JSON/CSV/PDF downloads and print invocation/CSS/PDF rendering.
7. Landing/workspace pages at mobile width, document overflow checks, invalid-upload feedback, unavailable-route recovery and navigation.

Native stability: the legacy compiled Numba cache reproduced a Windows access violation inside pYIN interpolation. A fresh compiler cache passed two independent worker/process runs with matching pitch arrays, and the versioned production cache passed two more. The real browser analysis and seven API comparisons also passed. The runtime now separates native caches by Python/Numba/librosa/NumPy versions; acoustic methods and frozen benchmark identities are unchanged. Startup enables faulthandler diagnostics.

Detailed public evidence: [automated browser checks](benchmarks/automated-browser-verification.json). Test traces, downloaded files and screenshots stay under tmp/browser-checks and are excluded from the shareable package. The browser suite checks that no page exceptions or error-level console messages occur. QA-created rubrics, annotations, analyses, references and microphone/upload recordings are removed afterwards; the four public accuracy recordings are retained.

## Transcription accuracy

Four fixed, newly downloaded LibriSpeech validation clips were each transcribed three times through the actual API (12 jobs per model). Draft WER fell from 4.82% with base.en to 3.61% with medium. Repeats were identical for every clip. The conservative comparison counts Mr. versus MISTER as substitutions; one proper-name spelling remains wrong. No gold transcript was supplied to recognition. This is a clean, one-reader sample check, not universal accuracy or an assurance of absence from upstream training.

Gold text, SHA-256 hashes, source/license, recognized text, edit counts and timings are saved in [accuracy results](benchmarks/transcription-accuracy.json), [baseline](benchmarks/draft-model-baseline.json) and dataset/asr_checks/manifest.json. The default draft recognizer is medium, CPU int8; TRANSCRIPTION_MODEL=base.en selects faster drafts with medium as the optional empty/unreliable-output retry. ASR_MODEL=base.en independently controls clarity, preserving the frozen scoring configuration.

The user previously confirmed clear physical microphone playback and clear spoken feedback in Brave. The original 50.98-second microphone recording now has a completed 29-word medium draft, but there is no verified exact gold transcript for that full private recording. Draft confirmation remains a normal product step; this recording is not used to claim accuracy. Private audio/text remain excluded from the package. Automated microphone capture uses public speech and does not claim a new physical-device test. Headless speech checks exercise OS voices if available or the actionable missing-voice state; the human listening confirmation establishes physical speaker output.

## Genuine speech benchmark and clarity

The frozen four-category v3.0 delivery benchmark completed 70/70 real inferences. Predictions match by type and interval IoU >= 0.25. Testing holds out Eisenhower; training and validation use different Reagan sources.

| Split | Files | Precision | Recall | F1 | Boundary MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training | 28 | 0.875 | 0.875 | 0.875 | 0.430 s |
| Validation | 21 | 0.824 | 0.778 | 0.800 | 0.320 s |
| Testing | 21 | 0.727 | 0.889 | 0.800 | 0.288 s |
| All | 70 | 0.810 | 0.850 | 0.829 | 0.355 s |

Ground truth records controlled acoustic edits, not human-rated rhetorical quality. Full predictions, hashes and split boundaries remain under benchmarks/.

Clarity is an independent recognition proxy: 100 * (1 - min(1, max(0, participant WER - reference WER))). It requires at least eight normalized words and reference WER <= 25%; unavailable clarity is excluded from the weighted average. Three identical-source controls scored 100; nine noise checks verified additional recognition errors. At -5 dB, the three excerpts scored 43.2, 3.6 and 21.1. Some milder noise improves ASR, so this is not a monotonic noise metric or a human pronunciation diagnosis. Exact results are in benchmarks/clarity-verification.json.

Seven five-category website comparisons passed, along with a separate noisy report (clarity 83.6, overall 95.33, four localized feedback regions). API verification covers result persistence, participant-aligned curves, word timestamps, audio ranges and all exports. Historical results retain their provider/rubric snapshots; the current independent draft model does not rewrite them.

## Documents and local scope

The six-page technical document and two-page real report were rendered for visual verification before packaging. The project archive excludes .env credentials, user recordings/databases, model weights, browser profiles and test traces. The final 6:33 video contains recorded real dashboard footage, actual upload/transcription/scoring, stress tests, clarity evidence, replay and PDF export, with English narration. Full video/audio decoding and chapter-frame inspection passed; details are in submission/final-demo-verification.json.

The temporary HTTPS demo uses a separate, public-audio-only database. Actual external HTTPS API checks passed for medium transcription, private recording exclusion, anonymous ownership, protected seed data, audio ranges and PDF export. External Chromium checks passed for real UI transcription, simulated microphone worklet capture, saved reports, PDF download and mobile layout, with no page exceptions or error-level console messages. Evidence is in submission/deployment-verification.json and submission/public-browser-verification.json. Keep the serving laptop and tunnel online; this preview does not provide durable uptime.

Windows/local SQLite is the verified execution target. Docker files are supplied, but Docker is not installed on this laptop; PostgreSQL and public multi-user hosting are outside this local completion. Native Brave print/playback/chart/word/flaw/voice checks from earlier turns remain historical evidence in browser-verification.json. The previously unfinished editor/settings/draft/export software checks are now covered by the completed Chromium suite; native Brave Save-dialog automation is not claimed.

## Reproduce

Run scripts/verify-local.ps1 for regression/build/dependency checks. With the website running, run scripts/verify_real_workflow.py and scripts/verify_transcription_accuracy.py. On a fresh machine, scripts/install-browser-checks.ps1 installs an isolated Chromium into model-artifacts/playwright; then run npm run test:e2e in frontend. The four public test WAVs are bundled, and scripts/download_asr_checks.py downloads them again if needed. Browser checks need at least one real report from verify_real_workflow.py and the accuracy jobs in the current local database.
