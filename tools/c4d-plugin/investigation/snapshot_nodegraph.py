"""Snapshot an explicitly discovered nodegraph object for zoom comparison."""
import builtins,json,struct
from pathlib import Path
nav=builtins._spacemouse_ui_navigation;read=nav.timeline['read'];ptr=nav.timeline['ptr'];root=Path('/Users/leah/Documents/Projects/SpaceMouse/.build')
rows=json.loads((root/'graph-objects.json').read_text());targets={int(f['pointer'],16) for r in rows for f in r['fields'] if f.get('class')=='net.maxon.mvp.gluon2.windowclasses.nodegraph'}
out=[]
for p in targets:
 assert read(ptr(ptr(p)+16),80).split(b'\0',1)[0]==b'net.maxon.mvp.gluon2.windowclasses.nodegraph'
 data=read(p,8192);out.append({'address':hex(p),'data':data.hex()})
(root/('nodegraph-snapshot-'+globals().get('LABEL','a')+'.json')).write_text(json.dumps(out));print('Nodegraph snapshot',len(out))
