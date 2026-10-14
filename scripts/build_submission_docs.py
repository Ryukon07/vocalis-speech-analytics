"""Produce the six-page technical document and an actual saved analysis PDF."""

from pathlib import Path
import json
import sys
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
import httpx

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/submission"
OUTPUT.mkdir(parents=True, exist_ok=True)
styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="Body", fontName="Helvetica", fontSize=10, leading=15, spaceAfter=10
    )
)
styles.add(
    ParagraphStyle(
        name="SmallText", fontName="Helvetica", fontSize=8, leading=12, spaceAfter=8
    )
)
styles["Title"].textColor = colors.HexColor("#203447")
styles["Heading1"].textColor = colors.HexColor("#203447")
styles["Heading2"].textColor = colors.HexColor("#158575")


def p(text, style="Body"):
    return Paragraph(escape(text), styles[style])


def table(rows, widths):
    value = Table(
        [[p(str(c), "SmallText") for c in row] for row in rows],
        colWidths=widths,
        hAlign="LEFT",
    )
    value.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7f2f1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#d7e2e7")),
            ]
        )
    )
    return value


def main():
    corpus = json.loads((ROOT / "dataset/contrastive/manifest.json").read_text())
    metrics = json.loads((ROOT / "docs/benchmarks/summary.json").read_text())
    story = [
        p("VOCALIS", "Title"),
        p("Contrastive speech analytics and temporal flaw grounding", "Heading1"),
        p(
            "Track C | Technical documentation | Local CPU edition 3.1.3 | 14 October 2026",
            "SmallText",
        ),
        Spacer(1, 16),
        p("1. System architecture", "Heading1"),
        p(
            "Vocalis compares the same spoken text in a reference and participant recording. It produces measured acoustic evidence, word timestamps, localized delivery deviations and a reproducible weighted rubric score."
        ),
        table(
            [
                ["Layer", "Implementation"],
                [
                    "Interface",
                    "React, TypeScript, TanStack Query, WaveSurfer, Recharts and accessible Radix dialogs. Microphone capture produces mono PCM WAV.",
                ],
                [
                    "API and persistence",
                    "FastAPI, Pydantic contracts, SQLAlchemy and Alembic; SQLite WAL for local use. Audio and feature artifacts use managed UUID storage keys.",
                ],
                [
                    "Transcription",
                    "Pinned, checksum-verified Faster-Whisper medium/int8 drafts on CPU. Independent clarity retains base.en. VAD and a repetition guard reduce unreliable output. Actual model identity is stored; drafts require review.",
                ],
                [
                    "Alignment",
                    "Pretrained wav2vec2 base 960h emissions with CTC forced alignment; original punctuation stays attached to each word. No synthetic timestamps.",
                ],
                [
                    "Acoustics",
                    "pYIN F0, median-centered semitones, RMS/dB energy, MFCCs, spectral centroid, word articulation rate and inter-word pauses.",
                ],
                [
                    "Jobs",
                    "Persisted asynchronous analysis/transcription jobs. Shared inference lock bounds memory. Cancellation/timeouts discard late output.",
                ],
            ],
            [100, 395],
        ),
        Spacer(1, 12),
        p(
            "Flow: record/upload -> generate and confirm transcript -> select same-text reference -> align both recordings -> extract features -> compare corresponding passages -> persist evidence -> inspect and export."
        ),
        PageBreak(),
        p("2. Dataset construction", "Heading1"),
        p(
            f"The bundled corpus contains {len(corpus['groups'])} reference excerpts and {sum(len(g['variants']) for g in corpus['groups'])} controlled variants from three attributed source speeches by two speakers."
        ),
        table(
            [
                ["Source", "Split", "Excerpts"],
                ["Reagan, Challenger address (1986)", "Training", "4"],
                ["Reagan, farewell address (1989)", "Validation", "3"],
                ["Eisenhower, farewell address (1961)", "Testing", "3"],
            ],
            [270, 115, 110],
        ),
        Spacer(1, 12),
        p(
            "Published transcripts were compared with ASR output to identify complete passages. Explicit selection ranges prevent repeated words elsewhere in a speech from extending an excerpt. Numbers are spelled out for the English alignment alphabet. WAV files are mono, 16 kHz, PCM 16-bit."
        ),
        p(
            "Each excerpt has seven variants: no injected delivery flaw with a small global gain change; mild and severe local rushing; local slowing; inserted mid-phrase silence; local attenuation; and compressed pitch variation via Praat overlap-add resynthesis."
        ),
        p(
            "Time stretching preserves pitch. Insertion and stretching record exact piecewise time mappings; attenuation and pitch edits preserve duration. Labels store the modified interval, flaw type, severity and transformation parameters. SHA-256 hashes verify every audio file."
        ),
        p(
            "Ground truth is transformation-derived. Word alignment is model-generated. Neither is represented as human-reviewed rhetorical quality. The unmodified reference is a contrastive baseline, not a universally perfect delivery."
        ),
        p(
            "Source IDs keep all excerpts and variants of a source speech in the same split, in both the manifest and API. Reagan appears in training and validation; Eisenhower is held out by speaker for testing. This is a small controlled corpus, not a diverse natural-performance benchmark."
        ),
        p(
            "Sources and recording-specific rights notes are retained in dataset/reference_speeches/sources.json and the corpus manifest. The official Eisenhower Library recording is the acquisition source for that speech. Existing Reagan originals are attributed to their archive pages."
        ),
        PageBreak(),
        p("3. Features and temporal grounding", "Heading1"),
        p(
            "Pitch: pYIN estimates voiced F0 between 65 and 600 Hz. F0 is converted to semitones with 12 log2(F0/440) + 69. The speaker median is subtracted to remove vocal-register differences without dividing away expressive variation. Unvoiced samples remain unavailable, not zero."
        ),
        p(
            "Energy: E = 20 log10(max(RMS, epsilon)). Subtracting the speech-active median compensates for recording gain. Word intervals distinguish quiet spoken words from pauses, so a low-energy flaw is not discarded by an absolute silence threshold."
        ),
        p(
            "Correspondence: a sequence match maps normalized reference words to participant words. Start/end anchors form a monotonic piecewise map from participant time to reference time. Reference curves are sampled through this map, with unavailable values outside supported bounds."
        ),
        p(
            "Pacing: overlapping four-word phrases compare articulation rates computed from actual word durations. Long pauses are evaluated separately. Overlapping pacing flags are merged and their evidence recomputed over the resulting passage."
        ),
        p(
            "Pitch and energy: windows are real participant-time intervals. Pitch IQR is compared across jointly voiced frames, reducing sensitivity to isolated octave-tracking errors. Low-energy windows compare normalized dB over spoken words. Window evidence remains tied to its actual measured interval."
        ),
        p(
            "Pauses: corresponding adjacent word boundaries are matched by sequence position, including repeated words. Candidate gaps are compared with the same boundary in the reference, with separate sentence-boundary tolerances."
        ),
        p(
            "MFCC 2 and spectral centroid add inspectable context. Clarity independently recognizes both recordings without a transcript prompt, then measures normalized word errors. Extra phrase errors are mapped to confirmed CTC word intervals; they are recognition disagreements, not phoneme diagnoses."
        ),
        p(
            "Every flaw stores the measured reference/participant values, delta, units, interval, severity, excerpt and a rule-derived explanation. Detection confidence remains unavailable until independently calibrated."
        ),
        PageBreak(),
        p("4. Scoring and reproducibility", "Heading1"),
        p(
            "The Complete delivery with clarity rubric weights pacing 25%, pitch 20%, energy 20%, pausing 15% and clarity 20%. Every job stores its rubric snapshot; historical four-category rubrics remain unchanged."
        ),
        p(
            "Acoustic delivery dimensions start at 100. A flaw deduction is base_weight x severity_multiplier x duration_fraction x 5. The duration fraction uses the larger of participant and corresponding reference interval where available, avoiding a smaller penalty merely because a rushed passage is shorter. Scores are bounded to [0,100]."
        ),
        p(
            "Severity multiplier = 0.7 + (severity - 1) x 0.325. Pacing severity derives from the log ratio of matched articulation rates; acoustic and pause severity use measured deviation magnitudes. Deductions and interval exposure are logged in the standalone report."
        ),
        p(
            "Clarity = 100 x (1 - min(1, max(0, participant WER - reference WER))). It requires at least eight normalized words and reference WER <= 25%; otherwise it is unavailable. WER is an ASR proxy affected by recording conditions and model bias, not calibrated human intelligibility. Website pacing and pausing deductions are separated. Overall = sum(weight x available enabled dimension score) / sum(available enabled weights). The backend independently checks this consistency before persistence. Unavailable pitch does not receive a perfect score."
        ),
        p(
            "Higher sensitivity narrows tolerated deviations. Default pace bounds are 70% and 130% of the reference, pitch spread ratio 0.40, energy deficit 12 dB, mid-phrase pause tolerance 1.5 seconds and sentence-boundary tolerance 2.5 seconds. Thresholds were revised with training examples before the final held-out evaluation."
        ),
        p(
            "Model versions, dependencies and CPU settings are pinned. ASR uses temperature zero and beam size five. Drafts additionally use word timestamps, silence hallucination handling and a final runaway-repetition guard. Alignment and acoustic caches are keyed by audio contents, transcript/model identity and feature configuration; cached data undergoes validation before reuse."
        ),
        p(
            "Replayable outputs include JSON, CSV, PDF, plots, word click-to-seek and spoken recommendations. A score is a documented relative heuristic, not a validated competition judging standard."
        ),
        PageBreak(),
        p("5. Verification and measured results", "Heading1"),
        p(
            "The frozen v3.0 delivery benchmark, excluding clarity, independently runs acoustic inference and forced alignment on each variant. A prediction matches a ground-truth edit when its type agrees and interval IoU is at least 0.25. Unmatched predictions are false positives; unmatched edit labels are false negatives."
        ),
        table(
            [["Split", "Files", "Precision", "Recall", "F1", "Boundary MAE (s)"]]
            + [
                [split, str(data["recordings"])]
                + [
                    ("N/A" if data[k] is None else f"{data[k]:.3f}")
                    for k in [
                        "precision",
                        "recall",
                        "f1",
                        "mean_boundary_error_seconds",
                    ]
                ]
                for split, data in metrics["results"].items()
                if split != "all"
            ],
            [95, 50, 85, 85, 85, 95],
        ),
        Spacer(1, 12),
        p(
            "Boundary error is the mean absolute start/end error for matched regions. A lenient IoU threshold is stated explicitly: it is not evidence of sub-word precision. Full per-recording predictions, matches, failures and elapsed times are saved under docs/benchmarks/."
        ),
        p(
            "Separate clarity checks use three source-isolated excerpts, three identical-audio controls and nine noise variants. Strongest-noise clarity scores were 43.2, 3.6 and 21.1; human rating correlation was not measured. A saved noisy website report scored clarity 83.6. The genuine localhost verification runs seven five-category website analyses spanning the variant spectrum, checks persisted participant-aligned curves and word timestamps, audio byte-range playback, JSON/CSV/PDF exports and a real transcription job."
        ),
        p(
            "Automated tests separately verify uploads, invalid inputs, storage cleanup, migrations, idempotency, rubric snapshots, job failure/retry/cancellation, transcription drafts, late-output rejection, source split isolation, result bounds, waveform seeking and the WAV encoder. Test counts and the latest production build are recorded in docs/VERIFICATION.md."
        ),
        p(
            "Final checks: 64 backend tests, 24 frontend tests and seven Chromium browser workflows passed, including real upload/transcription/inference, microphone worklet, settings, annotations, report controls/downloads and mobile layouts. Four fixed public LibriSpeech clips were transcribed three times per model: WER improved from 4.82% to 3.61%, with identical repeats. One reader and clean audio do not establish universal accuracy. Brave microphone playback and spoken feedback were human confirmed; simulated capture and headless print are separately labelled. The crashing legacy native pitch cache was replaced with a versioned cache and verified across restarts. Private microphone drafts still require review."
        ),
        PageBreak(),
        p("6. Local setup and operating limits", "Heading1"),
        p(
            "On Windows, use Python 3.12 and Node.js 24 LTS. Run setup-local.ps1 once, then start-local.ps1. Setup installs CPU-only model packages, applies migrations, imports the bundled corpus, builds the frontend and warms recognition and alignment models."
        ),
        p(
            "Website: http://127.0.0.1:5173. API: http://127.0.0.1:8000/api/v1. Models, recordings and database remain local. Internet is needed for the initial model/source downloads; cached inference does not require a paid API."
        ),
        p(
            "Local speech inputs are limited to three minutes to bound alignment memory. Short excerpts are recommended. Microphone capture uses an AudioWorklet and standard PCM WAV, avoiding browser-specific compressed recording formats. Browser microphone permission is required."
        ),
        p(
            "Background services are bound to loopback. Start scripts keep logs and owned process IDs under tmp/local-server. Run one backend server worker. Model inference is serialized to avoid competing memory-intensive jobs on the laptop."
        ),
        p(
            "Cancellation and timeout terminate the saved job state and reject late results; they do not forcibly interrupt a native model call. A hung call can occupy the local worker. A public/multi-user deployment requires process-isolated workers, authentication, retention controls and production reverse-proxy limits."
        ),
        p(
            "Docker files package the real runtime and use persistent model/data volumes. Docker execution requires an installed Docker engine and is recorded separately from Windows verification."
        ),
        p(
            "Submission assets: this six-page document, the paired corpus and manifest, construction/evaluation scripts, code documentation, benchmark evidence and a demonstration storyboard. GitHub and YouTube publication require the user account destinations; no credentials or private audio are published automatically."
        ),
        p(
            "Primary WER reference: huggingface.co/learn/audio-course/en/chapter5/evaluation. Model references: github.com/SYSTRAN/faster-whisper; docs.pytorch.org/audio/2.8/tutorials/ctc_forced_alignment_api_tutorial.html. The pinned TorchAudio 2.8 API is deprecated upstream; upgrading beyond this version requires replacing its forced-alignment API.",
            "SmallText",
        ),
    ]

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#546176"))
        canvas.drawString(44, 25, "Vocalis | Track C | Local CPU edition")
        canvas.drawRightString(A4[0] - 44, 25, f"{doc.page} / 6")

    doc = SimpleDocTemplate(
        str(OUTPUT / "technical-documentation.pdf"),
        pagesize=A4,
        leftMargin=44,
        rightMargin=44,
        topMargin=40,
        bottomMargin=42,
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    verification = json.loads(
        (ROOT / "docs/benchmarks/website-verification.json").read_text()
    )
    identifier = json.loads(
        (ROOT / "docs/benchmarks/clarity-website-result.json").read_text()
    )["analysis_id"]
    response = httpx.get(
        f"http://127.0.0.1:8000/api/v1/analyses/{identifier}/export/pdf", timeout=30
    )
    response.raise_for_status()
    (OUTPUT / "example-real-report.pdf").write_bytes(response.content)
    print("Created technical documentation and actual saved report.")


if __name__ == "__main__":
    main()
