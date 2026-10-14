"""Mux actual browser footage with offline English narration and chapter labels."""
from pathlib import Path
import json
import subprocess
import wave
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'tmp/dashboard-demo'
OUT=ROOT/'docs/submission'
labels=['1 / Vocalis: real dashboard and configurable rubric','2 / Dataset: attributed sources, paired spectrum and exact labels','3 / Real upload, local transcription, confirmation and inference','4 / Stress tests: monotone, rushing, pauses and combined deviations','5 / Clarity: independent recognition, evidence, playback and PDF','6 / Verification: controlled benchmark and reproducible workflow']

def main():
    manifest=json.loads((WORK/'recording-manifest.json').read_text())
    narration=json.loads((WORK/'narration.json').read_text())
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    font='C\\:/Windows/Fonts/segoeuib.ttf'
    segments=[]; timeline=[]; elapsed=0
    for entry,label,text in zip(manifest['chapters'],labels,narration):
        index=entry['index']; source=Path(entry['path']); target=WORK/f'final-chapter-{index}.mp4'; label_file=WORK/f'label-{index}.txt'; label_file.write_text(label,encoding='utf-8')
        duration=entry['duration_seconds']
        text_path=label_file.as_posix().replace(':','\\:')
        filters=f"scale=1280:720,drawbox=x=0:y=ih-34:w=iw:h=34:color=0x10131c@0.97:t=fill,drawtext=fontfile='{font}':textfile='{text_path}':fontcolor=0xb0a1f1:fontsize=15:x=18:y=h-26,format=yuv420p"
        subprocess.run([ffmpeg,'-y','-hide_banner','-loglevel','error','-i',str(source),'-i',str(WORK/f'narration-{index}.wav'),'-vf',filters,'-af','apad','-t',str(duration),'-r','24','-c:v','libx264','-preset','veryfast','-crf','23','-c:a','aac','-b:a','128k','-movflags','+faststart',str(target)],check=True)
        segments.append(target); timeline.append(dict(chapter=index,start_seconds=round(elapsed,2),end_seconds=round(elapsed+duration,2),title=label,text=text)); elapsed+=duration
        print('Encoded chapter',index,flush=True)
    concat=WORK/'final-segments.txt'; concat.write_text('\n'.join("file '"+p.as_posix()+"'" for p in segments))
    final=OUT/'vocalis-final-demo.mp4'
    subprocess.run([ffmpeg,'-y','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(final)],check=True)
    assert 180<=elapsed<=600,elapsed
    report=dict(duration_seconds=round(elapsed,2),resolution='1280x720',video='Real Playwright Chromium dashboard footage, actual localhost API and inference',audio='Offline synthesized English narration',no_api_fixtures=True,chapters=timeline)
    (OUT/'final-demo-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Final real dashboard video:',final,'duration',round(elapsed,1),'seconds',flush=True)

if __name__=='__main__':main()
