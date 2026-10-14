"""Build a reproducible controlled contrastive corpus from attributed public speeches.

Ground truth describes known edits, not human judgments. Word labels come from
wav2vec2 alignment. Original speech style is a contrastive reference, not a certified
universal ideal. Keep all excerpts of a source speech in one split.
"""

from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict
from difflib import SequenceMatcher
import numpy as np
import soundfile as sf
import librosa
import parselmouth

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import evaluator

CORPUS = ROOT / "dataset" / "contrastive"
SOURCES = ROOT / "dataset" / "reference_speeches"

EXCERPTS = [
    (
        "reagan_challenger_1986",
        "opening",
        "Ladies and gentlemen, I'd planned to speak to you tonight to report on the state of the Union, but the events of earlier today have led me to change those plans. Today is a day for mourning and remembering. Nancy and I are pained to the core by the tragedy of the shuttle Challenger. We know we share this pain with all of the people of our country. This is truly a national loss.",
    ),
    (
        "reagan_challenger_1986",
        "courage",
        "Nineteen years ago, almost to the day, we lost three astronauts in a terrible accident on the ground. But we've never lost an astronaut in flight; we've never had a tragedy like this. And perhaps we've forgotten the courage it took for the crew of the shuttle. But they, the Challenger Seven, were aware of the dangers, but overcame them and did their jobs brilliantly.",
    ),
    (
        "reagan_challenger_1986",
        "families",
        "For the families of the seven, we cannot bear, as you do, the full impact of this tragedy. But we feel the loss, and we're thinking about you so very much. Your loved ones were daring and brave, and they had that special grace, that special spirit that says, Give me a challenge, and I'll meet it with joy.",
    ),
    (
        "reagan_challenger_1986",
        "discovery",
        "They had a hunger to explore the universe and discover its truths. They wished to serve, and they did. They served all of us. We've grown used to wonders in this century. It's hard to dazzle us.",
    ),
    (
        "reagan_farewell_1989",
        "opening",
        "This is the thirty fourth time I'll speak to you from the Oval Office, and the last. We've been together eight years now, and soon it'll be time for me to go. But before I do, I wanted to share some thoughts, some of which I've been saving for a long time.",
    ),
    (
        "reagan_farewell_1989",
        "gratitude",
        "It's been the honor of my life to be your President. So many of you have written the past few weeks to say thanks, but I could say as much to you. Nancy and I are grateful for the opportunity you gave us to serve.",
    ),
    (
        "reagan_farewell_1989",
        "parting",
        "People ask how I feel about leaving. And the fact is, parting is such sweet sorrow. The sweet part is California and the ranch and freedom. The sorrow, the goodbyes, of course, and leaving this beautiful place.",
    ),
    (
        "eisenhower_farewell_1961",
        "transition",
        "Three days from now, after half a century in the service of our country, I shall lay down the responsibilities of office as, in traditional and solemn ceremony, the authority of the Presidency is vested in my successor.",
    ),
    (
        "eisenhower_farewell_1961",
        "farewell",
        "This evening I come to you with a message of leave-taking and farewell, and to share a few final thoughts with you, my countrymen. Like every other citizen, I wish the new President, and all who will labor with him, Godspeed. I pray that the coming years will be blessed with peace and prosperity for all.",
    ),
    (
        "eisenhower_farewell_1961",
        "agreement",
        "Our people expect their President and the Congress to find essential agreement on issues of great moment, the wise resolution of which will better shape the future of the Nation.",
    ),
]

EXCERPT_RANGES = {
    "reagan_challenger_1986-opening": (0, 25),
    "reagan_challenger_1986-courage": (24, 49),
    "reagan_challenger_1986-families": (66, 87),
    "reagan_challenger_1986-discovery": (86, 100),
    "reagan_farewell_1989-opening": (2, 17),
    "reagan_farewell_1989-gratitude": (17, 32),
    "reagan_farewell_1989-parting": (57, 73),
    "eisenhower_farewell_1961-transition": (21, 40),
    "eisenhower_farewell_1961-farewell": (39, 65),
    "eisenhower_farewell_1961-agreement": (65, 79),
}


def normalize(word):
    return re.sub(r"[^a-z']", "", word.lower())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_audio(path, audio):
    sf.write(path, audio, 16000, subtype="PCM_16")
    return dict(
        audio_file=str(path.relative_to(CORPUS)).replace("\\", "/"),
        sha256=digest(path),
        duration_seconds=round(len(audio) / 16000, 5),
    )


def replace_segment(audio, start, end, replacement):
    a, b = round(start * 16000), round(end * 16000)
    return np.concatenate([audio[:a], replacement, audio[b:]])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="+", help="Excerpt IDs, for incremental rebuilding")
    ap.add_argument(
        "--from-paired",
        action="store_true",
        help="Rebuild variants from the bundled reference excerpts, without full originals",
    )
    args = ap.parse_args()
    CORPUS.mkdir(parents=True, exist_ok=True)
    sources = {
        s["id"]: s
        for s in json.loads((SOURCES / "sources.json").read_text())["speeches"]
    }
    manifest_path = CORPUS / "manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    groups = {g["id"]: g for g in old.get("groups", [])}
    for source, name, transcript in EXCERPTS:
        ident = source + "-" + name
        if args.only and ident not in args.only:
            continue
        folder = CORPUS / ident
        folder.mkdir(exist_ok=True)
        original = SOURCES / "wav" / f"{source}.wav"
        if args.from_paired or not original.exists():
            if ident not in groups:
                raise ValueError(
                    f"{ident}: obtain the source original or provide the bundled paired corpus."
                )
            prior = groups[ident]
            reference_path = CORPUS / prior["reference"]["audio_file"]
            if digest(reference_path) != prior["reference"]["sha256"]:
                raise ValueError(f"{ident}: reference checksum mismatch")
            audio, sr = sf.read(reference_path, dtype="float32")
            start, end = prior["source_start_seconds"], prior["source_end_seconds"]
            coverage = prior["source_transcript_match_ratio"]
        else:
            full, sr = sf.read(original, dtype="float32")
            segments = json.loads(
                (SOURCES / "transcripts" / f"{source}-segments.json").read_text()
            )
            recognized = [w for s in segments for w in s["words"]]
            lower, upper = EXCERPT_RANGES[ident]
            recognized = [
                w
                for w in recognized
                if w["start"] >= lower - 0.3 and w["end"] <= upper + 0.3
            ]
            matcher = SequenceMatcher(
                None,
                [normalize(w) for w in transcript.split()],
                [normalize(w["word"]) for w in recognized],
                autojunk=False,
            )
            matches = [
                (i + k, j + k)
                for i, j, n in matcher.get_matching_blocks()
                for k in range(n)
            ]
            coverage = len(matches) / len(transcript.split())
            if coverage < 0.72:
                raise ValueError(
                    f"{ident}: source transcript could not be matched ({coverage:.0%})"
                )
            first = max(0, matches[0][1] - matches[0][0])
            last = min(
                len(recognized) - 1,
                matches[-1][1] + len(transcript.split()) - 1 - matches[-1][0],
            )
            start = max(0, recognized[first]["start"] - 0.12)
            end = recognized[last]["end"] + 0.12
            audio = full[round(start * sr) : round(end * sr)]
        assert sr == 16000
        text_path = folder / "transcript.txt"
        text_path.write_text(transcript + "\n", encoding="utf-8")
        baseline_path = folder / "reference.wav"
        baseline = save_audio(baseline_path, audio)
        print(ident, "aligning reference", round(end - start, 2), "seconds", flush=True)
        config = evaluator.EvaluatorConfig()
        words = evaluator.align_audio(str(baseline_path), transcript, config=config)
        (folder / "reference-alignment.json").write_text(
            json.dumps([asdict(w) for w in words], indent=2)
        )
        # A phrase in the first half is edited; speech elsewhere stays intact.
        left = max(3, len(words) // 4)
        right = min(len(words) - 3, left + 8)
        a, b = words[left].start, words[right - 1].end
        original = audio[round(a * sr) : round(b * sr)]
        variants = []
        edits = [
            ("near-perfect", 1, None, 1.0),
            ("rushed-mild", 2, "rushed_pacing", 1.35),
            ("rushed-severe", 5, "rushed_pacing", 1.8),
            ("slow", 4, "slow_pacing", 0.6),
            ("pause", 4, "awkward_pause", 2.2),
            ("low-energy", 4, "low_energy", 0.08),
            ("monotone", 4, "monotone_delivery", 0.03),
        ]
        for label, severity, flaw_type, amount in edits:
            annotations = []
            if flaw_type in ["rushed_pacing", "slow_pacing"]:
                replacement = librosa.effects.time_stretch(original, rate=amount)
                result = replace_segment(audio, a, b, replacement)
                new_end = a + len(replacement) / sr
                annotations = [
                    dict(
                        flaw_type=flaw_type,
                        start_seconds=a,
                        end_seconds=new_end,
                        severity=severity,
                    )
                ]
                mapping = dict(
                    kind="piecewise_time_stretch",
                    start=a,
                    original_end=b,
                    modified_end=new_end,
                    rate=amount,
                )
            elif flaw_type == "awkward_pause":
                # Choose a mid-phrase inter-word gap, never a punctuation boundary.
                boundary = next(
                    i
                    for i in range(left, right - 1)
                    if not re.search(r"[.!?,;:]$", words[i].word)
                )
                position = (words[boundary].end + words[boundary + 1].start) / 2
                sample = round(position * sr)
                result = np.concatenate(
                    [
                        audio[:sample],
                        np.zeros(round(amount * sr), dtype=np.float32),
                        audio[sample:],
                    ]
                )
                annotations = [
                    dict(
                        flaw_type=flaw_type,
                        start_seconds=words[boundary].end,
                        end_seconds=words[boundary + 1].start + amount,
                        severity=severity,
                    )
                ]
                mapping = dict(kind="insert_silence", position=position, seconds=amount)
            elif flaw_type == "low_energy":
                result = audio.copy()
                result[round(a * sr) : round(b * sr)] *= amount
                annotations = [
                    dict(
                        flaw_type=flaw_type,
                        start_seconds=a,
                        end_seconds=b,
                        severity=severity,
                    )
                ]
                mapping = dict(
                    kind="gain",
                    start=a,
                    end=b,
                    gain=amount,
                    delta_db=20 * np.log10(amount),
                )
            elif flaw_type == "monotone_delivery":
                sound = parselmouth.Sound(original, sampling_frequency=sr)
                manipulation = parselmouth.praat.call(
                    sound, "To Manipulation", 0.01, 65, 600
                )
                tier = parselmouth.praat.call(manipulation, "Extract pitch tier")
                n = parselmouth.praat.call(tier, "Get number of points")
                values = [
                    parselmouth.praat.call(tier, "Get value at index", i)
                    for i in range(1, n + 1)
                ]
                if n < 4:
                    raise ValueError(
                        f"{ident}: insufficient pitch points for controlled flattening"
                    )
                median = float(np.median(values))
                times = [
                    parselmouth.praat.call(tier, "Get time from index", i)
                    for i in range(1, n + 1)
                ]
                parselmouth.praat.call(tier, "Remove points between", 0, sound.duration)
                for t, v in zip(times, values):
                    parselmouth.praat.call(
                        tier, "Add point", t, median * (v / median) ** amount
                    )
                parselmouth.praat.call([tier, manipulation], "Replace pitch tier")
                replacement = (
                    parselmouth.praat.call(
                        manipulation, "Get resynthesis (overlap-add)"
                    )
                    .values[0]
                    .astype(np.float32)
                )
                replacement = replacement[: len(original)]
                if len(replacement) < len(original):
                    replacement = np.pad(
                        replacement, (0, len(original) - len(replacement))
                    )
                result = replace_segment(audio, a, b, replacement)
                annotations = [
                    dict(
                        flaw_type=flaw_type,
                        start_seconds=a,
                        end_seconds=b,
                        severity=severity,
                    )
                ]
                mapping = dict(
                    kind="pitch_tier_compression",
                    start=a,
                    end=b,
                    variation_ratio=amount,
                )
            else:
                result = audio * 0.95
                mapping = dict(kind="global_gain", gain=0.95)
            path = folder / f"{label}.wav"
            metadata = save_audio(path, result)
            variants.append(
                dict(
                    id=ident + "-" + label,
                    title=label,
                    level=severity,
                    **metadata,
                    annotations=annotations,
                    transformation=mapping,
                    ground_truth_source="known_controlled_edit",
                    alignment_file=next(
                        (
                            v.get("alignment_file")
                            for v in groups.get(ident, {}).get("variants", [])
                            if v["id"] == ident + "-" + label
                            and v["sha256"] == metadata["sha256"]
                        ),
                        None,
                    ),
                )
            )
        source_data = sources[source]
        groups[ident] = dict(
            id=ident,
            title=source_data["title"] + " - " + name,
            source_id=source,
            speaker_id=source_data["speaker"],
            source_url=source_data["source_page"],
            split=(
                "training"
                if source == "reagan_challenger_1986"
                else "validation" if source == "reagan_farewell_1989" else "testing"
            ),
            source_start_seconds=start,
            source_end_seconds=end,
            source_transcript_match_ratio=round(coverage, 4),
            transcript_file=str(text_path.relative_to(CORPUS)).replace("\\", "/"),
            transcript=transcript,
            reference=baseline,
            reference_alignment_file=str(
                (folder / "reference-alignment.json").relative_to(CORPUS)
            ).replace("\\", "/"),
            license="U.S. public-domain government speech audio; archive reuse basis and supplied-file provenance documented in dataset/LICENSE_NOTES.md.",
            label_review="Controlled edit intervals are exact; word alignment is model-generated, not human reviewed.",
            variants=variants,
        )
        manifest = dict(
            version="1.0",
            sample_rate=16000,
            channels=1,
            seed=0,
            description="Controlled contrastive delivery corpus, with transformation-derived ground truth.",
            limitations=[
                "Two source speakers; same-speaker transformed variants are not a substitute for natural flawed recordings.",
                "Source-level holdout; Reagan occurs in training and validation, Eisenhower is speaker-held-out testing.",
                "Near-perfect means no injected flaw, not a human-certified perfect speech.",
            ],
            groups=list(groups.values()),
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(ident, "saved", len(variants), "variants", flush=True)


if __name__ == "__main__":
    main()
