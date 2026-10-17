"""Read the finite component records of visible graph surfaces."""
import builtins,ctypes as C,json,struct
from pathlib import Path
nav=builtins._spacemouse_ui_navigation;n=nav.geometry;api=nav.timeline;ptr=api['ptr'];read=api['read'];o=n['objc'];call=n['call'];Rect=n['Rect']
o.class_getInstanceVariable.argtypes=[C.c_void_p,C.c_char_p];o.class_getInstanceVariable.restype=C.c_void_p
o.ivar_getOffset.argtypes=[C.c_void_p];o.ivar_getOffset.restype=C.c_long
offset=o.ivar_getOffset(o.class_getInstanceVariable(o.objc_getClass(b'MaxonView'),b'_messageView'))
rows=[]
def describe(address):
 out={'address':hex(address)}
 try:
  words=struct.unpack('<8Q',read(address,64));out['words']=[hex(v) for v in words]
  for depth,target in [('self',address),('class',words[0])]:
   for field in (8,16):
    try:
     value=read(ptr(target+field),160).split(b'\0',1)[0].decode()
     if value.isprintable():out[depth+str(field)]=value
    except (RuntimeError,UnicodeDecodeError):pass
 except RuntimeError:pass
 return out
app=call(o.objc_getClass(b'NSApplication'),'sharedApplication');windows=call(app,'windows')
for i in range(call(windows,'count',C.c_ulong)):
 window=call(windows,'objectAtIndex:',args=(i,),types=(C.c_ulong,))
 if not call(window,'isVisible',C.c_bool):continue
 def walk(view,depth=0):
  if not view or depth>24 or call(view,'isHiddenOrHasHiddenAncestor',C.c_bool):return
  if o.object_getClassName(view)==b'MaxonView':
   bounds=call(view,'bounds',Rect)
   if bounds.size.width>200 and bounds.size.height>100:
    try:
     message=ptr(view+offset);identity=read(ptr(ptr(message)+16),96).split(b'\0',1)[0]
     if identity==b'net.maxon.ui.oswindowclass.widgetuserdraw':
      row={'view':hex(view),'message':hex(message),'width':bounds.size.width,'height':bounds.size.height,'root':describe(message),'components':[]}
      array=ptr(message+0x10);count=ptr(message+0x18)
      if count>128:raise RuntimeError('Unexpected component count')
      row['components']=[dict(index=j,**describe(ptr(array+j*8))) for j in range(count) if ptr(array+j*8)]
      rows.append(row)
    except RuntimeError:pass
  children=call(view,'subviews')
  for j in range(call(children,'count',C.c_ulong)):walk(call(children,'objectAtIndex:',args=(j,),types=(C.c_ulong,)),depth+1)
 walk(call(window,'contentView'))
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/graph-components.json').write_text(json.dumps(rows,indent=2))
print('Graph component metadata saved')
