import argparse
from pathlib import Path
from boardlib import read,set_state,TRANSITIONS,event
p=argparse.ArgumentParser();p.add_argument('task');p.add_argument('status');p.add_argument('--board',default='.agent-board');p.add_argument('--runtime',default='local');a=p.parse_args();b=Path(a.board);old=read(b/'state'/f'{a.task}.json')['status']
if a.status not in TRANSITIONS.get(old,set()):raise SystemExit(f'illegal transition {old} -> {a.status}')
set_state(b,a.task,a.status);event(b,a.runtime,'state_transition',task=a.task,old=old,new=a.status);print(f'{old} -> {a.status}')
