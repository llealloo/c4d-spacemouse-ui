"""Exact-build guarded C4D viewport activation; no input synthesis."""
import ctypes as C,hashlib
from pathlib import Path
EXPECTED='1c0e204bc48bee5c7898b4e72e353a0f15304ea9b1036412434675f7ec848b62'
def bind(api):
    path=Path('/Applications/Maxon Cinema 4D 2027/corelibs/c4d_base.xlib')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED:raise RuntimeError('Viewport activation requires the inspected C4D build')
    lib=api['lib'];ptr=api['ptr'];read=api['read']
    base=next(lib._dyld_get_image_header(i) for i in range(lib._dyld_image_count()) if (lib._dyld_get_image_name(i) or b'').endswith(b'/c4d_base.xlib'))
    if read(base+0x1b3af0,8)!=bytes.fromhex('ff0302d1fa6703a9'):raise RuntimeError('Viewport activation code guard failed')
    table=ptr(api['BASE']+0x5b8b10)
    active=C.CFUNCTYPE(C.c_void_p,C.c_void_p)(ptr(table+23*8))
    view=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_int)(ptr(table+25*8))
    activate=C.CFUNCTYPE(None,C.c_void_p,C.c_int,C.c_int)(base+0x1b3af0)
    def set_view(doc,index,count):
        if not 0<=index<count:raise RuntimeError('Invalid viewport index')
        target=view(doc,index)
        if not target:raise RuntimeError('Viewport is no longer available')
        if active(doc)==target:return False
        activate(doc,index,0)
        if active(doc)!=target:raise RuntimeError('Viewport activation read-back failed')
        return True
    return {'active':active,'view':view,'set_view':set_view}
