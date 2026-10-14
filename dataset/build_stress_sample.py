"""Supplementary combined severe-delivery stress case from the bundled training reference."""

from pathlib import Path
import sys
import json
import hashlib
import numpy as np
import soundfile as sf
import librosa
import parselmouth

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import evaluator


def main():
    source = ROOT / "dataset/contrastive/reagan_challenger_1986-opening"
    output = ROOT / "dataset/stress_samples"
    output.mkdir(exist_ok=True)
    text = (source / "transcript.txt").read_text().strip()
    words = evaluator.align_audio(str(source / "reference.wav"), text)
    audio, sr = sf.read(source / "reference.wav", dtype="float32")
    pitch_start, pitch_end = words[4].start, words[17].end
    a, b = round(pitch_start * sr), round(pitch_end * sr)
    sound = parselmouth.Sound(audio[a:b], sampling_frequency=sr)
    manipulation = parselmouth.praat.call(sound, "To Manipulation", 0.01, 65, 600)
    tier = parselmouth.praat.call(manipulation, "Extract pitch tier")
    n = parselmouth.praat.call(tier, "Get number of points")
    values = [
        parselmouth.praat.call(tier, "Get value at index", i) for i in range(1, n + 1)
    ]
    times = [
        parselmouth.praat.call(tier, "Get time from index", i) for i in range(1, n + 1)
    ]
    median = float(np.median(values))
    parselmouth.praat.call(tier, "Remove points between", 0, sound.duration)
    for t, v in zip(times, values):
        parselmouth.praat.call(tier, "Add point", t, median * (v / median) ** 0.03)
    parselmouth.praat.call([tier, manipulation], "Replace pitch tier")
    changed = parselmouth.praat.call(
        manipulation, "Get resynthesis (overlap-add)"
    ).values[0]
    audio[a:b] = np.pad(changed[: b - a], (0, max(0, b - a - len(changed))))
    energy_start, energy_end = words[36].start, words[59].end
    audio[round(energy_start * sr) : round(energy_end * sr)] *= 0.15
    rate = 1.5
    audio = librosa.effects.time_stretch(audio, rate=rate)
    annotations = [
        dict(
            flaw_type="rushed_pacing",
            start_seconds=words[0].start / rate,
            end_seconds=words[-1].end / rate,
            severity=5,
        ),
        dict(
            flaw_type="monotone_delivery",
            start_seconds=pitch_start / rate,
            end_seconds=pitch_end / rate,
            severity=5,
        ),
        dict(
            flaw_type="low_energy",
            start_seconds=energy_start / rate,
            end_seconds=energy_end / rate,
            severity=5,
        ),
    ]
    insertions = []
    for index, seconds in [(11, 2.8), (43, 3.0)]:
        position = (words[index].end + words[index + 1].start) / (2 * rate)
        insertions.append(
            (position, seconds, words[index].end / rate, words[index + 1].start / rate)
        )
    # Apply from right to left so source-time insertion coordinates remain valid.
    for position, seconds, left, right in sorted(insertions, reverse=True):
        sample = round(position * sr)
        audio = np.concatenate(
            [
                audio[:sample],
                np.zeros(round(seconds * sr), dtype="float32"),
                audio[sample:],
            ]
        )

    def mapped(t):
        return t + sum(
            seconds for position, seconds, _, _ in insertions if t > position
        )

    for item in annotations:
        item["start_seconds"] = mapped(item["start_seconds"])
        item["end_seconds"] = mapped(item["end_seconds"])
    for position, seconds, left, right in insertions:
        offset = sum(s for p, s, _, _ in insertions if p < position)
        annotations.append(
            dict(
                flaw_type="awkward_pause",
                start_seconds=left + offset,
                end_seconds=right + offset + seconds,
                severity=4,
            )
        )
    path = output / "combined-severe.wav"
    sf.write(path, audio, sr, subtype="PCM_16")
    (output / "transcript.txt").write_text(text + "\n")
    metadata = dict(
        id="combined-severe-training-stress",
        source_id="reagan_challenger_1986",
        split="training",
        reference_file="../contrastive/reagan_challenger_1986-opening/reference.wav",
        audio_file="combined-severe.wav",
        transcript=text,
        annotations=annotations,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        transformations=dict(
            global_pace=rate,
            pitch_variation_ratio=0.03,
            local_gain=0.15,
            inserted_pauses=[2.8, 3.0],
        ),
        ground_truth_source="known_controlled_edits",
        benchmark_role="Supplementary training stress case, excluded from the frozen 70-file accuracy benchmark.",
    )
    (output / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    report = evaluator.evaluate(
        str(source / "reference.wav"),
        str(path),
        text,
        output_path=str(output / "evaluation.json"),
    )
    print(
        "Combined stress score:",
        report["scores"],
        "flaws:",
        len(report["flaw_regions"]),
        flush=True,
    )


if __name__ == "__main__":
    main()
