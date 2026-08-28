import argparse,json,uuid
from pathlib import Path
from boardlib import read,write_atomic,now,event
p=argparse.ArgumentParser();p.add_argument('task');p.add_argument('--board',default='.agent-board');p.add_argument('--runtime',required=True);p.add_argument('--worker',required=True);p.add_argument('--model',default='unknown');p.add_argument('--summary',required=True);p.add_argument('--base-commit');p.add_argument('--result-commit');a=p.parse_args();b=Path(a.board);cp=b/'claims'/f'{a.task}.json'
if not cp.exists():raise SystemExit('claim required')
c=read(cp)
if c['runtime_id']!=a.runtime or c['worker_id']!=a.worker:raise SystemExit('claim mismatch')
r='RUN-'+uuid.uuid4().hex[:10];x={'run_id':r,'task':a.task,'claim_id':c['claim_id'],'executor':{'runtime':a.runtime,'worker_role':a.worker,'model':a.model},'started_at':c['created_at'],'completed_at':now(),'git':{'base_commit':a.base_commit,'result_commit':a.result_commit},'result':{'summary':a.summary}}
write_atomic(b/'runs'/a.task/f'{r}.json',x);event(b,a.runtime,'run_recorded',task=a.task,run_id=r);print(json.dumps(x,indent=2))
