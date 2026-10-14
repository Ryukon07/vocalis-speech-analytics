# Vocalis Speech Intelligence

Vocalis is a local CPU application for Track C. Record or upload English speech, generate and correct a transcript, compare the same text with a reference, inspect measured flaws, replay passages and export the saved report.

## Submission links - Ryucoders

- [Public repository](https://github.com/Ryukon07/vocalis-speech-analytics)
- [Hosted report dashboard](https://ryukon07.github.io/vocalis-speech-analytics/) - free GitHub Pages viewer of 10 real model reports and 91 public recordings. Charts, word/flaw seeking, playback, spoken feedback and JSON/CSV/PDF downloads work without the serving laptop. New analysis and editing require the full Python workspace.
- [Custom paired dataset](https://github.com/Ryukon07/vocalis-speech-analytics/tree/main/dataset/contrastive) - 10 references, 70 variants, transcripts, alignments and exact labels
- [Temporary HTTPS demo](https://jackson-nutten-high-taken.trycloudflare.com) - real CPU inference, isolated public dataset and protected example reports. This development preview requires the serving laptop and tunnel to stay online; it has no permanent-hosting uptime guarantee.
- [Final real-dashboard video](docs/submission/vocalis-final-demo.mp4) - 6:33, actual browser footage and English narration; upload public/unlisted to YouTube for submission
- [Six-page technical document](docs/submission/technical-documentation.pdf)
- [Devpost/Unstop description](docs/submission/DEVPOST_DESCRIPTION.md)
- [Dataset reuse and attribution](dataset/LICENSE_NOTES.md)

The public preview uses a separate allowlisted database; private microphone recordings and local credentials are excluded. Anonymous browser sessions own their new items; seeded dataset/report edits are blocked. Use public/test audio. Deployment checks include actual medium-model transcription through HTTPS, guest isolation, byte-range playback and PDF exports.

## Start locally

This workspace already contains the installed speech runtime, cached models, built frontend and imported dataset.

```powershell
Set-Location D:\AI-Hackathon
.\start-local.ps1
```

Open **http://127.0.0.1:5173**. Double-click start-local.cmd as an alternative. API documentation: http://127.0.0.1:8000/docs.

On a new machine, install Python 3.12 and Node.js 24 LTS, then run setup-local.ps1 followed by start-local.ps1. Without the Python launcher, pass -PythonPath with the Python 3.12 executable. Setup installs CPU-only PyTorch, migrates the database, imports the corpus, builds the website and warms the models.

No dedicated GPU or paid API is required. Internet is needed for initial downloads. Models stay in model-artifacts; uploaded audio and SQLite stay in backend/data. stop-local.ps1 stops only the project-owned processes. Logs are under tmp/local-server.

## Speech workflow

1. Upload WAV/MP3/FLAC, select saved audio, or record with the microphone.
2. Stop, preview and save microphone capture as PCM WAV.
3. Generate a local ASR draft or import/paste text, then correct it against the recording.
4. Select a reference containing the same text.
5. Choose a versioned rubric, categories, sensitivity and windows.
6. Run the persisted asynchronous analysis.
7. Click words/flaws to seek playback. Inspect aligned acoustic curves, measured deltas and practice advice.
8. Listen to feedback through browser speech synthesis or download JSON, CSV and PDF.

Local inputs are limited to three minutes. Alignment supports English. Microphone capture requires localhost/HTTPS and browser permission. Spoken feedback selects a local English browser/OS voice and reports playback failures. Silent microphone clips are rejected before upload.

## Models and measurements

- Faster-Whisper medium for editable transcript drafts and base.en for independent clarity, CPU int8, voice activity detection, temperature zero and beam size five.
- Pretrained wav2vec2 base 960h with real CTC word alignment.
- pYIN pitch, speaker-median-centered semitones, normalized RMS/dB energy, articulation rate, pauses, MFCCs and spectral centroid.
- Word boundaries map reference features into participant time. Local phrases/windows ground delivery deviations.
- Rule-derived explanations preserve measured evidence. Confidence remains absent until calibrated.
- Clarity uses independent local ASR and normalized word error rate (WER). The score measures additional recognition errors relative to the reference, with phrase-level evidence and both recognized texts. It is an ASR proxy, not a calibrated human intelligibility or accent score.

The real provider is evaluator, version 3.1.3-local.1. Mock execution requires explicit demo settings and stays labeled. Dashboard score aggregates exclude mock history.

## Custom dataset

The bundled [paired corpus](dataset/contrastive/manifest.json) contains **10 references and 70 variants**, with matching transcripts, word alignment, exact controlled-edit intervals, severity, provenance and SHA-256 hashes.

The spectrum covers mild/severe rushing, slowing, inserted pauses, local attenuation, pitch flattening and no injected flaw with a small gain change. A supplementary combined severe case is provided under dataset/stress_samples and excluded from the frozen benchmark. Source splits are enforced; testing holds out Eisenhower. Ground truth describes controlled edits, not human-reviewed rhetorical quality.

See [dataset documentation](dataset/contrastive/README.md), [source catalog](dataset/reference_speeches/sources.json), and [construction script](dataset/build_dataset.py).

```powershell
.\.venv\Scripts\python.exe dataset/build_dataset.py
.\.venv\Scripts\python.exe dataset/evaluate_dataset.py
Set-Location backend
..\.venv\Scripts\python.exe -m app.import_dataset
```

Rebuilding uses retained originals when available; --from-paired regenerates identical variants from the bundled references without archive downloads. Included paired files can be evaluated independently. The importer is repeatable and rejects changed hashes rather than replacing saved analysis inputs.

## Verification

```powershell
.\scripts\verify-local.ps1
.\.venv\Scripts\python.exe scripts/verify_real_workflow.py
```

The second command needs the website running. Run scripts/verify_clarity.py and scripts/verify_clarity_workflow.py for independent recognition/noise checks and the saved five-category report. The frozen delivery benchmark (v3.0, four categories) completed **70/70 real inferences without failure**. At interval IoU >= 0.25, speaker-held-out testing achieved precision **0.727**, recall **0.889**, F1 **0.800**, and mean matched-boundary error **0.288 seconds**. These figures describe this controlled corpus.

See [verification](docs/VERIFICATION.md), [benchmarks](docs/benchmarks/summary.json), [architecture](docs/ARCHITECTURE.md), [API](docs/API.md), [ML integration](docs/ML_INTEGRATION.md), and [six-page technical document](docs/submission/technical-documentation.pdf).

## Configuration

Backend commands run from backend and read backend/.env. Frontend builds read frontend/.env.

| Setting | Local value |
| --- | --- |
| ANALYSIS_PROVIDER | evaluator |
| ENABLE_DEMO_MODE | false |
| EVALUATOR_DEVICE | cpu |
| EVALUATOR_LANGUAGE | en |
| ASR_MODEL (clarity) | base.en |
| TRANSCRIPTION_MODEL (drafts) | medium |
| TRANSCRIPTION_FALLBACK_MODEL | medium |
| CPU_THREADS | 4 |
| MODEL_CACHE_ROOT | ../model-artifacts |
| JOB_TIMEOUT_SECONDS | 1800 |
| MAX_UPLOAD_MB | 50 |
| VITE_API_BASE_URL | http://127.0.0.1:8000/api/v1 |

Choose **Complete delivery with clarity** for pacing 25%, pitch 20%, energy 20%, pausing 15% and clarity 20%. The older four-category rubric remains available for historical comparisons. Overall scores normalize the snapshot weights over available enabled dimensions. Missing pitch never becomes a perfect pitch score.

## Packaging and submission

Docker packages real inference and persistent data/model volumes.

```sh
docker compose up --build
docker compose exec backend python -m app.import_dataset
```

Docker requires an installed engine; local Windows execution is the verified target. New containers download models on first use. The paired dataset, technical document and demonstration materials are included.

GitHub/YouTube publication requires owner-selected accounts and destinations. Original private files, credentials and model caches are excluded from automatic publication.

## Operating limits

Run one backend worker. Inference is serialized to control laptop memory. Cancellation/timeouts reject late output but cannot forcibly interrupt native inference. Public multi-user hosting needs authentication, isolated workers, retention controls and a production proxy.

The rubric is a documented relative heuristic. Broader human-rated evaluation is needed before using it as a competition judging standard. TorchAudio 2.8 is pinned because later releases remove the alignment API.



## Clarity measurement

Score = 100 x (1 - min(1, max(0, participant WER - reference WER))). Recognition receives no confirmed transcript prompt. Case, punctuation, common contractions, numeric spellings and diacritics are normalized. At least eight normalized words and reference WER no greater than 25% are required; otherwise clarity is unavailable and excluded from the weighted average. Local phrase flags require at least four normalized words, 20 percentage points of additional errors, and at least 10 points globally. They indicate recognition disagreement, not a diagnosed pronunciation defect.

Twelve real-source recognition checks include three identical-audio controls and nine known-noise variants. See docs/benchmarks/clarity-verification.json. Mild noise can improve a recognizer, so this measure should not be treated as a monotonic noise meter or as a human judgment. Browser and physical microphone verification boundaries remain documented in docs/VERIFICATION.md.

The user confirmed clear microphone playback and spoken feedback in Brave. Drafts now use the pinned, checksum-verified medium model on the local CPU by default. Set TRANSCRIPTION_MODEL=base.en for faster drafts with an automatic medium retry on empty/unreliable output. The full microphone recording completed with a 29-word draft, including microphone-testing speech; this is not a claim of exact whole-recording transcript accuracy. The actual recognition model is recorded, and drafts remain editable and unconfirmed. Clarity continues to use base.en with its original independent recognition configuration.

Setup warms both recognition models and the alignment model. The medium weights require approximately 1.53 GB of disk space; no GPU or hosted speech service is required. Set TRANSCRIPTION_FALLBACK_MODEL to an empty string to disable the larger retry. The current laptop completed the full microphone job in about 59 seconds. See docs/VERIFICATION.md for current accuracy and browser evidence.

## Final transcription and browser verification (3.1.3)

Four fixed, newly downloaded LibriSpeech validation clips were each transcribed three times through the actual API (12 jobs per model). Draft WER fell from 4.82% with base.en to 3.61% with medium. Repeats were identical for every clip. The conservative comparison counts Mr. versus MISTER as substitutions; one proper-name spelling remains wrong. No gold transcript was supplied to recognition. This is a clean, one-reader sample check, not universal accuracy or an assurance of absence from upstream training.

All seven Chromium end-to-end checks passed, including the real wizard/inference, microphone worklet, settings/rubrics, annotation editing, completed report downloads, responsive pages and voice handling. Final checks: 65 backend tests, 24 frontend tests, production build, pip check and zero npm audit vulnerabilities. Additional external HTTPS browser checks passed for the temporary preview. See docs/VERIFICATION.md for precise physical-device and automated-test boundaries. Run scripts/install-browser-checks.ps1 once, then npm run test:e2e from frontend to reproduce.
