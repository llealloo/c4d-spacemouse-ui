"""Read-only enumeration of the inspected driver's live client bookkeeping."""
import builtins,ctypes as C,hashlib,json
from pathlib import Path
nav=builtins._spacemouse_ui_navigation
framework=Path('/Library/Frameworks/3DconnexionClient.framework/3DconnexionClient')
if hashlib.sha256(framework.read_bytes()).hexdigest()!='377cb3a9efda8a9496e202dce33055f7d1908d51e9e069d07419b6c8d442ae07':raise RuntimeError('Unexpected SDK build')
a=nav.timeline;lib=a['lib'];ptr=a['ptr'];n=nav.geometry;call=n['call'];o=n['objc']
base=next(lib._dyld_get_image_header(i) for i in range(lib._dyld_image_count()) if (lib._dyld_get_image_name(i) or b'').endswith(b'/3DconnexionClient'))
clients=ptr(base+0x1c0c0)
result={'class':o.object_getClassName(clients).decode(),'description':n['text'](call(clients,'description'))}
(nav.state/'driver-clients.json').write_text(json.dumps(result,indent=2))
print('Driver client inventory saved')
o.class_getInstanceVariable.argtypes=[C.c_void_p,C.c_char_p];o.class_getInstanceVariable.restype=C.c_void_p
o.ivar_getOffset.argtypes=[C.c_void_p];o.ivar_getOffset.restype=C.c_long
o.class_copyIvarList.argtypes=[C.c_void_p,C.POINTER(C.c_uint)];o.class_copyIvarList.restype=C.POINTER(C.c_void_p)
o.ivar_getName.argtypes=[C.c_void_p];o.ivar_getName.restype=C.c_char_p
o.ivar_getTypeEncoding.argtypes=[C.c_void_p];o.ivar_getTypeEncoding.restype=C.c_char_p
object_key=call(o.objc_getClass(b'NSString'),'stringWithUTF8String:',args=(b'object',),types=(C.c_char_p,))
keys=call(clients,'allKeys');result['clients']=[]
for i in range(call(keys,'count',C.c_ulong)):
 key=call(keys,'objectAtIndex:',args=(i,),types=(C.c_ulong,));entry=call(clients,'objectForKey:',args=(key,),types=(C.c_void_p,))
 obj=call(entry,'objectForKey:',args=(object_key,),types=(C.c_void_p,))
 ivar=o.class_getInstanceVariable(o.objc_getClass(b'ConnexionClientAPI'),b'applicationInfo')
 info=ptr(obj+o.ivar_getOffset(ivar));row={'id':call(key,'unsignedShortValue',C.c_ushort),'class':o.object_getClassName(info).decode(),'fields':{}}
 count=C.c_uint();ivars=o.class_copyIvarList(o.objc_getClass(b'TDxApplication'),C.byref(count))
 for j in range(count.value):
  ivar=ivars[j];name=o.ivar_getName(ivar).decode();typ=o.ivar_getTypeEncoding(ivar).decode();offset=o.ivar_getOffset(ivar)
  if typ.startswith('@'):
   value=ptr(info+offset);value=n['text'](call(value,'description')) if value else None
  else:value=a['read'](info+offset,8).hex()
  row['fields'][name]={'type':typ,'value':value}
 row['callbackPointers']=[hex(ptr(obj+off)) for off in (32,56)]
 row['apiPointer']=hex(obj)
 result['clients'].append(row)
(nav.state/'driver-clients.json').write_text(json.dumps(result,indent=2))

class DlInfo(C.Structure):
 _fields_=[('file',C.c_char_p),('base',C.c_void_p),('symbol',C.c_char_p),('address',C.c_void_p)]
lib.dladdr.argtypes=[C.c_void_p,C.POINTER(DlInfo)];lib.dladdr.restype=C.c_int
for row in result['clients']:
 row['callbackImages']=[]
 for value in row['callbackPointers']:
  if int(value,16):
   detail=DlInfo()
   if lib.dladdr(int(value,16),C.byref(detail)):row['callbackImages'].append(detail.file.decode())
(nav.state/'driver-clients.json').write_text(json.dumps(result,indent=2))
