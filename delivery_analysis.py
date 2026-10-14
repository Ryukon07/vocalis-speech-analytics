"""Text-constrained acoustic comparisons in the participant's actual clock."""

from difflib import SequenceMatcher
import re
import numpy as np


def token(text):
    return re.sub(r"[^a-z']", "", text.casefold())


def matched_words(baseline, candidate):
    matcher = SequenceMatcher(
        None,
        [token(w.word) for w in baseline],
        [token(w.word) for w in candidate],
        autojunk=False,
    )
    return [
        (baseline[i + k], candidate[j + k])
        for i, j, n in matcher.get_matching_blocks()
        for k in range(n)
    ]


def anchors(baseline, candidate):
    pairs = matched_words(baseline, candidate)
    if len(pairs) < max(2, 0.9 * len(candidate)):
        raise ValueError("Corresponding words could not be matched reliably.")
    points = sorted(
        (ct, bt) for b, c in pairs for ct, bt in [(c.start, b.start), (c.end, b.end)]
    )
    clean = []
    for ct, bt in points:
        if not clean or (ct > clean[-1][0] + 1e-6 and bt >= clean[-1][1]):
            clean.append((ct, bt))
    return np.asarray(clean), pairs


def mapped_feature(bl, cd, feature):
    points, _ = anchors(bl.words, cd.words)
    if feature == "pitch":
        times, values = bl.pitch_times, bl.f0_centered_st
        target = cd.pitch_times
    else:
        times, values = bl.energy_times, bl.energy_db_relative
        target = cd.energy_times
    source = np.interp(target, points[:, 0], points[:, 1])
    indices = np.clip(np.searchsorted(times, source), 0, len(times) - 1)
    output = np.asarray(values[indices], dtype=float).copy()
    output[(target < points[0, 0]) | (target > points[-1, 0])] = np.nan
    return target, output


def detect_delivery_flaws(bl, cd, config):
    points, pairs = anchors(bl.words, cd.words)
    flaws, warnings = [], [
        "Detection confidence is heuristic, not a calibrated probability."
    ]

    def emit(
        kind,
        start,
        end,
        severity,
        baseline,
        participant,
        units,
        measurement,
        threshold,
        recommendation,
        extra=None,
    ):
        difference = participant - baseline
        excerpt = " ".join(w.word for w in cd.words if w.end > start and w.start < end)
        flaws.append(
            dict(
                flaw_type=kind,
                start_time=round(float(start), 3),
                end_time=round(float(end), 3),
                severity=int(severity),
                confidence=None,
                description=f"{measurement.replace('_', ' ').capitalize()} differs from the matched reference.",
                causal_explanation=f"In the corresponding passage, participant {measurement.replace('_', ' ')} is "
                f"{participant:.2f} {units}; reference is {baseline:.2f} {units}. "
                f"Difference: {difference:+.2f} {units}. Detection threshold: {threshold:.2f} {units}.",
                evidence=dict(
                    baseline_value=round(float(baseline), 4),
                    participant_value=round(float(participant), 4),
                    absolute_deviation=round(float(difference), 4),
                    units=units,
                    measurement_name=measurement,
                    source="measured",
                    additional=extra or {},
                ),
                measured_value=float(participant),
                threshold=float(threshold),
                reference_value=float(baseline),
                transcript_excerpt=excerpt,
                recommendation=recommendation,
            )
        )

    # Pacing compares the same phrase; long silences are scored separately as pauses.
    groups = [pairs[i : i + 4] for i in range(0, len(pairs) - 2, 2)]
    for group in groups:
        if len(group) < 3:
            continue
        bw, cw = [p[0] for p in group], [p[1] for p in group]

        def articulation(words):
            return 60 * len(words) / max(0.2, sum(w.end - w.start for w in words))

        baseline, candidate = articulation(bw), articulation(cw)
        ratio = candidate / baseline
        if ratio > config.rushed_wpm_ratio or ratio < config.slow_wpm_ratio:
            rushed = ratio > 1
            severity = min(5, max(2, int(np.ceil(abs(np.log2(ratio)) * 5))))
            threshold = baseline * (
                config.rushed_wpm_ratio if rushed else config.slow_wpm_ratio
            )
            emit(
                "rushed_pacing" if rushed else "slow_pacing",
                cw[0].start,
                cw[-1].end,
                severity,
                baseline,
                candidate,
                "words/min",
                "phrase_articulation_rate",
                threshold,
                (
                    "Leave room for emphasis and slow this phrase."
                    if rushed
                    else "Build momentum through this phrase."
                ),
                {"reference_region_seconds": bw[-1].end - bw[0].start},
            )

    # Corresponding word boundaries are identified by sequence position, including repetitions.
    for (ba, ca), (bb, cb) in zip(pairs, pairs[1:]):
        b_gap, c_gap = max(0, bb.start - ba.end), max(0, cb.start - ca.end)
        sentence = bool(re.search(r"[.!?]$", ca.word))
        threshold = (
            config.sentence_boundary_max_sec if sentence else config.awkward_pause_sec
        )
        if c_gap >= threshold and c_gap > b_gap + 0.75:
            emit(
                "awkward_pause",
                ca.end,
                cb.start,
                min(5, max(2, int(c_gap))),
                b_gap,
                c_gap,
                "seconds",
                "pause_duration",
                threshold,
                "Connect these words smoothly while retaining intentional sentence pauses.",
                {
                    "baseline_boundary_matched": 1.0,
                    "sentence_boundary": float(sentence),
                },
            )

    # Each acoustic window is an actual time interval, never a count of DTW path cells.
    pitch_times, reference_pitch = mapped_feature(bl, cd, "pitch")
    energy_times, reference_energy = mapped_feature(bl, cd, "energy")
    start, stop = pairs[0][1].start, pairs[-1][1].end
    for t in np.arange(start, stop, config.window_step_sec):
        end = min(stop, t + config.window_sec)
        if end - t < 0.5:
            continue
        mask = (pitch_times >= t) & (pitch_times < end)
        bv, cv = reference_pitch[mask], cd.f0_centered_st[mask]
        voiced = np.isfinite(bv) & np.isfinite(cv)
        if voiced.sum() >= config.min_voiced_frames:
            # IQR is robust to isolated octave-tracking errors in historical audio.
            b_std = float(np.percentile(bv[voiced], 75) - np.percentile(bv[voiced], 25))
            c_std = float(np.percentile(cv[voiced], 75) - np.percentile(cv[voiced], 25))
            if (
                b_std >= config.min_baseline_semitone_std
                and c_std < b_std * config.monotone_std_ratio
            ):
                ratio = c_std / b_std
                emit(
                    "monotone_delivery",
                    t,
                    end,
                    4 if ratio < 0.2 else 3,
                    b_std,
                    c_std,
                    "semitones",
                    "pitch_interquartile_range",
                    b_std * config.monotone_std_ratio,
                    "Vary pitch on the important words in this passage.",
                    {"voiced_frames": float(voiced.sum())},
                )
        emask = (energy_times >= t) & (energy_times < end)
        be, ce = reference_energy[emask], cd.energy_db_relative[emask]
        # Word bounds retain quiet speech while excluding silences. A fixed noise floor
        # would incorrectly discard the very low-energy delivery being measured.
        word_mask = np.zeros(len(energy_times), dtype=bool)
        for word in cd.words:
            if word.end > t and word.start < end:
                word_mask |= (energy_times >= word.start) & (energy_times <= word.end)
        active = np.isfinite(be) & np.isfinite(ce) & word_mask[emask]
        if active.sum() >= 10:
            b_mean, c_mean = float(np.mean(be[active])), float(np.mean(ce[active]))
            deficit = b_mean - c_mean
            if deficit > config.energy_dip_db_threshold:
                emit(
                    "low_energy",
                    t,
                    end,
                    min(5, max(2, int(deficit / 5))),
                    b_mean,
                    c_mean,
                    "dB",
                    "speech_energy_db",
                    b_mean - config.energy_dip_db_threshold,
                    "Sustain projection and breath support across these words.",
                )

    # Keep window evidence attached to its measured interval. Merge only substantially
    # overlapping same-type windows; retain every constituent measurement for auditing.
    merged = []
    for kind in sorted({f["flaw_type"] for f in flaws}):
        group = sorted(
            [f for f in flaws if f["flaw_type"] == kind], key=lambda f: f["start_time"]
        )
        for f in group:
            if (
                merged
                and merged[-1]["flaw_type"] == kind
                and f["start_time"] < merged[-1]["end_time"]
            ):
                previous = merged[-1]
                if kind in ["rushed_pacing", "slow_pacing"]:
                    previous["end_time"] = max(previous["end_time"], f["end_time"])
                    region = [
                        (b, c)
                        for b, c in pairs
                        if c.end > previous["start_time"]
                        and c.start < previous["end_time"]
                    ]
                    bw, cw = [p[0] for p in region], [p[1] for p in region]
                    b_rate = 60 * len(bw) / max(0.2, sum(w.end - w.start for w in bw))
                    c_rate = 60 * len(cw) / max(0.2, sum(w.end - w.start for w in cw))
                    previous["severity"] = min(
                        5, max(2, int(np.ceil(abs(np.log2(c_rate / b_rate)) * 5)))
                    )
                    previous["evidence"].update(
                        baseline_value=b_rate,
                        participant_value=c_rate,
                        absolute_deviation=c_rate - b_rate,
                    )
                    previous["evidence"]["additional"]["reference_region_seconds"] = (
                        bw[-1].end - bw[0].start
                    )
                    previous["measured_value"] = c_rate
                    previous["reference_value"] = b_rate
                    previous["threshold"] = b_rate * (
                        config.rushed_wpm_ratio
                        if kind == "rushed_pacing"
                        else config.slow_wpm_ratio
                    )
                    previous["transcript_excerpt"] = " ".join(w.word for w in cw)
                    previous["causal_explanation"] = (
                        f"Matched articulation rate is {c_rate:.1f} words/min versus reference {b_rate:.1f} words/min, "
                        f"a {(c_rate/b_rate-1)*100:+.1f}% difference. Long pauses are evaluated separately."
                    )
                    continue
                if kind in ["monotone_delivery", "low_energy"]:
                    # Select the stronger measured window instead of expanding an interval
                    # while reusing evidence that describes only its first part.
                    if f["severity"] > previous["severity"]:
                        merged[-1] = f
                    continue
            merged.append(f)
    return sorted(merged, key=lambda f: f["start_time"]), warnings
