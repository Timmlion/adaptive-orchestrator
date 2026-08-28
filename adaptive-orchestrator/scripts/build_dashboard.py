import argparse,html
from pathlib import Path
from boardlib import read
p=argparse.ArgumentParser();p.add_argument('--board',default='.agent-board');a=p.parse_args();b=Path(a.board);pr=read(b/'project.json');rows=[]
for f in sorted((b/'tasks').glob('*.json')):
 t=read(f);s=read(b/'state'/f'{t["id"]}.json');rows.append(f'<tr><td>{html.escape(t["id"])}</td><td>{html.escape(t.get("title",""))}</td><td>{html.escape(t.get("department",""))}</td><td>{s["status"]}</td><td>{s.get("attempt",0)}</td></tr>')
page='<!doctype html><meta charset="utf-8"><title>Agent Board</title><style>body{font:14px system-ui;margin:32px;background:#111;color:#eee}table{width:100%;border-collapse:collapse;margin-top:24px}th,td{padding:10px;border-bottom:1px solid #333;text-align:left}</style>'+f'<h1>{html.escape(pr["name"])}</h1><p>{html.escape(pr["goal"])}</p><p>Phase: {pr["phase"]} · Mode: {pr["mode"]}</p><table><tr><th>Task</th><th>Title</th><th>Department</th><th>Status</th><th>Attempt</th></tr>'+''.join(rows)+'</table>'
out=b/'dashboard'/'index.html';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(page);print(out.resolve())
