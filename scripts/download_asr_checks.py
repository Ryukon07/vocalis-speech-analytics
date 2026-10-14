"""Download the first four public LibriSpeech dummy validation clips with gold text."""
from pathlib import Path
import hashlib
import io
import json
import ssl
import httpx
import soundfile as sf
import truststore

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dataset/asr_checks"
OUTPUT.mkdir(parents=True, exist_ok=True)
DATASET = "hf-internal-testing/librispeech_asr_dummy"

def main():
    with httpx.Client(timeout=45, follow_redirects=True,
                      verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)) as client:
        data = client.get("https://datasets-server.huggingface.co/rows", params={
            "dataset": DATASET, "config": "clean", "split": "validation", "offset": 0, "length": 4,
        }).raise_for_status().json()
        samples = []
        for item in data["rows"]:
            row = item["row"]
            payload = client.get(row["audio"][0]["src"]).raise_for_status().content
            audio, rate = sf.read(io.BytesIO(payload), dtype="float32")
            name = str(row["id"]) + ".wav"
            target = OUTPUT / name
            sf.write(target, audio, rate, subtype="PCM_16")
            samples.append(dict(id=row["id"], file=name, text=row["text"],
                speaker_id=row["speaker_id"], chapter_id=row["chapter_id"],
                sample_rate=rate, duration_seconds=len(audio)/rate,
                sha256=hashlib.sha256(target.read_bytes()).hexdigest(), row_index=item["row_idx"]))
            print("Downloaded known-text sample",row["id"],round(len(audio)/rate,2),"seconds",flush=True)
    result = dict(dataset=DATASET, config="clean", split="validation", selection="First four rows, before recognition; no accuracy-based selection",
        dataset_url="https://huggingface.co/datasets/"+DATASET,
        original_source="https://www.openslr.org/12/", license="CC BY 4.0",
        attribution="LibriSpeech, Vassil Panayotov, Daniel Povey, Guoguo Chen and Sanjeev Khudanpur; audiobook readings from LibriVox",
        limitations="Four clean clips from one reader; verifies this sample set, not general accent/noise performance or absence from upstream model training.",
        samples=samples)
    (OUTPUT/"manifest.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")

if __name__ == "__main__":main()
