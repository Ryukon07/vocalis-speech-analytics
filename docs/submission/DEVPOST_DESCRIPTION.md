# Vocalis - Contrastive Speech Analytics

**Team:** Ryucoders

**Tagline:** Turn vague speech feedback into timestamped, measurable evidence.

## Inspiration

Competitive speakers often lose points for delivery without knowing exactly where their pacing, pitch, energy or pauses changed. We built Vocalis to connect every piece of feedback with the passage, acoustic measurements and comparison that produced it.

## What it does

Vocalis compares a participant recording with a reference speaking the same text. Users upload WAV/MP3/FLAC or record through a microphone, generate and review a local transcript, select a reference and configure a versioned rubric. The dashboard returns word timestamps, five delivery dimensions, highlighted flaw intervals, baseline/participant feature overlays, measured explanations and practical recommendations. Clicking a word or flaw seeks playback. Reports export as JSON, CSV and PDF, and recommendations can be read by a local English voice.

## How we built it

Our custom contrastive dataset contains ten excerpts from three prominent public speeches by Reagan and Eisenhower and seventy paired, same-text variants. Each excerpt has near-perfect, mildly/severely rushed, slow, paused, low-energy and monotone versions. We preserve transcripts, audio hashes, word alignments, exact edit bounds, severity, time mappings and source attribution. A supplementary combined severe recording tests interacting deviations. Source-level splits keep related excerpts together; Eisenhower is held out by speaker for testing.

The React/TypeScript frontend uses WaveSurfer, Recharts and TanStack Query. A FastAPI/SQLAlchemy backend stores recordings, asynchronous jobs, rubric snapshots and structured evidence. Faster-Whisper medium provides editable CPU-int8 transcript drafts. Pretrained wav2vec2 performs real CTC alignment. pYIN extracts pitch; RMS/dB, MFCCs, spectral centroid, matched articulation rates and adjacent-word pauses describe delivery. Pitch is median-centered in semitones and energy is normalized against speech-active medians. Matched word boundaries map reference features into participant time.

The scoring method is transparent. Acoustic deductions depend on measured severity and interval exposure. Clarity independently recognizes both recordings with base.en and measures additional word errors relative to the reference. Available enabled dimensions are combined using the saved rubric weights. Missing measurements are excluded rather than replaced with perfect scores.

## Challenges we overcame

Different speaking speeds make independent recording clocks misleading, so we compare corresponding words and passages. Quiet spoken segments must remain in energy analysis to detect attenuation. Speech recognizers can hallucinate repeated words; drafts have silence/repetition safeguards and stay editable. We also diagnosed a native pitch-cache crash, isolated the compiler cache by runtime versions and verified it across process restarts. Cancellation and timeouts reject late results, while shared inference serialization bounds laptop resource use.

## Accomplishments

- All 70 controlled variants completed real inference.
- Speaker-held-out testing: precision 0.727, recall 0.889, F1 0.800; mean matched-boundary error 0.288 seconds at interval IoU >= 0.25.
- Four preselected public transcription clips, three actual API runs each: draft WER improved from 4.82% to 3.61%, with identical repeats.
- 65 backend tests, 24 frontend tests and seven complete browser workflows passed, including real transcription/scoring, microphone worklet capture, rubric/annotation editing, exports and mobile pages. Additional external HTTPS browser checks passed for the published preview.
- Physical microphone playback and spoken feedback were confirmed separately; automated microphone checks used public speech through a simulated media device.

## What we learned

Recognizer errors, recording noise and rhetorical delivery are different measurements. We expose raw evidence and limitations instead of presenting heuristic scores as calibrated human judgments. Controlled edits provide precise labels, but a small, two-speaker corpus cannot establish accuracy for all accents or natural performances.

## What's next

Expand the corpus with human-reviewed natural performances and more speakers, calibrate scoring against expert ratings, and introduce process-isolated inference workers and access controls for durable multi-user hosting.

## Built with

Python 3.12, FastAPI, Pydantic, SQLAlchemy, SQLite, Faster-Whisper, CTranslate2, PyTorch, TorchAudio, wav2vec2, librosa, NumPy, SciPy, Praat/Parselmouth, React, TypeScript, Vite, WaveSurfer, Recharts, Playwright.

## Submission links

- Project repository: https://github.com/Ryukon07/vocalis-speech-analytics
- Custom dataset: https://github.com/Ryukon07/vocalis-speech-analytics/tree/main/dataset/contrastive
- Dataset license and attribution: https://github.com/Ryukon07/vocalis-speech-analytics/blob/main/dataset/LICENSE_NOTES.md
- Temporary HTTPS demo: https://jackson-nutten-high-taken.trycloudflare.com
- Laptop-independent report dashboard: https://ryukon07.github.io/vocalis-speech-analytics/ (real saved results, replay, charts, spoken feedback and exports; new analysis/editing require the full workspace).
- Six-page technical document: https://github.com/Ryukon07/vocalis-speech-analytics/blob/main/docs/submission/technical-documentation.pdf
- Final narrated video file: `docs/submission/vocalis-final-demo.mp4` (6:33). Upload to YouTube and paste its final Public/Unlisted URL into the video field.

## Submission fields to fill on Devpost

- Add each teammate's real full name and Devpost account (team name: Ryucoders).
- Use the repository and dataset links above.
- Add the final 3-10 minute YouTube video, public or unlisted, with English narration.
- Attach/link the six-page technical document.
- Use the hosted report dashboard for judging access when the laptop is offline. The separate full inference demo requires the serving laptop to stay online.

The accompanying final video uses real recorded dashboard interactions and actual local API inference, with offline synthesized English narration. It does not use mocked API responses.
