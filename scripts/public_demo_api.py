"""Temporary isolated demo with protected seed data and anonymous session ownership."""
from pathlib import Path
from uuid import uuid4
import json
import re
from collections import defaultdict
import time
from starlette.responses import JSONResponse,Response
from sqlalchemy import select,func
from app.main import create_app
from app.core.config import Settings
from app.models import Analysis,Transcription
ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'tmp/public-demo'
protected=set(json.loads((STATE/'seed-manifest.json').read_text())['protected_ids'])
owners_path=STATE/'guest-ownership.json'
owners=json.loads(owners_path.read_text()) if owners_path.exists() else {}
counts=defaultdict(list)
settings=Settings(database_url='sqlite:///'+(STATE/'state.sqlite').as_posix(),storage_root=STATE/'storage',model_cache_root=ROOT/'model-artifacts',max_upload_mb=12,cors_origins=['http://127.0.0.1:5174'])
app=create_app(settings)

@app.middleware('http')
async def demo_guard(request,call_next):
    session=request.cookies.get('vocalis-demo-session','')
    if not re.fullmatch('[a-f0-9]{32}',session):session=uuid4().hex
    path=request.url.path
    identifier=next(iter(re.findall(r'(?<![a-f0-9])[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',path)),None)
    def denied(message,status=403):return JSONResponse({'error':{'code':'DEMO_RESTRICTION','message':message}},status_code=status)
    if identifier and identifier in owners and owners[identifier]!=session:return denied('This temporary demo item belongs to another browser session.',404)
    if request.method in ('PATCH','DELETE') and identifier in protected:return denied('Baseline dataset and saved example reports are protected. Create your own item to edit it.')
    if request.method in ('PATCH','DELETE') and identifier not in owners:return denied('Only items created by this browser session can be changed.')
    if request.method=='POST':
        try:length=int(request.headers.get('content-length','0'))
        except ValueError:return denied('Invalid request size.',400)
        if length>13*1024*1024:return denied('The public demo accepts at most 12 MB of test audio.',413)
        recent=[v for v in counts[session] if time.monotonic()-v<3600];counts[session]=recent
        if len(recent)>=40:return denied('This browser reached the temporary demo request allowance.',429)
        if '/transcriptions' in path or path.endswith('/analyses'):
            with app.state.sessions() as db:
                active=sum(db.scalar(select(func.count()).select_from(model).where(model.status.in_(['queued','processing']))) for model in (Analysis,Transcription))
            if active>=3:return denied('The demo has three active CPU jobs. Try again after a job finishes.',429)
        if 'application/json' in request.headers.get('content-type',''):
            try:body=await request.json()
            except Exception:body={}
            if not isinstance(body,dict):body={}
            for key in ('recording_id','participant_recording_id','reference_recording_id','reference_id','rubric_id'):
                value=body.get(key)
                if value in owners and owners[value]!=session:return denied('Choose an input owned by this session or a public baseline.',404)
        counts[session].append(time.monotonic())
    response=await call_next(request)
    is_json='application/json' in response.headers.get('content-type','')
    if is_json and (request.method=='GET' or (request.method=='POST' and response.status_code in (201,202))):
        payload=b''.join([chunk async for chunk in response.body_iterator])
        value=json.loads(payload)
        if request.method=='POST' and isinstance(value,dict) and value.get('id'):
            previous=owners.get(value['id'])
            if previous and previous!=session:return denied('A job for this shared baseline is already active in another session. Try again after it finishes.',429)
            owners[value['id']]=session
            temporary=owners_path.with_suffix('.tmp');temporary.write_text(json.dumps(owners));temporary.replace(owners_path)
        if request.method=='GET' and isinstance(value,dict) and isinstance(value.get('items'),list):
            value['items']=[item for item in value['items'] if item['id'] in protected or owners.get(item['id'])==session]
            value['total']=len(value['items']) if len(value['items'])<value.get('limit',20) else value['total']
        headers=dict(response.headers);headers.pop('content-length',None)
        response=Response(json.dumps(value),status_code=response.status_code,headers=headers,media_type='application/json')
    if not request.cookies.get('vocalis-demo-session'):
        response.set_cookie('vocalis-demo-session',session,httponly=True,samesite='lax',secure=request.headers.get('x-forwarded-proto')=='https',max_age=7200)
    return response
