"""Exercise the actual HTTPS proxy, public inference and anonymous item isolation."""
from pathlib import Path
import json
import re
import ssl
import time
import httpx
import truststore
ROOT=Path(__file__).resolve().parents[1]

def main():
    log=(ROOT/'tmp/public-demo/tunnel-errors.log').read_text()
    url=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',log).group(0)
    verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with httpx.Client(base_url=url,verify=verify,timeout=60,follow_redirects=True) as a,httpx.Client(base_url=url,verify=verify,timeout=60) as b:
        assert a.get('/').raise_for_status().status_code==200
        health=a.get('/api/v1/health').raise_for_status().json(); assert health['provider_ready']
        assert a.get('/api/v1/recordings/7e6dd76a-4ba4-4239-98ef-685218716ac3').status_code==404
        records=a.get('/api/v1/recordings?limit=100').raise_for_status().json()['items']
        assert not any(r['original_filename']=='speech-1791959497867.wav' for r in records)
        assert a.patch('/api/v1/recordings/'+records[0]['id'],json={'title':'must not persist'}).status_code==403
        path=ROOT/'dataset/asr_checks/1272-128104-0000.wav'
        with path.open('rb') as file:recording=a.post('/api/v1/recordings',files={'file':(path.name,file,'audio/wav')}).raise_for_status().json()
        identifier=recording['id'];assert b.get('/api/v1/recordings/'+identifier).status_code==404
        assert not any(r['id']==identifier for r in b.get('/api/v1/recordings?limit=100').raise_for_status().json()['items'])
        # A guest's new row sorts first, but must not displace another guest's
        # baseline page entries or change its total after filtering.
        first=b.get('/api/v1/recordings?limit=2').raise_for_status().json()
        second=b.get('/api/v1/recordings?offset=2&limit=2').raise_for_status().json()
        all_visible=b.get('/api/v1/recordings?limit=100').raise_for_status().json()
        assert first['total']==second['total']==all_visible['total']==len(all_visible['items'])
        assert len(first['items'])==len(second['items'])==2
        assert not {item['id'] for item in first['items']} & {item['id'] for item in second['items']}
        last=b.get(f"/api/v1/recordings?offset={all_visible['total']-1}&limit=2").raise_for_status().json()
        assert last['total']==all_visible['total'] and len(last['items'])==1
        job=a.post('/api/v1/recordings/'+identifier+'/transcriptions').raise_for_status().json()
        start=time.monotonic()
        while job['status'] in ('queued','processing') and time.monotonic()-start<240:
            time.sleep(0.5);job=a.get('/api/v1/transcriptions/'+job['id']).raise_for_status().json()
        assert job['status']=='completed' and 'Quilter' in job['transcript'],job
        assert b.get('/api/v1/transcriptions/'+job['id']).status_code==404
        audio=a.get('/api/v1/recordings/'+identifier+'/audio',headers={'Range':'bytes=0-99'}).raise_for_status()
        assert audio.status_code==206 and len(audio.content)==100
        a.delete('/api/v1/recordings/'+identifier).raise_for_status()
        analyses=a.get('/api/v1/analyses?limit=100').raise_for_status().json()['items']
        report=next(v for v in analyses if v['status']=='completed' and v['execution_mode']=='real')
        assert a.get('/api/v1/analyses/'+report['id']+'/export/pdf').raise_for_status().content.startswith(b'%PDF-')
    result=dict(url=url,temporary=True,requires_laptop_online=True,healthy=True,real_transcription=True,actual_model=job['model_name'],private_microphone_excluded=True,seed_mutation_protected=True,cross_session_items_hidden=True,session_pagination=True,audio_ranges=True,pdf_export=True)
    (ROOT/'docs/submission/deployment-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Verified actual HTTPS demo:',url,'model',job['model_name'],'private isolation and downloads passed',flush=True)

if __name__=='__main__':main()
