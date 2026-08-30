from pathlib import Path
from datetime import datetime, timezone
import json, os, uuid
from model_policy import plan_projection
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

def _required(value):
 if isinstance(value,dict):return [name for name,required in value.items() if required]
 return value or []

def _verified(values,name):
 if isinstance(values,dict):
  if name not in values:return 'missing'
  if values[name]=='unknown':return 'unknown'
  return 'false' if values[name] is False else 'verified'
 return 'verified' if name in values else 'missing'

def requirement_match(requirements,environment):
 capability_requirements=requirements.get('capabilities',requirements.get('required_capabilities',[]))
 capabilities=environment.get('capabilities',{})
 for capability in _required(capability_requirements):
  status=_verified(capabilities,capability)
  if status!='verified':return False,f'capability {capability} is {status}'
  if isinstance(capability_requirements,dict) and isinstance(capability_requirements[capability],bool) and capabilities[capability] is not capability_requirements[capability]:return False,f'capability {capability} does not match requirement'
 for tool in _required(requirements.get('tools',requirements.get('required_tools',[]))):
  status=_verified(environment.get('tools',{}),tool)
  if status!='verified':return False,f'tool {tool} is {status}'
 return True,None

def _records(board,directory,diagnostics,keyed=False):
 root=board/directory;records={} if keyed else []
 if not root.exists():return records
 for path in sorted(root.rglob('*.json')):
  try:record=read(path)
  except Exception as error:
   diagnostics.append(f'{path.relative_to(board)}: {error}');continue
  if not isinstance(record,dict):
   diagnostics.append(f'{path.relative_to(board)}: expected object');continue
  if keyed:records[path.stem]=record
  else:records.append(record)
 return records

def board_snapshot(board):
 board=Path(board);diagnostics=[]
 project=None
 project_path=board/'project.json'
 if project_path.exists():
  try:
   project=read(project_path)
  except Exception as error:
   diagnostics.append(f'project.json: {error}')
  else:
   if not isinstance(project,dict):
    diagnostics.append('project.json: expected object');project=None
 else:diagnostics.append('project.json: missing')
 tasks=_records(board,'tasks',diagnostics)
 states=_records(board,'state',diagnostics,True)
 environments=_records(board,'environment',diagnostics,True)
 plan={}
 for runtime,environment in environments.items():
  try:
   projection=plan_projection(environment,tasks,states,runtime)
  except Exception as error:
   diagnostics.append(f'environment/{runtime}.json: model_policy: {error}')
   projection={'status':'blocked','runtime':runtime,'routes':[],'capability_gaps':[],'blocked_tasks':[{'task':None,'reason':'invalid environment policy'}],'research_warnings':[],'summary':{'routed':0,'gaps':0,'blocked':1,'research_warnings':0}}
  if projection.get('status')=='blocked':
   blocked=projection.get('blocked_tasks',[])
   if blocked and isinstance(blocked[0],dict):
    reason=blocked[0].get('reason','invalid environment policy')
    if isinstance(reason,str) and reason.startswith('invalid environment policy: '):
     prefix='invalid environment policy: '
     diagnostics.append(f'environment/{runtime}.json: model_policy: {reason[len(prefix):]}')
  plan[runtime]=projection
 return {'project':project,'tasks':tasks,'states':states,'claims':_records(board,'claims',diagnostics),'runs':_records(board,'runs',diagnostics),'reviews':_records(board,'reviews',diagnostics),'environments':environments,'plan':plan,'diagnostics':diagnostics}
