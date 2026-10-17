"""Use the vendor's existing Navlib connection to reinitialize navigation."""
import ctypes as C,hashlib
from pathlib import Path
EXPECTED='780162c4f48dc402dbddb1a6feb8367fb371d268372112f3242164727fc4090f'
class Value(C.Structure):
    _fields_=[('type',C.c_int),('padding',C.c_int),('data',C.c_ubyte*128)]
def bind(api):
    lib=api['lib'];ptr=api['ptr']
    base=next(lib._dyld_get_image_header(i) for i in range(lib._dyld_image_count()) if (lib._dyld_get_image_name(i) or b'').endswith(b'/3DxCinema4D.xlib'))
    path=next(lib._dyld_get_image_name(i).decode() for i in range(lib._dyld_image_count()) if lib._dyld_get_image_header(i)==base)
    if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=EXPECTED:raise RuntimeError('Unexpected vendor plugin build')
    navlib=C.CDLL('/Library/Frameworks/3DconnexionNavlib.framework/3DconnexionNavlib')
    for name,offset in [('NlReadValue',0x56210),('NlWriteValue',0x56218)]:
        fn=getattr(navlib,name)
        # Require exact equality with the SDK-export address loaded by vendor.
        if ptr(base+offset)!=C.cast(fn,C.c_void_p).value:raise RuntimeError('Vendor SDK function identity mismatch')
        fn.argtypes=[C.c_uint64,C.c_char_p,C.POINTER(Value)];fn.restype=C.c_long
    read_value=navlib.NlReadValue;write_value=navlib.NlWriteValue
    def handle():
        root=ptr(base+0x563f8)
        if not root or ptr(root)!=base+0x507d8:raise RuntimeError('Vendor navigation object guard failed')
        owner=ptr(root+0x78)
        if not owner or ptr(root+0x70)!=owner+0x18:raise RuntimeError('Vendor accessor ownership guard failed')
        implementation=ptr(owner+0x70)
        if not implementation:raise RuntimeError('Vendor navigation connection unavailable')
        if ptr(implementation)!=base+0x516a0:raise RuntimeError('Vendor connection class guard failed')
        result=ptr(implementation+8)
        if not result:raise RuntimeError('Vendor navigation handle unavailable')
        return result
    def read(name):
        value=Value();value.type=7 if name==b'view.affine' else 1
        status=read_value(handle(),name,C.byref(value))
        return status,value
    def reset():
        value=Value();value.type=1
        status=write_value(handle(),b'motion',C.byref(value))
        if status:raise RuntimeError('Navlib motion reset failed: %s'%status)
        return status
    return {'read':read,'reset':reset,'handle':handle,'base':base,'chain':[hex(ptr(base+0x563f8)),hex(ptr(ptr(base+0x563f8)+0x70)),hex(handle())]}
