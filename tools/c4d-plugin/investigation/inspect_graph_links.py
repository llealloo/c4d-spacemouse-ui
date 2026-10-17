"""Read-only native graph object links; never invokes discovered code."""
import builtins,ctypes as C,json,struct
from pathlib import Path
nav=builtins._spacemouse_ui_navigation;api=nav.timeline;read=api['read'];ptr=api['ptr'];lib=api['lib']
class DlInfo(C.Structure):
 _fields_=[('file',C.c_char_p),('base',C.c_void_p),('symbol',C.c_char_p),('address',C.c_void_p)]
lib.dladdr.argtypes=[C.c_void_p,C.POINTER(DlInfo)];lib.dladdr.restype=C.c_int
rows=json.loads(Path('/Users/leah/Documents/Projects/SpaceMouse/.build/graph-components.json').read_text());out=[]
def info(address):
 d=DlInfo()
 if lib.dladdr(address,C.byref(d)):return {'file':(d.file or b'').decode(),'offset':hex(address-d.base),'symbol':(d.symbol or b'').decode()}
 return None
def inspect(address,size=512):
 result={'address':hex(address),'fields':[]}
 try:data=read(address,size)
 except RuntimeError:return result
 for offset in range(0,len(data),8):
  value=struct.unpack_from('<Q',data,offset)[0]
  if not value:continue
  field={'offset':hex(offset),'value':hex(value)};mapped=info(value)
  if mapped:field['image']=mapped
  else:
   try:
    v=ptr(value);mapped=info(v)
    if mapped:field['targetFirst']=mapped
    text=read(value,80).split(b'\0',1)[0].decode()
    if text.isprintable():field['text']=text
   except (RuntimeError,UnicodeDecodeError):pass
  result['fields'].append(field)
 return result
for row in rows:
 root=int(row['message'],16)
 out.append(inspect(root,512))
 for component in row['components']:
  if 'words' not in component:continue
  address=int(component['address'],16);out.append(inspect(address,64))
  target=int(component['words'][6],16)
  if target:out.append(inspect(target,1024))
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/graph-links.json').write_text(json.dumps(out,indent=2));print('Graph links saved')
