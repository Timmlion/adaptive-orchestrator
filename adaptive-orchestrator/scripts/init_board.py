import argparse
from pathlib import Path
from boardlib import write_atomic,now
p=argparse.ArgumentParser();p.add_argument('--board',default='.agent-board');p.add_argument('--name',required=True);p.add_argument('--goal',required=True);p.add_argument('--mode',choices=['autonomous','supervised'],default='autonomous');p.add_argument('--autonomy',choices=['autopilot','ask'],default='autopilot');a=p.parse_args();b=Path(a.board)
for d in ['environment','organization/departments','tasks','state','claims','runs','reviews','decisions','change-requests','events','artifacts','dashboard']:(b/d).mkdir(parents=True,exist_ok=True)
write_atomic(b/'protocol.json',{'protocol':'agent-board','version':'0.1'});write_atomic(b/'project.json',{'schema_version':'0.1','name':a.name,'goal':a.goal,'mode':a.mode,'autonomy':a.autonomy,'phase':'planning','created_at':now()});print(b.resolve())
