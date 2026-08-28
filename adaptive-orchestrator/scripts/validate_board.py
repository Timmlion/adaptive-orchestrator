import argparse,sys
from pathlib import Path
from boardlib import read,STATUSES
p=argparse.ArgumentParser();p.add_argument('--board',default='.agent-board');a=p.parse_args();b=Path(a.board);E=[];T={}
for x in ['protocol.json','project.json']:
 if not (b/x).exists():E.append('missing '+x)
for f in (b/'tasks').glob('*.json') if (b/'tasks').exists() else []:
 try:
  x=read(f);i=x.get('id')
  if not i:E.append(f'{f}: missing id');continue
  if i in T:E.append('duplicate '+i)
  T[i]=x
 except Exception as e:E.append(f'{f}: {e}')
for i,t in T.items():
 for d in t.get('dependencies',[]):
  if d not in T:E.append(f'{i}: missing dependency {d}')
 sf=b/'state'/f'{i}.json'
 if not sf.exists():E.append(f'{i}: missing state')
 elif read(sf).get('status') not in STATUSES:E.append(f'{i}: illegal status')
vis=set();done=set()
def dfs(n):
 if n in vis:E.append('dependency cycle at '+n);return
 if n in done:return
 vis.add(n)
 for d in T[n].get('dependencies',[]):
  if d in T:dfs(d)
 vis.remove(n);done.add(n)
for n in T:dfs(n)
if E:print('\n'.join('ERROR: '+x for x in E));sys.exit(1)
print(f'OK: {len(T)} tasks, DAG valid')
