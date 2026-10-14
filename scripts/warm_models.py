"""Cache local recognition/alignment models and verify genuine speech processing."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speech_runtime import transcribe
import evaluator

root = Path(__file__).resolve().parents[1]
folder = root / "dataset/contrastive/reagan_challenger_1986-opening"
if not (folder / "reference.wav").exists():
    raise SystemExit(
        "The bundled contrastive corpus is missing. Run dataset/build_dataset.py first."
    )
text = transcribe(str(folder / "reference.wav"))
fallback = transcribe(str(folder / "reference.wav"), model_name="medium")
words = evaluator.align_audio(
    str(folder / "reference.wav"), (folder / "transcript.txt").read_text()
)
print(
    f"Local models ready: {len(text.split())} primary words; {len(fallback.split())} fallback words; {len(words)} aligned words."
)
