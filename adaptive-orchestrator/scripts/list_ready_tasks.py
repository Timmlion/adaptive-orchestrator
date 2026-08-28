import argparse,json
from pathlib import Path
from boardlib import read
p=argparse.ArgumentParser();p.add_argument('--board',default='.agent-board');a=p.parse_args();b=Path(a.board);o=[]
for f in sorted((b/'tasks').glob('*.json')):
 t=read(f);s=read(b/'state'/f'{t["id"]}.json')
 if s['status']=='READY' and all(read(b/'state'/f'{d}.json')['status']=='DONE' for d in t.get('dependencies',[])):o.append({'id':t['id'],'title':t.get('title'),'requirements':t.get('requirements',{})})
print(json.dumps(o,indent=2))
