"""Compare the cached larger draft model on the same preselected public clips."""
from pathlib import Path
import json
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clarity_analysis import normalized_tokens, word_errors

def main():
    manifest = json.loads((ROOT/'dataset/asr_checks/manifest.json').read_text())
    rows = []
    for sample in manifest['samples']:
        start = time.monotonic()
        # This compares the draft decoder (not the frozen clarity decoder).
        import evaluator
        text = evaluator.transcribe_audio(str(ROOT/'dataset/asr_checks'/sample['file']), model_name='medium', device='cpu', language='en', cache_dir=str(ROOT/'model-artifacts'), cpu_threads=4)
        errors = word_errors(normalized_tokens(sample['text']), normalized_tokens(text))
        row = dict(sample_id=sample['id'], expected=sample['text'], recognized=text, model='medium', elapsed_seconds=round(time.monotonic()-start,3), **errors)
        rows.append(row)
        print(sample['id'],errors['word_error_rate'],text,flush=True)
    result = dict(protocol='Same four preselected clips, larger draft decoder, no supplied transcript', samples=rows, aggregate_wer=sum(r['errors'] for r in rows)/sum(len(normalized_tokens(r['expected'])) for r in rows))
    (ROOT/'docs/benchmarks/draft-model-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Medium aggregate WER',result['aggregate_wer'],flush=True)

if __name__=='__main__':main()
