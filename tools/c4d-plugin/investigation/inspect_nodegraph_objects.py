"""Bounded read-only graph object inspection."""
import builtins,ctypes as C,json,struct
from pathlib import Path
nav=builtins._spacemouse_ui_navigation;api=nav.timeline;read=api['read'];ptr=api['ptr'];lib=api['lib']
rows=json.loads(Path('/Users/leah/Documents/Projects/SpaceMouse/.build/graph-components.json').read_text());out=[];seen=set()
def text(p):
 try:
  b=read(p,200).split(b'\0',1)[0]
  return b.decode() if b and all(31<v<127 for v in b) else None
 except (RuntimeError,UnicodeDecodeError):return None
def walk(p,path,depth):
 if p in seen or len(seen)>400 or p<0x100000000 or p>0xffffffffff:return
 seen.add(p)
 try:data=read(p,4096)
 except RuntimeError:return
 fields=[]
 for offset in range(0,len(data),8):
  value=struct.unpack_from('<Q',data,offset)[0]
  if value<0x100000000 or value>0xffffffffff:continue
  s=text(value)
  if s:fields.append({'offset':hex(offset),'text':s})
  try:
   c=ptr(value);name=text(ptr(c+16))
   if name and name.startswith('net.maxon'):fields.append({'offset':hex(offset),'class':name,'pointer':hex(value)})
  except RuntimeError:pass
 if fields:out.append({'pointer':hex(p),'path':path,'fields':fields})
 if depth:
  for offset in range(0,len(data),8):walk(struct.unpack_from('<Q',data,offset)[0],path+'/'+hex(offset),depth-1)
previous=json.loads(Path('/Users/leah/Documents/Projects/SpaceMouse/.build/graph-objects.json').read_text())
targets={int(f['pointer'],16) for r in previous for f in r['fields'] if f.get('class')=='net.maxon.mvp.gluon2.windowclasses.nodegraph'}
for p in targets:walk(p,'nodegraph',1)
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/graph-objects.json').write_text(json.dumps(out,indent=2));print('Graph object links saved',len(seen))
