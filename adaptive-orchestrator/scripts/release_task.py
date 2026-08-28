import argparse
from pathlib import Path
from boardlib import read,set_state,event
p=argparse.ArgumentParser();p.add_argument('task');p.add_argument('--board',default='.agent-board');p.add_argument('--runtime',required=True);a=p.parse_args();b=Path(a.board);c=b/'claims'/f'{a.task}.json'
if not c.exists():raise SystemExit('no claim')
x=read(c)
if x['runtime_id']!=a.runtime:raise SystemExit('claim owned by another runtime')
c.unlink();s=read(b/'state'/f'{a.task}.json')
if s['status']=='CLAIMED':set_state(b,a.task,'READY')
event(b,a.runtime,'task_released',task=a.task,claim_id=x['claim_id']);print('released')
