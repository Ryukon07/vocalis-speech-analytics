"""Create a narrated walkthrough from real exported evidence, not a screen recording."""

from pathlib import Path
import json
import subprocess
import wave
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "tmp/walkthrough"
WORK.mkdir(parents=True, exist_ok=True)
OUTPUT = ROOT / "docs/submission"
OUTPUT.mkdir(parents=True, exist_ok=True)
BACKGROUND = "#101722"
TEXT = "#e7edf5"
MUTED = "#9bacc0"
GREEN = "#6ac9b6"
PURPLE = "#a89af0"
FONT = Path("C:/Windows/Fonts/segoeui.ttf")
BOLD = Path("C:/Windows/Fonts/segoeuib.ttf")
if not FONT.exists():
    FONT = Path("C:/Windows/Fonts/arial.ttf")
    BOLD = Path("C:/Windows/Fonts/arialbd.ttf")


def font(size, bold=False):
    return ImageFont.truetype(str(BOLD if bold else FONT), size)


def canvas(title, index):
    image = Image.new("RGB", (1280, 720), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text(
        (64, 32), "VOCALIS / SPEECH INTELLIGENCE", font=font(18, True), fill=GREEN
    )
    draw.text((64, 80), title, font=font(40, True), fill=TEXT)
    draw.line((64, 660, 1216, 660), fill="#344357", width=1)
    draw.text(
        (64, 678),
        "LOCAL CPU  |  Real exported measurements  |  Generated walkthrough",
        font=font(16),
        fill=MUTED,
    )
    draw.text((1160, 678), f"{index}/6", font=font(16), fill=MUTED)
    return image, draw


def lines(draw, text, xy, size=25, color=TEXT, width=74):
    x, y = xy
    for line in textwrap.wrap(text, width=width):
        draw.text((x, y), line, font=font(size), fill=color)
        y += size + 11
    return y


def chart(report, name, path):
    data = report["time_series_data"]
    feature = "pitch" if name == "pitch" else "energy"
    key = "f0_semitones" if name == "pitch" else "energy_db"
    fig, ax = plt.subplots(figsize=(11.52, 4.2), dpi=100)
    fig.patch.set_facecolor(BACKGROUND)
    ax.set_facecolor(BACKGROUND)
    for role, color, label in [
        ("baseline", GREEN, "Reference"),
        ("candidate", PURPLE, "Participant"),
    ]:
        times = data[f"{role}_{feature}_timestamps"]
        values = [np.nan if v is None else v for v in data[f"{role}_{key}"]]
        ax.plot(times, values, color=color, label=label, lw=1.8)
    for flaw in report["flaw_regions"]:
        if (name == "pitch" and flaw["flaw_type"] == "monotone_delivery") or (
            name == "energy" and flaw["flaw_type"] == "low_energy"
        ):
            ax.axvspan(
                flaw["start_time"], flaw["end_time"], color="#e47f91", alpha=0.18
            )
    ax.set_xlabel("Participant time (seconds)", color=MUTED)
    ax.set_ylabel(
        "Centered pitch (semitones)" if name == "pitch" else "Normalized energy (dB)",
        color=MUTED,
    )
    ax.tick_params(colors=MUTED, labelsize=12)
    ax.grid(alpha=0.12)
    for spine in ax.spines.values():
        spine.set_color("#344357")
    legend = ax.legend(facecolor=BACKGROUND, edgecolor="#344357", fontsize=12)
    for item in legend.get_texts():
        item.set_color(TEXT)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    manifest = json.loads((ROOT / "dataset/contrastive/manifest.json").read_text())
    metrics = json.loads((ROOT / "docs/benchmarks/summary.json").read_text())
    pitch = json.loads(
        (
            ROOT / "docs/benchmarks/reagan_challenger_1986-opening-monotone.json"
        ).read_text()
    )
    energy = json.loads(
        (
            ROOT / "docs/benchmarks/reagan_challenger_1986-opening-low-energy.json"
        ).read_text()
    )
    narration = [
        "Welcome to Vocalis, a local speech delivery analytics project for Track C. The application compares a participant recording with a reference speaking the same text. It preserves the actual acoustic measurements behind each flagged region. The complete workflow includes microphone recording, editable local transcription, word alignment, a versioned scoring rubric, synchronized playback, plots and downloadable reports. Processing uses pretrained speech models on the laptop CPU. No paid transcription API or dedicated graphics card is required. This walkthrough shows genuine exported results from the completed local system. It is generated from saved evidence rather than being a live browser recording.",
        "The custom dataset contains ten reference excerpts and seventy controlled variants. Three source speeches by Reagan and Eisenhower provide matching transcripts and attributed provenance. Every excerpt has a spectrum of edits: mild and severe rushing, slowing, an inserted awkward pause, reduced energy, flattened pitch, and a recording with no injected delivery flaw. Ground truth comes from the exact transformation intervals and time mappings. Each audio file has a checksum. All excerpts of one original speech remain in the same dataset split. The held-out test speaker is Eisenhower. These controlled labels are precise edit records, not human judgments that a delivery is universally ideal.",
        "The local inference pipeline begins with Faster Whisper in eight-bit CPU mode and voice activity detection. Its output is an editable draft. After confirming the spoken words, a pretrained wav two vec model produces actual word timestamps with C T C forced alignment. Acoustic extraction measures pitch, energy, articulation rate, pauses, M F C C features and spectral centroid. Median centering compensates for differences in vocal register and recording gain. Matching word boundaries map the reference into the participant's clock. This allows the report to compare corresponding passages even when delivery timing differs, rather than placing unrelated moments on top of one another.",
        "This chart shows the actual pitch curves for a reference passage and a participant variant with intentionally reduced pitch variation. Green is the reference and purple is the participant. The shaded interval is the returned flaw region. The detector compares the interquartile range of centered semitone pitch over corresponding voiced frames. The report preserves both measurements and their difference, so the explanation can be checked mathematically. Users can click the flaw or a transcript word to replay that passage. Isolated pitch tracking errors are handled with a robust spread measure. Unavailable pitch is excluded from scoring rather than being mistaken for perfect delivery.",
        "Here the participant's energy has been reduced in a known local passage. Both recordings are normalized against their own speech-active median so a simple global recording gain change does not define a delivery flaw. The detector compares normalized decibel values inside aligned spoken-word windows. It retains quiet speech instead of discarding the very region being measured. Local pacing uses matching phrases, and pause detection compares corresponding adjacent words, including repeated words. The selected rubric converts measured deviations and their duration into documented deductions. Written recommendations, spoken feedback, and PDF, JSON and CSV downloads all use the same stored report.",
        "Verification separates software correctness from speech accuracy. All seventy controlled variants completed real inference without a failed recording. On the speaker-held-out testing split, precision was about seventy-three percent and recall about eighty-nine percent, with an F one score of zero point eight. Mean matched boundary error was approximately zero point two nine seconds. The complete regression suite and production build also pass. These results describe this small controlled corpus, not every natural speech style or accent. The local website is available at one twenty seven dot zero dot zero dot one, port five one seven three. Start with a bundled reference, confirm the same text, and inspect the measured evidence.",
    ]
    image, draw = canvas("Speech feedback grounded in evidence", 1)
    lines(
        draw, "Record. Transcribe. Compare. Replay. Improve.", (64, 170), 32, width=60
    )
    for x, big, label in [
        (64, "2", "pretrained speech models"),
        (470, "80", "paired audio files"),
        (875, "CPU", "local processing"),
    ]:
        draw.rounded_rectangle((x, 290, x + 330, 480), radius=18, fill="#1b2637")
        draw.text((x + 24, 315), big, font=font(65, True), fill=GREEN)
        lines(draw, label, (x + 24, 410), 22, width=24)
    lines(
        draw,
        "Real acoustic measurements, saved rubric snapshots and actionable passage-level feedback.",
        (64, 535),
        24,
        color=MUTED,
        width=90,
    )
    image.save(WORK / "slide-1.png")
    image, draw = canvas("A custom good-to-bad delivery spectrum", 2)
    spectrum = [
        "Reference",
        "Near-perfect",
        "Mild rush",
        "Severe rush",
        "Slow",
        "Pause",
        "Low energy",
        "Monotone",
    ]
    for i, label in enumerate(spectrum):
        x = 64 + (i % 4) * 294
        y = 170 + (i // 4) * 115
        draw.rounded_rectangle((x, y, x + 272, y + 90), radius=12, fill="#1b2637")
        draw.text(
            (x + 16, y + 30), label, font=font(23, True), fill=GREEN if i < 2 else TEXT
        )
    lines(
        draw,
        "10 excerpts / 70 variants / shared transcripts / exact edit bounds / SHA-256 checksums",
        (64, 430),
        26,
        width=76,
    )
    lines(
        draw,
        "Training: Challenger | Validation: Reagan farewell | Testing: Eisenhower farewell",
        (64, 535),
        22,
        color=MUTED,
        width=86,
    )
    image.save(WORK / "slide-2.png")
    image, draw = canvas("Two models, one explainable comparison", 3)
    steps = [
        ("Record / upload", "Standard PCM microphone capture"),
        ("Generate / confirm", "Faster-Whisper base.en / CPU int8"),
        ("Align the words", "wav2vec2 / real CTC word timestamps"),
        ("Measure / compare", "Pitch, energy, pace, pauses, MFCCs"),
        ("Save / replay / export", "Aligned plots and measured flaw evidence"),
    ]
    for i, (name, detail) in enumerate(steps):
        y = 165 + i * 88
        draw.rounded_rectangle((64, y, 1216, y + 70), radius=12, fill="#1b2637")
        draw.text((86, y + 19), name, font=font(23, True), fill=GREEN)
        draw.text((430, y + 21), detail, font=font(22), fill=TEXT)
    image.save(WORK / "slide-3.png")
    for index, title, report, name in [
        (4, "Detecting a local loss of vocal expression", pitch, "pitch"),
        (5, "Finding the passage where energy fades", energy, "energy"),
    ]:
        image, draw = canvas(title, index)
        plot = WORK / f"{name}-chart.png"
        chart(report, name, plot)
        image.paste(Image.open(plot), (64, 155))
        flaw = next(
            f
            for f in report["flaw_regions"]
            if f["flaw_type"]
            == ("monotone_delivery" if name == "pitch" else "low_energy")
        )
        evidence = flaw["evidence"]
        label = f"Flagged {flaw['start_time']:.2f}-{flaw['end_time']:.2f}s | Reference {evidence['baseline_value']:.2f} | Participant {evidence['participant_value']:.2f} {evidence['units']}"
        lines(draw, label, (64, 590), 22, color=MUTED, width=100)
        image.save(WORK / f"slide-{index}.png")
    image, draw = canvas("Verified locally, with measured limits", 6)
    test = metrics["results"]["testing"]
    for x, value, label in [
        (64, f"{test['precision']:.1%}", "test precision"),
        (470, f"{test['recall']:.1%}", "test recall"),
        (875, f"{test['mean_boundary_error_seconds']:.2f}s", "boundary error"),
    ]:
        draw.rounded_rectangle((x, 185, x + 330, 370), radius=18, fill="#1b2637")
        draw.text((x + 24, 210), value, font=font(56, True), fill=GREEN)
        draw.text((x + 24, 305), label, font=font(23), fill=TEXT)
    lines(
        draw,
        "70 / 70 real inferences completed. Software regressions and production build pass.",
        (64, 410),
        27,
        width=82,
    )
    lines(
        draw,
        "Controlled edits in a small corpus; broader natural-speech evaluation remains necessary.",
        (64, 505),
        23,
        color=MUTED,
        width=93,
    )
    draw.text(
        (64, 590),
        "Open locally: http://127.0.0.1:5173",
        font=font(26, True),
        fill=PURPLE,
    )
    image.save(WORK / "slide-6.png")
    (WORK / "narration.json").write_text(json.dumps(narration), encoding="utf-8")
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-File",
            str(ROOT / "scripts/synthesize_walkthrough.ps1"),
            "-WorkDirectory",
            str(WORK),
        ],
        check=True,
    )
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    segments = []
    for index in range(1, 7):
        audio = WORK / f"narration-{index}.wav"
        with wave.open(str(audio)) as w:
            duration = max(32, w.getnframes() / w.getframerate() + 1)
        target = WORK / f"segment-{index}.mp4"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-loop",
                "1",
                "-framerate",
                "15",
                "-i",
                str(WORK / f"slide-{index}.png"),
                "-i",
                str(audio),
                "-vf",
                "format=yuv420p",
                "-af",
                "apad",
                "-t",
                str(duration),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "22",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(target),
            ],
            check=True,
        )
        segments.append(target)
    concat = WORK / "segments.txt"
    concat.write_text("\n".join("file '" + p.as_posix() + "'" for p in segments))
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(OUTPUT / "vocalis-walkthrough.mp4"),
        ],
        check=True,
    )
    transcript = "\n\n".join(f"{i+1}. {text}" for i, text in enumerate(narration))
    (OUTPUT / "walkthrough-transcript.txt").write_text(transcript, encoding="utf-8")
    print("Narrated walkthrough created:", OUTPUT / "vocalis-walkthrough.mp4")


if __name__ == "__main__":
    main()
