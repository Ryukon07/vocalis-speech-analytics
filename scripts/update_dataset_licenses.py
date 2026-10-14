"""Record primary-source archive reuse evidence without modifying audio/hashes."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
NOTES='U.S. public-domain government speech audio; archive reuse basis and supplied-file provenance documented in dataset/LICENSE_NOTES.md.'
evidence={
 'reagan_challenger_1986':dict(archive_item='https://www.reaganlibrary.gov/galleries/audio-recordings-01281986-launch-sts-mission-51-l',archive_identifier='7087577',tape='PP6028B',basis='WHCA audio collection public-domain statement; supplied MP3 receipt not retained; no byte-match claim'),
 'reagan_farewell_1989':dict(archive_item='https://www.reaganlibrary.gov/archives/audio/remarks-president-reagan-during-farewell-address-nation-oval-office',archive_identifier='7087581',tape='PP9011B',basis='WHCA audio collection public-domain statement; supplied MP3 receipt not retained; no byte-match claim'),
 'eisenhower_farewell_1961':dict(archive_item='https://www.eisenhowerlibrary.gov/research/online-documents/farewell-address',archive_identifier='EL-D16-138 RA',basis='Official Library download; U.S. Army Signal Corps; listed digitized items public-domain statement'),
}
p=ROOT/'dataset/contrastive/manifest.json'; manifest=json.loads(p.read_text())
for group in manifest['groups']: group['license']=NOTES; group['rights_evidence']=evidence[group['source_id']]
p.write_text(json.dumps(manifest,indent=2)+'\n')
p=ROOT/'dataset/reference_speeches/sources.json'; catalog=json.loads(p.read_text())
for item in catalog['speeches']:
 if item['id'] in evidence: item['recording_license']=NOTES; item['rights_evidence']=evidence[item['id']]
catalog['rights_notes']='Released corpus sources reviewed in dataset/LICENSE_NOTES.md; unused candidate rights remain unverified.'
p.write_text(json.dumps(catalog,indent=2)+'\n')
# Refresh presentation metadata only, leaving saved reports and original hashes untouched.
import httpx
with httpx.Client(base_url='http://127.0.0.1:8000/api/v1',timeout=30) as client:
 for record in client.get('/recordings?limit=100').raise_for_status().json()['items']:
  if any(record['original_filename'].startswith(source+'-') for source in evidence): client.patch('/recordings/'+record['id'],json={'license':NOTES}).raise_for_status()
 for reference in client.get('/references?limit=100').raise_for_status().json()['items']:
  if 'reagan' in reference['source_url'] or 'eisenhower' in reference['source_url']: client.patch('/references/'+reference['id'],json={'license':NOTES}).raise_for_status()
print('Updated reuse evidence for all three released speech sources; audio hashes unchanged.')
