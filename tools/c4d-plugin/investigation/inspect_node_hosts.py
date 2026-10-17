import builtins,json,ctypes as C
from pathlib import Path
nav=builtins._spacemouse_ui_navigation;n=nav.geometry;api=nav.timeline;o=n['objc'];call=n['call'];Rect=n['Rect'];read=api['read'];ptr=api['ptr']
ivar=o.class_getInstanceVariable(o.objc_getClass(b'MaxonView'),b'_messageView');offset=o.ivar_getOffset(ivar)
app=call(o.objc_getClass(b'NSApplication'),'sharedApplication');windows=call(app,'windows');out=[]
def identity(p):
 try:return read(ptr(ptr(p)+16),100).split(b'\0',1)[0].decode()
 except (RuntimeError,UnicodeDecodeError):return ''
for i in range(call(windows,'count',C.c_ulong)):
 window=call(windows,'objectAtIndex:',args=(i,),types=(C.c_ulong,));title=n['text'](call(window,'title'))
 if title!='Node Editor':continue
 row={'title':title,'window':call(window,'windowNumber',C.c_long),'views':[]}
 def walk(view,depth=0):
  if not view or depth>20:return
  name=(o.object_getClassName(view) or b'').decode()
  if name=='MaxonView':
   message=ptr(view+offset);bounds=call(view,'bounds',Rect)
   row['views'].append({'depth':depth,'view':hex(view),'message':hex(message),'identity':identity(message),'owner70':identity(ptr(message+0x70)),'owner78':identity(ptr(message+0x78)),'width':bounds.size.width,'height':bounds.size.height,'hidden':call(view,'isHiddenOrHasHiddenAncestor',C.c_bool)})
  children=call(view,'subviews')
  for j in range(call(children,'count',C.c_ulong)):walk(call(children,'objectAtIndex:',args=(j,),types=(C.c_ulong,)),depth+1)
 walk(call(window,'contentView'));out.append(row)
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/node-host-views.json').write_text(json.dumps(out,indent=2));print('Node host native views saved')
