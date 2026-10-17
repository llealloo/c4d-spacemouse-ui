"""Read-only pointer ownership validation. Calls no vendor functions."""
import builtins,ctypes as C,json
from pathlib import Path
api=builtins._spacemouse_ui_navigation.timeline;lib=api['lib'];ptr=api['ptr']
base=next(lib._dyld_get_image_header(i) for i in range(lib._dyld_image_count()) if (lib._dyld_get_image_name(i) or b'').endswith(b'/3DxCinema4D.xlib'))
class Info(C.Structure):
 _fields_=[('file',C.c_char_p),('base',C.c_void_p),('symbol',C.c_char_p),('address',C.c_void_p)]
lib.dladdr.argtypes=[C.c_void_p,C.POINTER(Info)];lib.dladdr.restype=C.c_int
result={}
for name,offset in [('create',0x56200),('read',0x56210),('write',0x56218)]:
 address=ptr(base+offset);info=Info();ok=lib.dladdr(address,C.byref(info))
 result[name]={'pointer':hex(address),'owner':info.file.decode() if ok else None,'symbol':info.symbol.decode() if ok and info.symbol else None}
root=ptr(base+0x563f8);impl=ptr(root+0x70)
owner=ptr(root+0x78);connection=ptr(owner+0x70)
result['connection']={'owner':hex(owner),'object':hex(connection),'words':[hex(ptr(connection+i*8)) for i in range(4)]}
result['chain']={'root':hex(root),'vtable':hex(ptr(root)-base),'implementation':hex(impl),'words':[hex(ptr(impl+i*8)) for i in range(10)]}
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/navlib-binding-inspection.json').write_text(json.dumps(result,indent=2))
print('Read-only Navlib binding inspection saved')
