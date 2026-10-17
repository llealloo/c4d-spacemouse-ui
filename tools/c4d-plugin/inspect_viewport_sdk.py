"""Read-only resolution of documented viewport SDK functions."""
import builtins,ctypes as C,json
from pathlib import Path
api=builtins._spacemouse_ui_navigation.timeline
ptr,read,base=api['ptr'],api['read'],api['BASE']
table=ptr(base+0x5b8b10)
class DlInfo(C.Structure):
 _fields_=[('file',C.c_char_p),('base',C.c_void_p),('symbol',C.c_char_p),('address',C.c_void_p)]
lib=api['lib'];lib.dladdr.argtypes=[C.c_void_p,C.POINTER(DlInfo)];lib.dladdr.restype=C.c_int
result={}
for name,offset in [('GetActiveBaseDraw',23*8),('GetRenderBaseDraw',24*8),('GetBaseDraw',25*8)]:
 address=ptr(table+offset);info=DlInfo();lib.dladdr(address,C.byref(info))
 result[name]={'address':hex(address),'image':info.file.decode(),'offset':hex(address-info.base),'bytes':read(address,64).hex()}
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/viewport-sdk.json').write_text(json.dumps(result,indent=2))
print('Viewport SDK inventory saved')
