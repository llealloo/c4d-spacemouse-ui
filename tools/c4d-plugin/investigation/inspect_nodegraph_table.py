import builtins,ctypes as C,json,struct
from pathlib import Path
api=builtins._spacemouse_ui_navigation.timeline;lib=api['lib'];ptr=api['ptr'];read=api['read']
base=next(lib._dyld_get_image_header(i) for i in range(lib._dyld_image_count()) if (lib._dyld_get_image_name(i) or b'').endswith(b'/c4d_nodeeditor.xlib'))
p=int(json.loads(Path('/Users/leah/Documents/Projects/SpaceMouse/.build/nodegraph-snapshot-a.json').read_text())[0]['address'],16)
offset=ptr(base+0x27a9d0+0x40);table=ptr(p)+offset
out={'base':hex(base),'root':hex(p),'offset':hex(offset),'table':hex(table),'methods':[]}
for slot in range(0,0x170,16):
 f,a=struct.unpack('<Qq',read(table+1+slot,16));out['methods'].append({'slot':hex(slot),'function':hex(f-base),'adjust':a})
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/nodegraph-table.json').write_text(json.dumps(out,indent=2));print('Nodegraph table saved')
component=p+1592
out['panZoom']=list(struct.unpack('<3f',read(component+0x1a40,12)))
out['limits']=list(struct.unpack('<2f',read(component+0x600,8)))
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/nodegraph-table.json').write_text(json.dumps(out,indent=2));print('Pan/zoom',out['panZoom'])
