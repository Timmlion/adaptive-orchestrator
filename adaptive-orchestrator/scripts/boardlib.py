from pathlib import Path
from datetime import datetime, timezone
import json, os, uuid
STATUSES={"PLANNED","READY","CLAIMED","IN_PROGRESS","IN_REVIEW","REVISION_REQUIRED","BLOCKED","WAITING_FOR_HUMAN","WAITING_FOR_EXTERNAL","DONE","CANCELLED"}
TRANSITIONS={"PLANNED":{"READY","BLOCKED","CANCELLED"},"READY":{"CLAIMED","BLOCKED","WAITING_FOR_HUMAN","WAITING_FOR_EXTERNAL","CANCELLED"},"CLAIMED":{"IN_PROGRESS","READY","BLOCKED","CANCELLED"},"IN_PROGRESS":{"IN_REVIEW","BLOCKED","CANCELLED"},"IN_REVIEW":{"DONE","REVISION_REQUIRED","BLOCKED"},"REVISION_REQUIRED":{"READY","CANCELLED"},"BLOCKED":{"READY","CANCELLED"},"WAITING_FOR_HUMAN":{"READY","DONE","CANCELLED"},"WAITING_FOR_EXTERNAL":{"READY","DONE","CANCELLED"},"DONE":set(),"CANCELLED":set()}
def now(): return datetime.now(timezone.utc).isoformat()
def read(p): return json.loads(Path(p).read_text())
def write_atomic(p,o):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp-'+uuid.uuid4().hex);t.write_text(json.dumps(o,indent=2)+'\n');os.replace(t,p)
def event(b,r,e,**d):
 p=Path(b)/'events'/f'{r}.jsonl';p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('a') as f:f.write(json.dumps({'ts':now(),'runtime':r,'event':e,**d},separators=(',',':'))+'\n')
def set_state(b,t,status,attempt=None):
 p=Path(b)/'state'/f'{t}.json';s=read(p);s['status']=status;s['updated_at']=now();
 if attempt is not None:s['attempt']=attempt
 write_atomic(p,s);return s
