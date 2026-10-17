"""Read-only comparison of graph-linked state around an isolated view zoom."""
import builtins,json,struct,math
from pathlib import Path
nav=builtins._spacemouse_ui_navigation;read=nav.timeline['read'];ptr=nav.timeline['ptr'];root=Path('/Users/leah/Documents/Projects/SpaceMouse/.build')
rows=json.loads((root/'nodegraph-snapshot-a.json').read_text());p=int(rows[0]['address'],16)
assert read(ptr(ptr(p)+16),80).split(b'\0',1)[0]==b'net.maxon.mvp.gluon2.windowclasses.nodegraph'
addresses={p:'self'}
data=read(p,0xa00)
for offset in range(0,len(data),8):
 value=struct.unpack_from('<Q',data,offset)[0]
 if 0x100000000<value<0xffffffffff:addresses[value]=hex(offset)
before={}
for address,path in addresses.items():
 try:before[address]=read(address,2048)
 except RuntimeError:pass
builtins._spacemouse_node_pan_probe['move'](0,-80,True)
out=[]
for address,data in before.items():
 try:after=read(address,len(data))
 except RuntimeError:continue
 changes=[]
 for fmt,stride in [('f',4),('d',8)]:
  for offset in range(0,len(data),stride):
   a=struct.unpack_from('<'+fmt,data,offset)[0];b=struct.unpack_from('<'+fmt,after,offset)[0]
   if math.isfinite(a) and math.isfinite(b) and .01<a<100 and .01<b<100 and .7<b/a<.95:
    changes.append({'offset':hex(offset),'format':fmt,'before':a,'after':b,'ratio':b/a})
 if changes:out.append({'path':addresses[address],'address':hex(address),'changes':changes})
(root/'nodegraph-linked-zoom.json').write_text(json.dumps(out,indent=2));print('Zoom-linked fields',len(out))
