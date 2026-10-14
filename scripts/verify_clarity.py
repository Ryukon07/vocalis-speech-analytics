"""Reproducible clarity checks on three source-held-out speech excerpts.

Known noise edits test ASR recoverability, not human intelligibility accuracy.
"""

from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from speech_runtime import recognize_for_clarity
from clarity_analysis import compare_recognition


def main():
    corpus = ROOT / "dataset/contrastive"
    manifest = json.loads((corpus / "manifest.json").read_text())
    destination = ROOT / "dataset/clarity"
    destination.mkdir(exist_ok=True)
    results = []
    for split in ["training", "validation", "testing"]:
        group = next(g for g in manifest["groups"] if g["split"] == split)
        reference = corpus / group["reference"]["audio_file"]
        text = recognize_for_clarity(reference, cache_dir=ROOT / "model-artifacts")
        samples, rate = sf.read(reference, dtype="float32")
        rms = float(np.sqrt(np.mean(samples**2)))
        noise = np.random.default_rng(20261014).normal(size=len(samples))
        noise /= np.sqrt(np.mean(noise**2))
        for snr in [None, 10, 0, -5]:
            if snr is None:
                path = reference
            else:
                path = destination / f"{group['id']}-noise-{snr}db.wav"
                noisy = samples + noise * rms / (10 ** (snr / 20))
                # Prevent introduced clipping; recognition sees the same signal-to-noise ratio.
                noisy = noisy / max(1.0, float(np.max(np.abs(noisy))) / 0.98)
                sf.write(path, noisy, rate, subtype="PCM_16")
            recognized = recognize_for_clarity(path, cache_dir=ROOT / "model-artifacts")
            measurement, _ = compare_recognition(group["transcript"], text, recognized)
            row = dict(
                group_id=group["id"],
                split=split,
                source_id=group["source_id"],
                snr_db=snr,
                audio_file=str(path.relative_to(ROOT)).replace("\\", "/"),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                measurement=measurement,
            )
            results.append(row)
            print(
                split,
                snr,
                "score",
                measurement["score"],
                "reference WER",
                measurement["reference"]["word_error_rate"],
                "participant WER",
                measurement["participant"]["word_error_rate"],
                flush=True,
            )
    controls = [r for r in results if r["snr_db"] is None]
    assert all(
        r["measurement"]["available"] and r["measurement"]["score"] == 100
        for r in controls
    )
    noisy = [r for r in results if r["snr_db"] == -5]
    assert np.mean(
        [r["measurement"]["participant"]["word_error_rate"] for r in noisy]
    ) > np.mean([r["measurement"]["participant"]["word_error_rate"] for r in controls])
    report = dict(
        provider_version="3.1.0-local.1",
        method="reference_relative_wer_v1",
        seed=20261014,
        interpretation="Controlled noise sensitivity only; no human clarity correlation has been measured.",
        cases=results,
    )
    (ROOT / "docs/benchmarks/clarity-verification.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (destination / "README.md").write_text(
        "# Clarity verification samples\n\nNine deterministic additive-noise variants (10, 0, -5 dB SNR) of three corpus excerpts, one per source-isolated split. Originals and confirmed transcripts remain in dataset/contrastive. Noise edits use NumPy seed 20261014; samples are gain scaled to avoid clipping. These are separate from the frozen 70-variant delivery benchmark. Reproduce with scripts/verify_clarity.py. Results include hashes and independently recognized texts in docs/benchmarks/clarity-verification.json. This checks recognition sensitivity, not human intelligibility or accent fairness.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
