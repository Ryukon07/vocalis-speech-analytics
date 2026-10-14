"""Reference-relative ASR recoverability, with explicit evidence and limits.

WER measures a recognizer, not human intelligibility. The score reports additional
recognition errors relative to the reference; no transcript is supplied to ASR.
"""

import math
import re
import unicodedata
from speech_runtime import alignment_spelling

METHOD = "reference_relative_wer_v1"
MIN_WORDS = 8
MAX_REFERENCE_WER = 0.25
CONTRACTIONS = {
    "can't": "cannot",
    "won't": "will not",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "it's": "it is",
    "that's": "that is",
    "i'm": "i am",
    "we're": "we are",
    "they're": "they are",
    "you're": "you are",
    "i've": "i have",
    "we've": "we have",
    "they've": "they have",
    "i'll": "i will",
    "we'll": "we will",
    "you'll": "you will",
    "cannot": "can not",
}


def normalized_tokens(text):
    text = (
        unicodedata.normalize("NFKD", text)
        .replace("’", "'")
        .replace("—", " ")
        .replace("–", " ")
        .lower()
    )
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    text = text.encode("ascii", "ignore").decode()
    # Treat hyphens as word boundaries, and numeric spellings consistently with alignment.
    pieces = re.findall(r"[a-z]+(?:'[a-z]+)?|\d+(?:st|nd|rd|th)?", text)
    result = []
    for piece in pieces:
        expanded = CONTRACTIONS.get(piece, piece)
        for word in expanded.split():
            result.extend(p.lower() for p in alignment_spelling(word).split("|") if p)
    # Normalize cannot again when produced by can't.
    return [
        part
        for token in result
        for part in (["can", "not"] if token == "cannot" else [token])
    ]


def word_errors(expected, recognized):
    """Levenshtein WER plus errors assigned to confirmed-token positions.

    Insertions are attached to the following confirmed token (last at the end).
    These positions locate recognition disagreements, not phoneme diagnoses.
    """
    n, m = len(expected), len(recognized)
    rows = [list(range(m + 1))]
    for i in range(1, n + 1):
        row = [i]
        for j in range(1, m + 1):
            row.append(
                min(
                    rows[i - 1][j] + 1,
                    row[j - 1] + 1,
                    rows[i - 1][j - 1] + (expected[i - 1] != recognized[j - 1]),
                )
            )
        rows.append(row)
    counts = dict(substitutions=0, deletions=0, insertions=0)
    positions = [0] * n
    i, j = n, m
    while i or j:
        if (
            i
            and j
            and expected[i - 1] == recognized[j - 1]
            and rows[i][j] == rows[i - 1][j - 1]
        ):
            i -= 1
            j -= 1
        elif i and j and rows[i][j] == rows[i - 1][j - 1] + 1:
            counts["substitutions"] += 1
            positions[i - 1] += 1
            i -= 1
            j -= 1
        elif i and rows[i][j] == rows[i - 1][j] + 1:
            counts["deletions"] += 1
            positions[i - 1] += 1
            i -= 1
        else:
            counts["insertions"] += 1
            if n:
                positions[min(i, n - 1)] += 1
            j -= 1
    errors = sum(counts.values())
    return dict(
        **counts,
        errors=errors,
        word_error_rate=errors / n if n else None,
        token_errors=positions,
    )


def compare_recognition(
    transcript, reference_text, participant_text, words=None, model_name="base.en"
):
    expected = normalized_tokens(transcript)
    reference = word_errors(expected, normalized_tokens(reference_text))
    participant = word_errors(expected, normalized_tokens(participant_text))
    measurement = dict(
        available=False,
        method=METHOD,
        model_name=model_name,
        score=None,
        confirmed_word_count=len(expected),
        minimum_word_count=MIN_WORDS,
        maximum_reference_wer=MAX_REFERENCE_WER,
        reference_text=reference_text,
        participant_text=participant_text,
        reference={k: v for k, v in reference.items() if k != "token_errors"},
        participant={k: v for k, v in participant.items() if k != "token_errors"},
        excess_word_error_rate=None,
        reason=None,
    )
    if len(expected) < MIN_WORDS:
        measurement["reason"] = (
            f"Clarity needs at least {MIN_WORDS} normalized confirmed words."
        )
        return measurement, []
    if reference["word_error_rate"] > MAX_REFERENCE_WER:
        measurement["reason"] = (
            "The reference has more than 25% recognition errors; it is not a reliable clarity baseline."
        )
        return measurement, []
    excess = max(0.0, participant["word_error_rate"] - reference["word_error_rate"])
    measurement.update(
        available=True,
        excess_word_error_rate=excess,
        score=round(100 * (1 - min(1.0, excess)), 1),
    )
    flaws = []
    if not words or excess < 0.10:
        return measurement, flaws
    # Group actual confirmed words into phrases; numeric expansions keep their original timestamp.
    cursor = 0
    groups = []
    for word in words:
        length = len(normalized_tokens(word.word))
        groups.append((word, cursor, cursor + length))
        cursor += length
    if cursor != len(expected):
        return measurement, flaws
    for start in range(0, len(groups), 6):
        block = groups[start : start + 6]
        a, b = block[0][1], block[-1][2]
        if b - a < 4:
            continue
        baseline = sum(reference["token_errors"][a:b]) / (b - a)
        candidate = sum(participant["token_errors"][a:b]) / (b - a)
        delta = candidate - baseline
        if delta < 0.20:
            continue
        flaws.append(
            dict(
                flaw_type="recognition_difficulty",
                start_time=float(block[0][0].start),
                end_time=float(block[-1][0].end),
                severity=min(5, max(1, math.ceil(delta * 5))),
                confidence=None,
                description="Additional speech-recognition errors in this phrase.",
                causal_explanation=f"The recognizer made {candidate:.0%} word errors in this phrase versus {baseline:.0%} in the reference. This can reflect pronunciation, recording conditions, or model bias; it does not establish a specific cause.",
                evidence=dict(
                    baseline_value=baseline * 100,
                    participant_value=candidate * 100,
                    absolute_deviation=delta * 100,
                    difference_percent=None,
                    normalized_deviation=delta,
                    units="% word errors",
                    measurement_name="phrase_word_error_rate",
                    source="measured",
                    additional=dict(
                        confirmed_words=b - a,
                        reference_errors=sum(reference["token_errors"][a:b]),
                        participant_errors=sum(participant["token_errors"][a:b]),
                        threshold_excess_percentage_points=20,
                    ),
                ),
                measured_value=candidate * 100,
                reference_value=baseline * 100,
                threshold=(baseline + 0.2) * 100,
                transcript_excerpt=" ".join(w.word for w, _, _ in block),
                recommendation="Listen to this phrase and check the recognized words. If unclear, articulate the word endings and record again in a quieter setting with a steady microphone position.",
            )
        )
    return measurement, flaws
