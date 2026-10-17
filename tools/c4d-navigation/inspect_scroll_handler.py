import ctypes as C
import json
import runpy
from pathlib import Path
n=runpy.run_path('/Users/leah/Documents/Projects/SpaceMouse/tools/c4d-navigation/inspect_native_views.py',run_name='native_probe')
o=n['objc']
o.class_getInstanceMethod.argtypes=[C.c_void_p,C.c_void_p];o.class_getInstanceMethod.restype=C.c_void_p
o.method_getImplementation.argtypes=[C.c_void_p];o.method_getImplementation.restype=C.c_void_p
class Info(C.Structure):
    _fields_=[('path',C.c_char_p),('base',C.c_void_p),('symbol',C.c_char_p),('address',C.c_void_p)]
lib=C.CDLL('/usr/lib/libSystem.B.dylib');lib.dladdr.argtypes=[C.c_void_p,C.POINTER(Info)];lib.dladdr.restype=C.c_int
result={}
for name in ['scrollWheel:','magnifyWithEvent:','mouseDragged:']:
    method=o.class_getInstanceMethod(o.objc_getClass(b'MaxonView'),o.sel_registerName(name.encode()))
    pointer=o.method_getImplementation(method); info=Info();lib.dladdr(pointer,C.byref(info))
    result[name]={'path':info.path.decode(),'offset':hex(pointer-info.base)}
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/input-handlers.json').write_text(json.dumps(result,indent=2))
print('Read-only input-handler inventory saved.')
# Resolve the live interface dispatch used by MaxonView without invoking it.
lib.mach_vm_read_overwrite.argtypes=[C.c_uint,C.c_uint64,C.c_uint64,C.c_uint64,C.POINTER(C.c_uint64)]
lib.mach_vm_read_overwrite.restype=C.c_int
def ptr(address):
    value=C.c_uint64(); size=C.c_uint64()
    task=C.c_uint.in_dll(lib,'mach_task_self_').value
    error=lib.mach_vm_read_overwrite(task,address,8,C.addressof(value),C.byref(size))
    if error or size.value!=8: raise RuntimeError('Unreadable diagnostic address')
    return value.value
cls=o.objc_getClass(b'MaxonView')
o.class_getInstanceVariable.argtypes=[C.c_void_p,C.c_char_p];o.class_getInstanceVariable.restype=C.c_void_p
o.ivar_getOffset.argtypes=[C.c_void_p];o.ivar_getOffset.restype=C.c_long
ivar=o.class_getInstanceVariable(cls,b'_messageView'); offset=o.ivar_getOffset(ivar)
call=n['call']; app=call(o.objc_getClass(b'NSApplication'),'sharedApplication'); windows=call(app,'windows')
for i in range(call(windows,'count',C.c_ulong)):
    window=call(windows,'objectAtIndex:',args=(i,),types=(C.c_ulong,))
    if not n['text'](call(window,'title')).startswith('Timeline'): continue
    view=call(window,'contentView'); message=ptr(view+offset)
    if not message: continue
    method=o.class_getInstanceMethod(cls,o.sel_registerName(b'scrollWheel:'))
    info=Info();lib.dladdr(o.method_getImplementation(method),C.byref(info))
    table=ptr(message)+ptr(info.base+0x1376c0+0x40)
    result['timeline-view-state']={'forwardToSuper':bool(ptr(message+0xf8)&255),
        'touchEnabled':bool((ptr(info.base+0x132f00)>>16)&255)}
    devices=ptr(info.base+0x12a6d8);count=ptr(info.base+0x12a6e0)
    result['touch-devices']=[ptr(devices+j*8) for j in range(min(count,32))] if devices else []
    for name,entry in [('scroll-implementation',0x111),('magnify-implementation',0x1a1)]:
        address=ptr(table+entry); details=Info();lib.dladdr(address,C.byref(details))
        result[name]={'path':details.path.decode(),'offset':hex(address-details.base)}
    break
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/input-handlers.json').write_text(json.dumps(result,indent=2))
result['gesture-capable-devices'] = ptr(info.base+0x132f00) & 0xffffff
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/input-handlers.json').write_text(json.dumps(result,indent=2))
