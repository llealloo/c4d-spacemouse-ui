"""Inspect exact-build scene-hook and SDK addresses; no memory writes."""
import builtins, ctypes as C, hashlib, json, struct
from pathlib import Path
api=builtins._spacemouse_ui_navigation.timeline
lib,read,ptr=api['lib'],api['read'],api['ptr']
images={lib._dyld_get_image_name(i).decode():lib._dyld_get_image_header(i) for i in range(lib._dyld_image_count())}
vendor_path=next(p for p in images if p.endswith('/3DxCinema4D.xlib'))
assert hashlib.sha256(Path(vendor_path).read_bytes()).hexdigest()=='780162c4f48dc402dbddb1a6feb8367fb371d268372112f3242164727fc4090f'
base=images[vendor_path]
assert read(base+0x5c98,8)==bytes.fromhex('eb2bb96de923016d')
assert read(base+0x5d48,8)==bytes.fromhex('1f04007121110054')
assert read(base+0x5f70,4)==bytes.fromhex('00008052')
# Match the vendor's SDK indirections to our already-bound document table.
doc_table=ptr(base+0x58b60)
assert doc_table==ptr(api['BASE']+0x5b8b10)
doc=api['active_document']()
find_hook=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_int)(ptr(doc_table+0x108))
hook=find_hook(doc,0x075bccbc)
assert hook, 'Vendor pivot scene hook is missing'
wrapper=ptr(hook+0x50);instance=ptr(wrapper+0x10);vtable=ptr(instance)
assert vtable==base+0x50530, 'Unexpected pivot drawing class'
assert ptr(vtable+27*8)==base+0x5c98
# Registered Draw must be the virtual member at vtable slot 27.
registration=ptr(wrapper)
member=struct.unpack('<Qq',read(registration+0x2a8,16))
assert member==(27*8,1), ('Unexpected Draw registration',member)
bd_table=ptr(base+0x58b90);object_table=ptr(base+0x58b58)
functions={'scene_camera':ptr(bd_table+0xb0),'editor_camera':ptr(bd_table+8),'camera_projection':ptr(object_table+0x3a0)}
class DlInfo(C.Structure):
 _fields_=[('file',C.c_char_p),('base',C.c_void_p),('symbol',C.c_char_p),('address',C.c_void_p)]
lib.dladdr.argtypes=[C.c_void_p,C.POINTER(DlInfo)];lib.dladdr.restype=C.c_int
resolved={}
for name,address in functions.items():
 info=DlInfo();assert lib.dladdr(address,C.byref(info))
 path=info.file.decode()
 assert path.startswith('/Applications/Maxon Cinema 4D 2027/corelibs/'),path
 resolved[name]={'image':path,'offset':hex(address-info.base),'bytes':read(address,16).hex()}
result={'vendor':vendor_path,'hook':hex(hook),'instance':hex(instance),'vtable':hex(vtable),'drawMember':member,'sdk':resolved}
Path('/Users/leah/Documents/Projects/SpaceMouse/.build/ortho-draw-inspection.json').write_text(json.dumps(result,indent=2))
print('Ortho Draw registration and SDK address guards passed; inspection saved')
