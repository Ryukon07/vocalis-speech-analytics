"""Prepare offline English narration and real public demo inputs."""
from pathlib import Path
import json
import subprocess
import wave
import httpx
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'tmp/dashboard-demo'
WORK.mkdir(parents=True,exist_ok=True)
narration=json.loads((ROOT/'docs/submission/demo-narration.json').read_text())
(WORK/'narration.json').write_text(json.dumps(narration),encoding='utf-8')
subprocess.run(['powershell.exe','-NoProfile','-File',str(ROOT/'scripts/synthesize_walkthrough.ps1'),'-WorkDirectory',str(WORK)],check=True)
durations=[]
for index in range(1,len(narration)+1):
    with wave.open(str(WORK/f'narration-{index}.wav')) as audio: durations.append(max(30,audio.getnframes()/audio.getframerate()+2))
manifest=json.loads((ROOT/'docs/benchmarks/transcription-accuracy.json').read_text())
sample=manifest['samples'][0]
with httpx.Client(base_url='http://127.0.0.1:8000/api/v1',timeout=30) as client:
    refs=client.get('/references?limit=100').raise_for_status().json()['items']
    ref=next((r for r in refs if r['title']=='LibriSpeech - Quilter demo reference'),None)
    if not ref:
        ref=client.post('/references',json=dict(title='LibriSpeech - Quilter demo reference',recording_id=sample['recording_id'],transcript=sample['expected'],speaker_id='LibriSpeech reader 1272',source_url='https://www.openslr.org/12/',license='CC BY 4.0; LibriSpeech contributors and LibriVox',eligible=True,profile=None)).raise_for_status().json()
    rubric=next(r for r in client.get('/rubrics?limit=100').raise_for_status().json()['items'] if r['name']=='Complete delivery with clarity')
settings=dict(durations=durations,reference_id=ref['id'],rubric_id=rubric['id'],expected=sample['expected'])
(WORK/'settings.json').write_text(json.dumps(settings,indent=2)+'\n')
(ROOT/'docs/submission/final-demo-transcript.txt').write_text('\n\n'.join(f'{i+1}. {t}' for i,t in enumerate(narration))+'\n',encoding='utf-8')
print('Prepared',len(durations),'chapters; narration duration',round(sum(durations),1),'seconds',flush=True)
