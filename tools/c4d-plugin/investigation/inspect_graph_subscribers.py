import builtins,json,struct
from pathlib import Path
nav=builtins._spacemouse_ui_navigation;ptr=nav.timeline['ptr'];read=nav.timeline['read'];out=[]
def identity(p):
 try:return read(ptr(ptr(p)+16),100).split(b'\0',1)[0].decode()
 except (RuntimeError,UnicodeDecodeError):return ''
rows=json.loads(Path('/Users/leah/Documents/Projects/SpaceMouse/.build/graph-components.json').read_text())
for row in rows:
 message=int(row['message'],16)
 for slot in (0xe8,0xf0,0x110,0x128,0x130,0x138,0x160,0x168,0x170,0x178):
  obs=ptr(message+slot)
  if identity(obs)!='net.maxon.class.observable':continue
  array=ptr(obs+0x28);count=ptr(obs+0x30)
  if not 0<count<20:continue
  r={'slot':hex(slot),'count':count,'entries':[]}
  for i in range(count):
   f=ptr(array+i*16+8);entry={'function':hex(f),'captures':[]}
   for j in range(0x18,0x80,8):
    try:
     p=ptr(f+j);q=ptr(p);name=identity(q)
     if name.startswith('net.maxon'):entry['captures'].append({'offset':hex(j),'pointer':hex(p),'target':hex(q),'class':name})
     name=identity(p)
     if name.startswith('net.maxon'):entry['captures'].append({'offset':hex(j),'target':hex(p),'class':name})
    except RuntimeError:pass
   r['entries'].append(entry)
  out.append(r)
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/graph-subscribers.json').write_text(json.dumps(out,indent=2));print('Subscriber metadata saved')
