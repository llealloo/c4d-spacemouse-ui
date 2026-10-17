"""Read-only native view inventory to distinguish embedded graph surfaces."""
import builtins,ctypes as C,json,struct
from pathlib import Path
nav=builtins._spacemouse_ui_navigation
n=nav.geometry;o=n['objc'];call=n['call'];Rect=n['Rect']
o.class_getInstanceVariable.argtypes=[C.c_void_p,C.c_char_p];o.class_getInstanceVariable.restype=C.c_void_p
o.ivar_getOffset.argtypes=[C.c_void_p];o.ivar_getOffset.restype=C.c_long
ivar=o.class_getInstanceVariable(o.objc_getClass(b'MaxonView'),b'_messageView')
offset=o.ivar_getOffset(ivar)
app=call(o.objc_getClass(b'NSApplication'),'sharedApplication');windows=call(app,'windows');result=[]
for i in range(call(windows,'count',C.c_ulong)):
 window=call(windows,'objectAtIndex:',args=(i,),types=(C.c_ulong,))
 if not call(window,'isVisible',C.c_bool):continue
 row={'window':call(window,'windowNumber',C.c_long),'title':n['text'](call(window,'title')),'views':[]}
 def walk(view,depth=0):
  if not view or depth>25:return
  bounds=call(view,'bounds',Rect);local=call(view,'convertRect:toView:',Rect,(bounds,None),(Rect,C.c_void_p));screen=call(window,'convertRectToScreen:',Rect,(local,),(Rect,))
  cls=o.object_getClassName(view).decode();item={'address':hex(view),'class':cls,'depth':depth,'hidden':bool(call(view,'isHiddenOrHasHiddenAncestor',C.c_bool)),'screen':[screen.origin.x,screen.origin.y,screen.size.width,screen.size.height]}
  if cls=='MaxonView' and nav.timeline:
   try:
    ptr=nav.timeline['ptr'];base=nav.timeline['BASE'];message=ptr(view+offset)
    item['message']=hex(message);item['messageClass']=hex(ptr(message)-base)
    words=struct.unpack('<16Q',nav.timeline['read'](message,128));item['words']=[hex(w) for w in words]
    descriptor=ptr(message)
    for field in (8,16):
     try:item['descriptorName'+str(field)]=nav.timeline['read'](ptr(descriptor+field),200).split(b'\0',1)[0].decode(errors='replace')
     except RuntimeError:pass
    item['children']={}
    for w in words[:8]:
     try:item['children'][hex(w)]=[hex(v) for v in struct.unpack('<8Q',nav.timeline['read'](w,64))]
     except RuntimeError:pass
   except Exception as error:item['error']=str(error)
  if cls=='MaxonView' and depth>0 and nav.timeline:
   try:
    callback=ptr(message+0x78) or ptr(message+0x70)
    item['callback']=hex(callback)
    item['ownerType']=nav.timeline['read'](ptr(ptr(callback)+16),200).split(b'\0',1)[0].decode(errors='replace')
    item['ownerName']=nav.timeline['read'](callback+0x90,160).decode(errors='replace')
    item['callbackWords']=[hex(w) for w in struct.unpack('<24Q',nav.timeline['read'](callback,192))]
   except RuntimeError:pass
  row['views'].append(item)
  children=call(view,'subviews')
  for j in range(call(children,'count',C.c_ulong)):walk(call(children,'objectAtIndex:',args=(j,),types=(C.c_ulong,)),depth+1)
 walk(call(window,'contentView'));result.append(row)
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/docked-node-views.json').write_text(json.dumps(result,indent=2))
print('Docked graph view inventory saved')
