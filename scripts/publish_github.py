"""Publish the authorized project using an existing credential, without logging it."""
from pathlib import Path
import os
import subprocess
import httpx
import json
ROOT=Path(__file__).resolve().parents[1]
OWNER='Ryukon07'
NAME='vocalis-speech-analytics'

def credentials():
    environment=os.environ.copy(); environment['GCM_INTERACTIVE']='Never'
    result=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,env=environment,timeout=20,check=True)
    fields=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    return fields['password'],environment

def run(*args): subprocess.run(['git',*args],cwd=ROOT,check=True)

def main():
    token,environment=credentials()
    with httpx.Client(base_url='https://api.github.com',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'},timeout=45) as client:
        account=client.get('/user').raise_for_status().json()
        assert account['login']==OWNER
        response=client.get(f'/repos/{OWNER}/{NAME}')
        if response.status_code==404:
            repository=client.post('/user/repos',json=dict(name=NAME,description='Track C: real local contrastive speech analytics, paired dataset, temporal grounding and explainable dashboard',private=False,auto_init=False)).raise_for_status().json()
        else:
            repository=response.raise_for_status().json()
            assert not repository['private'], 'Existing repository is private; do not change its visibility automatically.'
        run('config','user.name',OWNER)
        run('config','user.email',f"{account['id']}+{OWNER}@users.noreply.github.com")
        existing=subprocess.run(['git','remote','get-url','origin'],cwd=ROOT,capture_output=True,text=True)
        if existing.returncode:
            run('remote','add','origin',repository['clone_url'])
        else: assert existing.stdout.strip()==repository['clone_url']
        print('Authorized public repository ready:',repository['html_url'],flush=True)
        (ROOT/'docs/submission/github-publication.json').write_text(json.dumps(dict(repository=repository['html_url'],owner=OWNER,public=True),indent=2)+'\n')

if __name__=='__main__':main()
