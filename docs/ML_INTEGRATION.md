# Local speech processing integration

The real provider adapts evaluator.py to the persisted Pydantic result contract. speech_runtime.py manages Faster-Whisper and wav2vec2 CTC alignment. delivery_analysis.py compares corresponding words and acoustic windows.

## Runtime and transcription

Use Python 3.12 and root requirements. setup-local.ps1 installs CPU-only torch/torchaudio 2.8 first. Draft transcription defaults to medium/int8 and four CPU threads. Independent clarity recognition retains base.en/int8. Alignment uses WAV2VEC2_ASR_BASE_960H. Later TorchAudio versions remove the pinned alignment API.

Models, validated word caches and numeric acoustic caches stay in MODEL_CACHE_ROOT. Health checks check packages without downloading weights; scripts/warm_models.py verifies actual speech processing.

POST /recordings/{id}/transcriptions creates a persisted job. GET /transcriptions/{id} polls it. Drafts never overwrite confirmed metadata. The frontend inserts drafts into editable forms. Restart, timeout and cancellation reject late output.

Automatic analysis is supported with no transcript, but recognized words must match the reference. The standard website workflow generates, reviews and confirms text before comparison.

## Features and grounding

Pitch becomes median-centered semitones; RMS becomes median-normalized dB. MFCC 2, spectral centroid, pace curves and pauses add evidence. Missing pitch is null.

Words match by sequence. Their start/end anchors define a monotonic mapping into participant time. Local pacing uses overlapping four-word phrases and recomputes merged evidence. Acoustic windows use actual seconds. Pitch IQR reduces octave-outlier effects; pause comparisons use corresponding sequence boundaries, including repetitions.

Sensitivity changes pace, pitch, energy and mid-phrase pause thresholds. Real windows are at least 0.5 seconds and steps at least 0.1 seconds. Audio is bounded to 180 seconds.

## Contracts and scoring

AnalysisResult requires correct provider identity, finite measurements, bounded scores, ordered points and intervals within actual durations. Persistence checks reference/participant duration consistency and weighted overall score consistency.

Duration-normalized severity deductions are logged. The adapter separates pacing and pausing and applies the saved rubric. Clarity uses unprompted Faster-Whisper recognition, normalized edit counts and reference-relative WER; confidence is absent until calibrated. Explanations cannot modify measured evidence.

## Extensions

Implement SpeechAnalysisProvider with ProviderRequest, Capabilities, ProviderHealth and AnalysisResult. Register its factory in app/ml/registry.py. Providers receive internally resolved managed paths and advertise only functional modes/categories. The real provider requires recording comparison.

Call progress callbacks between expensive stages and propagate JobStopped. Inference shares a lock; cancellation is cooperative. Process isolation is appropriate for hard cancellation or public/distributed use.

## Evaluation

dataset/evaluate_dataset.py runs genuine inference against transformation-derived labels. Per-recording predictions, matches and timing are saved under docs/benchmarks. The small controlled corpus does not establish general accuracy on natural delivery. Unit tests measure software correctness, not acoustic accuracy.

## Clarity (provider 3.1)

clarity_analysis.py calculates exact word-edit distance and maps recognition disagreements back to confirmed CTC word intervals. The score is 100 Ã— (1 âˆ’ min(1, max(0, participant WER âˆ’ reference WER))). It requires at least eight normalized words and reference WER â‰¤ 25%. Phrase flags use non-overlapping six-word groups, at least four normalized tokens, â‰¥20 percentage points local excess and â‰¥10 points global excess. The threshold is fixed independently of the noise verification corpus. Pacing/pausing are not reused as clarity deductions.

The result includes a typed clarity measurement with recognized texts, substitutions/deletions/insertions, raw WER, formula identity, baseline gates and availability reason. JSON and PDF exports preserve these values; the UI shows them next to the score. Scores and edit-count consistency are validated before persistence. Recognition caches are content/configuration keyed. Disabling clarity avoids its extra ASR inference.

This is ASR recoverability, not human intelligibility, pronunciation grading or accent assessment. WER can exceed 100% through insertions; the displayed score stays bounded. Model errors and differences in recording conditions can affect it. A poor baseline returns unavailable. The frozen delivery benchmark disables clarity because its labels cover acoustic delivery edits; noise sensitivity is verified separately with scripts/verify_clarity.py.

WER definition: https://huggingface.co/learn/audio-course/en/chapter5/evaluation. ASR decoding: https://github.com/SYSTRAN/faster-whisper.

## Draft reliability safeguard (3.1.1)

Draft transcription enables word timestamps and Faster-Whisper hallucination_silence_threshold=1.0. Since temperature is fixed at zero, the library compression threshold may detect a failure yet still return the last output. A final guard checks individual segments and their combined output: at least 40 words, compression ratio >3.0, more than half of five-word n-grams repeated, and at least one n-gram appearing four times. The combined check prevents repetition split across short decoder segments from bypassing validation. This reliability gate flags uncertainty; it is not a claim that all repetition is invalid speech. It returns a safe failed-job message and retains the manual reviewed-transcript workflow. Recognition used for the reference-relative clarity measurement has its separately documented fixed configuration.

A private microphone recording exposed this reliability failure despite clear playback confirmed by the user. Independent resampling agreed with the decoder (correlation 0.99984). Smaller models, speech crops and preprocessing were diagnostic checks, not evidence of exact transcript accuracy. Private recordings and diagnostic transcripts are excluded from the submission package.

## Draft fallback (3.1.2)

Persisted draft jobs retry empty or UNRELIABLE_TRANSCRIPT output with TRANSCRIPTION_FALLBACK_MODEL (default medium). Other inference errors retain the failure path. The worker checks cancellation/timeouts before starting the second pass and again before saving it. Only successful output changes the stored model_name to the actual fallback model; confirmed recording metadata is never overwritten.

The medium model is pinned to Systran/faster-whisper-medium revision 08e178d48790749d25932bbc082711ddcfdfbc4f. Its model.bin SHA-256 is 9b45e1009dcc4ab601eff815b61d80e60ce3fd8c74c1a14f4a282258286b51ae. Runtime verifies this hash before loading and uses the local snapshot without a network lookup when complete. First setup caches approximately 1.53 GB of fallback weights. The English language constraint remains in effect; automatic language guesses were unstable on the microphone sample and were not promoted into the English analysis workflow.

The full 50.98-second private microphone file completed through the fallback with a 29-word editable draft in 58.69 seconds. It recovered microphone-testing English utterances, but exact whole-recording accuracy and recovery of the originally prescribed test sentence were not established. Review against the full recording remains required. Three public reference controls yielded WER 2.70%, 0% and 2.63%; results and timings are in docs/benchmarks/fallback-asr-verification.json. The fallback is used for draft jobs only. Clarity recognition remains base.en with its documented fixed configuration and cached benchmark identities.

## Independent draft default (3.1.3)

Four fixed, newly downloaded LibriSpeech validation clips were each transcribed three times through the actual API (12 jobs per model). Draft WER fell from 4.82% with base.en to 3.61% with medium. Repeats were identical for every clip. The conservative comparison counts Mr. versus MISTER as substitutions; one proper-name spelling remains wrong. No gold transcript was supplied to recognition. This is a clean, one-reader sample check, not universal accuracy or an assurance of absence from upstream training.

TRANSCRIPTION_MODEL=medium selects the higher-accuracy draft default; ASR_MODEL=base.en preserves clarity recognition and its cache signature. TRANSCRIPTION_FALLBACK_MODEL=medium only performs a retry when a different primary draft model is selected. A completed job records its actual model. Switching participant recordings clears transcript text so old words cannot be submitted against new audio.
