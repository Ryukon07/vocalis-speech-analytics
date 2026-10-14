import math
import time
from uuid import uuid5, NAMESPACE_URL
from app.schemas.contracts import (
    AnalysisResult,
    Scores,
    Flaw,
    Evidence,
    Series,
    Point,
    Alignment,
    Word,
)
from .base import SpeechAnalysisProvider
from .schemas import Capabilities, ProviderHealth

STAGES = [
    "Input validation",
    "Audio preprocessing",
    "Speech/transcript alignment",
    "Acoustic feature extraction",
    "Baseline normalization and comparison",
    "Flaw classification and severity estimation",
    "Temporal grounding",
    "Score calculation and report generation",
]


class MockSpeechAnalysisProvider(SpeechAnalysisProvider):
    """Deterministic illustrative fixture. Never measures or predicts uploaded speech."""

    def __init__(self, settings):
        self.delay = settings.mock_stage_delay

    def get_capabilities(self):
        return Capabilities(
            provider_name="mock",
            provider_version="fixture-1.0",
            execution_mode="mock",
            ready=True,
            message="Illustrative fixtures only. No analysis is inferred from audio.",
        )

    def health_check(self):
        return ProviderHealth(
            ready=True, message="Demo fixtures ready; no ML models loaded."
        )

    def analyze(self, request, progress_callback=None):
        for i, stage in enumerate(STAGES):
            if progress_callback:
                progress_callback("Demo simulation: " + stage, (i + 1) / 9 * 100)
            time.sleep(self.delay)
        duration = request.participant_duration_seconds
        # Unknown compressed-file durations: return unavailable measurements rather than make up bounds.
        if duration is None or duration <= 0:
            return AnalysisResult(
                analysis_id=request.job_id,
                provider_name="mock",
                provider_version="fixture-1.0",
                execution_mode="mock",
                participant_duration_seconds=None,
                reference_duration_seconds=request.reference_duration_seconds,
                warnings=[
                    "DEMO / MOCK ANALYSIS: not derived from your audio.",
                    "Duration unavailable. Upload WAV or use the demo fixture for illustrative intervals.",
                ],
            )
        categories = request.settings.enabled_categories
        values = {
            "pacing": 72.0,
            "pitch": 81.0,
            "energy": 86.0,
            "pausing": 68.0,
            "clarity": 90.0,
        }
        dims = {c: values[c] if c in categories else None for c in values}
        weights = request.rubric.weights
        total = sum(weights[c] for c in categories)
        overall = sum(values[c] * weights[c] for c in categories) / total
        flaws = []
        examples = [
            (
                "pacing",
                "excessive_pace",
                0.26,
                0.42,
                3,
                2.8,
                4.0,
                "words/second",
                "speech_rate",
                "Try a slower, deliberate delivery through this phrase.",
            ),
            (
                "pausing",
                "extended_pause",
                0.61,
                0.69,
                2,
                0.45,
                1.3,
                "seconds",
                "pause_duration",
                "Shorten the pause to keep the sentence connected.",
            ),
            (
                "pitch",
                "flat_intonation",
                0.78,
                0.91,
                2,
                4.2,
                1.5,
                "semitones",
                "pitch_variation",
                "Vary emphasis on the key words.",
            ),
        ]
        for (
            category,
            kind,
            start,
            end,
            severity,
            baseline,
            participant,
            unit,
            measure,
            action,
        ) in examples:
            if category not in categories:
                continue
            diff = participant - baseline
            flaws.append(
                Flaw(
                    id=str(uuid5(NAMESPACE_URL, request.job_id + kind)),
                    type=kind,
                    category=category,
                    start_seconds=round(duration * start, 4),
                    end_seconds=round(duration * end, 4),
                    severity=severity,
                    confidence=0.9,
                    evidence=Evidence(
                        baseline_value=baseline,
                        participant_value=participant,
                        absolute_deviation=diff,
                        difference_percent=round(diff / baseline * 100, 2),
                        units=unit,
                        measurement_name=measure,
                        source="mock",
                    ),
                    interpretation_source="mock",
                    explanation=f'Illustrative fixture: {measure.replace("_", " ")} differs from {baseline} to {participant} {unit}. These values were not measured from the audio.',
                    recommendation="Demo coaching example: " + action,
                )
            )
        features = {}
        if request.settings.detailed_plots:
            for name, unit, center, amplitude in [
                ("pitch", "Hz", 180, 24),
                ("energy", "RMS", 0.12, 0.05),
                ("speaking_rate", "words/second", 2.8, 0.5),
                ("pause", "activity (0/1)", 0.5, 0.5),
                ("mfcc_1", "coefficient", -110, 15),
            ]:
                features[name] = Series(
                    unit=unit,
                    time_axis="participant_aligned",
                    reference=[
                        Point(
                            time_seconds=duration * i / 80,
                            value=round(center + amplitude * math.sin(i / 6), 4),
                        )
                        for i in range(81)
                    ],
                    participant=[
                        Point(
                            time_seconds=duration * i / 80,
                            value=round(
                                center
                                + amplitude * math.sin(i / 6)
                                + (amplitude * 0.8 if 21 <= i <= 34 else 0),
                                4,
                            ),
                        )
                        for i in range(81)
                    ],
                    window_metadata={"provenance": "fixed synthetic fixture"},
                )
        # Words from uploaded text are spread for UI demonstration only, never described as forced alignment.
        words = request.transcript.split()
        alignment = Alignment(
            words=[
                Word(
                    text=w,
                    start_seconds=duration * i / len(words),
                    end_seconds=duration * (i + 1) / len(words),
                    confidence=None,
                )
                for i, w in enumerate(words)
            ]
        )
        return AnalysisResult(
            analysis_id=request.job_id,
            provider_name="mock",
            provider_version="fixture-1.0",
            execution_mode="mock",
            participant_duration_seconds=duration,
            reference_duration_seconds=request.reference_duration_seconds,
            scores=Scores(overall=round(overall, 2), dimensions=dims),
            flaws=flaws,
            feature_series=features,
            alignment=alignment,
            warnings=[
                "DEMO / MOCK ANALYSIS: scores, curves, evidence and word positions are illustrative fixtures, not inferred from this recording."
            ],
        )
