import argparse,json,os,uuid
from pathlib import Path
from boardlib import read,write_atomic,now,set_state,event
p=argparse.ArgumentParser();p.add_argument('task');p.add_argument('--board',default='.agent-board');p.add_argument('--runtime',required=True);p.add_argument('--worker',required=True);p.add_argument('--lease',type=int,default=900);p.add_argument('--heartbeat',action='store_true');a=p.parse_args();b=Path(a.board);cpath=b/'claims'/f'{a.task}.json'
if a.heartbeat:
 if not cpath.exists():raise SystemExit('no claim')
 c=read(cpath)
 if c['runtime_id']!=a.runtime or c['worker_id']!=a.worker:raise SystemExit('claim owned by another worker')
 c['heartbeat_at']=now();write_atomic(cpath,c);event(b,a.runtime,'claim_heartbeat',task=a.task,claim_id=c['claim_id']);print(json.dumps(c,indent=2));raise SystemExit
s=read(b/'state'/f'{a.task}.json')
if s['status']!='READY':raise SystemExit('task not READY: '+s['status'])
c={'task':a.task,'claim_id':'CLM-'+uuid.uuid4().hex[:10],'runtime_id':a.runtime,'worker_id':a.worker,'created_at':now(),'heartbeat_at':now(),'lease_seconds':a.lease,'attempt':s.get('attempt',0)+1}
try:
 fd=os.open(cpath,os.O_WRONLY|os.O_CREAT|os.O_EXCL);os.write(fd,(json.dumps(c,indent=2)+'\n').encode());os.close(fd)
except FileExistsError:raise SystemExit('task already claimed')
set_state(b,a.task,'CLAIMED',c['attempt']);event(b,a.runtime,'task_claimed',task=a.task,claim_id=c['claim_id'],worker=a.worker);print(json.dumps(c,indent=2))
