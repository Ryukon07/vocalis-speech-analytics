"""Copy an allowlisted public corpus and verified reports into isolated demo storage."""
from pathlib import Path
import sys
import json
import hashlib
import shutil
from sqlalchemy import select
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.core.config import Settings
from app.repositories.database import database
from app.models import Base,Recording,Reference,Rubric,Analysis,FeatureSeries,DetectedFlaw,ContrastiveGroup,Variant,Annotation

def main():
    target=ROOT/'tmp/public-demo'; target.mkdir(parents=True,exist_ok=True)
    destination=target/'state.sqlite'
    assert not destination.exists(),'An isolated demo already exists; do not overwrite active guest data.'
    local=Settings(); source_engine,source_sessions=database(local.database_url)
    target_engine,target_sessions=database('sqlite:///'+destination.as_posix()); Base.metadata.create_all(target_engine)
    allow={}
    corpus=json.loads((ROOT/'dataset/contrastive/manifest.json').read_text())
    for group in corpus['groups']:
        allow[group['id']+'-reference.wav']=group['reference']['sha256']
        for variant in group['variants']: allow[variant['id']+'.wav']=variant['sha256']
    asr=json.loads((ROOT/'dataset/asr_checks/manifest.json').read_text())
    for sample in asr['samples']:allow[sample['file']]=sample['sha256']
    allow['combined-severe-training-stress.wav']=hashlib.sha256((ROOT/'dataset/stress_samples/combined-severe.wav').read_bytes()).hexdigest()
    # The noisy public excerpt has a known analysis ID and original public reference.
    clarity_id=json.loads((ROOT/'docs/benchmarks/clarity-website-result.json').read_text())['analysis_id']
    analyses={j['id'] for j in json.loads((ROOT/'docs/benchmarks/website-verification.json').read_text())['jobs']}
    analyses|={clarity_id,json.loads((ROOT/'dataset/stress_samples/website-job.json').read_text())['id']}
    movie=ROOT/'tmp/dashboard-demo/recording-manifest.json'
    if movie.exists():analyses.add(json.loads(movie.read_text())['demo_analysis_url'].rsplit('/',1)[-1])
    source_storage=local.storage_root.resolve(); output_storage=target/'storage'; output_storage.mkdir(exist_ok=True)
    ids=set(); files=set()
    with source_sessions() as source,target_sessions() as destination_session:
        public_records=[]
        for row in source.scalars(select(Recording)):
            known=allow.get(row.original_filename)
            if known and hashlib.sha256((source_storage/row.storage_key).read_bytes()).hexdigest()==known:public_records.append(row)
        noisy_analysis=source.get(Analysis,clarity_id)
        noisy=source.get(Recording,noisy_analysis.participant_recording_id)
        assert noisy.original_filename.startswith('clarity-check-reagan_farewell_1989-')
        public_records.append(noisy)
        recording_ids={r.id for r in public_records}
        refs=list(source.scalars(select(Reference).where(Reference.recording_id.in_(recording_ids))))
        ref_ids={r.id for r in refs}
        rubrics=list(source.scalars(select(Rubric).where(Rubric.name.in_(['Balanced delivery','Complete delivery with clarity','Contrastive delivery']))))
        rubric_ids={r.id for r in rubrics}
        jobs=list(source.scalars(select(Analysis).where(Analysis.id.in_(analyses))))
        jobs=[a for a in jobs if a.participant_recording_id in recording_ids and a.reference_id in ref_ids and a.rubric_id in rubric_ids and a.status=='completed']
        analysis_ids={a.id for a in jobs}
        groups=list(source.scalars(select(ContrastiveGroup).where(ContrastiveGroup.reference_recording_id.in_(recording_ids))))
        group_ids={g.id for g in groups}
        rows_by_model=[(Recording,public_records),(Rubric,rubrics),(Reference,refs),(ContrastiveGroup,groups),(Variant,list(source.scalars(select(Variant).where(Variant.group_id.in_(group_ids))))),(Annotation,list(source.scalars(select(Annotation).where(Annotation.recording_id.in_(recording_ids))))),(Analysis,jobs),(DetectedFlaw,list(source.scalars(select(DetectedFlaw).where(DetectedFlaw.analysis_id.in_(analysis_ids))))),(FeatureSeries,list(source.scalars(select(FeatureSeries).where(FeatureSeries.analysis_id.in_(analysis_ids)))))]
        for model,rows in rows_by_model:
            for row in rows:
                value={column.name:getattr(row,column.name) for column in model.__table__.columns}
                destination_session.add(model(**value));ids.add(row.id)
                if model in (Recording,FeatureSeries):files.add(row.storage_key)
            destination_session.commit()
        for key in files:shutil.copy2(source_storage/key,output_storage/key)
        assert not destination_session.scalar(select(Recording).where(Recording.original_filename=='speech-1791959497867.wav'))
    summary=dict(protocol='Isolated allowlisted public corpus and verified reports; private microphone/database data excluded',recordings=len(recording_ids),analyses=len(analysis_ids),protected_ids=sorted(ids))
    (target/'seed-manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    target_engine.dispose();source_engine.dispose()
    print('Isolated public demo prepared:',len(recording_ids),'public recordings;',len(analysis_ids),'verified reports; private microphone excluded.',flush=True)

if __name__=='__main__':main()
